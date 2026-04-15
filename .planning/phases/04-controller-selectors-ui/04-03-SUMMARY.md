---
phase: 04-controller-selectors-ui
plan: 03
subsystem: ui
tags: [streamlit, ui-shell, callbacks, selectors]
requirements: [UX-01, UX-02, UX-03, UX-04]
dependency-graph:
  requires:
    - mlb_park.controller.build_view              (Plan 04-02)
    - mlb_park.controller._sorted_teams           (Plan 04-02)
    - mlb_park.controller._sorted_hitters         (Plan 04-02)
    - mlb_park.controller._hr_of                  (Plan 04-02)
    - mlb_park.services.mlb_api.get_teams         (Phase 1)
    - mlb_park.services.mlb_api.get_team_hitting_stats (Plan 04-01)
    - mlb_park.services.mlb_api.load_all_parks    (Phase 1)
    - mlb_park.pipeline.CURRENT_SEASON
  provides:
    - mlb_park.app (Streamlit entry point — full UI shell)
    - mlb_park.app._on_team_change   (UX-04 callback)
    - mlb_park.app._on_player_change (UX-03 callback)
  affects:
    - Phase 5 (Plotly chart) — will replace the raw st.dataframe block
    - Phase 6 (polish) — will add spinners, retry, summary metrics
tech-stack:
  added: []
  patterns:
    - on_change callbacks reading/writing st.session_state via dict-shim friendly API
    - cascading no-fetch-before-selection (D-18) — gated module-level fetches
    - controller helper composition (_sorted_teams, _sorted_hitters, _hr_of) reused inside option-builder code
key-files:
  created:
    - tests/controller/test_callbacks.py
    - .planning/phases/04-controller-selectors-ui/04-03-SUMMARY.md
  modified:
    - src/mlb_park/app.py (Phase 1 placeholder → full UI shell, +189 / -2)
decisions:
  - Player option label uses `controller._hr_of(entry)` (the existing private helper) rather than re-walking `person.stats[0].splits[0].stat.homeRuns` inline. Keeps the HR-extraction defensive logic (D-13 fallback for missing stats) in one place. The plan's example used inline access; switching to `_hr_of` is a strict generalization (same output, fewer KeyError surfaces).
  - `_on_player_change` no-team-selected branch returns silently (no log, no exception) per the plan's defensive intent. A third unit test guards the no-op contract.
  - LOC: src/mlb_park/app.py = 192 lines (raw, includes module docstring + comments). Single-file shell appropriate for Phase 4; splits into views/ would be premature ahead of Phase 5's chart introduction.
metrics:
  duration: ~15 min
  completed: 2026-04-15
  tasks_completed: 3
  tests_added: 3 (callback shim suite)
  full_suite: 95 passed
---

# Phase 04 Plan 03: Controller & Selectors UI Shell Summary

**One-liner:** Replaced the Phase 1 placeholder `app.py` with the full Streamlit UI shell — three cascading Team → Player → Stadium selectboxes wired to `controller.build_view`, with `on_change` callbacks for the UX-03/UX-04 reset semantics, all empty-state copy from UI-SPEC §State messages, and a 3-test session-state dict-shim suite covering both callbacks (95/95 full suite green, no third-party Streamlit components introduced).

## Commits

| Task | Commit    | Message |
|------|-----------|---------|
| 1 RED   | `2fa7b76` | `test(04-03): add failing tests for app.py on_change callbacks` |
| 2 GREEN | `9cdb093` | `feat(04-03): wire Streamlit UI shell with cascading Team/Player/Stadium selectors` |

## app.py Structure

Top-to-bottom in `src/mlb_park/app.py`:

1. Module docstring locking the Phase 4 scope (raw dump, no chart, no polish) and the D-18/D-23 invariants.
2. Imports — `pandas`, `streamlit as st`, `controller`, `CURRENT_SEASON`, three services functions.
3. **Callbacks** (defined before any widget so `on_change=` references resolve):
   - `_on_team_change()` — sets `session_state["player_id"] = None` and `session_state["venue_id"] = None`.
   - `_on_player_change()` — looks up the selected team's `venue.id` from `get_teams()` (cached) and writes it to `session_state["venue_id"]`. Defensive no-op when `team_id is None`.
4. **Page chrome** — `st.title("MLB HR Park Factor Explorer")` + `st.caption("Phase 4 — raw ViewModel dump. Chart arrives in Phase 5.")`.
5. **Team selectbox** — always populated from `controller._sorted_teams(get_teams())`. `index=None`, placeholder, help text, format_func from UI-SPEC, `on_change=_on_team_change`.
6. **Player selectbox** — populated only when `team_id is not None` (D-18). Uses `controller._sorted_hitters(get_team_hitting_stats(team_id, CURRENT_SEASON))`. Disabled while team is unset.
7. **Stadium selectbox** — populated only when `player_id is not None` (D-18). Uses `load_all_parks()` sorted by venue name. **No `on_change`** — manual override sticks (UI-SPEC).
8. `st.divider()`.
9. **Render region** — guard `st.info("Select a team, player, and stadium to begin.")` until all three IDs are set; otherwise call `controller.build_view(team_id, player_id, venue_id)` then render:
   - `st.warning("{n} game feed{s} failed to fetch; …")` when `view.errors` (singular/plural per D-27).
   - `st.info(f"{view.player_name} has no home runs in {view.season}.")` when `events` is empty (D-25).
   - `st.info("No HRs have hitData …")` when `events` non-empty but `plottable_events` empty (D-26).
   - `st.subheader("ViewModel (raw)")` + `st.json(view.to_dict())` always.
   - `st.subheader("Plottable HRs")` + `st.dataframe(pd.DataFrame(rows), use_container_width=True)` when `plottable_events` non-empty. Six columns in the locked order: `game_date`, `opponent_abbr`, `distance_ft`, `launch_speed`, `launch_angle`, `clears_selected`.

## Callback Wiring (D-30 Test Strategy)

Both callbacks read/write `st.session_state` and otherwise do no Streamlit-runtime work, so the unit suite swaps `st.session_state` with a plain dict via `monkeypatch.setattr("mlb_park.app.st.session_state", fake_state)` — Streamlit's `SessionState` is dict-like.

**Critical patch target:** `mlb_park.app.get_teams` (NOT `mlb_park.services.mlb_api.get_teams`). The callback resolves `get_teams` by the local name bound in `app.py`'s namespace at import time; patching the services module would not intercept it. Replacing the whole callable also fully bypasses the `@st.cache_data` wrapper.

| Test | Assertion |
|------|-----------|
| `test_on_team_change_nulls_children` | After `_on_team_change()`, `session_state["player_id"] is None` and `session_state["venue_id"] is None`; `team_id` untouched. |
| `test_on_player_change_sets_home_venue` | With NYY (id=147, venue.id=3313) in stub `get_teams()`, `_on_player_change()` sets `session_state["venue_id"] == 3313`. |
| `test_on_player_change_no_team_selected_is_noop` | When `team_id is None`, callback does NOT raise and does NOT call `get_teams` (an `AssertionError`-raising stub gates this). `venue_id` stays `None`. |

## D-18 No-Fetch-Before-Selection Audit (Source Inspection)

| Cold-start condition | Function call | Gated? |
|----------------------|---------------|--------|
| All three IDs `None`     | `get_teams()`              | NO  — required to populate Team selectbox (intentional, per UI-SPEC) |
| All three IDs `None`     | `get_team_hitting_stats()` | YES — guarded by `if team_id is not None:` |
| All three IDs `None`     | `load_all_parks()`         | YES — guarded by `if player_id is not None:` |
| All three IDs `None`     | `controller.build_view()`  | YES — guarded by `if team_id is None or player_id is None or venue_id is None:` |

This satisfies CLAUDE.md's "no hammering the API, aggressive caching" posture.

## HREvent Field Names — Used Verbatim

The dataframe row builder accesses `ev.game_date`, `ev.opponent_abbr`, `ev.distance_ft`, `ev.launch_speed`, `ev.launch_angle`. These are the **real** attribute names verified in `src/mlb_park/pipeline/events.py` (the plan called out `distance_ft` specifically — no `total_distance` adaptation needed). Zero adapter shims.

## Verification

| Check | Command | Result |
|-------|---------|--------|
| Callback suite               | `pytest tests/controller/test_callbacks.py -q` | **3 passed** |
| Full suite                   | `pytest tests/ -q`                              | **95 passed** |
| AST parse                    | `python -c "import ast; ast.parse(open('src/mlb_park/app.py').read())"` | OK |
| Module import (bare-mode)    | `python -c "import mlb_park.app"`               | Imports successfully (4× `missing ScriptRunContext` warnings expected and ignorable per Streamlit docs) |
| Forbidden-pattern grep       | `grep -E "streamlit_extras\|unsafe_allow_html\|cache_data\|st.tabs\|st.expander\|st.sidebar" src/mlb_park/app.py` | 0 matches each |
| LOC                          | `wc -l src/mlb_park/app.py`                     | 192 |

## Manual Smoke Status

**Pending — requires human browser verification.** Per Plan 04-03 Task 3 step 3, headless Streamlit launch from a Bash tool call on Windows is not portably reliable, and Claude can't drive a browser. The automated gates above (callback suite, full suite, AST parse, bare-mode module import) confirm the app loads and executes its top-level widget calls without raising; the formal end-to-end UI walkthrough is the orchestrator-owned phase verify gate (`.planning/phases/04-controller-selectors-ui/04-VALIDATION.md §Manual Smoke Checklist`).

The checklist to be run by the human verifier:

- [ ] `streamlit run src/mlb_park/app.py` launches without errors
- [ ] Page title "MLB HR Park Factor Explorer" visible; dev caption below
- [ ] All three selectboxes render with placeholders; no dropdown is pre-selected
- [ ] No HTTP traffic observed before first team selection
- [ ] Selecting "New York Yankees" populates Player selectbox sorted by HR desc
- [ ] Selecting "Aaron Judge" populates Venue selectbox defaulted to "Yankee Stadium"
- [ ] Raw dump renders below with `st.json` (ViewModel) + `st.dataframe` (plottable HRs)
- [ ] Changing team back to "Arizona Diamondbacks" clears player/venue (guard `st.info` returns)
- [ ] Picking a different stadium (same player) updates `clears_selected_park` in JSON/dataframe
- [ ] No Python exceptions in the Streamlit terminal at any point

## Deviations from Plan

### 1. [Rule 2 — Critical functionality] Use `controller._hr_of` for player labels

- **Found during:** Task 2 implementation
- **Issue:** The plan's reference snippet built the player label by inlining `(e.get("person", {}).get("stats") or [{}])[0].get("splits", [{}])[0].get("stat", {}).get("homeRuns", 0)`. The exact same defensive walk already exists in `mlb_park.controller._hr_of` (Plan 04-02), which additionally coerces non-int strings safely via `int(raw or 0)` in a try/except.
- **Fix:** Replaced the inline walk with `controller._hr_of(e)`. Output is identical for clean fixtures and strictly more robust against the malformed-stats edge case the helper was designed for (D-13).
- **Files modified:** `src/mlb_park/app.py`
- **Commit:** `9cdb093`

## Success Criteria

- [x] `src/mlb_park/app.py` replaces the placeholder with the full UI shell per UI-SPEC (exact copy, locked widget order, callback wiring).
- [x] `_on_team_change` and `_on_player_change` pass the three shim-based tests (patch target `mlb_park.app.get_teams`, full-callable swap bypasses cache).
- [x] Cold start fires only `get_teams()` — verified by source-level guard inspection.
- [x] Guard `st.info` renders until all three IDs are set; `build_view` is not called before that.
- [x] All three empty-state variants render the exact UI-SPEC copy when their conditions hold.
- [x] Raw dump = `st.subheader("ViewModel (raw)")` + `st.json(view.to_dict())`, then optional `st.subheader("Plottable HRs")` + `st.dataframe(...)` with the 6 locked column names.
- [x] Dataframe uses HREvent's real `distance_ft` field (no adaptation needed).
- [x] Full test suite green (95/95).
- [x] Manual smoke checklist documented in SUMMARY (pending-human form per plan Task 3 step 2).
- [x] No `streamlit-extras`, `unsafe_allow_html`, `@st.cache_data`, `st.tabs`, `st.expander`, or `st.sidebar` introduced.

## Known Stubs

None. Plan 04-03 closes Phase 4's UI loop end-to-end. The deliberately-deferred items (chart, spinner, retry button, summary metrics card, conditional row coloring) are Phase 5/6 scope and explicitly enumerated in UI-SPEC §"What Is Intentionally Unstyled".

## Self-Check: PASSED

Files verified on disk:
- `src/mlb_park/app.py` FOUND (192 LOC, full UI shell)
- `tests/controller/test_callbacks.py` FOUND (3 tests)
- `.planning/phases/04-controller-selectors-ui/04-03-SUMMARY.md` FOUND (this file)

Commits verified (via `git log --oneline 21a39c5..HEAD`):
- `2fa7b76` FOUND — `test(04-03): add failing tests for app.py on_change callbacks`
- `9cdb093` FOUND — `feat(04-03): wire Streamlit UI shell with cascading Team/Player/Stadium selectors`
