---
status: issues_found
phase: 05
depth: standard
files_reviewed: 5
findings:
  critical: 0
  warning: 2
  info: 3
  total: 5
---

# Phase 05 Code Review

## Warnings

### WR-01: Potential plottable_events / verdict_matrix length mismatch
**File:** `src/mlb_park/chart.py:200`
**Severity:** warning

Controller line 314 further filters `hit_data_list` after extracting `plottable`, so the verdict matrix could have fewer rows than `plottable_events`. `chart.py` indexes `verdict_matrix.cleared[i, :]` by plottable-event index, which would crash with `IndexError` if the lengths diverge.

**Fix:** Align both sequences in the controller, or add a defensive assertion in `chart.py`.

### WR-02: app.py calls underscore-prefixed private functions
**File:** `src/mlb_park/app.py:61,80,87`
**Severity:** warning

`app.py` calls `controller._sorted_teams()`, `controller._sorted_hitters()`, and `controller._hr_of()` which are all underscore-prefixed private functions not in `__all__`.

**Fix:** Promote to public API or expose higher-level selector helpers.

## Info

### IN-01: Stale Phase 4 caption in app.py
**File:** `src/mlb_park/app.py:57`
**Severity:** info

Caption still says "Phase 4 -- raw ViewModel dump. Chart arrives in Phase 5." but Phase 5 is now implemented.

### IN-02: Magic number for mound radius
**File:** `src/mlb_park/chart.py:142`
**Severity:** info

Mound radius `5.0` is a magic number; other infield dimensions are named constants.

### IN-03: Dead constant BASE_MARKER_SIZE_FT
**File:** `src/mlb_park/chart.py:162`
**Severity:** info

`BASE_MARKER_SIZE_FT = 1.25` defined on line 38 but never used; `_bases_trace` uses hardcoded `size=10` (pixels). Dead constant or missing reference.
