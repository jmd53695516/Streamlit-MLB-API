---
phase: 03
plan: 02
subsystem: pipeline
tags: [extraction, dataclasses, fixtures, tdd, dependency-injection]
requires:
  - src/mlb_park/pipeline/events.py (Plan 03-01: HREvent, PipelineResult, PipelineError)
  - src/mlb_park/services/mlb_api.py (real MLBAPIError + get_game_log + get_game_feed names)
  - src/mlb_park/config.py (CURRENT_SEASON = 2026)
  - tests/pipeline/conftest.py (StubAPI + 5 fixture loaders from Plan 03-01)
  - tests/pipeline/fixtures/feed_*.json + gamelog_count_mismatch.json (7 synthetic from Plan 03-01)
  - tests/fixtures/feed_82*.json + gamelog_592450_2026.json (Phase 1 real Judge fixtures)
provides:
  - mlb_park.pipeline.extract.extract_hrs(player_id, season=None, *, api=...) -> PipelineResult
  - mlb_park.pipeline.extract._walk_feed_for_hrs / _extract_hit_data / _detect_itp / _opponent_abbr (private helpers)
affects:
  - Plan 03-03 (consumes extract_hrs in the integration test surface)
  - Phase 04 controller (sole entry point for player_id -> HREvent list)
tech-stack:
  added: []
  patterns:
    - Module-as-dependency injection (`api: Any = _default_api` kw-only) per D-17
    - Lazy import of CURRENT_SEASON inside function body (D-16) — avoids Plan-01 circular imports if config grows
    - Reverse-scan fallback for hitData lookup (D-10) — terminal playEvent first, last non-null on miss
    - Frozen-dataclass output via tuple(events) / tuple(errors) — PipelineResult immutability
key-files:
  created:
    - src/mlb_park/pipeline/extract.py (197 lines)
    - tests/pipeline/test_extract_hrs.py (251 lines, 6 tests)
    - tests/pipeline/test_degradation.py (110 lines, 4 tests)
    - tests/pipeline/test_error_handling.py (132 lines, 3 tests)
  modified: []
decisions:
  - "extract.py is a single file (D-18 'split if line count warrants'); 197 lines is well under the threshold — kept colocated for readability"
  - "Inline minimal feed builders for opponent-abbr / chronological-order / per-feed-error tests instead of committing new fixtures — keeps fixture inventory tight (only the 7 D-19 cases are on disk)"
  - "_GameLogRaisingStub / _CountingStub / _ArgsRecordingStub all subclass StubAPI rather than monkey-patching — preserves D-17 'no monkey-patching needed' guarantee"
  - "Used `caplog.at_level(logging.WARNING, logger='mlb_park.pipeline.extract')` (specific logger) instead of root capture — avoids cross-test pollution if other modules log at WARNING"
metrics:
  duration_sec: 2400
  tasks_complete: 3
  files_created: 4
  files_modified: 0
  tests_passing: 13
  tests_passing_full_suite: 58
  completed: "2026-04-15"
---

# Phase 03 Plan 02: extract_hrs Implementation Summary

End-to-end `(player_id, season) -> PipelineResult[HREvent]` extraction landed: gameLog-pre-filter (DATA-01), batter+eventType feed walk (DATA-02), null-safe hitData with independent degradation flags (DATA-05), ITP detection, opponent-abbr resolution, count-mismatch warning, and per-feed `MLBAPIError` recovery — all driven by 13 fixture-injected tests with zero network.

## What shipped

### `src/mlb_park/pipeline/extract.py` (197 lines)

```python
def extract_hrs(
    player_id: int,
    season: int | None = None,
    *,
    api: Any = _default_api,
) -> PipelineResult: ...
```

Plus four private helpers (D-18 single-file layout):

| Helper | Purpose | Decision |
|---|---|---|
| `_walk_feed_for_hrs(feed, player_id, batter_team_id)` | Iterate `allPlays`, filter by `(eventType, batter.id)`, build HREvent per play | D-08 single filter, Pitfall 2: enumerate index |
| `_extract_hit_data(play)` | Prefer terminal `playEvents[-1].hitData`, reverse-scan if null, return `None` if absent | D-10 |
| `_detect_itp(description)` | Case-insensitive `"inside-the-park"` substring check | D-11 |
| `_opponent_abbr(feed, batter_team_id)` | Pick non-batter team from feed, fall back `abbreviation -> teamName -> clubName -> name -> "???"` | Pitfall 3 + RESEARCH §field map |

### Decision-to-code traceability (D-07..D-17 verbatim)

| Decision | Code location |
|---|---|
| D-07 (DATA-01 filter before fetch) | `extract_hrs`: `hr_rows = [r for r in game_log if int(r.get("stat", {}).get("homeRuns", 0)) >= 1]` BEFORE the for-loop that calls `api.get_game_feed` |
| D-08 (DATA-02 batter+eventType filter) | `_walk_feed_for_hrs`: `if result.get("eventType") != "home_run": continue` then `if batter.get("id") != player_id: continue` |
| D-09 (count mismatch warning) | `extract_hrs`: `logger.warning("gameLog/feed HR count mismatch for gamePk=%d: expected %d, matched %d", ...)` — kept matched plays |
| D-10 (hitData fallback) | `_extract_hit_data`: terminal-first then `for e in reversed(events)` |
| D-11 (ITP substring) | `_detect_itp`: `return "inside-the-park" in description.lower()` |
| D-12 (independent flags) | `_walk_feed_for_hrs`: three `bool` computations using strict AND for `has_coords` and `has_launch_stats` |
| D-13 (PipelineResult ordering) | `extract_hrs`: `events.sort(key=lambda e: (e.game_date, e.play_idx))` |
| D-14 (error handling split) | `try/except api.MLBAPIError` only around `get_game_feed`; `get_game_log` call left bare so its failures propagate |
| D-15 (no internal retry) | No retry loop in `extract.py` — per-feed exception goes straight to PipelineError |
| D-16 (season default) | `if season is None: from mlb_park.config import CURRENT_SEASON; season = CURRENT_SEASON` |
| D-17 (api kw-only injection) | `*, api: Any = _default_api` and the catch uses `api.MLBAPIError` (Pitfall 6 — caught error is the stub's class attribute when api is a StubAPI) |

### Test inventory (13 tests, all green)

**`tests/pipeline/test_extract_hrs.py` (6 tests, DATA-01/DATA-02 + ordering)**

| Test | One-line assertion |
|---|---|
| `test_filter_before_fetch` | Stub records 2 `get_game_feed` calls (only HR>=1 rows), 0-HR gamePk never fetched (D-07) |
| `test_batter_filter` | `feed_non_batter_hr.json` (HR by 999999) + gameLog HR=1 -> `events == ()` AND D-09 warning logged |
| `test_season_defaults_to_current` | `extract_hrs(42, api=stub)` calls `get_game_log(42, CURRENT_SEASON)` and result.season == 2026 |
| `test_chronological_order` | Two feeds (Mar 27, Apr 03) in reverse gameLog order produce events sorted ascending |
| `test_opponent_abbr_home_and_away` | Judge-home feed -> `opponent_abbr=="LAA"`; Judge-away feed -> `opponent_abbr=="SF"` |
| `test_happy_path_judge_fixtures` | 5 real Judge feeds + judge_gamelog -> exactly 6 events, all flags True, is_itp False, gamePks match {823243, 823241, 823568, 822998, 823563x2} |

**`tests/pipeline/test_degradation.py` (4 tests, DATA-05)**

| Test | One-line assertion |
|---|---|
| `test_missing_hitdata_all_flags_false` | `feed_missing_hitdata.json` -> 1 event, all 4 flags False, all 5 measurements None |
| `test_itp_flag` | `feed_itp.json` -> `is_itp is True` AND has_distance/has_coords/has_launch_stats all True |
| `test_partial_hitdata_independent_flags` | `feed_partial_hitdata.json` -> distance=410.0, coords None, launch=108.4/27.0, has_coords=False, others True |
| `test_terminal_lacks_hitdata_fallback` | `feed_terminal_lacks_hitdata.json` -> all flags True, distance=415.5 (fallback found earlier event) |

**`tests/pipeline/test_error_handling.py` (3 tests, D-09/D-13/D-14)**

| Test | One-line assertion |
|---|---|
| `test_per_feed_mlbapierror_collected` | Stub raises for 900006, succeeds for 900008 -> 1 event (900008), 1 error with `endpoint=="game_feed"` and `"503" in message` |
| `test_gamelog_mlbapierror_propagates` | `_GameLogRaisingStub` -> `pytest.raises(stub.MLBAPIError)` (no catch in extract_hrs) |
| `test_count_mismatch_warning_not_error` | `gamelog_count_mismatch.json` (HR=2) + `feed_count_mismatch.json` (1 match) -> 1 event emitted, exact warning string `"gameLog/feed HR count mismatch for gamePk=900006: expected 2, matched 1"` in caplog |

### Verification snapshot

```text
$ pytest tests/pipeline/ -q
...................                                                      [100%]
19 passed in 1.25s

$ pytest -q
..........................................................               [100%]
58 passed in 1.76s

$ grep -rn "import requests\|import streamlit" src/mlb_park/pipeline/
(no matches)
```

19 = 6 events tests (Plan 01) + 6 extract tests + 4 degradation + 3 error_handling.
58 full-suite = 39 Phase 2 + 6 Plan 01 events + 13 Plan 02.

## Tasks executed

| Task | Name | Commit | Files |
|---|---|---|---|
| 1 | Implement `extract_hrs` + 4 helpers | `be01d90` | src/mlb_park/pipeline/extract.py |
| 2 | DATA-01/DATA-02 + ordering tests (6 tests) | `ac7e8c4` | tests/pipeline/test_extract_hrs.py |
| 3 | DATA-05 degradation + D-14 error tests (7 tests) | `e738488` | tests/pipeline/test_degradation.py, tests/pipeline/test_error_handling.py |

## Deviations from Plan

**None — plan executed exactly as written.** The Task 1 skeleton in `<action>` was used verbatim. No deviations from the RESEARCH.md two-phase-walk pattern. Inline-feed-builder choice for opponent-abbr / chronological / per-feed-error tests was explicitly permitted by the plan ("synthesize two minimal feeds inline").

One environmental note (not a plan deviation): the worktree was missing its editable install at start, so `from mlb_park.pipeline.extract import ...` initially failed. Resolved by `pip install -e . --no-deps -q` in the worktree. Documented previously in Plan 03-01 SUMMARY.

## Threat Flags

None. Plan stayed within the modelled register (T-3-02 mitigated by D-07 pre-filter; T-3-03 mitigated by `.get(...) or {}` chain + `isinstance(..., dict)` checks; T-3-06 accepted; T-3-07 accepted — logged values are gamePk + integer counts, no PII). No new network endpoints, no trust-boundary expansion.

## Known Stubs

None. `extract_hrs` is the production extraction function — not a placeholder. The `_default_api` injection point IS a deliberate test seam, not a stub — production callers omit `api=` and get the real `mlb_park.services.mlb_api`.

## What Plan 03-03 can assume

- `from mlb_park.pipeline.extract import extract_hrs` returns a callable with signature `(player_id, season=None, *, api=_default_api) -> PipelineResult`.
- Passing a `StubAPI` instance via `api=` works; production calls omit the kwarg.
- Per-feed `MLBAPIError` is automatically converted to `PipelineError(game_pk, "game_feed", str(exc))` and other games still process — Plan 03-03 can rely on partial results.
- Events are returned chronological (game_date asc, play_idx asc); no need to re-sort.
- Count mismatches log at `mlb_park.pipeline.extract` logger, never raise.

## Self-Check: PASSED

- [x] `src/mlb_park/pipeline/extract.py` — exists, 197 lines, contains `extract_hrs` + 4 `_`-prefixed helpers
- [x] `tests/pipeline/test_extract_hrs.py` — exists, 6 tests, all green
- [x] `tests/pipeline/test_degradation.py` — exists, 4 tests, all green
- [x] `tests/pipeline/test_error_handling.py` — exists, 3 tests, all green
- [x] `pytest tests/pipeline/ -q` -> 19 passed, 0 failed
- [x] `pytest -q` (full suite) -> 58 passed, 0 failed (Phase 2 regression-free)
- [x] Zero `import requests` / `import streamlit` matches under `src/mlb_park/pipeline/`
- [x] Commits `be01d90`, `ac7e8c4`, `e738488` all present in git log
