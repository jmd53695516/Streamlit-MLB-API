---
phase: 04-controller-selectors-ui
verified: 2026-04-15T19:00:00Z
status: human_needed
score: 5/5 must-haves verified
overrides_applied: 0
human_verification:
  - test: "Launch streamlit run src/mlb_park/app.py and verify UX-01: dropdown lists all 30 MLB teams"
    expected: "Team dropdown renders with placeholder 'Select a team…', contains all 30 MLB teams, no selection on cold start."
    why_human: "Streamlit UI rendering cannot be verified programmatically without a browser; bare-mode import checks AST only."
  - test: "Select New York Yankees and verify UX-02: player dropdown shows non-pitcher hitters sorted by HR count desc"
    expected: "Player dropdown enables after team pick; entries exclude pitchers; Judge/top HR hitter at top; labels include '{name} — {N} HR'."
    why_human: "Observable widget population + sort order require live Streamlit session; unit tests cover _sorted_hitters in isolation but not the selectbox integration."
  - test: "Select Aaron Judge and verify UX-03: stadium dropdown defaults to Yankee Stadium and allows override"
    expected: "On player pick, venue_id auto-sets to 3313 (Yankee Stadium); user can change to any of 30 parks; change sticks (no on_change reset)."
    why_human: "Callback unit tests cover _on_player_change in isolation; full cascading widget flow (on_change firing during rerun) requires live Streamlit runtime."
  - test: "Change Team back and verify UX-04 reset semantics"
    expected: "Switching team clears player_id and venue_id (guard st.info 'Select a team, player, and stadium to begin.' returns); switching player resets venue_id to new player's home park."
    why_human: "Streamlit rerun + session_state interaction can only be observed in a live browser session."
  - test: "With all three selections set, verify raw ViewModel dump renders (controller pipeline end-to-end)"
    expected: "st.subheader('ViewModel (raw)') followed by st.json(view.to_dict()); when plottable_events non-empty, st.subheader('Plottable HRs') + st.dataframe with 6 columns (game_date, opponent_abbr, distance_ft, launch_speed, launch_angle, clears_selected)."
    why_human: "End-to-end rendering requires live API + Streamlit runtime; automated checks confirm the code path exists and parses but cannot visually validate the rendered output."
---

# Phase 4: Controller & Selectors UI Verification Report

**Phase Goal:** Thinnest Streamlit app that proves the three cascading selectors + ViewModel pipeline work end-to-end, rendering a raw JSON/dataframe dump (deferring the chart).
**Verified:** 2026-04-15T19:00:00Z
**Status:** human_needed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | User can select any of the 30 MLB teams from a dropdown. | ✓ VERIFIED (code path) | `src/mlb_park/app.py:60-73` — `st.selectbox("Team", options=team_options, ...)` populated via `controller._sorted_teams(get_teams())`; full suite green incl. `_sorted_teams` tests. Live widget rendering deferred to human. |
| 2 | After selecting a team, player dropdown shows non-pitcher hitters sorted by current-season HR count desc. | ✓ VERIFIED (code path) | `app.py:77-104` — gated by `if team_id is not None`; uses `controller._sorted_hitters(get_team_hitting_stats(team_id, CURRENT_SEASON))`. `_sorted_hitters` tests (9) cover pitcher-exclusion + `(-homeRuns, fullName)` sort + D-12/D-13 fallbacks. |
| 3 | After selecting a player, stadium dropdown defaults to player's home park; user can override to any of 30 parks. | ✓ VERIFIED (code path) | `app.py:_on_player_change` (lines 38-51) writes `session_state["venue_id"] = team["venue"]["id"]`; stadium selectbox (`app.py:120-130`) has NO `on_change` (manual override sticks per UI-SPEC). Covered by `test_on_player_change_sets_home_venue`. |
| 4 | Changing team clears player; changing player resets stadium to player's home park (via st.session_state). | ✓ VERIFIED | `_on_team_change` nulls `player_id` + `venue_id` (test_on_team_change_nulls_children pass); `_on_player_change` sets `venue_id` to team's venue.id (test_on_player_change_sets_home_venue pass); no-op defensive branch covered. |
| 5 | Raw ViewModel dump (JSON or dataframe) renders below the selectors. | ✓ VERIFIED (code path) | `app.py:140-192` — `controller.build_view(team_id, player_id, venue_id)` invoked when all 3 IDs set, then `st.subheader("ViewModel (raw)") + st.json(view.to_dict())` and optional `st.dataframe` with 6 locked columns. 7 `build_view` tests exercise the pipeline composition end-to-end. |

**Score:** 5/5 truths verified (automated code-path checks). Live UI walkthrough deferred to human verifier.

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `src/mlb_park/controller.py` | ViewModel + build_view + helpers | ✓ VERIFIED | 351 LOC; contains `class ViewModel`, `build_view`, `_sorted_teams`, `_sorted_hitters`, `_hr_of`, `_name_of`, `_clears_for_venue`, `_compute_totals`, `to_dict`. No `import streamlit` (purity test passes). |
| `src/mlb_park/app.py` | Full UI shell | ✓ VERIFIED | 192 LOC; three selectboxes with exact UI-SPEC copy, `_on_team_change` + `_on_player_change` callbacks, guard `st.info`, error warning, empty-state banners, raw JSON + dataframe render. Imports cleanly (`python -c "import mlb_park.app"` succeeds with expected bare-mode warning). |
| `src/mlb_park/services/mlb_api.py` | get_team_hitting_stats wrapper | ✓ VERIFIED | `get_team_hitting_stats` + `_raw_team_hitting_stats` present (3 grep hits); decorated `@st.cache_data(ttl="1h")` per D-14. |
| `src/mlb_park/pipeline/__init__.py` | load_parks re-export | ✓ VERIFIED | `load_parks` importable from `mlb_park.pipeline` (D-02 single-import-origin). |
| `tests/controller/test_callbacks.py` | 3 callback tests | ✓ VERIFIED | 3 tests (nulls_children, sets_home_venue, no_team_selected_is_noop); all pass. Patch target `mlb_park.app.get_teams` correctly bypasses `@st.cache_data`. |
| `tests/controller/test_build_view.py` | 7 D-29 cases | ✓ VERIFIED | 7 tests present; all pass. |
| `tests/controller/test_helpers.py` | 9 sort/filter tests | ✓ VERIFIED | All pass. |
| `tests/controller/test_purity.py` | D-23 no-streamlit guard | ✓ VERIFIED | All pass; controller.py has only docstring mentions of streamlit, no imports. |
| `tests/controller/test_view_model.py` | JSON round-trip + frozen | ✓ VERIFIED | 5 tests pass. |
| `tests/fixtures/team_stats_{empty,all_pitchers,zero_hr_player}.json` | 3 synthetic fixtures | ✓ VERIFIED | All 3 present on disk. |

### Key Link Verification

| From | To | Via | Status | Details |
|------|-----|-----|--------|---------|
| `src/mlb_park/app.py` | `mlb_park.controller.build_view` | Function call guarded by three non-None IDs | ✓ WIRED | `app.py:140` — `view = controller.build_view(team_id, player_id, venue_id)` inside the `else` branch of the guard. |
| `src/mlb_park/app.py::_on_player_change` | `st.session_state["venue_id"]` | Lookup of team's venue.id from cached get_teams() | ✓ WIRED | `app.py:51` — `st.session_state["venue_id"] = team["venue"]["id"]`. |
| `src/mlb_park/controller.py::build_view` | `mlb_park.pipeline.extract_hrs` | api-injected call | ✓ WIRED | `controller.py:301` — `result = extract_hrs(player_id, season=season, api=api)`. |
| `src/mlb_park/controller.py::build_view` | `mlb_park.pipeline.compute_verdict_matrix` | Called with hr_event_to_hit_data-adapted plottable events | ✓ WIRED | `controller.py:316` — `matrix = compute_verdict_matrix(hit_data_list, park_objs)`. |
| `src/mlb_park/controller.py` | `mlb_park.pipeline` | imports HREvent, HitData, PipelineError, CURRENT_SEASON, load_parks | ✓ WIRED | `controller.py:20-31` — single import block via pipeline (D-02). |
| `tests/controller/conftest.py` | `tests/pipeline/conftest.py::StubAPI` | subclass pattern | ✓ WIRED | ControllerStubAPI subclasses Phase 3 StubAPI (per 04-01-SUMMARY). |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|---------------------|--------|
| `app.py` (team selectbox) | `team_options` | `controller._sorted_teams(get_teams())` | Yes — `get_teams()` calls statsapi.mlb.com via cached wrapper; tests confirm sorted pass-through | ✓ FLOWING |
| `app.py` (player selectbox) | `player_options` | `controller._sorted_hitters(get_team_hitting_stats(...))` | Yes — live API roster; conditional on `team_id is not None` (D-18) | ✓ FLOWING |
| `app.py` (stadium selectbox) | `venue_options` | `load_all_parks()` | Yes — returns `dict[int, dict]` of all 30 MLB venues | ✓ FLOWING |
| `app.py` (JSON dump) | `view` | `controller.build_view(team_id, player_id, venue_id)` | Yes — composes extract_hrs + compute_verdict_matrix; 7 build_view tests prove non-empty real outputs | ✓ FLOWING |
| `app.py` (dataframe rows) | `rows` | Iterated from `view.plottable_events` zipped with `view.clears_selected_park` | Yes — HREvent attributes populated per pipeline tests | ✓ FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Full test suite green | `pytest tests/ -q` | 95 passed | ✓ PASS |
| Controller suite green | `pytest tests/controller/ tests/services/test_team_hitting_stats.py -q` | 30 passed | ✓ PASS |
| app.py imports cleanly | `python -c "import mlb_park.app"` | imports with expected bare-mode warnings only | ✓ PASS |
| Controller has no streamlit import | `grep -n "streamlit\|session_state" src/mlb_park/controller.py` | 3 docstring mentions only (no imports/runtime refs) | ✓ PASS |
| load_parks re-export works | covered by `from mlb_park.pipeline import load_parks` in controller.py | imports without error | ✓ PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| UX-01 | 04-02, 04-03 | User can select a team from a dropdown of all 30 MLB teams | ✓ SATISFIED | `_sorted_teams` implemented + tested; Team selectbox wired in app.py:64-73 populated from `get_teams()`. Live 30-team render deferred to human. |
| UX-02 | 04-02, 04-03 | Player selector filtered to non-pitchers, sorted by HR count desc | ✓ SATISFIED | `_sorted_hitters` implements D-12 pitcher filter + D-13 (-HR, name) sort; 9 helper tests pass; Player selectbox wired app.py:94-104 using `_sorted_hitters(get_team_hitting_stats(...))`. |
| UX-03 | 04-03 | Stadium selector defaults to player's home stadium | ✓ SATISFIED | `_on_player_change` sets `venue_id = team["venue"]["id"]` (app.py:51); test_on_player_change_sets_home_venue passes. Manual override allowed (no on_change on stadium selectbox). |
| UX-04 | 04-03 | Changing Team resets Player; changing Player resets stadium | ✓ SATISFIED | `_on_team_change` nulls player_id + venue_id (app.py:32-35; test_on_team_change_nulls_children); `_on_player_change` writes home venue_id. |

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| — | — | None | — | Clean. No TODO/FIXME/placeholder/return-null stubs in controller.py or app.py. No hardcoded empty defaults flowing to render. |

### Human Verification Required

See `human_verification:` frontmatter. Five items cover the manual-smoke checklist from 04-03-SUMMARY / VALIDATION.md §Manual Smoke Checklist. Streamlit live UI + full cascading widget flow + real-time session_state rerun behavior cannot be programmatically verified.

### Gaps Summary

No automated gaps. All five Success Criteria have verifiable code paths, all four requirements (UX-01..UX-04) are satisfied by tested implementation, the full test suite passes (95/95), and the app module imports cleanly. The phase's stated goal ("raw JSON/dataframe dump proving the controller pipeline is wired end-to-end") is structurally achieved in code; the only remaining verification is a live browser walkthrough, which Claude cannot perform.

**LOC note:** controller.py = 351 raw / 205 code-only (D-21 soft-cap of 200 exceeded by 5); documented and declined in 04-02-SUMMARY — informational only, not a gap.

---

_Verified: 2026-04-15T19:00:00Z_
_Verifier: Claude (gsd-verifier)_
