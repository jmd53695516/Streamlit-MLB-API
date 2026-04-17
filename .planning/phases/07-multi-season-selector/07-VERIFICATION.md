---
phase: 07-multi-season-selector
verified: 2026-04-16T20:38:00Z
status: human_needed
score: 5/5 must-haves verified
overrides_applied: 0
human_verification:
  - test: "Open the app locally (`streamlit run src/mlb_park/app.py`), confirm the Season selectbox appears at the top before the Team selectbox, defaulting to the current year (2026)."
    expected: "Season selectbox visible, shows 2026 as default, lists 5 years descending (2026, 2025, 2024, 2023, 2022)."
    why_human: "Streamlit widget rendering and visual ordering cannot be verified without running the app."
  - test: "Select a team and player, then change the Season selectbox to a different year."
    expected: "Team, Player, and Stadium selectors all reset to empty/None; page reloads with the new season."
    why_human: "Cascade reset behavior requires live Streamlit session state interaction."
  - test: "Select a past season (e.g., 2024), choose the Yankees, and confirm Aaron Judge appears in the player list."
    expected: "Player list shows full-season roster including players who may have been traded or are no longer active."
    why_human: "Requires live MLB StatsAPI network call to confirm rosterType=fullSeason returns the correct historical players."
---

# Phase 7: Multi-Season Selector Verification Report

**Phase Goal:** Users can explore any MLB season from 2022 onward, with the app correctly fetching and caching season-specific rosters and HR data
**Verified:** 2026-04-16T20:38:00Z
**Status:** human_needed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths (from ROADMAP Success Criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | User sees a season selectbox defaulting to current year; selecting a past year reloads data for that season | VERIFIED (automated) / ? (runtime) | `st.selectbox("Season", options=AVAILABLE_SEASONS, key="season", index=0)` in app.py line 66-73; `season = st.session_state.get("season", CURRENT_SEASON)` at line 75; `get_team_hitting_stats(team_id, season)` line 99; `build_view(..., season=season)` line 161. Runtime rendering needs human. |
| 2 | Changing the season resets the player and stadium selectors so stale selections cannot carry over | VERIFIED | `_on_season_change()` nulls `team_id`, `player_id`, `venue_id`; `test_on_season_change_nulls_all_three_children` passes. |
| 3 | A player who was traded or retired in a past season appears in the roster for that year | VERIFIED (code) / ? (live data) | `_raw_team_hitting_stats` uses `rosterType=fullSeason` when `season < CURRENT_SEASON` (mlb_api.py line 116); tests pass; live data requires human. |
| 4 | Switching to a past season fetches cached responses with 30d TTL; switching back to current season uses 1h TTL | VERIFIED | `get_game_log_historical` (ttl="30d"), `get_game_log_current` (ttl=TTL_GAMELOG="1h"); `get_team_hitting_stats_historical` (ttl="30d"), `get_team_hitting_stats_current` (ttl=TTL_GAMELOG); dispatch via `season < CURRENT_SEASON`; all 6 dispatch tests pass. |
| 5 | The game-feed cache is bounded and does not exhaust Streamlit Community Cloud memory on a cold load of a high-HR player | VERIFIED | `@st.cache_data(ttl="30d", max_entries=200)` on `get_game_feed` (mlb_api.py line 200); `test_game_feed_has_max_entries_200` and `test_game_feed_ttl_is_30d` pass. |

**Score:** 5/5 truths verified (3 with human runtime confirmation needed)

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `src/mlb_park/config.py` | Dynamic CURRENT_SEASON and AVAILABLE_SEASONS | VERIFIED | `_current_season()` defined at line 35; `CURRENT_SEASON: int = _current_season()` at line 40; `AVAILABLE_SEASONS: list[int]` at line 41; hardcoded `= 2026` removed. |
| `src/mlb_park/app.py` | Season selectbox + cascade callback + season-threaded downstream calls | VERIFIED | `_on_season_change()` defined line 32; selectbox at line 66-73; `season` variable line 75; all downstream calls use `season`. |
| `src/mlb_park/pipeline/__init__.py` | Re-exports AVAILABLE_SEASONS | VERIFIED | `from mlb_park.config import AVAILABLE_SEASONS, CURRENT_SEASON` at line 14; `"AVAILABLE_SEASONS"` in `__all__` at line 35. |
| `src/mlb_park/services/mlb_api.py` | Conditional rosterType, two-function TTL split, max_entries cap | VERIFIED | All four split functions defined; dispatcher logic present; `max_entries=200`; `ttl="30d"` on 3 functions. |
| `tests/test_config_season.py` | Unit tests for dynamic season computation | VERIFIED | 7 tests present; all pass. |
| `tests/controller/test_callbacks.py` | Unit test for _on_season_change callback | VERIFIED | `test_on_season_change_nulls_all_three_children` at line 59; passes. |
| `tests/services/test_mlb_api_season.py` | Tests for TTL dispatcher routing and max_entries | VERIFIED | 8 tests present; all pass. |
| `tests/services/test_team_hitting_stats.py` | Extended test for historical roster type | VERIFIED | `test_historical_season_uses_full_season_roster_type` at line 91; passes. |
| `scripts/test_historical_roster.py` | Live API validation script for rosterType=fullSeason | VERIFIED | File exists; validates NYY 2024 with `rosterType=fullSeason` and hydration; requires network to execute. |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `src/mlb_park/app.py` | `src/mlb_park/config.py` | `from mlb_park.config import AVAILABLE_SEASONS` | WIRED | Line 20: `from mlb_park.config import AVAILABLE_SEASONS, CURRENT_SEASON` |
| `src/mlb_park/app.py` | `src/mlb_park/controller.py` | `build_view` call with `season=` kwarg | WIRED | Line 161: `view = controller.build_view(team_id, player_id, venue_id, season=season)` |
| `get_game_log` dispatcher | `get_game_log_historical` | `season < CURRENT_SEASON` check | WIRED | Lines 169-172; confirmed by test_get_game_log_historical_dispatches_correctly |
| `get_team_hitting_stats` dispatcher | `get_team_hitting_stats_historical` | `season < CURRENT_SEASON` check | WIRED | Lines 194-197; confirmed by test_get_team_hitting_stats_historical_dispatches_correctly |
| `_raw_team_hitting_stats` | statsapi.mlb.com roster endpoint | conditional `rosterType` param | WIRED | Line 116: `roster_type = "active" if season >= CURRENT_SEASON else "fullSeason"` |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|-------------------|--------|
| `app.py` player selectbox | `roster` from `get_team_hitting_stats(team_id, season)` | dispatcher → `_raw_team_hitting_stats` → MLB StatsAPI `/teams/{id}/roster` | Yes (live API + cache) | FLOWING |
| `app.py` build_view call | `season` from `st.session_state.get("season", CURRENT_SEASON)` | Season selectbox widget binding | Yes (widget state) | FLOWING |
| `app.py` HR count/chart | `view` from `controller.build_view(..., season=season)` | game log pipeline using selected season | Yes (passes season through) | FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| CURRENT_SEASON not hardcoded | `grep "CURRENT_SEASON = 2026" src/mlb_park/config.py` | 0 matches | PASS |
| _on_season_change defined + used | `grep -c "_on_season_change" src/mlb_park/app.py` | 2 | PASS |
| Season selectbox uses AVAILABLE_SEASONS | `grep 'options=AVAILABLE_SEASONS' src/mlb_park/app.py` | 1 match | PASS |
| fullSeason in mlb_api | `grep -c "fullSeason" src/mlb_park/services/mlb_api.py` | 3 matches | PASS |
| max_entries=200 in mlb_api | `grep -c "max_entries=200" src/mlb_park/services/mlb_api.py` | 1 match | PASS |
| Two dispatcher season checks | `grep -c "season < CURRENT_SEASON" src/mlb_park/services/mlb_api.py` | 2 matches | PASS |
| 30d TTL on 3 functions | `grep -c 'ttl="30d"' src/mlb_park/services/mlb_api.py` | 3 matches | PASS |
| Full test suite | `python -m pytest tests/ -x -q` | 127 passed | PASS |
| Season-specific tests | `python -m pytest tests/test_config_season.py tests/controller/test_callbacks.py tests/services/test_mlb_api_season.py tests/services/test_team_hitting_stats.py` | 24 passed | PASS |
| get_team_hitting_stats uses season var | `grep "get_team_hitting_stats(team_id, season)" src/mlb_park/app.py` | 1 match | PASS |
| build_view uses season kwarg | `grep "season=season" src/mlb_park/app.py` | 1 match | PASS |
| Retry button text | `grep "Retry Request" src/mlb_park/app.py` | 1 match | PASS |
| Player help copy updated | `grep "sorted by season HR count" src/mlb_park/app.py` | 1 match | PASS |
| No-plottable banner uses view.season | `grep "plottable HRs in {view.season}" src/mlb_park/app.py` | 1 match | PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| SEASON-01 | 07-01-PLAN.md | User can select any MLB season from the past 5 years via a selectbox | SATISFIED | `st.selectbox("Season", options=AVAILABLE_SEASONS, key="season", index=0)` in app.py; `AVAILABLE_SEASONS` = 5-year descending list from `CURRENT_SEASON` |
| SEASON-02 | 07-01-PLAN.md | Changing the season resets the player and stadium selectors | SATISFIED | `_on_season_change()` nulls `team_id`, `player_id`, `venue_id`; `on_change=_on_season_change` wired to selectbox |
| SEASON-03 | 07-02-PLAN.md | Historical seasons use fullSeason roster so traded/retired players appear | SATISFIED | `roster_type = "active" if season >= CURRENT_SEASON else "fullSeason"` in `_raw_team_hitting_stats`; 3 tests confirm |
| SEASON-04 | 07-02-PLAN.md | Past-season API responses cached with 30d TTL; current season retains 1h TTL | SATISFIED | `get_game_log_historical` (ttl="30d"), `get_team_hitting_stats_historical` (ttl="30d"); dispatchers route on `season < CURRENT_SEASON`; 4 dispatch tests confirm |
| SEASON-05 | 07-02-PLAN.md | Game feed cache capped at max_entries to prevent OOM on Community Cloud | SATISFIED | `@st.cache_data(ttl="30d", max_entries=200)` on `get_game_feed`; 2 tests confirm |

No orphaned requirements: REQUIREMENTS.md maps SEASON-01 through SEASON-05 to Phase 7, and both plans claim all 5. All 5 are accounted for and satisfied.

### Anti-Patterns Found

| File | Pattern | Severity | Impact |
|------|---------|----------|--------|
| `src/mlb_park/app.py` lines 88/118/144 | `placeholder=` kwarg on selectboxes | Info | Legitimate Streamlit UI hint text — not a stub. No impact. |

No blockers or warnings found.

### Human Verification Required

#### 1. Season Selectbox Visual Rendering

**Test:** Run `streamlit run src/mlb_park/app.py` and observe the initial page layout.
**Expected:** Season selectbox renders at the top of the page, before Team, defaulting to 2026. Dropdown shows exactly 5 options: 2026, 2025, 2024, 2023, 2022.
**Why human:** Streamlit widget rendering and visual layout order cannot be verified without running the app in a browser.

#### 2. Season Change Cascade Reset (Live Session)

**Test:** In the running app, select any team and player, then change the Season selectbox to a different year.
**Expected:** Team, Player, and Stadium selectors immediately reset to their placeholder/empty state. The page reloads with the new season active and the team list still populated.
**Why human:** Cascade reset behavior depends on live Streamlit session state and widget re-render cycle, which cannot be simulated in unit tests.

#### 3. Historical Roster Completeness (Live API)

**Test:** Select season 2024, pick the New York Yankees, open the Player selectbox.
**Expected:** Players who were on the 2024 Yankees roster (including traded/DFA'd players) appear in the list — not just the current active roster.
**Why human:** Requires a live network call to `statsapi.mlb.com` with `rosterType=fullSeason&season=2024` to confirm the roster contains historical players. The code logic and unit tests confirm the conditional parameter is set correctly, but the API response content requires a human with network access to verify.

### Gaps Summary

No automated gaps found. All 5 SEASON requirements are satisfied in the codebase. All 127 tests pass. The 3 human verification items above are runtime/network behaviors that cannot be verified statically — they do not indicate code defects, but do require a human to confirm end-to-end behavior with the live app and live API.

---

_Verified: 2026-04-16T20:38:00Z_
_Verifier: Claude (gsd-verifier)_
