# Streamlit MLB HR Park Factor Explorer

## What This Is

A Streamlit app that lets a user pick an MLB team, then a player, then a stadium, and visualizes every home run the player has hit this season. For each HR, the app calculates how many of the 30 MLB ballparks the ball would have cleared the fence at, and overlays the HRs on the selected stadium's outline — color-coded by whether each HR clears that specific park. Summary metrics and a 30-park ranking table complete the picture.

## Core Value

Given any MLB hitter, quickly answer "how cheap or no-doubt were their home runs this season?" by comparing each HR's distance and spray angle against every MLB park's fence dimensions.

## Requirements

### Validated

- ✓ Streamlit app with three cascading selectors: Team → Player → Stadium — v1.0
- ✓ Fetch current season HR events (distance, spray coordinates, exit velo, launch angle) from `statsapi.mlb.com` — v1.0
- ✓ Compute per-HR: spray angle, interpolated fence distance at that angle for each of 30 parks, HR/not-HR verdict — v1.0
- ✓ Summary card: total HRs, average parks cleared (out of 30), no-doubters count, cheap-HR count — v1.0
- ✓ Spray chart visualization: selected stadium outline drawn from fieldInfo, HRs plotted green/red by verdict — v1.0
- ✓ Cache API responses via `st.cache_data` with per-endpoint TTLs — v1.0
- ✓ Loading spinner and error handling with retry — v1.0
- ✓ 30-park ranking table sorted by clears with top/bottom highlighting — v1.0

### Active

- [ ] Season selector — user can pick any of the past 5 MLB seasons
- [ ] All API calls and caching parameterized by selected season
- [ ] Deploy to Streamlit Community Cloud with a shareable URL
- [ ] Deployment prep — secrets management, README, requirements for cloud

## Current Milestone: v1.1 Multi-Season & Deploy

**Goal:** Add a season selector (last 5 years) and deploy to Streamlit Community Cloud for friends to access.

**Target features:**
- Season selector — pick any of the past 5 MLB seasons
- Parameterize all API calls and caching by selected season
- Deploy to Streamlit Community Cloud with a shareable URL
- Deployment prep — secrets management, README, requirements for cloud

### Out of Scope

- Wall height modeling (Green Monster, etc.) — API doesn't return fence heights; accepted as a v1 caveat
- Career HR history — scope creep; current season keeps data volume tractable
- Park factor calculations (run/HR multipliers) — not in the API; FanGraphs territory
- Third-party wrapper libraries — user prefers direct HTTP to inspect raw JSON
- Live/in-progress game updates — hobby app, not a live scoreboard
- User accounts, saved players, sharing — single-user local app

## Context

Shipped v1.0 with 5,151 LOC Python (2,143 source + 3,008 tests), 110 passing tests.

Tech stack: Python 3.12, Streamlit, Plotly, pandas, requests, numpy.

Architecture: `mlb_api.py` (cached HTTP wrappers) → `pipeline/extract.py` (HR extraction with degradation) → `geometry/` (coordinate transform, fence interpolation, verdict matrix) → `controller.py` (ViewModel assembly) → `chart.py` (Plotly rendering) → `app.py` (Streamlit entry point).

## Constraints

- **Tech stack**: Python + Streamlit + requests + Plotly — hobby project, stay lightweight
- **API**: Direct HTTP to `statsapi.mlb.com/api/v1` only — no third-party wrappers
- **Scope**: Current season only, single-user local app — no persistence beyond Streamlit cache
- **Rate**: Aggressive caching, avoid unnecessary API calls

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Direct HTTP over third-party wrappers | User wants to inspect raw JSON and keep deps minimal | ✓ Good |
| Ignore wall height in v1 HR verdict | API doesn't expose fence height; distance+angle is a good first approximation | ✓ Good — caveat accepted |
| Current season only | Keeps per-player game feed fetches bounded (~50-60 games with HRs max) | ✓ Good |
| Streamlit (not Flask/FastAPI+frontend) | Fastest path for a hobby data app with interactive selectors | ✓ Good |
| Plotly over Matplotlib/Altair | Native interactivity, polygon overlays trivial, hover tooltips built-in | ✓ Good |
| `st.cache_data` only, no requests-cache | Single caching layer at the function boundary; avoids dual-invalidation | ✓ Good |
| Pure-function geometry (no shapely) | 1-D distance-at-angle interpolation, not 2-D containment; avoids GEOS C dep | ✓ Good |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition:**
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone:**
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-04-16 after v1.1 milestone start*
