# Phase 7: Multi-Season Selector - Context

**Gathered:** 2026-04-16
**Status:** Ready for planning

<domain>
## Phase Boundary

Add a season selectbox (past 5 years, dynamically computed) as the top-level selector, thread the selected year through all API calls and caching, and adjust roster fetching for historical seasons. Scope: UI selector + API parameterization + caching adjustments. No new endpoints, no new pages, no deployment work.

</domain>

<decisions>
## Implementation Decisions

### Season Selector Placement & Cascade
- **D-01:** Season selectbox placed BEFORE the Team selector — cascade order: Season → Team → Player → Stadium
- **D-02:** Changing season resets ALL downstream selectors (Team, Player, Stadium) to blank — full cascade reset, not partial

### Historical Roster Strategy
- **D-03:** For past seasons, use `rosterType=fullSeason&season=YYYY` instead of `rosterType=active`. Returns everyone who appeared on the team that season — historically accurate
- **D-04:** For the current season, keep `rosterType=active` (existing behavior)

### Caching Strategy
- **D-05:** Past-season API responses cached with 30d TTL (immutable data). Current season retains existing TTLs (teams 24h, roster 6h, gameLog 1h, feed 7d)
- **D-06:** Conditional TTL logic: check if `season < current_year` → use 30d TTL, otherwise use existing per-endpoint TTLs

### Claude's Discretion
- Game feed `max_entries` cap value — Claude picks an appropriate value to prevent OOM on Streamlit Community Cloud (~1GB memory limit)

### Season Range & Default
- **D-07:** Available seasons computed dynamically: `range(current_year, current_year - 5, -1)` — always 5 seasons, no hardcoded list to maintain
- **D-08:** Default season is the current year (most users want current season data)

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Existing source files (season threading)
- `src/mlb_park/config.py` — Contains `CURRENT_SEASON = 2026`, TTL constants, and disk cache paths
- `src/mlb_park/app.py` — Only file that touches `st.session_state`; has `_on_team_change` and `_on_player_change` callbacks; imports `CURRENT_SEASON` from pipeline
- `src/mlb_park/controller.py` — `build_view()` entry point; imports `CURRENT_SEASON`; `ViewModel` already has `season` field
- `src/mlb_park/services/mlb_api.py` — All 5 cached endpoint wrappers; `get_team_hitting_stats` already takes `season: int`; `_raw_roster` uses `rosterType=active` (needs conditional for past seasons)
- `src/mlb_park/pipeline/extract.py` — `extract_hrs` accepts `season` param, falls back to `CURRENT_SEASON` if None

### Research
- `.planning/research/SUMMARY.md` — Synthesized research findings for v1.1
- `.planning/research/ARCHITECTURE.md` — Integration points and caching strategy
- `.planning/research/PITFALLS.md` — Season split-brain risk, roster mismatch, Cloud OOM

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `config.py:CURRENT_SEASON` — Currently hardcoded to 2026; will be replaced with dynamic computation
- `app.py:_on_team_change()` — Existing cascade callback pattern; new `_on_season_change()` follows same pattern
- `controller.py:ViewModel` — Already has `season: int` field; no model changes needed
- `mlb_api.py:get_team_hitting_stats(team_id, season)` — Already parameterized by season
- `mlb_api.py:get_game_log(person_id, season)` — Already parameterized by season

### Established Patterns
- All `st.session_state` access in `app.py` only (D-23)
- All HTTP + caching in `mlb_api.py` only
- Cascade callbacks null downstream selectors
- `st.cache_data` keys by function arguments (season automatically creates separate cache entries)

### Integration Points
- `app.py` line 20: `from mlb_park.pipeline import CURRENT_SEASON` — replace with widget value
- `app.py` line 79: `get_team_hitting_stats(team_id, CURRENT_SEASON)` — replace with session_state season
- `controller.py` line 284: `season = CURRENT_SEASON` fallback — replace with explicit parameter
- `pipeline/extract.py` line 45-46: `CURRENT_SEASON` fallback — replace with explicit parameter
- `mlb_api.py` line 80: `rosterType=active` — make conditional on season vs current year

</code_context>

<specifics>
## Specific Ideas

No specific requirements — open to standard approaches

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 07-multi-season-selector*
*Context gathered: 2026-04-16*
