# Phase 4: Controller & Selectors UI - Context

**Gathered:** 2026-04-15
**Status:** Ready for planning

<domain>
## Phase Boundary

Thinnest Streamlit shell that proves the full pipeline works end-to-end. Three cascading selectors (Team → Player → Stadium), one `controller.build_view(team_id, player_id, venue_id)` that composes Phase 1 (services), Phase 3 (`extract_hrs`), and Phase 2 (`compute_verdict_matrix`) into a single `ViewModel`, and a raw dump (JSON + dataframe) that renders the model below the selectors. No chart, no summary card, no polish — those are Phase 5 and Phase 6.

Satisfies UX-01 (team dropdown, 30 teams), UX-02 (player list: non-pitchers sorted by current-season HR desc), UX-03 (stadium dropdown defaults to player's home park), UX-04 (session_state reset cascade). UX-05 (spinners / error UI polish) is explicitly Phase 6.

</domain>

<decisions>
## Implementation Decisions

### Locked from prior phases / roadmap / CLAUDE.md

- **D-01:** Only `src/mlb_park/services/mlb_api.py` touches `requests` and `st.cache_data`. Phase 4's controller composes services and pipeline — never imports `requests` directly.
- **D-02:** Phase 4 imports the public surface at `mlb_park.pipeline` (which already re-exports `extract_hrs`, `HitData`, `compute_verdict_matrix`, `load_all_parks`, `CURRENT_SEASON`, `MLBAPIError`, `HREvent`, `PipelineResult`, `PipelineError`, `hr_event_to_hit_data`). Single import origin; no reaching into `mlb_park.pipeline.extract` or `mlb_park.geometry.verdict`.
- **D-03:** URL query-param state is explicitly **v2 (V2-05)** — not in Phase 4. Streamlit 1.55's `bind=` feature exists but we are not using it.
- **D-04:** UX-05 (spinner + friendly error on fetch failure) is **Phase 6**, not Phase 4. Phase 4 may use `st.spinner` / `st.warning` as dev conveniences but is not expected to satisfy UX-05.

### ViewModel shape (the Phase 5 + Phase 6 contract)

- **D-05:** `controller.build_view(team_id, player_id, venue_id, *, season=None, api=...) -> ViewModel`. Signature mirrors Phase 3's `extract_hrs` conventions: `season` defaults to `CURRENT_SEASON`; `api` is a keyword-only injection seam for tests (stub module with `get_team_hitting_stats`, `get_teams`, `get_roster`, `get_game_feed`, `get_game_log`, `load_all_parks`, `MLBAPIError`).
- **D-06:** `ViewModel` is a **rich, pre-computed** frozen dataclass. Phase 5/6 consume it without recomputing anything. Shape:
  ```
  ViewModel(
      # Selections (the state that produced this view)
      season: int,
      team_id: int,
      team_abbr: str,                          # convenience for tooltips / titles
      player_id: int,
      player_name: str,                        # display name
      venue_id: int,                           # selected stadium for the verdict flip
      venue_name: str,
      player_home_venue_id: int,               # needed for UX-03 default + reset logic

      # HR data
      events: tuple[HREvent, ...],             # all HRs, chronological (from PipelineResult)
      plottable_events: tuple[HREvent, ...],   # subset where has_distance AND has_coords
      verdict_matrix: VerdictMatrix | None,    # Phase 2 type; None when plottable_events is empty
      clears_selected_park: tuple[bool, ...],  # aligned with plottable_events; True if HR clears venue_id

      # Derived totals (Phase 6 summary card lives here in final form;
      # Phase 4 includes them now so the schema is fixed)
      totals: dict[str, int | float],          # keys: total_hrs, plottable_hrs, avg_parks_cleared,
                                               #       no_doubters (30/30), cheap_hrs (<=5/30)

      # Error carrier (forward-compat for Phase 6's UX-05)
      errors: tuple[PipelineError, ...],
  )
  ```
- **D-07:** `HREvent → HitData` filter happens **inside `build_view`**, not in Phase 5. `plottable_events = tuple(ev for ev in events if ev.has_distance and ev.has_coords)`. `verdict_matrix` is built from `[hr_event_to_hit_data(ev) for ev in plottable_events]`. Single source of truth for "which HRs can be scored."
- **D-08:** `clears_selected_park`: for each plottable event, look up `verdict_matrix.records[park_id=venue_id]` and read the `HR` verdict for that event's `(game_pk, play_idx)` identifier. Aligned by index with `plottable_events`.
- **D-09:** `totals` is computed in Phase 4 and schema-locked now so Phase 6 doesn't break the contract:
  - `total_hrs = len(events)`
  - `plottable_hrs = len(plottable_events)`
  - `avg_parks_cleared` = mean across `plottable_events` of (count of parks where HR clears in `verdict_matrix`). `0.0` if `plottable_events` is empty.
  - `no_doubters` = count of plottable events that clear all 30 parks.
  - `cheap_hrs` = count of plottable events that clear ≤ 5 parks.
  Phase 6 may **rename** keys only via a new CONTEXT entry; no silent schema drift.
- **D-10:** `verdict_matrix` is `None` when `plottable_events` is empty (0-HR player OR all HRs lack hitData). Downstream consumers branch on `verdict_matrix is None`, they do not receive a zero-row matrix.

### Player list — UX-02 strategy

- **D-11 (AMENDED 2026-04-15 after research):** Sort + filter data source: the **hydrated roster endpoint**. Add a new services wrapper: `get_team_hitting_stats(team_id: int, season: int) -> list[dict]` calling `GET /teams/{team_id}/roster?rosterType=active&hydrate=person(stats(type=statsSingleSeason,season={season},group=hitting))`. Returns one entry per active-roster player with top-level `position.type` and hydrated `person.stats[0].splits[0].stat.homeRuns` (absent when player has 0 season HRs — treat as 0). One HTTP call per team selection — no per-player fan-out. Respects CLAUDE.md's "aggressive caching, no hammering." **Superseded the earlier `/teams/{id}/stats?stats=season` proposal, which returns team aggregates, not per-player rows — see `04-RESEARCH.md` §Q1 and fixture `tests/fixtures/team_stats_147_2026.json`.**
- **D-12 (AMENDED 2026-04-15):** Non-pitcher filter: top-level `entry["position"]["type"] != "Pitcher"` on each roster entry (keeps DH, OF, IF, C, and any "Two-Way Player" type so Ohtani stays in). Fixture-verified against `tests/fixtures/team_stats_147_2026.json`. Handle missing `position` defensively by treating as non-pitcher (logged warning).
- **D-13:** Sort order: `sorted(..., key=lambda p: (-stat_home_runs, player_name))` — HR desc, name asc as tiebreak for determinism. Zero-HR hitters are **included** at the bottom (a player with 0 season HRs is still a legitimate selection; the pipeline just returns an empty `events` tuple).
- **D-14:** Cache TTL for `get_team_hitting_stats`: 1 hour (matches gameLog TTL pattern — season totals update after each game). `@st.cache_data(ttl="1h")` at the services boundary, consistent with D-01.
- **D-15:** If `get_team_hitting_stats` ever returns an empty list (team with zero rostered hitters — defensive), the player selectbox shows an empty list and `build_view` is not called. No crash.

### Session state + reset mechanism — UX-04

- **D-16:** Canonical session_state keys: `"team_id"`, `"player_id"`, `"venue_id"`. Short, flat, project-local.
- **D-17:** Reset mechanism: **Streamlit `on_change` callbacks**. Three selectboxes:
  - Team selectbox `key="team_id"`, `on_change=_on_team_change` → clears `st.session_state["player_id"]` and `st.session_state["venue_id"]`.
  - Player selectbox `key="player_id"`, `on_change=_on_player_change` → sets `st.session_state["venue_id"] = teams[team_id].venue.id` (the player's home park — UX-03 default).
  - Stadium selectbox `key="venue_id"` has no callback; user's manual override sticks until Player or Team changes.
- **D-18:** Initial load: **empty placeholders** (Streamlit 1.55 `index=None` on `st.selectbox`). No API fetches until the user picks a team. Zero cold-start cost; satisfies CLAUDE.md's rate posture.
- **D-19:** Guard: `build_view` is only invoked when all three of `team_id`, `player_id`, `venue_id` are non-None. Before that, the raw-dump area shows a subtle `st.info("Select a team, player, and stadium to begin.")`.
- **D-20:** Player's home venue lookup: derived from the Phase 1 `get_teams()` response — `team["venue"]["id"]` — not a separate endpoint. Already cached via the teams wrapper. The `_on_player_change` callback reads the currently-selected team's venue id.

### Controller module layout + caching boundary

- **D-21:** **Single module** at `src/mlb_park/controller.py`. Exposes `build_view` and the `ViewModel` (frozen dataclass). Package-ifying (`controller/`) is ceremony — defer to if/when the file grows past ~200 LOC. Phase 6 polish can refactor.
- **D-22:** **No `@st.cache_data` on `build_view`.** Caching lives at the services boundary (`get_teams`, `get_roster`, `get_team_hitting_stats`, `get_game_log`, `get_game_feed`, `load_all_parks` are all individually cached). `build_view` is cheap pure composition; adding a cache on it would create a second invalidation model with no speed win, and the cache key would need `(player_id, season, venue_id)` which defeats itself whenever the user rotates the stadium.
- **D-23:** `build_view` is **pure** (no Streamlit calls inside — no `st.*`, no `session_state`). All session-state reads happen in `app.py`; `build_view` receives IDs by argument. Makes the controller unit-testable with fixtures and a stub `api` module.

### Raw dump format + empty state

- **D-24:** Raw dump is two blocks stacked:
  1. `st.json(view.to_dict())` — full structured ViewModel for dev inspection. `ViewModel.to_dict()` is a helper that converts dataclass → JSON-safe dict (datetimes → iso strings, VerdictMatrix → `.to_dict()` or summary dict).
  2. `st.dataframe(pd.DataFrame([{...event fields, clears_selected_park}] for ev in plottable_events))` — scannable per-HR table. Columns: `game_date`, `opponent_abbr`, `distance_ft`, `launch_speed`, `launch_angle`, `clears_selected`.
- **D-25:** 0-HR empty state: when `events` is empty, skip the dataframe block and show `st.info(f"{player_name} has no home runs in {season}.")`. The `st.json(view.to_dict())` block still renders (totals all zero) so the pipeline end-to-end is still provably wired.
- **D-26:** All-missing-hitData state: when `events` is non-empty but `plottable_events` is empty (pre-Statcast / all ITP), show `st.info("No HRs have hitData for the verdict matrix — pipeline returned events but none are plottable.")` above the JSON dump. Dataframe block omitted.

### Pipeline error surfacing

- **D-27:** `ViewModel.errors` **always carries** `PipelineResult.errors` forward. Phase 4 additionally renders a minimal `st.warning(f"{len(errors)} game feed(s) failed to fetch; see raw ViewModel for details.")` when `errors` is non-empty. Final polished error UX (retry button, per-game breakdown) is Phase 6's UX-05.

### Testing

- **D-28:** Unit tests for the controller under `tests/controller/test_build_view.py`. Inject a stub `api` module (same pattern as Phase 3's `StubAPI` — reuse the fixture loaders from `tests/pipeline/conftest.py` where applicable; add a minimal `tests/controller/conftest.py` for controller-specific stubs like `get_team_hitting_stats`).
- **D-29:** Minimum test coverage:
  - Happy path: Judge fixtures → `build_view(NYY, Judge, YankeeStadium)` → asserts `len(events)`, `len(plottable_events)`, `verdict_matrix is not None`, `clears_selected_park` length matches, `totals` arithmetic, `errors == ()`.
  - 0-HR player: stub returns gameLog with `homeRuns=0` → `events == ()`, `plottable_events == ()`, `verdict_matrix is None`, `totals["total_hrs"] == 0`, no exception.
  - All-missing-hitData: feed with hitData nulls → `events` non-empty, `plottable_events == ()`, `verdict_matrix is None`.
  - One feed fails: stub raises `MLBAPIError` for one gamePk → `errors` non-empty, other HRs still in `events`.
  - Stadium flip: same `(team_id, player_id)`, two different `venue_id` → `clears_selected_park` differs, `verdict_matrix` identical.
- **D-30:** No Streamlit in controller tests. `app.py` (the Streamlit entry point) is **not unit-tested** in Phase 4 — manual smoke test after plans complete. Streamlit AppTest framework is deferred to Phase 6 if it proves valuable.

### Claude's Discretion

- Whether `ViewModel.to_dict()` uses `dataclasses.asdict` with custom handling, or a hand-rolled method. Either works.
- Whether the three `on_change` callbacks live in `app.py` as module-level functions or inside a tiny helper module.
- Exact CSS/layout details — `st.columns`, `st.sidebar` vs main area — as long as the three selectors are visible and the raw dump renders below.
- Whether to log (via `logging.info`) each `build_view` invocation for dev visibility. Fine either way.
- Whether `totals` is a plain `dict` or a `Totals` frozen dataclass. `dict` keeps JSON serialization trivial; a dataclass adds type safety. Planner picks.
- Whether the dataframe block uses pandas explicitly or `st.dataframe` with a list of dicts (Streamlit accepts both).
- Exact non-pitcher path in the team-stats JSON (`primaryPosition.type` vs nested under `player`) — researcher confirms against a fixture.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project instructions
- `CLAUDE.md` — Streamlit 1.55+ pinning, direct HTTP only, `st.cache_data` at services boundary, no `requests-cache`, aggressive caching posture.

### Planning artifacts
- `.planning/REQUIREMENTS.md` — UX-01 / UX-02 / UX-03 / UX-04 acceptance criteria (Phase 4 scope); UX-05 (Phase 6); V2-05 URL state (out of scope).
- `.planning/ROADMAP.md` §Phase 4 — Goal: thinnest Streamlit app + ViewModel + raw dump; `UI hint: yes`.
- `.planning/PROJECT.md` — Core value, evolution rules, key decisions.

### Phase 1 artifacts (API layer Phase 4 composes)
- `src/mlb_park/services/mlb_api.py` — Existing wrappers: `get_teams`, `get_roster`, `get_game_log`, `get_game_feed`, `get_venue`, `load_all_parks`, `MLBAPIError`. Phase 4 adds `get_team_hitting_stats` (D-11) following the same `@st.cache_data` / `_raw_*` / public-wrapper pattern.
- `src/mlb_park/config.py` — `CURRENT_SEASON` default (D-05).

### Phase 2 artifacts (geometry consumed by ViewModel)
- `src/mlb_park/geometry/verdict.py` — `HitData`, `VerdictMatrix`, `VerdictRecord`, `compute_verdict_matrix`. ViewModel stores a `VerdictMatrix | None` (D-06).
- `src/mlb_park/geometry/park.py` — `Park`, `load_parks(venues)`. `compute_verdict_matrix` takes parks + hit_data_list.

### Phase 3 artifacts (pipeline consumed by controller)
- `src/mlb_park/pipeline/__init__.py` — The public import surface. Phase 4 imports `extract_hrs`, `hr_event_to_hit_data`, `HREvent`, `PipelineResult`, `PipelineError`, `HitData`, `compute_verdict_matrix`, `load_all_parks`, `CURRENT_SEASON`, `MLBAPIError` from here.
- `src/mlb_park/pipeline/events.py` — `HREvent` field reference for tooltip / dataframe columns.
- `.planning/phases/03-hr-pipeline/03-CONTEXT.md` — D-05 (HREvent shape), D-06 (adapter), D-13 (PipelineResult), D-17 (api injection seam). Phase 4 inherits these contracts.

### Streamlit references
- Streamlit 1.55 release notes — `index=None` support on `st.selectbox`, `on_change` semantics. See CLAUDE.md "Recommended Stack" section.

### External references
- No external ADRs. Ground truth is the fixtures under `tests/fixtures/` and any new team-stats fixture added in Phase 4 (researcher should record one for a known team, e.g., NYY 2026).

</canonical_refs>

<specifics>
## Specific Ideas

- Selector layout: three `st.selectbox` widgets at the top of `app.py`, stacked vertically (or side-by-side via `st.columns(3)` — planner's call). Raw dump renders below with `st.divider()` separator.
- Team selectbox options: `get_teams()` sorted by `name` asc; display format `"{team.name} ({team.abbreviation})"`, option value = `team.id`.
- Player selectbox options: from `get_team_hitting_stats(team_id, season)` filtered to non-pitchers, sorted by `(-homeRuns, name)`; display format `"{fullName} — {homeRuns} HR"`, option value = `player.id`.
- Stadium selectbox options: `load_all_parks()` sorted by `venue.name` asc; display format `venue.name`, option value = `venue.id`.
- `_on_team_change`: `st.session_state["player_id"] = None; st.session_state["venue_id"] = None`.
- `_on_player_change`: `st.session_state["venue_id"] = _current_team_home_venue(st.session_state["team_id"])` where the helper looks up the venue id from cached `get_teams()`.
- ViewModel JSON rendering: `VerdictMatrix.to_dict()` (already exists on the Phase 2 class — verify). If not, add a small summary-dict helper: `{park_id: {cleared: bool for hr_identifier}}` truncated for large matrices. Keep the top-level JSON under a reasonable size — the dataframe is the scannable view.
- Totals key exact names (schema-locked): `total_hrs`, `plottable_hrs`, `avg_parks_cleared`, `no_doubters`, `cheap_hrs`.

</specifics>

<deferred>
## Deferred Ideas

- **V2-05:** URL query-param state for shareable player/stadium view. Streamlit 1.55's `bind=` feature would satisfy this trivially — revisit after v1 ships.
- **V2:** Persisted last-used selections across sessions (disk or cookie). Not in scope for single-user local hobby app.
- **V2:** Loading spinners + per-fetch friendly error messages (`UX-05`). Phase 6's domain.
- **V2:** Streamlit AppTest framework for `app.py` unit tests. Phase 4 relies on controller unit tests + manual smoke.
- **V2:** Expanding `Totals` into its own dataclass if Phase 6 adds many derived metrics.
- **V2-02:** Per-HR details table with sortable columns — Phase 4's raw `st.dataframe` is a stepping stone; V2 polishes it with explicit column config, sort, format.
- **V2-03:** Wall-height caveat banner — pure UI copy, fits Phase 6 polish.
- **V2-04:** Cheap-HR threshold slider — `cheap_hrs` is hardcoded to ≤5/30 in D-09; slider would make the threshold user-configurable.
- Splitting `controller.py` into a package if it grows past ~200 LOC.
- Namespacing session_state keys (`mlb_park.team_id`) if a multi-page app ever lands.

</deferred>

---

*Phase: 04-controller-selectors-ui*
*Context gathered: 2026-04-15 via /gsd-discuss-phase*
