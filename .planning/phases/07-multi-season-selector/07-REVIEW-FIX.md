---
phase: 07-multi-season-selector
fixed_at: 2026-04-16T00:00:00Z
review_path: .planning/phases/07-multi-season-selector/07-REVIEW.md
iteration: 1
findings_in_scope: 3
fixed: 3
skipped: 0
status: all_fixed
---

# Phase 7: Code Review Fix Report

**Fixed at:** 2026-04-16T00:00:00Z
**Source review:** .planning/phases/07-multi-season-selector/07-REVIEW.md
**Iteration:** 1

**Summary:**
- Findings in scope: 3
- Fixed: 3
- Skipped: 0

## Fixed Issues

### WR-01: `rosterType` dispatcher uses `>=` instead of `==`, allowing future seasons to use `active`

**Files modified:** `src/mlb_park/services/mlb_api.py`
**Commit:** c617d6f
**Applied fix:** Changed `season >= CURRENT_SEASON` to `season == CURRENT_SEASON` on line 116 of `_raw_team_hitting_stats`. This ensures only the exact current season uses `rosterType=active`; any other season (past or future) falls through to `fullSeason`.

### WR-02: Hardcoded season `2026` in test will silently assert wrong `rosterType` after this year

**Files modified:** `tests/services/test_team_hitting_stats.py`
**Commit:** 66a0521
**Applied fix:** Replaced hardcoded `2026` with `CURRENT_SEASON` import in `test_raw_helper_builds_expected_url`. The test now dynamically uses the current season constant for both the function call and the hydrate-string assertion, so it remains correct across year boundaries.

### WR-03: `test_game_feed_ttl_is_30d` source-text check is too broad

**Files modified:** `tests/services/test_mlb_api_season.py`
**Commit:** 7ee7bf2
**Applied fix:** Replaced the whole-file string search with a targeted check that locates the `def get_game_feed` line, walks backwards to find its `@st.cache_data` decorator, and asserts `ttl="30d"` on that specific decorator line. This prevents false positives from other functions that also use `ttl="30d"`.

---

_Fixed: 2026-04-16T00:00:00Z_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
