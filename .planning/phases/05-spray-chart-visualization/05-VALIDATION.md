---
phase: 05
slug: spray-chart-visualization
status: draft
nyquist_compliant: false
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
| **Quick run command** | `pytest tests/test_chart.py tests/test_chart_purity.py -x -q` |
| **Full suite command** | `pytest -q` |
| **Estimated runtime** | ~3 seconds |

---

## Sampling Rate

- **After every task commit:** `pytest tests/test_chart.py tests/test_chart_purity.py -x -q`
- **After every plan wave:** `pytest -q` (full suite)
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** ~3 seconds

---

## Per-Task Verification Map

*Populated during planning — one row per task. Each task must have an automated verify command OR declare a Wave 0 dependency OR be marked manual-only with justification.*

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| TBD | TBD | TBD | VIZ-01 | — | N/A | unit (structural) | `pytest tests/test_chart.py::test_fair_territory_polygon_closed -x` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | VIZ-01 | — | N/A | unit (structural) | `pytest tests/test_chart.py::test_layout_ranges_and_aspect_ratio -x` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | VIZ-01 | — | N/A | unit (structural) | `pytest tests/test_chart.py::test_axes_hidden -x` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | VIZ-01 / D-10 | — | N/A | unit (parametrized) | `pytest tests/test_chart.py::test_fair_polygon_handles_five_and_seven_points -x` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | VIZ-02 | — | N/A | unit (structural) | `pytest tests/test_chart.py::test_hr_marker_colors_match_clears_tuple -x` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | VIZ-02 | — | N/A | unit (structural) | `pytest tests/test_chart.py::test_hr_scatter_is_last_trace -x` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | VIZ-03 | — | N/A | unit | `pytest tests/test_chart.py::test_hovertemplate_has_six_fields -x` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | VIZ-03 | — | N/A | unit | `pytest tests/test_chart.py::test_customdata_shape_and_cleared_count -x` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | D-06 | — | N/A | unit | `pytest tests/test_chart.py::test_empty_plottable_events -x` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | D-09 | — | N/A | unit (purity) | `pytest tests/test_chart_purity.py -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

Planner MUST fill in `Task ID`, `Plan`, `Wave`, and flip `File Exists` to ✅ when Wave 0 tasks land.

---

## Wave 0 Requirements

- [ ] `tests/test_chart.py` — structural assertions for VIZ-01/02/03 + D-06 + D-10
- [ ] `tests/test_chart_purity.py` — greps `src/mlb_park/chart.py` for `import streamlit` / `from streamlit` / `st.session_state`; mirrors `tests/controller/test_purity.py`
- [ ] Shared fixture: `ViewModel` factory in `tests/conftest.py` (or a new `tests/charts/conftest.py`). Must provide:
  - Non-empty variant using existing Phase 3 Judge fixtures → populated `plottable_events` + `verdict_matrix` + `clears_selected_park`
  - Empty variant with `plottable_events=()` to exercise the empty-state path
  - At least one 5-point park (e.g., `tests/fixtures/park_fenway.json`-derived) and one 7-point park (e.g., `tests/fixtures/park_yankee.json`-derived) so `test_fair_polygon_handles_five_and_seven_points` can parametrize

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Visual correctness of the rendered spray chart (colors, marker placement, hover display) | VIZ-01..03 | Plotly rendering quality and hover UX are browser-runtime behaviors; structural assertions verify the data contract but not the pixels | `streamlit run src/mlb_park/app.py` → pick Yankees → Judge → step through a handful of parks → confirm green/red flip, stadium outline sizes correctly, hover shows all 6 fields |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references (`test_chart.py`, `test_chart_purity.py`, `ViewModel` fixture factory)
- [ ] No watch-mode flags
- [ ] Feedback latency < 5s
- [ ] `nyquist_compliant: true` set in frontmatter after planner completes the per-task map

**Approval:** pending
