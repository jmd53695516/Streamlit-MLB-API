# Phase 3: HR Pipeline - Context

**Gathered:** 2026-04-15
**Status:** Ready for planning

<domain>
## Phase Boundary

End-to-end `player_id → list[HREvent]` pipeline: filter the season gameLog to HR games *before* any feed fetch, walk each game feed to find the player's HR plays, extract `hitData` with null-safe degradation flags, and return an events+errors result. No UI, no chart — pure data layer consumed by Phase 4's controller.

Satisfies DATA-01 (gameLog filter), DATA-02 (feed walk + hitData), DATA-03 (reuse Phase 1's disk-backed venue cache), DATA-05 (graceful degradation on missing hitData). DATA-04 is already satisfied in Phase 1.

</domain>

<decisions>
## Implementation Decisions

### Locked from prior phases / roadmap / CLAUDE.md

- **D-01:** Only `services/mlb_api.py` touches `requests` and `st.cache_data`. Phase 3 modules import `mlb_park.services.mlb_api` — never `requests`.
- **D-02:** Pipeline consumes the Phase 2 `HitData(distance_ft, coord_x, coord_y, identifier)` contract. Per-HR verdicts are computed by Phase 2's `compute_verdict_matrix`; Phase 3 does NOT recompute geometry.
- **D-03:** Reuse Phase 1's `load_all_parks()` for DATA-03; disk-backed `data/venues_cache.json` already exists with a 30-day TTL. Phase 3 calls it, doesn't reimplement it.
- **D-04:** No HR is dropped silently. Missing/partial `hitData` → retain with flags (DATA-05). Failed feed fetches → collected in an errors list, not raised (decision D-13 below).

### HREvent shape (rich event)

- **D-05:** `HREvent` is a frozen dataclass with the fields Phase 5 (VIZ-03 tooltip) and Phase 6 (VIZ-04/05 rankings) will need, so Phase 3 is the single place that walks feeds:
  ```
  HREvent(
      # Core identity
      game_pk: int,
      game_date: datetime.date,          # YYYY-MM-DD (from gameLog or feed)
      opponent_abbr: str,                 # 3-letter team code vs the batter's team
      inning: int,
      half_inning: str,                   # "top" | "bottom"
      play_idx: int,                      # index into allPlays (stable within feed)

      # Measurements (may be None when has_* flags are False)
      distance_ft: float | None,
      coord_x: float | None,
      coord_y: float | None,
      launch_speed: float | None,         # mph
      launch_angle: float | None,         # degrees

      # Degradation flags
      has_distance: bool,
      has_coords: bool,
      has_launch_stats: bool,             # True iff launch_speed AND launch_angle present
      is_itp: bool,                       # inside-the-park
  )
  ```
- **D-06:** `HREvent → HitData` adapter: when `has_distance` and `has_coords` are both True, produce a `HitData(distance_ft, coord_x, coord_y, identifier=(game_pk, play_idx))` for the geometry layer. HRs missing distance or coords are passed through to downstream consumers as events but **excluded from the verdict matrix input** (Phase 4 handles the split). Planner decides whether the adapter lives in `pipeline.py` or a thin `HREvent.to_hit_data()` method.

### HR identification & feed walk (DATA-01, DATA-02)

- **D-07:** `extract_hrs` first calls `get_game_log(player_id, season)` and keeps only rows where `stat.homeRuns >= 1`. No feed is fetched for 0-HR games (DATA-01 rate-limit posture from CLAUDE.md).
- **D-08:** For each HR game, call `get_game_feed(gamePk)` once and walk `liveData.plays.allPlays`. Keep plays where `matchup.batter.id == player_id` AND `result.eventType == "home_run"`. This is the only filter — no review-reversal special-casing (if the final feed says `home_run`, it counts).
- **D-09:** Sanity check: after filtering, if `len(matched_plays) != gameLog_row.stat.homeRuns`, log a warning with `(game_pk, gamelog_count, matched_count)` but **keep the matched plays**. Mismatches are data-quality signals, not fatal errors.
- **D-10:** `hitData` lookup path: prefer `play["playEvents"][-1]["hitData"]`. If the terminal event lacks `hitData`, fall back to the last `playEvent` that has a non-null `hitData`. If none of the playEvents carry `hitData`, emit the event with `has_distance=False`, `has_coords=False`, `has_launch_stats=False`.
- **D-11:** ITP detection: `is_itp = True` if `result.description` contains the literal substring `"inside-the-park"` (case-insensitive). Pre-Statcast games also lack hitData but are NOT ITP — the distinction is substring-based, not flag-inferred.
- **D-12:** Field-level null safety inside `hitData`:
  - `has_distance = hitData.totalDistance is not None`
  - `has_coords = hitData.coordinates.coordX is not None AND hitData.coordinates.coordY is not None`
  - `has_launch_stats = hitData.launchSpeed is not None AND hitData.launchAngle is not None`
  These are independent — an event can have coords but no launch stats, etc.

### Error handling (DATA-05 + UX-05 forward-compat)

- **D-13:** `extract_hrs` returns a `PipelineResult` dataclass:
  ```
  PipelineResult(
      events: tuple[HREvent, ...],          # chronological by game_date asc, then play_idx
      errors: tuple[PipelineError, ...],    # per-failure records
      season: int,
      player_id: int,
  )
  PipelineError(game_pk: int | None, endpoint: str, message: str)
  ```
- **D-14:** Exception handling strategy: if `get_game_log` fails → raise (nothing to return; Phase 4 surfaces via UX-05). If an individual `get_game_feed(gamePk)` fails → catch `MLBAPIError`, append a `PipelineError(game_pk, "game_feed", str(exc))` to the errors list, continue with remaining games. One flaky feed does not nuke the whole HR list.
- **D-15:** `extract_hrs` does NOT retry on its own. Retries live at the `@st.cache_data` / user-initiated level (Phase 6's retry button will clear the offending cache entry and re-call). Keeping the pipeline deterministic given its inputs makes fixture-driven tests trivial.

### Entry point & season resolution

- **D-16:** Public signature: `extract_hrs(player_id: int, season: int | None = None) -> PipelineResult`. When `season is None`, resolve from `config.CURRENT_SEASON` (constant already in `config.py` per Phase 1 pattern). Callers in tests can override for fixture years.
- **D-17:** `api` module injection for testability (success criterion 4): the pipeline's functions take an optional `api` keyword argument defaulting to `mlb_park.services.mlb_api`. Tests pass a stub module with `get_game_log` / `get_game_feed` / `load_all_parks` attributes that return fixture JSON. No monkey-patching needed.

### Module layout

- **D-18:** New files under `src/mlb_park/pipeline/`:
  - `pipeline/__init__.py` — re-exports `extract_hrs`, `HREvent`, `PipelineResult`, `PipelineError`.
  - `pipeline/events.py` — `HREvent`, `PipelineResult`, `PipelineError` dataclasses.
  - `pipeline/extract.py` — `extract_hrs` + internal helpers (`_walk_feed_for_hrs`, `_extract_hit_data`, `_detect_itp`).
  - Planner may collapse to a single file if the line count is low; keep the public API the same.

### Testing

- **D-19:** Fixture-driven tests only — no network. Use existing `tests/fixtures/gamelog_592450_2026.json` + `feed_82*.json` for the happy path (6 Judge HRs). Synthetic fixtures for degradation cases:
  - A game feed with a non-HR batter's HR play in `allPlays` (verify batter filter).
  - A play with `playEvents[-1].hitData` null but an earlier playEvent carrying hitData (verify fallback).
  - A play with `result.description` containing "inside-the-park" (verify `is_itp`).
  - A play with no `hitData` at all (verify flags all False, event still emitted).
  - A game with `get_game_feed` raising `MLBAPIError` (verify PipelineError collection, other games still processed).
  - A gameLog row with `homeRuns=2` but only 1 matching play in the feed (verify warning logged, 1 event returned, no exception).

### Claude's Discretion

- Exact `PipelineResult` / `PipelineError` field names (as long as the spirit of D-13 holds).
- Whether `HREvent.to_hit_data()` lives on the class or as a module-level helper.
- Whether to use `logging.warning` or a structured record for the gameLog-vs-feed count mismatch (logging is fine; keep it simple).
- Whether to split `pipeline/extract.py` into smaller helpers or keep one file.
- Exact chronological sort tiebreakers beyond `(game_date, play_idx)` (unlikely to matter with <60 HRs/season).
</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project instructions
- `CLAUDE.md` — Direct HTTP to `statsapi.mlb.com/api/v1` only, no third-party wrappers; `@st.cache_data` at the function boundary only; aggressive caching, no hammering.

### Planning artifacts
- `.planning/REQUIREMENTS.md` — DATA-01, DATA-02, DATA-03, DATA-05 acceptance criteria; out-of-scope list.
- `.planning/ROADMAP.md` §Phase 3 — Phase goal, success criteria, research flag on `hitData` location and HR `eventType` values.
- `.planning/PROJECT.md` — Core value, evolution rules.

### Phase 1 artifacts (API layer Phase 3 consumes)
- `src/mlb_park/services/mlb_api.py` — `get_game_log`, `get_game_feed`, `load_all_parks`, `MLBAPIError`. The only `requests` / `st.cache_data` boundary.
- `src/mlb_park/config.py` — `CURRENT_SEASON` constant, cache TTLs, venue cache path.
- `tests/fixtures/gamelog_592450_2026.json` — Judge 2026 gameLog (ground truth for DATA-01 filter).
- `tests/fixtures/feed_822998.json`, `feed_823241.json`, `feed_823243.json`, `feed_823563.json`, `feed_823568.json` — 5 game feeds covering 6 Judge HRs (ground truth for DATA-02 walk).
- `tests/fixtures/venue_*.json` — 30 venues' fieldInfo (reused transitively via `load_all_parks`).
- `.planning/phases/01-foundation-api-layer/01-RESEARCH.md` — Endpoint semantics and cache-TTL rationale.
- `.planning/phases/01-foundation-api-layer/01-03-SUMMARY.md` — Fixture inventory.

### Phase 2 artifacts (geometry layer that consumes Phase 3's output)
- `src/mlb_park/geometry/verdict.py` — `HitData`, `VerdictMatrix`, `compute_verdict_matrix`. Pipeline produces `HitData` via the `HREvent → HitData` adapter.
- `.planning/phases/02-models-geometry/02-CONTEXT.md` — D-17 (HitData shape) is the upstream contract Phase 3 must honor.

### External references
- No external ADRs. Ground truth is the fixture set.
</canonical_refs>

<specifics>
## Specific Ideas

- Chronological order: `(game_date asc, play_idx asc)`. Phase 5/6 can re-sort but the pipeline's default is stable and time-ordered.
- Sanity-check warning format: `"gameLog/feed HR count mismatch for gamePk=%d: expected %d, matched %d"`.
- ITP substring check is case-insensitive: `"inside-the-park" in description.lower()`.
- `has_launch_stats` requires BOTH `launchSpeed` AND `launchAngle` present — either alone is incomplete for VIZ-03's tooltip.
- Opponent abbr resolution: read from the feed's `gameData.teams.{home,away}.abbreviation` against the batter's team (gameLog row has team info). If neither the feed nor gameLog exposes a 3-letter abbr directly, fall back to the short team name — planner/researcher picks based on fixture inspection.
</specifics>

<deferred>
## Deferred Ideas

- **V2-02:** Per-HR details table (date, distance, EV, LA, parks cleared /30) below the chart — HREvent shape already carries the raw fields, so v2 is a UI change only.
- **V2-05:** URL query-param state (`?player=...&stadium=...`) — pipeline doesn't need to change.
- **V2:** Retry-on-failure at the pipeline level. v1 defers retry to Phase 6's user-initiated cache-clear pattern.
- **V2:** Career / multi-season history (explicitly out of scope per REQUIREMENTS §Out of Scope).
- **V2:** Reversed-play reconciliation. The current feed's final `eventType` is the oracle; if MLB later reverses a play, the next cache refresh picks it up.
- **V2:** MLB video link-out per HR — would need `playId` reliability confirmation.
</deferred>

---

*Phase: 03-hr-pipeline*
*Context gathered: 2026-04-15 via /gsd-discuss-phase*
