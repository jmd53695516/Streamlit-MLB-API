---
phase: 06-summary-rankings-polish
plan: 02
subsystem: controller, app
tags: [metrics, rankings, ux, error-handling, spinner, tdd]
dependency_graph:
  requires: [06-01]
  provides: [summary-metrics-card, park-rankings-table, loading-spinner, error-handler]
  affects: [src/mlb_park/controller.py, src/mlb_park/app.py, tests/controller/test_build_view.py]
tech_stack:
  added: [pandas (already dependency, now imported at controller module level)]
  patterns: [tdd-red-green, pandas-styler-row-highlighting, st.spinner-try-except]
key_files:
  modified:
    - src/mlb_park/app.py
    - src/mlb_park/controller.py
    - tests/controller/test_build_view.py
decisions:
  - build_park_ranking lives in controller.py (not app.py) for testability
  - Park Rankings expander placed inside the spray-chart else branch (only shown when chart renders)
  - Retry button uses st.cache_data.clear() + st.rerun(); st.stop() halts stale rendering
  - Pandas Styler uses rgba versions of chart.py CLEARS/DOESNT_CLEAR palette for row tinting
metrics:
  duration_minutes: 18
  completed_date: "2026-04-16"
  tasks_completed: 2
  tasks_total: 2
  files_changed: 3
---

# Phase 6 Plan 02: Summary, Rankings & Polish Summary

**One-liner:** Added 4-metric summary card, 30-park collapsible ranking table with top/bottom row tinting, spinner wrapping build_view, and try/except error handler with cache-clearing Retry button.

## What Was Built

### Task 1 — app.py: Metrics row + spinner + error handling (commit 31735a7)

- `build_view` wrapped in `try/except` with `st.spinner("Loading player data...")`
- On exception: `st.error(f"Could not load data... ({type(e).__name__})")` displayed
- `st.button("Retry")` calls `st.cache_data.clear()` then `st.rerun()`
- `st.stop()` after error block prevents stale UI rendering
- 4-column `st.metric` row above the spray chart: Total HRs, Avg Parks Cleared (formatted as "X.X / 30"), No-Doubters (30/30), Cheap HRs (≤5/30)
- All values sourced from `view.totals` dict (no recomputation in app.py)
- Park Rankings expander added inside the plottable-events branch with pandas Styler row highlighting

### Task 2 — controller.py: build_park_ranking (commits 39b0cb2, a882054)

TDD flow:
- RED: 3 failing tests committed (39b0cb2) — `test_build_park_ranking_basic`, `test_build_park_ranking_empty`, `test_build_park_ranking_format`
- GREEN: `build_park_ranking` implemented in controller.py (a882054)

`build_park_ranking(view)` returns a pandas DataFrame with columns `["Park", "Clears", "Clear %", "Avg Margin (ft)"]`, sorted by Clears descending then Park name ascending (tie-break). Returns empty DataFrame with correct columns when `verdict_matrix is None` or `plottable_events` is empty. Added to `__all__`.

## Verification

```
python -m pytest tests/ -x -q  →  110 passed
python -c "from mlb_park.controller import build_park_ranking; print('import OK')"  →  OK
grep "st.metric|st.spinner|st.error|st.expander" app.py  →  all 4 present
grep "build_park_ranking" controller.py  →  defined + in __all__
grep -c "def test_build_park_ranking" test_build_view.py  →  3
```

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed Park constructor field name in test helper**
- **Found during:** Task 2 GREEN phase
- **Issue:** Test helper used `distances_ft=` but `Park` dataclass field is `fence_ft`
- **Fix:** Updated `_make_minimal_view` helper to use `fence_ft=np.array([330.0, 400.0, 330.0])`
- **Files modified:** `tests/controller/test_build_view.py`
- **Commit:** a882054

## Known Stubs

None — all metric values wired to live `view.totals` dict from `_compute_totals`. Park ranking wired to `view.verdict_matrix`. No placeholder text or empty-value stubs.

## Threat Flags

None — no new trust boundaries, endpoints, or auth paths introduced. `st.button("Retry")` triggers only Streamlit-internal operations (`st.cache_data.clear()`, `st.rerun()`); no user input flows into cache keys or API URLs.

## Commits

| Task | Commit | Description |
|------|--------|-------------|
| 1 | 31735a7 | feat(06-02): add metrics row, spinner, error handler to app.py |
| 2 (RED) | 39b0cb2 | test(06-02): add failing tests for build_park_ranking |
| 2 (GREEN) | a882054 | feat(06-02): add build_park_ranking to controller.py |

## Self-Check: PASSED

- `src/mlb_park/app.py` — modified, committed in 31735a7
- `src/mlb_park/controller.py` — modified, committed in a882054
- `tests/controller/test_build_view.py` — modified, committed in 39b0cb2 + a882054
- All 3 commits verified present in git log
- 110 tests passing
