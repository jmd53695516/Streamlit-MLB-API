---
phase: 05-spray-chart-visualization
plan: 03
subsystem: visualization
tags: [chart, plotly, hr-scatter, hover, customdata, app-wiring, wave-3]
dependency_graph:
  requires: [05-01 (chart skeleton), 05-02 (stadium traces)]
  provides: [_hr_scatter_trace with colors/customdata/hovertemplate, app.py chart render, D-12 empty-state banner]
  affects: [Phase 6 (summary card, polish)]
tech_stack:
  added: []
  patterns: [pre-formatted customdata (Pitfall 3 defense), CALIB_* raw coord transform for true HR bearing]
key_files:
  created: []
  modified:
    - src/mlb_park/chart.py
    - src/mlb_park/app.py
decisions:
  - Pre-format all customdata fields to strings Python-side (no d3-format specifiers) to avoid Pitfall 3 mixed-dtype rendering issues
  - Use CALIB_OX/OY/S raw coord transform for HR marker position (preserves true bearing, not clamped angle)
  - D-12 empty-state banner uses f-string with view.player_name for personalized messaging
  - Park resolved in app.py from parks_map via Park.from_field_info (two-arg build_figure signature)
metrics:
  duration: ~3min
  completed: "2026-04-16T02:25:00Z"
  tasks: 2/2 complete + 1 checkpoint (Task 3 manual smoke)
  files_created: 0
  files_modified: 2
---

# Phase 5 Plan 03: HR Scatter + App Wiring Summary

Full HR scatter trace with green/red verdict colors, 6-field hover tooltip via pre-formatted customdata, and app.py wiring with D-12 empty-state banner. Phase 5 chart surface complete pending manual smoke verification.

## What Was Built

### src/mlb_park/chart.py (HR scatter implementation)

- **HOVERTEMPLATE constant**: Module-level string with 6 `%{customdata[i]}` slots (date vs opponent, distance ft, exit velocity mph, launch angle deg, clears N/30 parks) + `<extra></extra>` to suppress trace-name box. Zero d3-format specifiers (Pitfall 3 defense).
- **CALIB import**: `from mlb_park.geometry.calibration import CALIB_OX, CALIB_OY, CALIB_S` for raw coord transform.
- **_hr_scatter_trace(view)**: Full implementation replacing Wave 1 stub:
  - Position: `x = CALIB_S * (ev.coord_x - CALIB_OX)`, `y = CALIB_S * (CALIB_OY - ev.coord_y)` -- preserves true HR bearing.
  - Colors: `[CLEARS if c else DOESNT_CLEAR for c in view.clears_selected_park]` -- 1:1 positional alignment.
  - customdata: `np.empty((n, 6), dtype=object)` with per-field string pre-formatting. Column layout: [date_iso, opponent_abbr, distance_str, launch_speed_str, launch_angle_str, cleared_count_int].
  - Empty-state: returns empty trace with `hoverinfo="skip"` when `plottable_events` is empty.

### src/mlb_park/app.py (chart wiring + empty-state)

- **Imports added**: `from mlb_park import chart` and `from mlb_park.geometry.park import Park`.
- **Park resolution**: `Park.from_field_info(parks_map[view.venue_id].get("fieldInfo"), ...)` in the else-branch.
- **Chart render**: `st.plotly_chart(chart.build_figure(view, park), use_container_width=True)` with `st.subheader("Spray Chart")`.
- **Empty-state flow** (3 branches):
  - `not view.events` -- "{player} has no home runs in {season}." (Phase 4 banner preserved)
  - `view.events but not view.plottable_events` -- D-12: "{player} has no plottable HRs this season."
  - `view.plottable_events` -- chart renders
- Raw JSON + dataframe dumps remain below the chart for Phase 6 debugging.

### Customdata Column Layout

| Column | Content | Format | Source |
|--------|---------|--------|--------|
| 0 | Game date | ISO 8601 string | `ev.game_date.isoformat()` |
| 1 | Opponent abbreviation | 3-letter uppercase | `ev.opponent_abbr` |
| 2 | Distance (ft) | Integer string | `f"{ev.distance_ft:.0f}"` |
| 3 | Exit velocity (mph) | 1-decimal string | `f"{ev.launch_speed:.1f}"` or em-dash |
| 4 | Launch angle (deg) | 1-decimal string | `f"{ev.launch_angle:.1f}"` or em-dash |
| 5 | Parks cleared count | Integer | `int(verdict_matrix.cleared[i, :].sum())` |

### Final Test State

| Test | Status |
|------|--------|
| test_no_streamlit_in_chart_module | PASS |
| test_chart_imports_have_no_streamlit | PASS |
| test_layout_ranges_and_aspect_ratio | PASS |
| test_axes_hidden | PASS |
| test_hr_scatter_is_last_trace | PASS |
| test_trace_z_order | PASS |
| test_empty_plottable_events | PASS |
| test_fair_territory_polygon_closed | PASS |
| test_fair_polygon_handles_five_and_seven_points | PASS |
| test_hr_marker_colors_match_clears_tuple | PASS |
| test_hovertemplate_has_six_fields | PASS |
| test_customdata_shape_and_cleared_count | PASS |

**Full suite**: 107 passed, 0 failed. Zero regressions across Phases 1-5.

## Deviations from Plan

None -- plan executed exactly as written.

## Decisions Made

1. **Pre-formatted customdata over d3-format specs**: All 6 fields are formatted to strings Python-side before passing to the numpy object array. The hovertemplate uses plain `%{customdata[i]}` without `:` format suffixes. This is the Pitfall 3 defense recommended by research.
2. **Park resolved in app.py, not chart.py**: Maintains chart.py purity (no service imports). Park is built from `parks_map` already in scope in app.py's else-branch.

## Phase 6 Handoff Notes

- The raw JSON dump and plottable dataframe remain below the chart in app.py -- Phase 6 can replace/remove them when adding the summary metrics card and best/worst parks ranking.
- The chart render tree has exactly 6 traces in locked z-order: fair, infield, baselines, mound, bases, hrs. Phase 6 should not insert traces between bases and hrs (HR scatter must remain last for z-order correctness).
- `use_container_width=True` triggers a DeprecationWarning in Streamlit 1.56 (Pitfall 5). Phase 6 or a future cleanup can migrate to `width="stretch"`.
- The `HOVERTEMPLATE` constant is module-level -- Phase 6 can extend it if additional tooltip fields are needed (e.g., margin_ft per park).

## Checkpoint: Manual Smoke (Task 3)

Task 3 is a `checkpoint:human-verify` gate. All programmatic verification passed:
- pytest: 107 passed
- chart.py purity: CLEAN (no streamlit imports)
- Forbidden pattern grep: no d3-format specifiers in HOVERTEMPLATE

Awaiting manual smoke verification of the 7 items defined in the plan.

## Commits

| Task | Commit | Description |
|------|--------|-------------|
| 1 | 9621633 | _hr_scatter_trace with colors, customdata, hovertemplate |
| 2 | 4d9c963 | Wire chart into app.py with D-12 empty-state banner |

## Self-Check: PASSED
