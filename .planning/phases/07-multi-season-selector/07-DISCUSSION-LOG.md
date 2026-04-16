# Phase 7: Multi-Season Selector - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-16
**Phase:** 07-multi-season-selector
**Areas discussed:** Season selector placement & cascade, Historical roster strategy, Caching strategy for past seasons, Season range & default

---

## Season Selector Placement & Cascade

| Option | Description | Selected |
|--------|-------------|----------|
| Before Team (Recommended) | Season → Team → Player → Stadium. Changing season resets all three downstream selectors. Cleanest — season is the top-level filter. | ✓ |
| Beside Team (same row) | Season and Team side by side in columns. Changing season resets Player and Stadium but not Team. | |
| In the sidebar | Season picker in st.sidebar, Team/Player/Stadium in main area. | |

**User's choice:** Before Team (Recommended)
**Notes:** None

### Follow-up: Reset scope on season change

| Option | Description | Selected |
|--------|-------------|----------|
| Keep Team, reset Player & Stadium | Teams are stable across seasons. User probably wants to compare the same team's players across years. | |
| Reset everything | Full cascade reset — Season change clears Team, Player, and Stadium. Clean slate. | ✓ |

**User's choice:** Reset everything
**Notes:** None

---

## Historical Roster Strategy

| Option | Description | Selected |
|--------|-------------|----------|
| fullSeason roster (Recommended) | Use rosterType=fullSeason&season=YYYY for past years. Returns everyone who appeared on the team that season. More players but historically accurate. | ✓ |
| Filter by stats | Keep using rosterType=active but filter to only show players who had stats in the selected season. Simpler but may miss some players. | |
| You decide | Claude picks the best approach during implementation. | |

**User's choice:** fullSeason roster (Recommended)
**Notes:** None

---

## Caching Strategy for Past Seasons

| Option | Description | Selected |
|--------|-------------|----------|
| 30d for past seasons (Recommended) | Past season data is immutable — cache roster, gameLog, and feeds for 30 days. Current season keeps existing TTLs. | ✓ |
| Same TTLs as current season | Keep existing TTLs for all seasons. Simpler code, more API calls. | |
| You decide | Claude picks TTLs during implementation. | |

**User's choice:** 30d for past seasons (Recommended)
**Notes:** None

### Follow-up: Cache entry cap

| Option | Description | Selected |
|--------|-------------|----------|
| Cap at 200 entries (Recommended) | max_entries=200 on get_game_feed. Prevents memory blowup when users browse multiple players across seasons. | |
| No cap | Let st.cache_data manage memory naturally. Simpler but riskier on Cloud. | |
| You decide | Claude picks the cap value during implementation. | ✓ |

**User's choice:** You decide
**Notes:** Claude has discretion on max_entries value

---

## Season Range & Default

| Option | Description | Selected |
|--------|-------------|----------|
| Dynamic: current year back 4 | Compute from datetime.now().year. Always shows 5 seasons ending at the current year. No hardcoded year list to update. | ✓ |
| Hardcoded [2022, 2023, 2024, 2025, 2026] | Explicit list in config.py. Simple but needs manual update each year. | |
| You decide | Claude picks the approach during implementation. | |

**User's choice:** Dynamic: current year back 4
**Notes:** None

### Follow-up: Default season

| Option | Description | Selected |
|--------|-------------|----------|
| Current year (Recommended) | Default to 2026 (or whatever datetime.now().year is). Most users want this season's data. | ✓ |
| No default (blank) | Force user to pick a season before anything loads. Extra click but explicit. | |
| Last completed season | Default to current_year - 1 so data is complete. Good for mid-season when current year data is partial. | |

**User's choice:** Current year (Recommended)
**Notes:** None

---

## Claude's Discretion

- Game feed `max_entries` cap value for OOM prevention on Cloud

## Deferred Ideas

None — discussion stayed within phase scope
