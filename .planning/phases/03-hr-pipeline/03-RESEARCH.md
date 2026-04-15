# Phase 3: HR Pipeline - Research

**Researched:** 2026-04-15
**Domain:** MLB StatsAPI feed walking, null-safe hitData extraction, fixture-driven pipeline tests
**Confidence:** HIGH (fixture ground-truth verified empirically for every claim)

## Summary

Phase 3 builds `extract_hrs(player_id, season) -> PipelineResult` on top of Phase 1's cached HTTP layer and Phase 2's `HitData` contract. CONTEXT.md has already locked the design (D-01..D-19) — this research confirms every CONTEXT.md decision against the 5 committed fixtures (6 Judge HRs) and fills in the empirical gaps the planner needs to write tasks.

**Verified findings from fixtures:**
- `hitData` sits at `playEvents[-1].hitData` for **all 15** `home_run` plays across the 5 feeds (6 of which are Judge's). The D-10 fallback to "last playEvent with non-null hitData" is never triggered by the real fixture set but is sound defensive logic — must be covered with a **synthetic** fixture.
- `result.eventType` for every HR in the fixture set is exactly `"home_run"` — no variants, no `"home_run_inside_park"`, no review-reversal residue. `eventType` enum in this fixture pool: `field_out, strikeout, single, walk, double, home_run, grounded_into_double_play, triple, hit_by_pitch, sac_fly, sac_bunt, force_out, field_error, intent_walk, fielders_choice_out, fielders_choice`.
- Opponent 3-letter abbreviation lives at `gameData.teams.{home,away}.abbreviation` (**present on every fixture**). It is **NOT** on gameLog rows (gameLog's `team`/`opponent` objects only carry `id`, `link`, `name`). Phase 3 must read abbr from the feed.
- Game date is at `gameData.datetime.officialDate` as `"YYYY-MM-DD"` on every feed; also present as `date` on the gameLog row. Either is authoritative.
- `inning` / `halfInning` / `atBatIndex` all live under `play.about` on HR plays in every fixture. `atBatIndex == allPlays` array index on all 6 Judge plays.
- `hitData` inner fields (`totalDistance`, `launchSpeed`, `launchAngle`, `coordinates.coordX`, `coordinates.coordY`) are **never null in the fixture set** (0/242 playEvents with `hitData` across all 5 feeds). Degradation paths MUST therefore be exercised via synthetic fixtures per D-19.
- `matchup.batter.id` is present on all 6 Judge HR plays — the D-08 filter is reliable.

**Primary recommendation:** Implement exactly what CONTEXT.md D-01..D-19 specifies. The opponent-abbr resolution uses `gameData.teams.{home,away}.abbreviation` keyed off the batter's team id (available on `matchup.batter.parentTeamId` and redundantly on the gameLog row's `team.id`). No design tweaks required.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**D-01..D-04 (from prior phases / CLAUDE.md):**
- Only `services/mlb_api.py` touches `requests` and `st.cache_data`. Phase 3 modules import `mlb_park.services.mlb_api` — never `requests`.
- Pipeline consumes the Phase 2 `HitData(distance_ft, coord_x, coord_y, identifier)` contract. Per-HR verdicts are computed by Phase 2's `compute_verdict_matrix`; Phase 3 does NOT recompute geometry.
- Reuse Phase 1's `load_all_parks()` for DATA-03; disk-backed `data/venues_cache.json` already exists with a 30-day TTL.
- No HR is dropped silently. Missing/partial `hitData` → retain with flags (DATA-05). Failed feed fetches → collected in errors list, not raised.

**D-05 HREvent shape** (frozen dataclass):
```
HREvent(
    game_pk: int, game_date: datetime.date, opponent_abbr: str,
    inning: int, half_inning: str, play_idx: int,
    distance_ft: float | None, coord_x: float | None, coord_y: float | None,
    launch_speed: float | None, launch_angle: float | None,
    has_distance: bool, has_coords: bool, has_launch_stats: bool, is_itp: bool,
)
```

**D-06 HREvent → HitData adapter:** when both `has_distance` and `has_coords` are True, produce `HitData(distance_ft, coord_x, coord_y, identifier=(game_pk, play_idx))`. HRs missing distance/coords are emitted but excluded from verdict-matrix input (Phase 4 handles the split). Planner picks between a module-level helper vs `HREvent.to_hit_data()` method.

**D-07 gameLog filter (DATA-01):** `extract_hrs` first calls `get_game_log(player_id, season)` and keeps only rows where `stat.homeRuns >= 1`. No feed is fetched for 0-HR games.

**D-08 Feed-walk filter:** For each HR game, call `get_game_feed(gamePk)` once and walk `liveData.plays.allPlays`. Keep plays where `matchup.batter.id == player_id` AND `result.eventType == "home_run"`. No review-reversal special-casing — the current feed's final eventType is the oracle.

**D-09 Count sanity check:** if `len(matched_plays) != gameLog_row.stat.homeRuns`, log a warning `"gameLog/feed HR count mismatch for gamePk=%d: expected %d, matched %d"` but KEEP the matched plays (no exception).

**D-10 hitData lookup path:** Prefer `play["playEvents"][-1]["hitData"]`. If the terminal event lacks `hitData`, fall back to the last playEvent that has non-null hitData. If none, emit with `has_distance=False`, `has_coords=False`, `has_launch_stats=False`.

**D-11 ITP detection:** `is_itp = True` iff `"inside-the-park" in result.description.lower()`. Pre-Statcast games also lack hitData but are NOT ITP — the distinction is substring-based.

**D-12 Field-level null safety:**
- `has_distance = hitData.totalDistance is not None`
- `has_coords = hitData.coordinates.coordX is not None AND hitData.coordinates.coordY is not None`
- `has_launch_stats = hitData.launchSpeed is not None AND hitData.launchAngle is not None`
- These flags are independent — an event can have coords but no launch stats.

**D-13 PipelineResult shape:**
```
PipelineResult(
    events: tuple[HREvent, ...],            # chronological: (game_date asc, play_idx asc)
    errors: tuple[PipelineError, ...],
    season: int, player_id: int,
)
PipelineError(game_pk: int | None, endpoint: str, message: str)
```

**D-14 Exception handling:** `get_game_log` failure → raise (nothing to return; Phase 4 surfaces via UX-05). Individual `get_game_feed(gamePk)` failure → catch `MLBAPIError`, append `PipelineError(game_pk, "game_feed", str(exc))`, continue remaining games.

**D-15 No retries in pipeline.** Retries live at `@st.cache_data` / user-initiated level (Phase 6's retry button clears cache and re-calls). Pipeline is deterministic given its inputs → fixture-tests trivial.

**D-16 Public signature:** `extract_hrs(player_id: int, season: int | None = None) -> PipelineResult`. When `season is None`, resolve from `config.CURRENT_SEASON`.

**D-17 API module injection:** Pipeline functions take optional `api` kwarg defaulting to `mlb_park.services.mlb_api`. Tests pass a stub module with `get_game_log` / `get_game_feed` / `load_all_parks` attributes. No monkey-patching.

**D-18 Module layout:** New files under `src/mlb_park/pipeline/`:
- `pipeline/__init__.py` — re-exports `extract_hrs`, `HREvent`, `PipelineResult`, `PipelineError`
- `pipeline/events.py` — `HREvent`, `PipelineResult`, `PipelineError` dataclasses
- `pipeline/extract.py` — `extract_hrs` + helpers (`_walk_feed_for_hrs`, `_extract_hit_data`, `_detect_itp`)
- Planner may collapse to a single file if line count is low; keep the public API the same.

**D-19 Testing:** Fixture-driven only — no network. Happy path uses existing `gamelog_592450_2026.json` + `feed_82*.json` (6 Judge HRs). Synthetic fixtures required for:
- A game feed with a non-HR-batter's HR play in `allPlays` (verify batter filter).
- A play with `playEvents[-1].hitData` null but earlier playEvent carrying hitData (verify fallback).
- A play with `result.description` containing "inside-the-park" (verify `is_itp`).
- A play with no `hitData` at all (verify flags all False, event still emitted).
- A game where `get_game_feed` raises `MLBAPIError` (verify PipelineError collection, other games still processed).
- A gameLog row with `homeRuns=2` but only 1 matching play (verify warning logged, 1 event returned, no exception).

### Claude's Discretion

- Exact `PipelineResult` / `PipelineError` field names (as long as D-13 spirit holds).
- Whether `HREvent.to_hit_data()` lives on the class or as a module-level helper.
- Whether to use `logging.warning` or a structured record for count mismatch (logging is fine — keep it simple).
- Whether to split `pipeline/extract.py` into smaller helpers or keep one file.
- Exact chronological sort tiebreakers beyond `(game_date, play_idx)`.

### Deferred Ideas (OUT OF SCOPE)

- **V2-02:** Per-HR details table below the chart — HREvent already carries raw fields; v2 is UI-only.
- **V2-05:** URL query-param state — pipeline doesn't need to change.
- **V2:** Retry-on-failure at the pipeline level — v1 defers to Phase 6 user-initiated cache-clear.
- **V2:** Career / multi-season history — REQUIREMENTS §Out of Scope.
- **V2:** Reversed-play reconciliation — current feed's final `eventType` is the oracle.
- **V2:** MLB video link-out per HR — would need `playId` reliability confirmation.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| DATA-01 | Retrieve current season's gameLog and identify HR-containing games | `_raw_game_log` already returns `stats[0].splits`; row `stat.homeRuns` is int ≥ 0; D-07 filter runs pre-feed-fetch. Verified: 5/17 fixture rows have `homeRuns >= 1`. |
| DATA-02 | For each HR game, fetch live feed, extract Judge HR plays and their hitData (launchSpeed, launchAngle, totalDistance, coordinates.coordX/coordY) | `liveData.plays.allPlays[*]` filtered by `matchup.batter.id == player_id AND result.eventType == "home_run"`. hitData at `playEvents[-1].hitData`. Verified in all 6 Judge plays. |
| DATA-03 | fieldInfo for all 30 stadiums cached on disk, persists between restarts | Already implemented in Phase 1 (`load_all_parks()` + `data/venues_cache.json` + 30-day TTL via `VENUES_STALE_DAYS`). Phase 3 calls it, does not reimplement. |
| DATA-05 | Per-HR extraction degrades gracefully — HRs missing hitData (ITP, pre-Statcast) retained and flagged | D-10..D-12 null-safe flag scheme. Fixture set has 0 missing-hitData HRs; DATA-05 compliance proved via synthetic fixtures (D-19). |
</phase_requirements>

## Empirical Fixture Verification

### Fixture inventory (ground truth)

| File | gamePk | officialDate | Home/Away | Judge HR count | Judge HR play_idx (=atBatIndex) |
|------|--------|--------------|-----------|----------------|----------------------------------|
| `gamelog_592450_2026.json` | — | 2026-03-25 … 2026-04-13 | — | **5 games / 6 HRs** total | see below |
| `feed_823243.json` | 823243 | 2026-03-27 | SF home, NYY away | 1 | 35 |
| `feed_823241.json` | 823241 | 2026-03-28 | SF home, NYY away | 1 | 36 |
| `feed_823568.json` | 823568 | 2026-04-03 | NYY home, MIA away | 1 | 5 |
| `feed_822998.json` | 822998 | 2026-04-12 | TB home, NYY away | 1 | 65 |
| `feed_823563.json` | 823563 | 2026-04-13 | NYY home, LAA away | **2** | 4, 58 |

**GameLog HR row mapping:** 5 rows with `stat.homeRuns >= 1` (2026-03-27 / 28 / 04-03 / 04-12 / 04-13), where 2026-04-13 row has `homeRuns=2` and the rest have `homeRuns=1`. Sum = 6, matches 6 feed-walked plays (D-09 sanity check passes for all 5 games).

### Verification of each empirical claim

| Claim | Finding | Confidence |
|-------|---------|------------|
| `hitData` always at `playEvents[-1]` for HR plays | **15/15** HR plays across 5 feeds have hitData in terminal playEvent. 0 cases where hitData exists but not in last position. | HIGH (fixture-verified) |
| HR eventType always `"home_run"` | 15/15 HR plays have `eventType == "home_run"`. No variants in 16 distinct eventType values seen in fixtures. | HIGH |
| `matchup.batter.id` present on HR plays | 6/6 Judge HR plays. | HIGH |
| `about.inning`, `about.halfInning`, `about.atBatIndex` present | 6/6. `halfInning` values seen: `"top"` (Judge batting as away), `"bottom"` (Judge batting at home). `atBatIndex` equals the `allPlays` array index in all 6. | HIGH |
| Opponent abbr via `gameData.teams.{home,away}.abbreviation` | Present on all 5 feeds for both teams. Values: SF/NYY, TB/NYY, NYY/LAA, NYY/MIA. 3-letter, standard. | HIGH |
| `gameData.datetime.officialDate` as `"YYYY-MM-DD"` | Present on all 5 feeds. Parseable with `datetime.date.fromisoformat`. | HIGH |
| hitData inner fields (`totalDistance`, `launchSpeed`, `launchAngle`, `coordinates.coordX/Y`) | 242/242 playEvents-with-hitData across all 5 feeds have zero nulls. Degradation paths are unreachable from real fixtures → synthetic fixtures mandatory (D-19). | HIGH |
| gameLog row team/opponent lacks `abbreviation` key | Confirmed. `team`/`opponent` keys are only `{id, link, name}`. Abbr MUST come from feed. | HIGH |
| No ITP plays in fixture set | 0/15 HR `result.description` contains "inside-the-park". ITP path is synthetic-only. | HIGH |
| D-10 fallback ever needed in real data | Not observed in 5-feed sample. Defensive only. | MEDIUM (fixture sample size = 15 HR plays) |

## Module & Data Contracts (consumed and produced)

### Consumed API surface (from Phase 1)

| Function | Signature | Returns | Notes |
|----------|-----------|---------|-------|
| `mlb_park.services.mlb_api.get_game_log` | `(person_id: int, season: int)` | `list[dict]` (splits) | Each row has `date`, `game.gamePk`, `stat.homeRuns`, `team.id`, `opponent.id`. **No abbreviation field.** |
| `mlb_park.services.mlb_api.get_game_feed` | `(game_pk: int)` | `dict` (full feed) | Uses `v1.1` base URL. Raises `MLBAPIError` on failure. |
| `mlb_park.services.mlb_api.load_all_parks` | `()` | `dict[int, dict]` | Satisfies DATA-03 already — Phase 3 only re-exports / re-wraps for the Phase 4 controller. |
| `mlb_park.services.mlb_api.MLBAPIError` | Exception | — | Catch per-game-feed (D-14). |
| `mlb_park.config.CURRENT_SEASON` | — | Not yet defined | **Gap:** config.py currently has `YANKEES_TEAM_ID`, `JUDGE_PERSON_ID` but no `CURRENT_SEASON` constant. Phase 3 adds `CURRENT_SEASON = 2026`. |

### Produced contract (for Phase 4+)

```python
# pipeline/events.py
from dataclasses import dataclass
import datetime

@dataclass(frozen=True)
class HREvent:
    game_pk: int
    game_date: datetime.date
    opponent_abbr: str
    inning: int
    half_inning: str                 # "top" | "bottom"
    play_idx: int                    # allPlays index; also == atBatIndex in all observed cases
    distance_ft: float | None
    coord_x: float | None
    coord_y: float | None
    launch_speed: float | None
    launch_angle: float | None
    has_distance: bool
    has_coords: bool
    has_launch_stats: bool
    is_itp: bool

@dataclass(frozen=True)
class PipelineError:
    game_pk: int | None
    endpoint: str                    # e.g. "game_feed", "game_log"
    message: str

@dataclass(frozen=True)
class PipelineResult:
    events: tuple[HREvent, ...]
    errors: tuple[PipelineError, ...]
    season: int
    player_id: int
```

### HREvent → HitData adapter (D-06)

```python
# Module-level helper in pipeline/extract.py (discretion D-06)
def hr_event_to_hit_data(ev: HREvent) -> HitData | None:
    if not (ev.has_distance and ev.has_coords):
        return None
    return HitData(
        distance_ft=ev.distance_ft,
        coord_x=ev.coord_x,
        coord_y=ev.coord_y,
        identifier=(ev.game_pk, ev.play_idx),
    )
```

## Field-by-Field Extraction Map

For a single HR play `p` from `feed["liveData"]["plays"]["allPlays"][i]`:

| HREvent field | Source | Fallback | Type coercion |
|---------------|--------|----------|---------------|
| `game_pk` | `feed["gamePk"]` (also `feed["gameData"]["game"]["pk"]`) | — | `int` |
| `game_date` | `feed["gameData"]["datetime"]["officialDate"]` | gameLog row's `date` | `datetime.date.fromisoformat(str)` |
| `opponent_abbr` | **Resolved**: batter's team id is `p["matchup"]["batter"]["parentTeamId"]` OR gameLog row's `team.id`; compare against `feed["gameData"]["teams"]["home"]["id"]` vs `["away"]["id"]`; opponent is the OTHER side's `abbreviation` | If `abbreviation` missing on a side, fall back to `teamName` or `clubName` (all present in every fixture) | `str` |
| `inning` | `p["about"]["inning"]` | — | `int` |
| `half_inning` | `p["about"]["halfInning"]` | — | `str` (values: `"top"` / `"bottom"`) |
| `play_idx` | Enumerate index into `allPlays` (`for i, p in enumerate(allPlays)`) — equals `p["about"]["atBatIndex"]` in all fixtures but the **enumerate index is safer**, does not depend on atBatIndex being stable | — | `int` |
| `distance_ft` | `hitData["totalDistance"]` where `hitData` is picked by D-10 | `None` | `float` or `None` |
| `coord_x` | `hitData["coordinates"]["coordX"]` | `None` | `float` or `None` |
| `coord_y` | `hitData["coordinates"]["coordY"]` | `None` | `float` or `None` |
| `launch_speed` | `hitData["launchSpeed"]` | `None` | `float` or `None` |
| `launch_angle` | `hitData["launchAngle"]` | `None` | `float` or `None` |
| `has_distance` | `hitData.totalDistance is not None` (per D-12) | — | `bool` |
| `has_coords` | `coordX is not None AND coordY is not None` | — | `bool` |
| `has_launch_stats` | `launchSpeed is not None AND launchAngle is not None` | — | `bool` |
| `is_itp` | `"inside-the-park" in p["result"]["description"].lower()` | — | `bool` |

**Opponent-abbr algorithm (canonical):**
```python
def _opponent_abbr(feed: dict, batter_team_id: int) -> str:
    teams = feed["gameData"]["teams"]
    home, away = teams["home"], teams["away"]
    if home["id"] == batter_team_id:
        opp = away
    else:
        opp = home  # covers away-batter and also the "teams we can't match" edge
    return opp.get("abbreviation") or opp.get("teamName") or opp.get("clubName") or opp.get("name", "???")
```

`batter_team_id` source: the gameLog row carries `team.id` (verified: value is 147 for all 5 HR rows — Judge is a Yankee). Alternatively `p["matchup"]["batter"]["parentTeamId"]` (not checked in all 6 plays but standard across StatsAPI) — **use the gameLog row's `team.id` to avoid an extra lookup and remain robust if `parentTeamId` is absent on some plays.**

### hitData lookup (D-10 canonical form)

```python
def _extract_hit_data(play: dict) -> dict | None:
    events = play.get("playEvents") or []
    if not events:
        return None
    # Prefer terminal event (observed in 15/15 HR fixture plays)
    last = events[-1]
    if last.get("hitData"):
        return last["hitData"]
    # Defensive fallback (synthetic-test only in v1): last event with hitData
    for e in reversed(events):
        if e.get("hitData"):
            return e["hitData"]
    return None
```

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python stdlib `dataclasses` | 3.12 | `HREvent`, `PipelineResult`, `PipelineError` | Frozen dataclasses match Phase 2 pattern (`HitData`, `VerdictMatrix`). No third-party DI/validation framework — overkill for a hobby app. |
| Python stdlib `datetime` | 3.12 | `game_date` parsing | `date.fromisoformat("YYYY-MM-DD")` handles every fixture's `officialDate`. |
| Python stdlib `logging` | 3.12 | D-09 count-mismatch warning | Planner discretion per CONTEXT.md — use `logging.getLogger(__name__).warning(...)` with the CONTEXT.md format string. |
| `mlb_park.services.mlb_api` | in-repo | HTTP boundary (D-01) | Only `requests`/`st.cache_data` module. |
| `mlb_park.geometry.verdict.HitData` | in-repo (Phase 2) | Adapter target (D-06) | Frozen dataclass — 3 floats + opaque identifier. |
| `mlb_park.config` | in-repo | `CURRENT_SEASON` (add new) | Already the home for constants. |

### Supporting
None — pure-stdlib phase beyond the two in-repo modules.

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `@dataclass(frozen=True)` | `pydantic.BaseModel` | Validation/serialization nice-to-have, but adds a heavy dep; Phase 2 already uses plain dataclasses — stay consistent. |
| `logging.warning` | `warnings.warn` + stderr | `warnings` is for deprecations; `logging` is the standard observability channel for data-quality signals. |
| Enumerate index for `play_idx` | `p["about"]["atBatIndex"]` | Both are equal in 6/6 fixtures, but enumerate index is guaranteed stable regardless of API schema drift. Use enumerate. |

**Installation:** Nothing new to install. Phase 3 uses only stdlib + already-pinned Phase 1/2 modules.

**Version verification:** No new PyPI dependencies introduced by this phase — no `npm view` equivalent needed.

## Architecture Patterns

### Recommended Project Structure
```
src/mlb_park/
├── services/
│   └── mlb_api.py          # Phase 1 — unchanged
├── geometry/
│   └── verdict.py          # Phase 2 — provides HitData
├── pipeline/                # NEW in Phase 3
│   ├── __init__.py          # re-exports extract_hrs, HREvent, PipelineResult, PipelineError
│   ├── events.py            # frozen dataclasses (D-18)
│   └── extract.py           # extract_hrs + private helpers
└── config.py                # add CURRENT_SEASON = 2026
```

### Pattern 1: Stub-injection for testability (D-17)
**What:** Pipeline top-level functions accept `api` kwarg defaulting to real module.
**When to use:** Any pipeline function that would otherwise import `mlb_park.services.mlb_api` at module top-level.
**Example:**
```python
# pipeline/extract.py
from mlb_park.services import mlb_api as _default_api

def extract_hrs(player_id: int, season: int | None = None, *, api=_default_api) -> PipelineResult:
    if season is None:
        from mlb_park.config import CURRENT_SEASON
        season = CURRENT_SEASON
    try:
        game_log = api.get_game_log(player_id, season)
    except api.MLBAPIError as exc:
        raise  # D-14
    ...
```

Test injects a namespace-like stub:
```python
# tests/test_pipeline.py
class FakeAPI:
    MLBAPIError = RuntimeError  # any raisable
    def get_game_log(self, pid, season): return [...]
    def get_game_feed(self, gamepk): return {...}
fake = FakeAPI()
result = extract_hrs(592450, 2026, api=fake)
```

### Pattern 2: Two-phase walk (filter-before-fetch)
**What:** Split `extract_hrs` into (a) filter gameLog to HR games (DATA-01), (b) fetch + walk each HR game's feed (DATA-02).
**Why:** Satisfies the CLAUDE.md "no hammering the API" posture — we fetch ≤ N feeds where N = number of HR games (≤ ~60 across a full season, typically single digits early-season).
**Example:**
```python
def extract_hrs(player_id, season=None, *, api=_default_api):
    game_log = api.get_game_log(player_id, season)
    hr_rows = [r for r in game_log if int(r["stat"]["homeRuns"]) >= 1]
    events, errors = [], []
    for row in hr_rows:
        game_pk = int(row["game"]["gamePk"])
        try:
            feed = api.get_game_feed(game_pk)
        except api.MLBAPIError as exc:
            errors.append(PipelineError(game_pk, "game_feed", str(exc)))
            continue
        matched = _walk_feed_for_hrs(feed, player_id, row)
        if len(matched) != int(row["stat"]["homeRuns"]):
            logger.warning("gameLog/feed HR count mismatch for gamePk=%d: expected %d, matched %d",
                           game_pk, int(row["stat"]["homeRuns"]), len(matched))
        events.extend(matched)
    events.sort(key=lambda e: (e.game_date, e.play_idx))
    return PipelineResult(tuple(events), tuple(errors), season, player_id)
```

### Anti-Patterns to Avoid
- **Fetching feeds before filtering gameLog.** Violates DATA-01 success criterion and CLAUDE.md rate posture.
- **Importing `requests` or `streamlit` in `pipeline/`.** Violates D-01. Only `mlb_park.services.mlb_api` may.
- **Monkey-patching `mlb_park.services.mlb_api` in tests** instead of using the `api` kwarg. Harder to read, easier to leak state between tests.
- **Dropping HRs with missing hitData.** Violates DATA-05 / D-04. Emit the event with flags.
- **Re-raising `MLBAPIError` from a single bad feed.** One flaky game must not nuke the whole HR list (D-14).
- **Recomputing geometry in pipeline code.** D-02 — verdicts are Phase 2's job.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| HTTP + caching | Custom `requests` wrapper | `mlb_park.services.mlb_api` (D-01) | Boundary already owns session, retries, TTLs. |
| Disk-backed venue cache | New JSON reader | `api.load_all_parks()` (D-03) | Already atomic-writes, handles 30-day TTL, Phase 1-tested. |
| HR verdict computation | Fence-distance logic in pipeline | `mlb_park.geometry.verdict.compute_verdict_matrix` (D-02) | Phase 2 owns all geometry. |
| Date parsing | String slicing on `officialDate` | `datetime.date.fromisoformat(s)` | Stdlib handles `"YYYY-MM-DD"` exactly. |
| Stub injection framework | `unittest.mock.patch` on module-level imports | Plain `api=` kwarg (D-17) | Zero deps, zero magic, reads like the production call. |

**Key insight:** Phase 3 is a pure composition of Phase 1 fetchers and Phase 2 models. If you find yourself importing `requests`, re-implementing fence interpolation, or writing JSON cache logic — stop: the work is already done in another module.

## Runtime State Inventory

> Phase 3 is a greenfield pipeline module. No rename / refactor / migration involved — no runtime state to inventory. The only writeable state is the disk-backed `data/venues_cache.json` which Phase 1 already owns and Phase 3 only reads via `load_all_parks()`.

**Nothing to migrate** — verified by grep: `pipeline/` directory does not exist yet (`src/mlb_park/` currently has `services/`, `geometry/`, `config.py`, `__init__.py` only).

## Common Pitfalls

### Pitfall 1: `None` vs missing key in `hitData` null checks
**What goes wrong:** Code uses `hitData["totalDistance"]` and KeyErrors on pre-Statcast games where the key is absent (not `None`).
**Why it happens:** StatsAPI omits unset keys rather than setting them to null in some historical feeds.
**How to avoid:** Always `hitData.get("totalDistance")` and treat both `None` and missing-key as "no distance". Same for `coordinates.get("coordX")`.
**Warning signs:** A test with `hitData = {}` raises KeyError.

### Pitfall 2: Using `atBatIndex` instead of enumerate index for `play_idx`
**What goes wrong:** Two plays share the same `atBatIndex` (rare but possible with pitching-change reset bugs in historical feeds), or a play is missing `about.atBatIndex`.
**Why it happens:** `atBatIndex` is a semantic index, not array position.
**How to avoid:** Use `for i, play in enumerate(allPlays)` for `play_idx`. Observed fixture invariant (atBatIndex == array index) is a happy coincidence, not a guarantee.
**Warning signs:** Two `HREvent`s with the same `(game_pk, play_idx)` identifier.

### Pitfall 3: Opponent-abbr misassigned on Judge's home games
**What goes wrong:** Naively reading `gameData.teams.away.abbreviation` gives the away team — which is Judge's team in ~half of games.
**Why it happens:** StatsAPI labels `home`/`away` by stadium, not by "our player's team".
**How to avoid:** Always resolve "opponent" relative to the batter's team id. Use `gameLog row.team.id` (147 = NYY in fixtures) as the anchor.
**Warning signs:** All 6 Judge fixtures are correct only when you compare IDs, not when you blindly pick `away`.

### Pitfall 4: `int(stat.homeRuns)` — StatsAPI returns numbers as strings sometimes
**What goes wrong:** `row["stat"]["homeRuns"] >= 1` is TRUE for `"0"` because `"0" >= 1` raises TypeError in Python 3.
**Why it happens:** StatsAPI sometimes serializes numeric stats as strings. (In current fixtures they're ints, but be defensive.)
**How to avoid:** `int(row["stat"].get("homeRuns", 0)) >= 1`. Same for `gamePk`.
**Warning signs:** A TypeError comparing str with int when running against a slightly different season.

### Pitfall 5: Sorting by date-as-string vs `datetime.date`
**What goes wrong:** "2026-03-28" < "2026-04-03" sorts correctly as strings — but "2026-4-3" would not. If an edge feed returns a non-padded date, lexicographic order breaks.
**Why it happens:** fromisoformat expects zero-padded month/day.
**How to avoid:** Convert to `datetime.date` before sorting; D-13 already specifies `game_date: datetime.date`.
**Warning signs:** A July HR sorts before an April HR in the output.

### Pitfall 6: `MLBAPIError` subclass coverage in the stub API
**What goes wrong:** Test stub's `get_game_feed` raises `RuntimeError`, but production catches `api.MLBAPIError`. The raise escapes the catch.
**Why it happens:** The `api` kwarg IS the source of `MLBAPIError` (D-17). The stub must define its own `MLBAPIError` attribute that the pipeline catches.
**How to avoid:** Stub module MUST expose `MLBAPIError` as an attribute the pipeline references (`api.MLBAPIError`), e.g. `FakeAPI.MLBAPIError = RuntimeError`. Then `except api.MLBAPIError:` catches it.
**Warning signs:** Test for "bad feed raises, others continue" fails with an un-caught exception.

### Pitfall 7: `has_launch_stats=True` with only one of speed/angle present
**What goes wrong:** An HR has `launchSpeed=108.9` but `launchAngle is None`; a naive `has_launch_stats = launch_speed is not None` lets the tooltip render a partial "EV: 108.9 / LA: None".
**Why it happens:** D-12 is explicit about conjunction, but an off-by-one in flag logic is easy.
**How to avoid:** `has_launch_stats = launch_speed is not None AND launch_angle is not None` — strict AND.
**Warning signs:** VIZ-03 tooltip shows "LA: None mph".

## Code Examples

### Extracting opponent abbreviation (verified against all 5 feeds)
```python
# Source: empirical verification against tests/fixtures/feed_*.json (2026-04-15)
def opponent_abbr(feed: dict, batter_team_id: int) -> str:
    home = feed["gameData"]["teams"]["home"]
    away = feed["gameData"]["teams"]["away"]
    opp = away if home["id"] == batter_team_id else home
    return opp.get("abbreviation") or opp.get("teamName") or opp.get("name", "???")

# Verified:
# batter_team_id=147 (NYY) on all 5 fixtures →
#   feed_822998: TB (home=TB, so opp=home=TB) ✓ matches gameLog opponent "Tampa Bay Rays"
#   feed_823241: SF ✓
#   feed_823243: SF ✓
#   feed_823563: LAA (NYY home, so opp=away=LAA) ✓
#   feed_823568: MIA (NYY home, so opp=away=MIA) ✓
```

### Full feed walk for one game (happy path)
```python
# Source: synthesis from fixture inspection + CONTEXT.md D-08/D-10/D-11/D-12
def _walk_feed_for_hrs(feed: dict, player_id: int, gamelog_row: dict) -> list[HREvent]:
    import datetime
    all_plays = feed.get("liveData", {}).get("plays", {}).get("allPlays", []) or []
    game_pk = int(feed["gamePk"])
    game_date = datetime.date.fromisoformat(feed["gameData"]["datetime"]["officialDate"])
    batter_team_id = int(gamelog_row["team"]["id"])
    opp_abbr = opponent_abbr(feed, batter_team_id)

    out: list[HREvent] = []
    for i, play in enumerate(all_plays):
        matchup = play.get("matchup", {})
        result = play.get("result", {})
        if matchup.get("batter", {}).get("id") != player_id:
            continue
        if result.get("eventType") != "home_run":
            continue
        about = play.get("about", {})
        desc = result.get("description", "") or ""
        is_itp = "inside-the-park" in desc.lower()

        hd = _extract_hit_data(play) or {}
        coords = hd.get("coordinates", {}) or {}
        total_d = hd.get("totalDistance")
        launch_s = hd.get("launchSpeed")
        launch_a = hd.get("launchAngle")
        cx = coords.get("coordX")
        cy = coords.get("coordY")

        has_d = total_d is not None
        has_c = (cx is not None) and (cy is not None)
        has_ls = (launch_s is not None) and (launch_a is not None)

        out.append(HREvent(
            game_pk=game_pk, game_date=game_date, opponent_abbr=opp_abbr,
            inning=int(about.get("inning", 0)),
            half_inning=str(about.get("halfInning", "")),
            play_idx=i,
            distance_ft=float(total_d) if has_d else None,
            coord_x=float(cx) if has_c else None,
            coord_y=float(cy) if has_c else None,
            launch_speed=float(launch_s) if launch_s is not None else None,
            launch_angle=float(launch_a) if launch_a is not None else None,
            has_distance=has_d, has_coords=has_c, has_launch_stats=has_ls,
            is_itp=is_itp,
        ))
    return out
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| N/A (greenfield) | N/A | — | — |

**Deprecated/outdated:** none — this is a new module.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `atBatIndex == allPlays` array index is a happy coincidence, not a guarantee | Pitfall 2 | LOW — using enumerate index (recommended) sidesteps the issue entirely |
| A2 | StatsAPI may sometimes serialize `homeRuns` / `gamePk` as strings (pitfall 4 is defensive) | Pitfall 4 | LOW — defensive coercion costs nothing |
| A3 | The D-10 fallback ("last playEvent with hitData if terminal lacks it") covers a real case even though not seen in fixtures | D-10 section, Empirical verification | MEDIUM — if the fallback is never-real, dead code; if real but subtly different (e.g., reviewed-play hitData lives on a non-terminal event), the synthetic fixture catches it |
| A4 | `p["matchup"]["batter"]["parentTeamId"]` is not reliably present on all plays, so we use gameLog row `team.id` | Field-by-field extraction map | LOW — gameLog row `team.id` is observed on all 5 HR rows |

## Open Questions

1. **Should `CURRENT_SEASON` come from `config.py` or from the most-recent gameLog date at runtime?**
   - What we know: CONTEXT.md D-16 says `config.CURRENT_SEASON`. Phase 1 `config.py` does NOT currently export this constant — it has `YANKEES_TEAM_ID`, `JUDGE_PERSON_ID` only.
   - What's unclear: Is the planner expected to add `CURRENT_SEASON = 2026` to `config.py` as part of this phase, or pull it from `datetime.date.today().year`?
   - Recommendation: Add `CURRENT_SEASON = 2026` as a module-level constant in `config.py`. Deterministic, matches fixtures, trivially overridable for tests via the existing `season` kwarg.

2. **Does D-06's adapter belong on `HREvent` or as a module-level helper?**
   - What we know: CONTEXT.md explicitly leaves this to planner discretion.
   - Recommendation: Module-level `hr_event_to_hit_data(ev) -> HitData | None` in `pipeline/extract.py`. Keeps `HREvent` a pure data dataclass with no cross-package method coupling; mirrors the Phase 2 pattern where `HitData` has no methods either.

3. **Should the chronological sort tiebreak beyond `(game_date, play_idx)`?**
   - What we know: Two HRs on the same date in the same game will differ in `play_idx`. Two HRs on the same date but different games (doubleheader) — `play_idx` ties are possible but `game_pk` differs.
   - Recommendation: `key=lambda e: (e.game_date, e.game_pk, e.play_idx)` to be deterministic across doubleheaders. Low practical risk.

## Environment Availability

> Phase 3 is pure Python-stdlib + already-pinned in-repo deps. No new external dependencies. Skipped per the research template's skip condition.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (already in use per Phase 1/2 tests in `tests/`) |
| Config file | `pyproject.toml` / `pytest.ini` (inferred from existing Phase 2 test runs — confirm in Wave 0) |
| Quick run command | `pytest tests/test_pipeline.py -x -q` |
| Full suite command | `pytest tests/ -q` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| DATA-01 | `extract_hrs` filters gameLog to `homeRuns >= 1` games BEFORE fetching any feed (0-HR games never call `get_game_feed`) | unit (with stub api, spy on `get_game_feed` calls) | `pytest tests/test_pipeline.py::test_gamelog_filter_before_feed_fetch -x` | ❌ Wave 0 |
| DATA-01 | One `HREvent` produced per HR in the gameLog (6 HRs from fixture set) | unit | `pytest tests/test_pipeline.py::test_judge_6_hrs_end_to_end -x` | ❌ Wave 0 |
| DATA-02 | For each HR game, feed is walked and `matchup.batter.id == player_id AND eventType == "home_run"` plays are kept | unit | `pytest tests/test_pipeline.py::test_batter_filter_excludes_other_batters -x` | ❌ Wave 0 |
| DATA-02 | `hitData` extracted for each HR: `totalDistance`, `coordX`, `coordY`, `launchSpeed`, `launchAngle` match fixture values exactly | unit | `pytest tests/test_pipeline.py::test_hitdata_values_match_fixtures -x` | ❌ Wave 0 |
| DATA-03 | `load_all_parks()` available via the pipeline's api module; disk cache reuse verified by calling twice (2nd call doesn't re-fetch) | unit (stub api with a fetch counter) | `pytest tests/test_pipeline.py::test_venue_cache_reuse -x` | ❌ Wave 0 — OR defer to Phase 1's existing tests (DATA-03 is already 100% satisfied in Phase 1; Phase 3 only needs a smoke test that it can call through) |
| DATA-05 | HR with missing `hitData` (all flags False) emitted as event, not dropped | unit (synthetic fixture) | `pytest tests/test_pipeline.py::test_missing_hitdata_retained_with_flags -x` | ❌ Wave 0 |
| DATA-05 | HR with `has_coords=True, has_distance=False, has_launch_stats=False` (partial degradation) | unit (synthetic) | `pytest tests/test_pipeline.py::test_partial_hitdata_independent_flags -x` | ❌ Wave 0 |
| DATA-05 | ITP HR (`"inside-the-park"` in description) → `is_itp=True` | unit (synthetic) | `pytest tests/test_pipeline.py::test_itp_detection -x` | ❌ Wave 0 |
| D-08 filter | Non-Judge HR play in `allPlays` is NOT included | unit (synthetic) | `pytest tests/test_pipeline.py::test_other_batters_hr_excluded -x` | ❌ Wave 0 |
| D-09 mismatch warn | gameLog says 2, feed has 1 → warning logged, 1 event returned, no raise | unit (synthetic, `caplog`) | `pytest tests/test_pipeline.py::test_count_mismatch_warns -x` | ❌ Wave 0 |
| D-10 fallback | `playEvents[-1]` lacks hitData but earlier event has it → event emitted with extracted values | unit (synthetic) | `pytest tests/test_pipeline.py::test_hitdata_fallback_to_earlier_event -x` | ❌ Wave 0 |
| D-14 per-game error | One `get_game_feed` raises `MLBAPIError` → `PipelineError` recorded, other games' HRs still emitted | unit (stub api) | `pytest tests/test_pipeline.py::test_single_feed_failure_captured_as_error -x` | ❌ Wave 0 |
| D-14 total failure | `get_game_log` raises → `extract_hrs` raises (not swallowed) | unit (stub api) | `pytest tests/test_pipeline.py::test_gamelog_failure_propagates -x` | ❌ Wave 0 |
| D-16 season default | `season=None` resolves to `config.CURRENT_SEASON` | unit | `pytest tests/test_pipeline.py::test_default_season_from_config -x` | ❌ Wave 0 |
| Integration | Pipeline output → Phase 2 `compute_verdict_matrix` via adapter → produces 6×30 matrix with known shape | integration | `pytest tests/test_pipeline_geometry_integration.py -x` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `pytest tests/test_pipeline.py -x -q` (fast — all stubs, no I/O)
- **Per wave merge:** `pytest tests/ -q` (runs Phase 1, Phase 2, and Phase 3 suites)
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] `tests/test_pipeline.py` — primary unit suite, stubs `api` via kwarg
- [ ] `tests/test_pipeline_geometry_integration.py` — end-to-end `extract_hrs` (stubbed) → `compute_verdict_matrix` → 6×30 golden
- [ ] `tests/fixtures/synthetic/feed_itp.json` — fabricate: copy any real feed, rewrite ONE HR play's `result.description` to include "inside-the-park"
- [ ] `tests/fixtures/synthetic/feed_no_hitdata.json` — fabricate: copy any real feed, delete `hitData` from the HR play's `playEvents`
- [ ] `tests/fixtures/synthetic/feed_hitdata_not_in_last.json` — fabricate: copy any real feed, move HR play's `hitData` to an earlier playEvent and blank the last one
- [ ] `tests/fixtures/synthetic/feed_partial_hitdata.json` — fabricate: copy any real feed, set `launchSpeed`/`launchAngle` to `None`, keep coords + distance
- [ ] `tests/fixtures/synthetic/feed_wrong_batter_hr.json` — fabricate: copy any real feed, change HR play's `matchup.batter.id` to a different person
- [ ] `tests/fixtures/synthetic/gamelog_count_mismatch.json` — fabricate: clone one HR row and set `homeRuns=2` so feed-matched count of 1 triggers warning
- [ ] `tests/conftest.py` — shared fixtures: `FakeAPI` class with `get_game_log` / `get_game_feed` / `load_all_parks` / `MLBAPIError` attributes, parameterized to return specific fixture files per game_pk

## Sources

### Primary (HIGH confidence)
- `tests/fixtures/gamelog_592450_2026.json` — empirical ground truth for gameLog shape, HR-row count (5 rows, 6 HRs)
- `tests/fixtures/feed_{822998,823241,823243,823563,823568}.json` — empirical ground truth for feed shape, hitData location, eventType enumeration, team abbreviation paths, inning/halfInning/atBatIndex presence
- `.planning/phases/03-hr-pipeline/03-CONTEXT.md` — locked decisions D-01..D-19 (authoritative)
- `.planning/phases/02-models-geometry/02-CONTEXT.md` D-17 — HitData contract (upstream Phase 2)
- `src/mlb_park/services/mlb_api.py` — consumed API surface (Phase 1)
- `src/mlb_park/geometry/verdict.py` — HitData dataclass + identifier semantics
- `src/mlb_park/config.py` — constants and `CURRENT_SEASON` gap identified

### Secondary (MEDIUM confidence)
- None — every claim in this document traces to one of the fixture files or the in-repo module sources.

### Tertiary (LOW confidence)
- None. (No WebSearch needed — this phase's ground truth is local fixtures.)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — stdlib + two in-repo modules with explicit contracts
- Architecture / data contracts: HIGH — every field path empirically verified in 5 feeds + 1 gameLog
- Pitfalls: HIGH (1-4, 6-7) / MEDIUM (5) — most are direct corollaries of fixture observations; pitfall 5 (date padding) is defensive against unseen future data
- D-10 fallback necessity: MEDIUM — 0/15 HR plays in fixtures have hitData outside `playEvents[-1]`, so the fallback is defensive and must be validated with a synthetic fixture

**Research date:** 2026-04-15
**Valid until:** 2026-05-15 (30 days — stable; MLB StatsAPI schema changes rarely mid-season)

## RESEARCH COMPLETE
