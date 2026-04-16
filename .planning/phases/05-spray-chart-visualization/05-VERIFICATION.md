---
status: passed
phase: 05
phase_name: spray-chart-visualization
score: 4/4
requirements_verified: [VIZ-01, VIZ-02, VIZ-03]
verified: 2026-04-15
---

# Phase 05: Spray Chart Visualization — Verification Report

**Phase Goal:** Render the ViewModel as a Plotly spray chart: selected stadium outline in feet, all HRs plotted and color-coded by whether they clear that stadium, hover tooltips with per-HR detail.

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Stadium outline renders correctly scaled in feet with LF/CF/RF orientation | VERIFIED | `_fair_territory_trace(park)` at `chart.py:74` builds closed polygon from `Park.angles_deg + fence_ft` via vectorized `np.sin/cos`. Handles 5pt and 7pt parks. Viewport fixed [-450,450]×[0,500] with `scaleanchor="x"`, `scaleratio=1`, `constrain="domain"`. Five additional stadium traces (infield skin, baselines, mound, bases) present in locked z-order. |
| 2 | Every HR appears as a dot at calibrated coordinates | VERIFIED | `_hr_scatter_trace(view)` at `chart.py:171` computes `x = CALIB_S*(coord_x - CALIB_OX)`, `y = CALIB_S*(CALIB_OY - coord_y)` preserving true bearing from raw Gameday coords. |
| 3 | Green/red coloring by verdict against selected park | VERIFIED | `chart.py:193-194`: `colors = [CLEARS if cleared else DOESNT_CLEAR for cleared in view.clears_selected_park]`. Constants match D-08: CLEARS=`#2ca02c`, DOESNT_CLEAR=`#d62728`. Test `test_hr_marker_colors_match_clears_tuple` asserts exact color list. |
| 4 | Hover tooltip with 6 fields (date, opponent, distance, EV, LA, parks cleared /30) | VERIFIED | HOVERTEMPLATE at `chart.py:47-54` has 6 `%{customdata[i]}` slots plus `<extra></extra>`. Customdata pre-formatted to strings (Pitfall 3 defense). Tests `test_hovertemplate_has_six_fields` and `test_customdata_shape_and_cleared_count` validate. |

### Requirements Coverage

| Req ID | Status | Evidence |
|--------|--------|----------|
| VIZ-01 | SATISFIED | Stadium outline via `_fair_territory_trace` + infield traces; fixed viewport; hidden axes; tests green |
| VIZ-02 | SATISFIED | HR scatter with `CLEARS`/`DOESNT_CLEAR` hex colors; `test_hr_marker_colors_match_clears_tuple` green |
| VIZ-03 | SATISFIED | 6-field hover via `customdata` + `hovertemplate`; both structural tests green |

### Design Decision Compliance (D-01 through D-12)

| Decision | Status |
|----------|--------|
| D-01 filled polygon + infield + mound + bases + baselines | VERIFIED |
| D-02 MLB-standard constants (60.5/90/95 ft) | VERIFIED |
| D-03 white background | VERIFIED |
| D-04 fixed viewport [-450,450]×[0,500], hidden axes | VERIFIED |
| D-05 uniform 12px circles, opacity 0.7, white border | VERIFIED |
| D-06 silently drop degraded HRs | VERIFIED (uses plottable_events) |
| D-07 per-HR hover with all VIZ-03 fields | VERIFIED |
| D-08 explicit hex color constants | VERIFIED |
| D-09 chart.py purity (no streamlit imports) | VERIFIED (purity tests green) |
| D-10 polygon from angles/fence via sin/cos | VERIFIED |
| D-11 sign convention 0°=CF, +=RF | VERIFIED |
| D-12 empty-state: outline + st.info banner | VERIFIED |

### Key Wiring

| From | To | Status |
|------|----|--------|
| `app.py:19` | `from mlb_park import chart` | WIRED |
| `app.py:153` | `Park.from_field_info` resolves selected park | WIRED |
| `app.py:166-168` | `st.plotly_chart(chart.build_figure(view, park))` | WIRED |
| `app.py:163` | D-12 empty-state `st.info` banner | WIRED |
| `chart.py` | Zero `layout.shapes` / `fig.add_shape` (all-traces z-order) | VERIFIED |

### Test Suite

- Full suite: **107 passed, 0 failed**
- Chart structural tests: 12/12 green
- Chart purity tests: 2/2 green
- Manual smoke: **approved by user** during execution

### Anti-Patterns

None blocking. One info item: stale `st.caption` in `app.py:57` references Phase 4 — cleanup candidate for Phase 6.
