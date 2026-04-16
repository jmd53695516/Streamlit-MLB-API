---
phase: 06-summary-rankings-polish
plan: 01
subsystem: controller, chart, app
tags: [cleanup, refactor, api-promotion, constants, dead-code]
dependency_graph:
  requires: [05-03]
  provides: [public-controller-api, clean-app-entry-point]
  affects: [src/mlb_park/controller.py, src/mlb_park/chart.py, src/mlb_park/app.py]
tech_stack:
  added: []
  patterns: [public-helper-api, named-constants, guarded-lookups]
key_files:
  modified:
    - src/mlb_park/controller.py
    - src/mlb_park/chart.py
    - src/mlb_park/app.py
    - tests/controller/test_helpers.py
decisions:
  - Promoted all private helpers (_sorted_teams, _sorted_hitters, _hr_of, _name_of) to public API; updated __all__ accordingly
  - Guarded both next() calls in build_view with None default + ValueError raise
  - Hardened hr_of with isinstance(stats[0], dict) guard and top-level try/except
  - Extracted MOUND_RADIUS_FT = 5.0 named constant; removed dead BASE_MARKER_SIZE_FT
  - Removed stale Phase 4 caption, raw st.json debug dump, and stale error banner copy
metrics:
  duration_minutes: 12
  completed_date: "2026-04-16"
  tasks_completed: 2
  tasks_total: 2
  files_changed: 4
---

# Phase 6 Plan 01: Code Review Cleanup Summary

**One-liner:** Promoted private controller helpers to public API, guarded unguarded next() calls, extracted MOUND_RADIUS_FT constant, and removed stale Phase 4 UI copy — landing Plan 02 on a clean base.

## What Was Built

All Phase 4 + 5 code review findings (WR-01, WR-02, IN-01, IN-02, IN-03) resolved:

### Task 1 — controller.py (commit e26d5d8)

- Renamed `_sorted_teams` → `sorted_teams`, `_sorted_hitters` → `sorted_hitters`, `_hr_of` → `hr_of`, `_name_of` → `name_of`
- Updated `__all__` to export public names; removed dead `"field"` re-export
- Both `next()` calls in `build_view` now use `next((... ), None)` pattern with explicit `ValueError` raises
- `hr_of` hardened: `isinstance(stats[0], dict)` guard before accessing `.get("splits")`; wrapped in `try/except (TypeError, ValueError, AttributeError)`
- Updated `tests/controller/test_helpers.py` imports to match public names (deviation Rule 1 — tests would have broken otherwise)

### Task 2 — chart.py + app.py (commit bf39142)

- Added `MOUND_RADIUS_FT = 5.0` constant in infield constants block; `_mound_trace()` uses `radius = MOUND_RADIUS_FT`
- Removed dead `BASE_MARKER_SIZE_FT = 1.25` constant (unused; `_bases_trace` uses pixel `size=10` directly)
- Removed `st.caption("Phase 4 — raw ViewModel dump. Chart arrives in Phase 5.")`
- Updated module docstring: "MLB HR Park Factor Explorer — Streamlit entry point."
- Updated all call sites: `controller._sorted_teams` → `controller.sorted_teams`, etc.
- Removed `st.subheader("ViewModel (raw)")` + `st.json(view.to_dict())` debug dump
- Fixed stale error banner copy that referenced "raw ViewModel below"

## Verification

```
python -m pytest tests/ -x -q  →  107 passed
grep "def sorted_teams|def sorted_hitters|def hr_of" controller.py  →  found (public, no underscore)
grep "_sorted_teams|_sorted_hitters|_hr_of" app.py  →  (none)
grep "MOUND_RADIUS_FT" chart.py  →  line 38 (defined), line 142 (used)
grep "Phase 4" app.py  →  (none)
grep "st.json" app.py  →  (none)
grep "BASE_MARKER_SIZE_FT" chart.py  →  (none)
```

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Updated test_helpers.py imports to use public names**
- **Found during:** Task 1
- **Issue:** `tests/controller/test_helpers.py` imported `_sorted_hitters, _sorted_teams` — would break after rename
- **Fix:** Updated import line and all test function call sites to use `sorted_hitters`, `sorted_teams`
- **Files modified:** `tests/controller/test_helpers.py`
- **Commit:** e26d5d8

**2. [Rule 1 - Bug] Fixed stale error banner copy**
- **Found during:** Task 2
- **Issue:** Error warning banner text said "see raw ViewModel below for details" — the raw dump was being removed in the same task
- **Fix:** Updated to "HR data may be incomplete."
- **Files modified:** `src/mlb_park/app.py`
- **Commit:** bf39142

## Known Stubs

None — no stub patterns found in modified files.

## Threat Flags

None — no new trust boundaries, endpoints, or auth paths introduced.

## Commits

| Task | Commit | Description |
|------|--------|-------------|
| 1 | e26d5d8 | feat(06-01): promote private controller helpers to public API |
| 2 | bf39142 | feat(06-01): chart + app.py cleanup — constants, caption, call sites |

## Self-Check: PASSED

- `src/mlb_park/controller.py` — modified, committed in e26d5d8
- `src/mlb_park/chart.py` — modified, committed in bf39142
- `src/mlb_park/app.py` — modified, committed in bf39142
- `tests/controller/test_helpers.py` — modified, committed in e26d5d8
- Both commits verified present in git log
- 107 tests passing
