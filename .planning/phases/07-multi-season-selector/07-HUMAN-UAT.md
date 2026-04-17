---
status: partial
phase: 07-multi-season-selector
source: [07-VERIFICATION.md]
started: 2026-04-16T20:35:00-04:00
updated: 2026-04-16T20:35:00-04:00
---

## Current Test

[awaiting human testing]

## Tests

### 1. Season selectbox visual rendering
expected: Season selectbox renders at top of page before Team selectbox, defaults to 2026, shows 5 options (2026-2022)
result: [pending]

### 2. Season change cascade reset in live session
expected: After selecting a team and player, changing the season resets all three downstream selectors (team, player, stadium) to empty/default
result: [pending]

### 3. Historical roster completeness via live API
expected: Selecting season 2024 + Yankees shows the full-season roster including traded/retired players (e.g., Juan Soto appears despite being traded)
result: [pending]

## Summary

total: 3
passed: 0
issues: 0
pending: 3
skipped: 0
blocked: 0

## Gaps
