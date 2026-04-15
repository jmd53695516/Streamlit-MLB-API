---
phase: 03-hr-pipeline
verified: 2026-04-15T00:00:00Z
status: passed
score: 4/4 must-haves verified
overrides_applied: 0
requirements_verified: [DATA-01, DATA-02, DATA-03, DATA-05]
tests_passing:
  pipeline: 26
  full_suite: 65
---

# Phase 3: HR Pipeline Verification Report

**Phase Goal:** Given a `player_id`, produce a list of `HREvent` objects with per-HR degradation flags, validated end-to-end against fixtures before any UI exists.
**Verified:** 2026-04-15
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths (ROADMAP Success Criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | `extract_hrs(player_id, season)` filters gameLog to `homeRuns >= 1` BEFORE fetching any game feed, returns one HREvent per HR attributed to batter | VERIFIED | `src/mlb_park/pipeline/extract.py:52` — `hr_rows = [r for r in game_log if int(r.get("stat", {}).get("homeRuns", 0)) >= 1]` executes BEFORE the for-loop that calls `api.get_game_feed(game_pk)` at line 62. Tested by `tests/pipeline/test_extract_hrs.py::test_filter_before_fetch` which asserts stub records feed calls only for HR>=1 rows. Per-play attribution by `batter.id == player_id` AND `eventType == "home_run"` verified at `extract.py:116-121` (`_walk_feed_for_hrs`). Judge happy-path test produces 6 events across 5 feeds. |
| 2 | HRs with missing/partial `hitData` (ITP, pre-Statcast, review-reversed) retained with explicit flags (`has_distance`, `has_coords`, `is_itp`), not dropped | VERIFIED | `events.py:29-49` — HREvent has all 4 flag fields: `has_distance`, `has_coords`, `has_launch_stats`, `is_itp`. `extract.py:133-136` computes flags independently (no early returns when data absent). `test_degradation.py` covers all 4 degradation paths: `test_missing_hitdata_all_flags_false`, `test_itp_flag`, `test_partial_hitdata_independent_flags` (distance present but coords None → has_distance=True, has_coords=False), `test_terminal_lacks_hitdata_fallback` (D-10). |
| 3 | Disk-backed venue cache (`data/venues_cache.json`, 30-day TTL) populated on first run and reused on cold starts | VERIFIED | `data/venues_cache.json` exists on disk (30 venues, age 0.9 days). `src/mlb_park/services/mlb_api.py:174-196` — `load_all_parks()` checks `VENUES_FILE.exists()`, compares `age_days < 30` (line 186-189), reads from disk if fresh, rebuilds atomically otherwise. Re-exported as `mlb_park.pipeline.load_all_parks` (identity check — same object as services module). This was delivered in Phase 1 but is consumed/composed by Phase 3 per DATA-03. |
| 4 | Pipeline is testable with a stub `api` module — fixture-driven tests pass without network access | VERIFIED | `extract_hrs(..., *, api=_default_api)` — D-17 injection seam at `extract.py:22`. `tests/pipeline/conftest.py` exposes `StubAPI` with 4 attrs matching real module (`MLBAPIError`, `get_game_log`, `get_game_feed`, `load_all_parks`) + `make_stub_api` factory + `judge_feeds`/`judge_gamelog` loaders. `grep -rn "import requests" src/mlb_park/pipeline/ tests/pipeline/` returns zero matches. All 26 pipeline tests run in 1.24s with no network access. |

**Score:** 4/4 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `src/mlb_park/pipeline/__init__.py` | Public API re-exports | VERIFIED | 33 lines; re-exports `extract_hrs`, `hr_event_to_hit_data`, `HREvent`, `PipelineResult`, `PipelineError`, `load_all_parks`, `HitData`, `compute_verdict_matrix`, `MLBAPIError`, `CURRENT_SEASON` in `__all__`. |
| `src/mlb_park/pipeline/events.py` | 3 frozen dataclasses (D-05/D-13) | VERIFIED | 74 lines; HREvent (15 fields including `is_itp`, `has_distance`, `has_coords`, `has_launch_stats`), PipelineError, PipelineResult (tuple fields, not list). All `@dataclass(frozen=True)`. |
| `src/mlb_park/pipeline/extract.py` | extract_hrs + helpers + adapter | VERIFIED | 224 lines. Contains `extract_hrs` (line 18), `_walk_feed_for_hrs` (97), `_extract_hit_data` (158), `_detect_itp` (176), `_opponent_abbr` (181), `hr_event_to_hit_data` (210). |
| `src/mlb_park/config.py::CURRENT_SEASON` | = 2026 (D-16) | VERIFIED | Verified importable via `from mlb_park.config import CURRENT_SEASON`; pipeline re-export points to the same object. |
| `data/venues_cache.json` | Disk cache populated | VERIFIED | Exists, 30 venue entries, mtime ~0.9 days ago. |
| `tests/pipeline/fixtures/*.json` (7 synthetic) | D-19 degradation coverage | VERIFIED | All 7 present: `feed_missing_hitdata`, `feed_itp`, `feed_partial_hitdata`, `feed_non_batter_hr`, `feed_terminal_lacks_hitdata`, `feed_count_mismatch`, `gamelog_count_mismatch`. |
| `tests/pipeline/conftest.py` | StubAPI + fixtures | VERIFIED | 148 lines; contains `class StubAPI`, `MLBAPIError = type(...)`, `get_game_log`, `get_game_feed`, `load_all_parks`, `make_stub_api`, `synthetic_feed`, `synthetic_gamelog`, `judge_feeds`, `judge_gamelog`. Zero imports of `mlb_park.services.mlb_api`. |
| Test files | `test_events`, `test_extract_hrs`, `test_degradation`, `test_error_handling`, `test_adapter`, `test_integration` | VERIFIED | All 6 present under `tests/pipeline/`; 26 tests total passing. |

### Key Link Verification

| From | To | Via | Status | Details |
|------|-----|-----|--------|---------|
| `pipeline/__init__.py` | `pipeline/events.py` | `from mlb_park.pipeline.events import HREvent, PipelineError, PipelineResult` | WIRED | Line 16 of __init__.py. |
| `pipeline/__init__.py` | `pipeline/extract.py` | `from mlb_park.pipeline.extract import extract_hrs, hr_event_to_hit_data` | WIRED | Line 17 of __init__.py. |
| `pipeline/__init__.py` | `services.mlb_api` | `from mlb_park.services.mlb_api import MLBAPIError, load_all_parks` | WIRED | Line 18; Phase 3-03 SUMMARY confirms `load_all_parks is services.mlb_api.load_all_parks` (identity re-export, not wrapped). |
| `pipeline/extract.py` | `services.mlb_api` | `from mlb_park.services import mlb_api as _default_api` | WIRED | Line 12; `api=_default_api` kw-only default (D-17). |
| `pipeline/extract.py` | `geometry.verdict` | `from mlb_park.geometry.verdict import HitData` | WIRED | Line 207 (adapter-adjacent import by plan). |
| `test_integration.py` | `compute_verdict_matrix` | adapter chain | WIRED | End-to-end test composes `extract_hrs → hr_event_to_hit_data → compute_verdict_matrix` against 5 Judge feeds + 30 venues, produces (6,30) VerdictMatrix. |
| `tests/pipeline/*` | `StubAPI` | `api=` kwarg | WIRED | All tests inject stub via `make_stub_api` factory — no real HTTP. |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| `extract_hrs` | `game_log`, `feed` | `api.get_game_log`, `api.get_game_feed` (injectable; prod defaults to real HTTP wrappers) | Yes — real Judge gameLog + 5 feeds produce 6 HREvents in integration test | FLOWING |
| `hr_event_to_hit_data` | HREvent fields | HREvent from pipeline | Yes — round-trips (game_pk, play_idx) through `identifier`; integration test asserts `vm.hrs[i].identifier == hd.identifier` | FLOWING |
| `load_all_parks` | venues dict | `data/venues_cache.json` or `/venues/{id}?hydrate=fieldInfo` | Yes — cache file exists with 30 entries | FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Pipeline package imports and adapter is pure function | `python -c "from mlb_park.pipeline import extract_hrs, hr_event_to_hit_data, HREvent; ..."` | 26 pipeline tests pass; import chain exercised | PASS |
| `pytest tests/pipeline/ -q` | — | 26 passed in 1.24s, 0 failed | PASS |
| `pytest -q` (full suite) | — | 65 passed in 1.43s, 0 failed | PASS |
| Venues cache file exists | `ls data/venues_cache.json` | 30 venues, age 0.9 days | PASS |
| No `requests`/`streamlit` in pipeline module | `grep -rn "import requests\|import streamlit" src/mlb_park/pipeline/` | 0 matches (D-01 preserved) | PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| DATA-01 | 03-02 | App retrieves current-season game log and identifies HR games | SATISFIED | `extract.py:49-52`; `test_filter_before_fetch` proves pre-filter before feed fetch. |
| DATA-02 | 03-02 | For each HR game, fetch feed, extract HRs for player, collect hitData | SATISFIED | `_walk_feed_for_hrs` (extract.py:97) filters by `eventType=="home_run"` AND `batter.id==player_id`; `_extract_hit_data` collects totalDistance, launchSpeed, launchAngle, coordX/Y with D-10 fallback. Happy-path Judge test emits 6 events with full hitData. |
| DATA-03 | 03-03 | fieldInfo for all 30 stadiums cached; disk-backed cache persists | SATISFIED | Delivered by Phase 1 `services.mlb_api.load_all_parks()`; 30-day TTL disk cache at `data/venues_cache.json` (30 entries present); re-exported at `mlb_park.pipeline.load_all_parks` for DATA-03 "single import origin" composition; integration test loads 30 venues via Phase 2 `load_parks(venues)` and produces (6,30) matrix. |
| DATA-05 | 03-02 | Per-HR extraction degrades gracefully with flags | SATISFIED | `events.py` 4 bool flag fields; `extract.py:133-136` independent flag computation; `test_degradation.py` (4 tests) covers missing/partial/ITP/fallback paths. |

All 4 requirement IDs declared in PLAN frontmatter (03-01: DATA-05; 03-02: DATA-01, DATA-02, DATA-05; 03-03: DATA-03) are accounted for. Cross-reference against REQUIREMENTS.md line 73-77 confirms Phase 3 owns exactly DATA-01/-02/-03/-05; DATA-04 belongs to Phase 1.

### Anti-Patterns Found

None. Scanned all files under `src/mlb_park/pipeline/` and `tests/pipeline/`:
- No TODO/FIXME/XXX/HACK/PLACEHOLDER strings in production code.
- No `return null` / empty-dict / `pass`-only implementations.
- No hardcoded empty dataflows — `extract_hrs` returns real events from real (or fixture) inputs.
- No `console.log`-equivalent stubs (`logger.warning` is intentional D-09 behavior, not a stub).

### Human Verification Required

None. This phase delivers a pure-data pipeline validated entirely by fixture-driven tests — no UI, no real-time behavior, no visual output, no external-service live integration. The production `api=_default_api` network path is exercised indirectly by Phase 1's own tests; Phase 3 tests correctly injection-isolate extract_hrs from HTTP.

### Gaps Summary

No gaps. Every ROADMAP success criterion is observably true in the codebase:
1. Pre-filter is a list comprehension preceding the feed-fetch loop (line-level evidence).
2. All 4 degradation flags exist on HREvent and are tested independently.
3. `data/venues_cache.json` exists on disk with 30 venues and is re-exported at the pipeline boundary (DATA-03 single-import-origin).
4. 26 pipeline tests pass in 1.24s with zero network, driven by StubAPI injection.

Phase 3 is ready for Phase 4 to consume via `from mlb_park.pipeline import ...`.

---

_Verified: 2026-04-15_
_Verifier: Claude (gsd-verifier)_
