# Streamlit MLB HR Park Factor Explorer

## What This Is

A lightweight Streamlit hobby app that lets a user pick a team, then a player on that team, then a stadium, and visualizes every home run the player has hit this season. For each HR, the app calculates how many of the 30 MLB ballparks the ball would have cleared the fence at, and overlays the HRs on the selected stadium's outline — color-coded by whether each HR clears that specific park.

## Core Value

Given any MLB hitter, quickly answer "how cheap or no-doubt were their home runs this season?" by comparing each HR's distance and spray angle against every MLB park's fence dimensions.

## Requirements

### Validated

(None yet — ship to validate)

### Active

- [ ] Streamlit app with three cascading selectors: Team → Player → Stadium
- [ ] Fetch current season HR events (distance, spray coordinates, exit velo, launch angle) for the selected player from `statsapi.mlb.com`
- [ ] Compute per-HR: spray angle from `coordX/coordY`, interpolated fence distance at that angle for each of the 30 parks, HR/not-HR verdict
- [ ] Summary card: total HRs, average parks cleared (out of 30), no-doubters count, cheap-HR count
- [ ] Spray chart visualization: selected stadium's outline drawn from `fieldInfo` dimensions, all HRs plotted with green/red based on whether they clear that stadium
- [ ] Per-HR table: date, distance, exit velo, launch angle, parks cleared out of 30
- [ ] Cache API responses (Streamlit `st.cache_data`) — venues long TTL, game feeds ~1hr TTL

### Out of Scope

- Wall height modeling (Green Monster, etc.) — API doesn't return fence heights; accepted as a v1 caveat to revisit later
- Career HR history — scope creep; current season keeps the data volume tractable
- Park factor calculations (run/HR multipliers) — not in the API; FanGraphs territory
- Third-party wrapper libraries (e.g., `MLB-StatsAPI` PyPI package) — user prefers direct HTTP to inspect raw JSON shape
- Live/in-progress game updates beyond what the daily feed provides — hobby app, not a live scoreboard
- User accounts, saved players, sharing — single-user local app

## Context

- **MLB StatsAPI is unofficial but stable**: `statsapi.mlb.com/api/v1/...` is the endpoint MLB's own Gameday site uses. Not officially documented for public use, but widely consumed and stable.
- **Key endpoints already verified**:
  - `/schedule?sportId=1&date=...` — games by date, gamePks
  - `/teams?sportId=1` — all 30 MLB teams
  - `/teams/{id}/roster` — rostered players
  - `/people/{id}/stats?stats=gameLog&group=hitting&season=...` — per-game hitting logs (identifies games where player hit HRs)
  - `/game/{gamePk}/feed/live` — play-by-play with `hitData` (launchSpeed, launchAngle, totalDistance, coordX/Y) per batted ball
  - `/venues/{id}?hydrate=fieldInfo` — fence distances (LF line, LF, LCF, CF, RCF, RF line), capacity, roof, elevation
- **Data pipeline**: for a player, pull gameLog → filter games with HRs → fetch each game feed → extract HR plays matching batter id → collect `hitData`.
- **Coordinate system**: `hitData.coordinates.coordX/coordY` uses Gameday's field coordinate system (home plate near ~(125, 200)). Spray angle is derived geometrically from these coords.

## Constraints

- **Tech stack**: Python + Streamlit + `requests` + matplotlib/plotly for plotting — hobby project, stay lightweight
- **API**: Direct HTTP to `statsapi.mlb.com/api/v1` only — no `MLB-StatsAPI` PyPI wrapper or similar
- **Scope**: Current season only, single-user local app — no persistence beyond Streamlit cache
- **Rate**: No hammering the API — aggressive caching, avoid fetching all 162 games per team

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Direct HTTP over third-party wrappers | User wants to inspect raw JSON and keep deps minimal | — Pending |
| Ignore wall height in v1 HR verdict | API doesn't expose fence height; distance+angle is a good first approximation | — Pending |
| Current season only | Keeps per-player game feed fetches bounded (~50-60 games with HRs max) | — Pending |
| Streamlit (not Flask/FastAPI+frontend) | Fastest path for a hobby data app with interactive selectors | — Pending |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd-complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-04-14 after initialization*
