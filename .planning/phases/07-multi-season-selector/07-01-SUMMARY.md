---
phase: 07-multi-season-selector
plan: 01
subsystem: config, app, pipeline
tags: [season-selector, ui, cascade-reset, config, tdd]
requirements: [SEASON-01, SEASON-02]

dependency_graph:
  requires: []
  provides:
    - AVAILABLE_SEASONS constant (5-year descending list)
    - _current_season() dynamic computation
    - Season selectbox in app.py (before Team)
    - _on_season_change() cascade callback
    - season threading through build_view and get_team_hitting_stats
  affects:
    - src/mlb_park/config.py
    - src/mlb_park/app.py
    - src/mlb_park/pipeline/__init__.py

tech_stack:
  added: []
  patterns:
    - TDD (RED -> GREEN) for both config constants and UI callback
    - datetime.datetime.now() for dynamic season computation
    - st.selectbox key= binding for season state
    - on_change= callback pattern for cascade reset

key_files:
  created:
    - tests/test_config_season.py
  modified:
    - src/mlb_park/config.py
    - src/mlb_park/app.py
    - src/mlb_park/pipeline/__init__.py
    - tests/controller/test_callbacks.py

decisions:
  - "_current_season() uses month >= 3 threshold: Jan-Feb is off-season, maps to prior year"
  - "AVAILABLE_SEASONS defined as list(range(CURRENT_SEASON, CURRENT_SEASON - 5, -1)) — 5 descending years"
  - "season selectbox placed before Team selectbox per D-01 UI spec"
  - "season variable computed via st.session_state.get('season', CURRENT_SEASON) after selectbox"

metrics:
  duration_seconds: 303
  completed_date: "2026-04-16"
  tasks_completed: 2
  tasks_total: 2
  files_created: 1
  files_modified: 4
  tests_added: 8
  tests_total: 118
---

# Phase 7 Plan 01: Season Selector UI Summary

**One-liner:** Dynamic season constants (5-year descending from computed current year) and season selectbox wired into all downstream API calls via st.session_state cascade.

## What Was Built

Added multi-season UI support to the MLB HR Park Factor Explorer:

1. **Dynamic `_current_season()` in `config.py`** — replaces hardcoded `CURRENT_SEASON = 2026` with a function that returns `datetime.now().year` when month >= 3 (season active) or `year - 1` when month < 3 (off-season). `AVAILABLE_SEASONS` is a 5-element descending list starting from `CURRENT_SEASON`.

2. **Pipeline re-export** — `pipeline/__init__.py` now re-exports `AVAILABLE_SEASONS` alongside `CURRENT_SEASON` for downstream consumers.

3. **Season selectbox in `app.py`** — appears before Team selectbox, bound to `st.session_state["season"]`, uses `AVAILABLE_SEASONS` as options, defaults to index 0 (current season).

4. **`_on_season_change()` callback** — nulls `team_id`, `player_id`, and `venue_id` on season change (full cascade reset per SEASON-02).

5. **Season threading** — `get_team_hitting_stats(team_id, season)` and `controller.build_view(..., season=season)` now use the selected season from session state, not the `CURRENT_SEASON` constant.

6. **Copy updates** — player help text: "sorted by season HR count.", no-plottable banner: `f"has no plottable HRs in {view.season}."`, retry button: "Retry Request".

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Dynamic season constants + tests | 4daa907 | src/mlb_park/config.py, src/mlb_park/pipeline/__init__.py, tests/test_config_season.py |
| 2 | Season selectbox, callback, season threading | 7bca482 | src/mlb_park/app.py, tests/controller/test_callbacks.py |

## Verification

- `python -m pytest tests/ -x -q --tb=short` — 118 passed (110 baseline + 8 new)
- `grep "CURRENT_SEASON = 2026" src/mlb_park/config.py` — 0 matches
- `grep -c "_on_season_change" src/mlb_park/app.py` — 2 matches
- `grep 'options=AVAILABLE_SEASONS' src/mlb_park/app.py` — 1 match

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

None — all functionality fully wired.

## Threat Flags

None — no new network endpoints, auth paths, or trust boundaries introduced. Season value is constrained by `st.selectbox` to `AVAILABLE_SEASONS` list (public year integers). Covered by existing T-7-01 and T-7-02 in plan threat model.

## Self-Check: PASSED

Files created/exist:
- FOUND: src/mlb_park/config.py (modified)
- FOUND: src/mlb_park/app.py (modified)
- FOUND: src/mlb_park/pipeline/__init__.py (modified)
- FOUND: tests/test_config_season.py (created)
- FOUND: tests/controller/test_callbacks.py (modified)

Commits exist:
- FOUND: 4daa907 feat(07-01): dynamic CURRENT_SEASON and AVAILABLE_SEASONS in config.py
- FOUND: 7bca482 feat(07-01): season selectbox, cascade callback, and season threading in app.py
