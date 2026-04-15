---
phase: 4
slug: controller-selectors-ui
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-15
---

# Phase 4 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution. Sourced from `04-RESEARCH.md §Validation Architecture`.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x (already pinned) |
| **Config file** | existing `pyproject.toml` — Phases 1-3 tests run green |
| **Quick run command** | `pytest tests/controller/ -q` |
| **Full suite command** | `pytest tests/ -q` |
| **Manual smoke command** | `streamlit run src/mlb_park/app.py` |
| **Estimated runtime (quick)** | ~1-2 seconds (stub API, no network) |
| **Estimated runtime (full)** | ~3-5 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/controller/ -q` — gates the Phase 4 task.
- **After every wave merge:** Run `pytest tests/ -q` — ensures Phase 1-3 regression coverage holds.
- **Before phase verification:** Full suite green **plus** manual smoke checklist complete.

---

## Phase Requirements → Test Map (Nyquist Dimension 8)

| REQ / Decision | Behavior | Test Type | Test File | Status |
|---|---|---|---|---|
| UX-01 | 30 teams populate Team selectbox; sorted by name | unit | `tests/controller/test_helpers.py::test_sorted_teams` | Wave 0 |
| UX-01 | Cold-start selectbox returns None (no default) | manual smoke | human checklist | N/A |
| UX-02 | Pitchers filtered out; zero-HR hitters included at bottom | unit | `tests/controller/test_helpers.py::test_sorted_hitters_excludes_pitchers` | Wave 0 |
| UX-02 | Sort order `(-homeRuns, fullName)` deterministic | unit | `tests/controller/test_helpers.py::test_sorted_hitters_sort_order` | Wave 0 |
| UX-02 | Missing `position` defaults to non-pitcher with warning log | unit | `tests/controller/test_helpers.py::test_sorted_hitters_missing_position` | Wave 0 |
| UX-03 | After picking Judge on NYY, `venue_id` defaults to Yankee Stadium id | unit (callback shim) | `tests/controller/test_callbacks.py::test_on_player_change_sets_home_venue` | Wave 0 |
| UX-04 | Team-change nulls `player_id` and `venue_id` | unit (callback shim) | `tests/controller/test_callbacks.py::test_on_team_change_nulls_children` | Wave 0 |
| UX-04 | Player-change resets `venue_id` to player's home park | unit (callback shim) | `tests/controller/test_callbacks.py::test_on_player_change_resets_venue` | Wave 0 |
| D-05..D-09 | `build_view(NYY, Judge, YankeeStadium)` happy path | unit (Judge fixture) | `tests/controller/test_build_view.py::test_happy_path` | Wave 0 |
| D-10 / D-25 | 0-HR player → `verdict_matrix is None`, `events == ()` | unit | `tests/controller/test_build_view.py::test_zero_hr_player` | Wave 0 |
| D-10 / D-26 | All-missing-hitData → `verdict_matrix is None`, events non-empty | unit | `tests/controller/test_build_view.py::test_all_missing_hitdata` | Wave 0 |
| D-27 | One feed fails → `errors` non-empty, other HRs still present | unit | `tests/controller/test_build_view.py::test_one_feed_fails` | Wave 0 |
| D-08 | Stadium flip: same (team, player), different `venue_id` → `clears_selected_park` differs | unit | `tests/controller/test_build_view.py::test_stadium_flip` | Wave 0 |
| D-09 | `totals` arithmetic (5 keys) | unit | `tests/controller/test_build_view.py::test_totals` | Wave 0 |
| D-24 | `ViewModel.to_dict()` is JSON-serializable | unit | `tests/controller/test_view_model.py::test_to_dict_json_safe` | Wave 0 |
| D-23 | `build_view` contains no `streamlit` or `session_state` imports | unit (import inspection) | `tests/controller/test_purity.py::test_no_streamlit_in_controller` | Wave 0 |
| D-11 amended | `get_team_hitting_stats` services wrapper returns hydrated roster entries | unit (services layer) | `tests/services/test_team_hitting_stats.py` | Wave 0 |
| Manual | `streamlit run` → NYY → Judge → Yankee Stadium → 6 HRs render with correct columns | manual smoke | human checklist | N/A |

---

## Wave 0 Scaffolding Required

All test infrastructure is new in Phase 4. Wave 0 must land before any `build_view` implementation:

- [ ] `tests/controller/__init__.py`
- [ ] `tests/controller/conftest.py` — extends Phase 3 `StubAPI` with `get_team_hitting_stats` and `get_teams`; provides Judge-preloaded factory
- [ ] `tests/controller/test_build_view.py` — 6 tests per D-29 + stadium-flip + totals
- [ ] `tests/controller/test_callbacks.py` — `_on_team_change` / `_on_player_change` via session_state dict shim (no Streamlit runtime needed)
- [ ] `tests/controller/test_helpers.py` — `_sorted_hitters`, `_sorted_teams`
- [ ] `tests/controller/test_view_model.py` — `ViewModel.to_dict()` JSON round-trip
- [ ] `tests/controller/test_purity.py` — import-inspection guard (D-23)
- [ ] `tests/services/test_team_hitting_stats.py` — new services wrapper unit test

### Synthetic Fixtures (beyond the Judge set)

| Fixture | Purpose | Build approach |
|---|---|---|
| `tests/fixtures/team_stats_empty.json` | D-15 empty-roster guard | Hand-written `{"roster": []}` |
| `tests/fixtures/team_stats_all_pitchers.json` | Edge: only pitchers filtered out | Subset of `team_stats_147_2026.json` keeping only Pitcher entries |
| `tests/fixtures/team_stats_zero_hr_player.json` | 0-HR player drives empty-events path | One roster entry with `splits[0].stat.homeRuns = 0` |
| reuse `tests/pipeline/fixtures/feed_missing_hitdata.json` | all-missing-hitData path | existing |
| reuse `tests/fixtures/team_stats_147_2026.json` | happy path + filter/sort tests | existing (from research) |

None require network.

---

## Manual Smoke Checklist

Run after all automated tests pass. Copy to the Phase 4 HUMAN-UAT.md if any step fails.

- [ ] `streamlit run src/mlb_park/app.py` launches without errors
- [ ] Page title "MLB HR Park Factor Explorer" visible; dev caption below
- [ ] All three selectboxes render with placeholders; no dropdown is pre-selected
- [ ] No HTTP traffic observed before first team selection (verify via terminal logs or browser devtools)
- [ ] Selecting "New York Yankees" populates the Player selectbox with non-pitchers sorted by HR desc
- [ ] Selecting "Aaron Judge" populates Venue selectbox defaulted to "Yankee Stadium"
- [ ] Raw dump renders below with `st.json` (ViewModel) + `st.dataframe` (plottable HRs)
- [ ] Changing team back to "Arizona Diamondbacks" clears player selection (guard `st.info` returns)
- [ ] Picking a different stadium while keeping the same player updates `clears_selected_park` visibly in the JSON/dataframe
- [ ] No Python exceptions in the Streamlit terminal at any point

---

## Nyquist Compliance

Dimension 8 coverage: every UX requirement (UX-01..UX-04) and every load-bearing CONTEXT decision (D-05..D-10, D-17, D-23, D-24, D-25, D-26, D-27) has at least one automated or manual test row. Sampling rate is defined (per-commit quick, per-wave full, per-phase full+smoke). Wave 0 scaffolding is enumerated.

Mark `nyquist_compliant: true` in frontmatter once all Wave 0 items and test rows are implemented.
