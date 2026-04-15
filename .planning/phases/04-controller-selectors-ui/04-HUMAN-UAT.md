---
status: partial
phase: 04-controller-selectors-ui
source: [04-VERIFICATION.md]
started: 2026-04-15T19:05:00Z
updated: 2026-04-15T19:05:00Z
---

## Current Test

[awaiting human testing]

## Tests

### 1. UX-01 — Team dropdown renders all 30 MLB teams (cold start)
expected: Team dropdown renders with placeholder 'Select a team…', contains all 30 MLB teams, no selection on cold start.
result: [pending]

### 2. UX-02 — Player dropdown populates for NYY, sorted by HR desc, excludes pitchers
expected: Player dropdown enables after team pick; entries exclude pitchers; Judge/top HR hitter at top; labels include '{name} — {N} HR'.
result: [pending]

### 3. UX-03 — Stadium defaults to player's home park, user can override
expected: On player pick, venue_id auto-sets to 3313 (Yankee Stadium) for Judge; user can change to any of 30 parks; change sticks (no on_change reset).
result: [pending]

### 4. UX-04 — Team change clears children; player change resets venue to home park
expected: Switching team clears player_id and venue_id (guard st.info 'Select a team, player, and stadium to begin.' returns); switching player resets venue_id to new player's home park.
result: [pending]

### 5. End-to-end — Raw ViewModel dump renders below selectors
expected: st.subheader('ViewModel (raw)') followed by st.json(view.to_dict()); when plottable_events non-empty, st.subheader('Plottable HRs') + st.dataframe with 6 columns (game_date, opponent_abbr, distance_ft, launch_speed, launch_angle, clears_selected).
result: [pending]

## Summary

total: 5
passed: 0
issues: 0
pending: 5
skipped: 0
blocked: 0

## Gaps
