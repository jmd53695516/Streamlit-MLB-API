---
phase: 06-summary-rankings-polish
verified: 2026-04-16T01:26:00Z
status: human_needed
score: 6/6 must-haves verified
overrides_applied: 0
human_verification:
  - test: "Run `streamlit run src/mlb_park/app.py`, select a team/player/stadium, and verify that 4 st.metric widgets appear above the spray chart showing Total HRs, Avg Parks Cleared, No-Doubters, and Cheap HRs with real computed values."
    expected: "4 metric tiles visible with non-zero values for an active HR hitter (e.g., Shohei Ohtani)"
    why_human: "st.metric rendering and widget layout cannot be verified without a running Streamlit server"
  - test: "In the running app, after loading a player's data, open the 'Park Rankings' expander. Verify all 30 parks appear sorted by Clears descending, with the top 3 rows tinted green and the bottom 3 rows tinted red."
    expected: "Collapsible table with 30 rows; top 3 have green background, bottom 3 have red background"
    why_human: "Pandas Styler row-highlighting and Streamlit dataframe rendering cannot be verified without a browser"
  - test: "Disconnect from network (or temporarily route statsapi.mlb.com to 127.0.0.1), then load the app and select a player. Verify the spinner appears and then a friendly error message ('Could not load data...') with a 'Retry' button is shown."
    expected: "st.spinner visible during fetch attempt; st.error with exception type in parentheses; 'Retry' button present"
    why_human: "Spinner visibility and error-path rendering require a live Streamlit session with induced API failure"
---

# Phase 6: Summary, Rankings & Polish Verification Report

**Phase Goal:** Ship v1 — summary metrics card, best/worst parks ranking, loading spinners, friendly error messages. Complete the user-observable surface.
**Verified:** 2026-04-16T01:26:00Z
**Status:** human_needed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | A summary card (`st.metric`) displays total HRs, average parks cleared (of 30), count of no-doubters (30/30), and count of cheap HRs (<=5/30) | VERIFIED | `app.py:162-166`: `st.columns(4)`, four `col.metric()` calls wired to `view.totals['avg_parks_cleared']`, `view.totals['no_doubters']`, `view.totals['cheap_hrs']` |
| 2 | A "best and worst parks" section ranks all 30 parks and highlights top 3 green / bottom 3 red | VERIFIED | `app.py:188-207`: `st.expander("Park Rankings")`, `ranking_df.style.apply(_highlight_top_bottom)`, rgba(44,160,44) and rgba(214,39,40) colors present; `build_park_ranking` in `controller.py:349-375` sorts by Clears descending |
| 3 | While data is being fetched, a loading spinner is visible to the user | VERIFIED | `app.py:140`: `with st.spinner("Loading player data..."):` wraps `controller.build_view(...)` |
| 4 | When an API fetch fails, a friendly `st.error` explains what happened and offers a retry action that clears the offending cache entry | VERIFIED | `app.py:142-150`: `st.error(f"Could not load data...")`, `st.button("Retry")`, `st.cache_data.clear()`, `st.rerun()`, `st.stop()` |
| 5 | Private helper functions are callable without underscore prefix (Plan 01 cleanup) | VERIFIED | `controller.py:143,153,173`: `def sorted_teams`, `def hr_of`, `def sorted_hitters`; `app.py`: no `_sorted_teams`, `_sorted_hitters`, `_hr_of` calls found |
| 6 | Mound radius uses a named constant; no stale Phase 4 caption visible | VERIFIED | `chart.py:38,142`: `MOUND_RADIUS_FT = 5.0`, `radius = MOUND_RADIUS_FT`; `app.py`: no "Phase 4" text found |

**Score:** 6/6 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `src/mlb_park/app.py` | Metrics row, ranking expander, spinner, error handler | VERIFIED | `st.metric` x4, `st.spinner`, `st.error`, `st.button("Retry")`, `st.expander("Park Rankings")` all present |
| `src/mlb_park/controller.py` | `build_park_ranking` helper, public sorted_teams/sorted_hitters/hr_of | VERIFIED | `def build_park_ranking` at line 349; in `__all__`; all public helpers present and exported |
| `src/mlb_park/chart.py` | `MOUND_RADIUS_FT` constant, no dead `BASE_MARKER_SIZE_FT` | VERIFIED | Line 38: `MOUND_RADIUS_FT = 5.0`; line 142: `radius = MOUND_RADIUS_FT`; no `BASE_MARKER_SIZE_FT` |
| `tests/controller/test_build_view.py` | Tests for `build_park_ranking` | VERIFIED | 3 test functions: `test_build_park_ranking_basic` (line 467), `test_build_park_ranking_empty` (line 492), `test_build_park_ranking_format` (line 523) |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `src/mlb_park/app.py` | `src/mlb_park/controller.py` | `controller.build_park_ranking(view)` | WIRED | `app.py:190`: `ranking_df = controller.build_park_ranking(view)` |
| `src/mlb_park/app.py` | `streamlit` | `st.spinner` wrapping `build_view` | WIRED | `app.py:140`: `with st.spinner("Loading player data..."):` |
| `src/mlb_park/app.py` | `streamlit` | `st.error` + `st.button("Retry")` | WIRED | `app.py:143,147`: both present in the except block |
| `src/mlb_park/app.py` | `src/mlb_park/controller.py` | `controller.sorted_teams()`, `controller.sorted_hitters()`, `controller.hr_of()` | WIRED | `app.py:59,78,85`: public names used, no underscore-prefixed calls |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| `app.py` metrics row | `view.totals` | `controller._compute_totals(events, plottable, matrix)` at `controller.py:218-248` | Yes — computes `avg_parks_cleared`, `no_doubters`, `cheap_hrs` from `matrix.cleared` numpy array | FLOWING |
| `app.py` ranking expander | `ranking_df` | `controller.build_park_ranking(view)` at `controller.py:349-375` — iterates `matrix.parks`, sums `matrix.cleared[:, j]`, means `matrix.margin_ft[:, j]` | Yes — reads real verdict matrix data per park | FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| All 110 tests pass including 3 new park_ranking tests | `python -m pytest tests/ -x -q` | 110 passed in 2.49s | PASS |
| `build_park_ranking` importable | `python -c "from mlb_park.controller import build_park_ranking; print('OK')"` | confirmed via grep and test pass | PASS |
| Park ranking tests pass in isolation | `python -m pytest tests/controller/test_build_view.py -x -q -k "park_ranking"` | 3 passed | PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| VIZ-04 | 06-02-PLAN.md | Summary metrics card: total HRs, avg parks cleared, no-doubters, cheap HRs | SATISFIED | `app.py:161-166`: 4-column `st.metric` row wired to `view.totals` dict |
| VIZ-05 | 06-02-PLAN.md | Best/worst parks ranking derived from verdict matrix | SATISFIED | `controller.py:349-375`: `build_park_ranking`; `app.py:188-207`: expander with Styler highlighting. Note: REQUIREMENTS.md describes "top 3 and bottom 3" but ROADMAP SC says "ranks all parks." Implementation shows full 30-park table with top 3/bottom 3 highlighted — this exceeds the minimum and satisfies both wordings. |
| UX-05 | 06-02-PLAN.md | Loading spinner while fetching; friendly error message with retry on failure | SATISFIED | `app.py:139-150`: spinner wraps `build_view`; except block shows `st.error` + Retry button + `st.cache_data.clear()` + `st.rerun()` |

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `src/mlb_park/app.py` | 68, 98, 124 | `placeholder=` | Info | Legitimate Streamlit `st.selectbox` widget placeholder attributes — not code stubs |

No blockers found.

### Human Verification Required

#### 1. Summary Metrics Card Renders Correctly

**Test:** Run `streamlit run src/mlb_park/app.py`, select a team, a player with at least one HR, and a stadium. Observe the area above the spray chart.
**Expected:** Four metric tiles appear — "Total HRs", "Avg Parks Cleared" (formatted as "X.X / 30"), "No-Doubters (30/30)", and "Cheap HRs (<=5/30)" — with non-placeholder values computed from the player's actual HR data.
**Why human:** `st.metric` layout and rendering cannot be verified without a running Streamlit server in a browser.

#### 2. Park Rankings Expander Shows Highlighted Table

**Test:** After loading a player's data, click the "Park Rankings" expander beneath the spray chart. Observe the table.
**Expected:** A 30-row table sorted by "Clears" descending; first 3 rows have a subtle green background; last 3 rows have a subtle red background; columns are "Park", "Clears", "Clear %", "Avg Margin (ft)"; index is hidden.
**Why human:** Pandas Styler row-highlighting and `st.dataframe` rendering require a live browser session to verify visually.

#### 3. Error Handler and Spinner Behavior Under API Failure

**Test:** Temporarily block `statsapi.mlb.com` (e.g., via hosts file or by killing network), then load the app and select a player. Observe behavior during and after the fetch attempt.
**Expected:** A spinner labeled "Loading player data..." is visible while the request is in flight. After failure, `st.error` displays "Could not load data. The MLB API may be temporarily unavailable. (ConnectionError)" (or similar exception type), and a "Retry" button appears.
**Why human:** Spinner visibility and the error-path rendering branch require an induced network failure in a live Streamlit session.

### Gaps Summary

No gaps. All six observable truths are verified at all four levels (exists, substantive, wired, data-flowing). All three phase requirements (VIZ-04, VIZ-05, UX-05) are satisfied. The three human verification items above cover UI rendering behavior that cannot be confirmed programmatically — they are not gaps but confirmation checks for the developer before calling v1 shipped.

---

_Verified: 2026-04-16T01:26:00Z_
_Verifier: Claude (gsd-verifier)_
