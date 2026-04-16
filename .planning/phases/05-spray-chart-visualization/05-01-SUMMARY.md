---
phase: 05-spray-chart-visualization
plan: 01
subsystem: visualization
tags: [chart, plotly, scaffolding, tdd, wave-0]
dependency_graph:
  requires: [Phase 4 ViewModel, Phase 2 Park/VerdictMatrix, Phase 3 HREvent]
  provides: [chart.py skeleton, chart test fixtures, structural test stubs]
  affects: [05-02-PLAN (Wave 2 fair-territory), 05-03-PLAN (Wave 3 HR scatter)]
tech_stack:
  added: []
  patterns: [pure-module purity guard, session-scoped fixture factory, ControllerStubAPI reuse]
key_files:
  created:
    - src/mlb_park/chart.py
    - tests/charts/__init__.py
    - tests/charts/conftest.py
    - tests/charts/test_chart.py
    - tests/charts/test_chart_purity.py
  modified: []
decisions:
  - Reused ControllerStubAPI from tests/controller/conftest.py instead of building a new _StubAPI (simpler, no duplication)
  - Docstring wording avoids literal "import streamlit" / "st.session_state" substrings to pass purity guard
metrics:
  duration: ~6min
  completed: "2026-04-16T02:16:00Z"
  tasks: 3/3
  files_created: 5
  files_modified: 0
---

# Phase 5 Plan 01: Wave 0 Scaffolding Summary

Chart module skeleton with constants, empty build_figure stub, and 11 structural tests (6 green, 5 red Nyquist gates for Waves 2/3) using ControllerStubAPI-backed Judge HR fixtures.

## What Was Built

### src/mlb_park/chart.py (skeleton)

- **Constants block**: D-08 color palette (CLEARS `#2ca02c`, DOESNT_CLEAR `#d62728`, FAIR_TERRITORY `#e8f5e9`, INFIELD_DIRT `#c1a17a`, etc.), D-02 infield dimensions (MOUND_DISTANCE_FT 60.5, BASE_DISTANCE_FT 90.0, etc.), D-04 viewport (X_RANGE [-450, 450], Y_RANGE [0, 500]).
- **build_figure(view, park)**: Returns a `go.Figure` with a single empty HR trace (named "hrs") and the locked layout applied. Fair-territory, infield, baselines, mound, and bases traces are stubs for Wave 2.
- **_hr_scatter_trace(view)**: Returns an empty `go.Scatter(x=[], y=[], name="hrs")` placeholder.
- **_apply_layout(fig)**: Applies D-04 viewport, hidden axes, aspect lock (`scaleanchor="x"`, `scaleratio=1`), `constrain="domain"` on both axes.
- **Purity**: Zero `import streamlit` / `from streamlit` / `st.session_state` references.

### tests/charts/conftest.py (fixture factory)

- **StubAPI approach**: Reuses `ControllerStubAPI` from `tests/controller/conftest.py` (Phase 4) rather than building a new stub class. The ControllerStubAPI already extends the Phase 3 `StubAPI` with `get_teams()` and `get_team_hitting_stats()`.
- **Fixture data**: Uses existing Judge 2026 fixtures (`teams.json`, `team_stats_147_2026.json`, `gamelog_592450_2026.json`, `feed_*.json`, `venue_*.json`).
- **sample_view**: ViewModel with 6 Judge HRs (all plottable), verdict_matrix populated, built via `build_view(team_id=147, player_id=592450, venue_id=3313)`.
- **empty_view**: Direct ViewModel construction with `plottable_events=()`, `verdict_matrix=None`.
- **sample_park / yankee_park_7pt**: 7-point Park from venue fixture (venue_1, Angel Stadium).
- **fenway_park_5pt**: 5-point Park from venue fixture (venue_14, Rogers Centre).

### Test State After Commit (Nyquist RED)

| Test | Status | Gate |
|------|--------|------|
| test_no_streamlit_in_chart_module | PASS | -- |
| test_chart_imports_have_no_streamlit | PASS | -- |
| test_layout_ranges_and_aspect_ratio | PASS | -- |
| test_axes_hidden | PASS | -- |
| test_hr_scatter_is_last_trace | PASS | -- |
| test_empty_plottable_events | PASS | -- |
| test_fair_territory_polygon_closed | FAIL | Wave 2 |
| test_fair_polygon_handles_five_and_seven_points | FAIL | Wave 2 |
| test_hr_marker_colors_match_clears_tuple | FAIL | Wave 3 |
| test_hovertemplate_has_six_fields | FAIL | Wave 3 |
| test_customdata_shape_and_cleared_count | FAIL | Wave 3 |

**Full suite**: 101 passed, 5 failed (all 5 are expected Wave 2/3 gates). Zero Phase 1-4 regressions.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Chart.py docstring triggered purity guard false positive**
- **Found during:** Task 1
- **Issue:** The docstring contained literal substrings `import streamlit` and `st.session_state` (in a "NEVER do this" comment), which the source-level purity guard matched.
- **Fix:** Rewrote the docstring line to "D-09 purity rule: this module must stay free of any Streamlit dependency."
- **Files modified:** `src/mlb_park/chart.py`
- **Commit:** 1885d39

**2. [Rule 3 - Blocking] Used ControllerStubAPI instead of building new _StubAPI**
- **Found during:** Task 2
- **Issue:** Plan suggested building a new `_StubAPI` in conftest.py, but an equivalent `ControllerStubAPI` already existed in `tests/controller/conftest.py` with all required methods.
- **Fix:** Imported and reused `ControllerStubAPI` directly. Smaller code, no duplication, same test coverage.
- **Files modified:** `tests/charts/conftest.py`
- **Commit:** b7b8cae

## Decisions Made

1. **ControllerStubAPI reuse over new stub**: The existing Phase 4 test infrastructure already provides the exact API surface needed by `build_view`. Building a new `_StubAPI` would duplicate 60+ lines of code.
2. **Docstring phrasing**: Avoided forbidden substrings in docstrings by describing the purity rule generically rather than quoting the specific forbidden imports.

## Self-Check: PASSED
