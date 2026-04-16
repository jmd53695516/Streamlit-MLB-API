---
phase: 05-spray-chart-visualization
plan: 02
subsystem: visualization
tags: [chart, plotly, stadium-geometry, traces, wave-2]
dependency_graph:
  requires: [05-01 (chart skeleton, fixture factory)]
  provides: [_fair_territory_trace, _infield_skin_trace, _baselines_trace, _mound_trace, _bases_trace, locked z-order]
  affects: [05-03-PLAN (Wave 3 HR scatter overlay)]
tech_stack:
  added: []
  patterns: [all-traces z-order (no layout.shapes), vectorized sin/cos polygon, parametric circle trace]
key_files:
  created: []
  modified:
    - src/mlb_park/chart.py
    - tests/charts/test_chart.py
decisions:
  - Home plate rendered as first point of _bases_trace with symbol="pentagon"; 1B/2B/3B use symbol="diamond" -- single trace, 4 markers
  - All stadium elements are go.Scatter traces (zero layout.shapes) to guarantee trace-order z-stacking and avoid Pitfall 2
  - Mound rendered as 25-vertex parametric circle (radius 5ft) with fill="toself" rather than layout.shapes circle
metrics:
  duration: ~2.5min
  completed: "2026-04-15T22:19:00Z"
  tasks: 2/2
  files_created: 0
  files_modified: 2
---

# Phase 5 Plan 02: Stadium Geometry Traces Summary

Five private trace helpers in chart.py rendering fair-territory polygon, infield dirt arc, baselines, mound circle, and base markers -- all as go.Scatter traces in locked z-order, with test_trace_z_order enforcing the 6-trace sequence.

## What Was Built

### src/mlb_park/chart.py (stadium geometry traces)

- **_fair_territory_trace(park)**: Builds closed polygon from Park.angles_deg/fence_ft via vectorized np.sin/np.cos. Vertices: (0,0) + N fence points + (0,0). fill="toself", fillcolor=FAIR_TERRITORY. Handles both 5-point and 7-point parks transparently.
- **_infield_skin_trace()**: Quarter-annulus polygon at INFIELD_SKIN_RADIUS_FT (95 ft), 33-vertex arc from -45 to +45 degrees, closed to origin. fill="toself", fillcolor=INFIELD_DIRT.
- **_baselines_trace()**: Closed path home -> 1B -> 2B -> 3B -> home. Thin white lines (width=1.5).
- **_mound_trace()**: 25-vertex parametric circle (radius 5 ft) centered at (0, 60.5). fill="toself", fillcolor=MOUND_DIRT.
- **_bases_trace()**: 4 markers -- home plate as "pentagon" symbol, 1B/2B/3B as "diamond" symbols. White fill with gray border.
- **Base position constants**: _FIRST_BASE (+63.64, +63.64), _SECOND_BASE (0, 127.28), _THIRD_BASE (-63.64, +63.64), _HOME_PLATE (0, 0).
- **build_figure z-order**: fair -> infield -> baselines -> mound -> bases -> hrs (locked, enforced by test).

### tests/charts/test_chart.py (new + updated tests)

- **test_trace_z_order**: Asserts exact 6-trace sequence ["fair", "infield", "baselines", "mound", "bases", "hrs"].
- **test_empty_plottable_events**: Extended with assertion that "fair" trace is present even with zero HRs (D-12).

### Final Test State

| Test | Status | Gate |
|------|--------|------|
| test_fair_territory_polygon_closed | PASS | -- |
| test_fair_polygon_handles_five_and_seven_points | PASS | -- |
| test_layout_ranges_and_aspect_ratio | PASS | -- |
| test_axes_hidden | PASS | -- |
| test_hr_scatter_is_last_trace | PASS | -- |
| test_empty_plottable_events | PASS | -- |
| test_trace_z_order | PASS | -- |
| test_hr_marker_colors_match_clears_tuple | FAIL | Wave 3 |
| test_hovertemplate_has_six_fields | FAIL | Wave 3 |
| test_customdata_shape_and_cleared_count | FAIL | Wave 3 |

**Full suite**: 104 passed, 3 failed (all 3 are expected Wave 3 gates). Zero Phase 1-4 regressions.

## Trace Z-Order (Locked)

```
1. fair              -- fair-territory polygon (bottom)
2. infield           -- dirt arc
3. baselines         -- home->1B->2B->3B->home lines
4. mound             -- pitcher's mound circle
5. bases             -- 4 base markers (home + 1B/2B/3B)
6. hrs               -- HR scatter (MUST BE LAST -- always on top)
```

## Decisions Made

1. **All traces, zero layout.shapes**: Every stadium element is a go.Scatter trace. This guarantees that trace-add order alone controls z-stacking, avoiding Pitfall 2 (layout.shapes default layer="above" would bury HR markers).
2. **Home plate in _bases_trace**: Home plate is the first point in the 4-marker _bases_trace with symbol="pentagon"; 1B/2B/3B use symbol="diamond". Single trace keeps the trace count at 6 total.
3. **Mound as parametric circle trace**: 25-vertex circle with fill="toself" rather than layout.shapes type="circle". Consistent with the all-traces approach.

## Wave 3 Gate Tests (Still RED)

These 3 tests remain intentionally RED -- they are owned by Plan 05-03 (HR scatter overlay):
- `test_hr_marker_colors_match_clears_tuple` -- needs real HR marker colors from clears_selected_park
- `test_hovertemplate_has_six_fields` -- needs customdata + hovertemplate wiring
- `test_customdata_shape_and_cleared_count` -- needs customdata array population

## Deviations from Plan

None -- plan executed exactly as written.

## Commits

| Task | Commit | Description |
|------|--------|-------------|
| 1 | bda522b | Fair-territory polygon + infield skin traces |
| 2 | 311cc45 | Baselines + mound + bases traces with z-order test |

## Self-Check: PASSED
