---
phase: "07"
plan: "07-02"
subsystem: services/mlb_api
tags: [caching, api, historical-roster, ttl, oom-guard]
key-files:
  created:
    - scripts/test_historical_roster.py
    - tests/services/test_mlb_api_season.py
  modified:
    - src/mlb_park/services/mlb_api.py
    - tests/services/test_team_hitting_stats.py
metrics:
  tests_added: 13
  tests_total: 119
  files_changed: 5
---

# Plan 07-02 Summary: Historical Roster API & Caching

## Objective
Validate the historical roster API assumption, then implement conditional rosterType for historical seasons, two-function TTL split for past vs current season caching, and game feed max_entries cap.

## What Was Built

### Task 0: Historical Roster API Validation
Created `scripts/test_historical_roster.py` — a standalone validation script that hits the live MLB StatsAPI with `rosterType=fullSeason&season=2024` for NYY. Confirms the `person.stats` hydration returns the same structure as `rosterType=active`. API assumption validated.

### Task 1: Conditional rosterType, TTL Split, max_entries Cap
- **Conditional rosterType (SEASON-03):** `_raw_team_hitting_stats` now accepts a `season` parameter and uses `rosterType=fullSeason` for past seasons, `rosterType=active` for current season
- **Two-function TTL split (SEASON-04):** Added `get_game_log_historical` (30d TTL) and `get_team_hitting_stats_historical` (30d TTL) alongside existing 1h-TTL functions. Public dispatchers route based on `season < CURRENT_SEASON`
- **max_entries cap (SEASON-05):** `get_game_feed` now uses `max_entries=200` with `@st.cache_data(max_entries=200, ttl="30d")` to prevent OOM on Streamlit Community Cloud

## Commits

| # | Hash | Description |
|---|------|-------------|
| 1 | `9bd2e0e` | chore(07-02): add historical roster API validation script |
| 2 | `1a4d0eb` | test(07-02): add failing tests for SEASON-03/04/05 |
| 3 | `cf9f0aa` | feat(07-02): conditional rosterType, TTL split, max_entries cap |

## Deviations

None — implementation followed the plan. API validation (Task 0) confirmed the `fullSeason` assumption, so the primary implementation path was used (no fallback needed).

## Self-Check: PASSED

- [x] `_raw_team_hitting_stats` uses `rosterType=fullSeason` when `season < CURRENT_SEASON`
- [x] `get_game_log_historical` has `ttl="30d"` decorator
- [x] `get_team_hitting_stats_historical` has `ttl="30d"` decorator
- [x] `get_game_feed` has `max_entries=200`
- [x] All 13 new tests pass
- [x] Full suite: 119 tests passing
