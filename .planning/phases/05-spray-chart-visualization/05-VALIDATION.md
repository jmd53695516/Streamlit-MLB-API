---
phase: 05
slug: spray-chart-visualization
status: planned
nyquist_compliant: true
wave_0_complete: false
created: 2026-04-15
---

# Phase 05 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x (already pinned in requirements.txt) |
| **Config file** | None yet — pytest auto-discovers `tests/` at repo root per project convention |
| **Quick run command** | `pytest tests/charts/ -x -q` |
| **Full suite command** | `pytest -q` |
| **Estimated runtime** | ~3 seconds |

---

## Sampling Rate

- **After every task commit:** `pytest tests/charts/ -x -q`
- **After every plan wave:** `pytest -q` (full suite)
- **Before `/gsd-verify-work`:** Full suite must be green + manual smoke signed off
- **Max feedback latency:** ~3 seconds

---

## Per-Task Verification Map

One row per testable behavior. Plan / Wave / owning-task columns reflect the locked plan set.

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 05-01-T3 | 05-01 | 1 | D-09 | T-05-01 | N/A | unit (purity) | `pytest tests/charts/test_chart_purity.py -x` | ✅ after 05-01-T1+T3 | ⬜ pending |
| 05-01-T3 | 05-01 | 1 | VIZ-01 | T-05-01 | N/A | unit (structural) | `pytest tests/charts/test_chart.py::test_layout_ranges_and_aspect_ratio -x` | ✅ after 05-01 | ⬜ pending |
| 05-01-T3 | 05-01 | 1 | VIZ-01 | T-05-01 | N/A | unit (structural) | `pytest tests/charts/test_chart.py::test_axes_hidden -x` | ✅ after 05-01 | ⬜ pending |
| 05-02-T1 | 05-02 | 2 | VIZ-01 | T-05-02 | N/A | unit (structural) | `pytest tests/charts/test_chart.py::test_fair_territory_polygon_closed -x` | ✅ after 05-02-T1 | ⬜ pending |
| 05-02-T1 | 05-02 | 2 | VIZ-01 / D-10 | T-05-02 | N/A | unit (parametrized) | `pytest tests/charts/test_chart.py::test_fair_polygon_handles_five_and_seven_points -x` | ✅ after 05-02-T1 | ⬜ pending |
| 05-02-T1 | 05-02 | 2 | D-06 / D-12 | T-05-02 | N/A | unit | `pytest tests/charts/test_chart.py::test_empty_plottable_events -x` | ✅ after 05-02-T1 | ⬜ pending |
| 05-02-T2 | 05-02 | 2 | VIZ-01 / D-01 | T-05-02 | N/A | unit (structural) | `pytest tests/charts/test_chart.py::test_trace_z_order -x` | ✅ after 05-02-T2 | ⬜ pending |
| 05-01-T3 | 05-01 | 1 | VIZ-02 | T-05-02 | N/A | unit (structural) | `pytest tests/charts/test_chart.py::test_hr_scatter_is_last_trace -x` | ✅ after 05-01 | ⬜ pending |
| 05-03-T1 | 05-03 | 3 | VIZ-02 | T-05-03 | N/A | unit (structural) | `pytest tests/charts/test_chart.py::test_hr_marker_colors_match_clears_tuple -x` | ✅ after 05-03-T1 | ⬜ pending |
| 05-03-T1 | 05-03 | 3 | VIZ-03 | T-05-03 | N/A | unit | `pytest tests/charts/test_chart.py::test_hovertemplate_has_six_fields -x` | ✅ after 05-03-T1 | ⬜ pending |
| 05-03-T1 | 05-03 | 3 | VIZ-03 | T-05-03 | N/A | unit | `pytest tests/charts/test_chart.py::test_customdata_shape_and_cleared_count -x` | ✅ after 05-03-T1 | ⬜ pending |
| 05-03-T3 | 05-03 | 3 | VIZ-01..03 | T-05-04 | N/A | manual smoke | `streamlit run src/mlb_park/app.py` → Yankees → Judge → several parks → hover + verdict flip check | n/a | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

### Wave-by-wave gate state (post-commit, before next wave starts)

| Wave | Plan | Expected green | Expected red (owned by later wave) |
|------|------|----------------|-------------------------------------|
| 1 | 05-01 | purity (×2), layout_ranges_and_aspect_ratio, axes_hidden, hr_scatter_is_last_trace, empty_plottable_events (partial — outline assertion lives in 05-02) | fair_territory_polygon_closed, fair_polygon_handles_five_and_seven_points, hr_marker_colors_match_clears_tuple, hovertemplate_has_six_fields, customdata_shape_and_cleared_count, trace_z_order |
| 2 | 05-02 | + fair_territory_polygon_closed, fair_polygon_handles_five_and_seven_points, trace_z_order, empty_plottable_events (full) | hr_marker_colors_match_clears_tuple, hovertemplate_has_six_fields, customdata_shape_and_cleared_count |
| 3 | 05-03 | ALL GREEN + manual smoke | — |

---

## Wave 0 Requirements

Wave 0 scaffolding is delivered by **Plan 05-01**. Its completion is the gate for Waves 2 and 3:

- [x] `tests/charts/test_chart.py` — structural assertions for VIZ-01/02/03 + D-06 + D-10 (Plan 05-01 Task 3)
- [x] `tests/charts/test_chart_purity.py` — greps `src/mlb_park/chart.py` for `import streamlit` / `from streamlit` / `st.session_state`; mirrors `tests/controller/test_purity.py` (Plan 05-01 Task 3)
- [x] `tests/charts/conftest.py` — ViewModel factory (Plan 05-01 Task 2):
  - `sample_view` (non-empty Judge HRs, verdict_matrix populated, `clears_selected_park` mixed True/False)
  - `empty_view` (plottable_events=(), verdict_matrix=None)
  - `sample_park` (7-point)
  - `fenway_park_5pt` (5-point — from a 5-point fixture or synthetic fallback)
  - `yankee_park_7pt` (7-point — alias of sample_park for clarity)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Visual correctness of the rendered spray chart (colors, marker placement, hover display, aspect ratio on window resize) | VIZ-01..03 | Plotly rendering quality and hover UX are browser-runtime behaviors; structural assertions verify the data contract but not the pixels | `streamlit run src/mlb_park/app.py` → pick Yankees → Judge → step through a handful of parks → confirm green/red flip, stadium outline resizes correctly per park, hover shows all 6 fields with no "nan"/"None" strings, no double-tooltip box |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies (manual smoke is the sole manual item, Task 05-03-T3)
- [x] Sampling continuity: no 3 consecutive tasks without automated verify (every task commits with a pytest gate)
- [x] Wave 0 covers all MISSING references (`test_chart.py`, `test_chart_purity.py`, ViewModel fixture factory)
- [x] No watch-mode flags
- [x] Feedback latency < 5s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** pending execution sign-off after Wave 3 manual smoke.
