# Phase 1: Foundation & API Layer - Context

**Gathered:** 2026-04-14
**Status:** Ready for planning

<domain>
## Phase Boundary

Pin Python dependencies, scaffold the `src/mlb_park/` package, implement five `@st.cache_data`-decorated HTTP wrappers for `statsapi.mlb.com/api/v1` (teams, roster, gameLog, game feed, venue), add a disk-backed venue cache, and record JSON fixtures for Aaron Judge's 2026 season HR games. Validated by a scratch script — no UI in this phase.
</domain>

<decisions>
## Implementation Decisions

### Project Layout & Entry Point

- **D-01:** Use `src/` layout. Package lives at `src/mlb_park/` with submodules per research/ARCHITECTURE.md. Requires `pyproject.toml` for editable install (`uv pip install -e .`).
- **D-02:** Streamlit entry point is `src/mlb_park/app.py`. Run with `streamlit run src/mlb_park/app.py`. Single-page app — no Streamlit multi-page `pages/` directory.
- **D-03:** JSON fixtures live at `tests/fixtures/` (repo-root level, outside the package). Loaded by tests via relative path.
- **D-04:** Runtime disk cache lives at `data/venues_cache.json` (repo-root). Gitignored. Directory auto-created on first use.

### Fixtures Strategy

- **D-05:** Calibration target: an Aaron Judge 2026 regular-season HR with complete `hitData` (non-ITP, distance present, coordinates present). Used in Phase 2 to back-solve the Gameday coord-to-feet transform.
- **D-06:** Fixture scope: capture the full set of 2026 regular-season games in which Aaron Judge hit at least one HR (early-April 2026 → expect ~5-15 games, manageable repo size). Commit raw JSON for each game feed plus teams, roster, gameLog, and all 30 venue responses.
- **D-07:** Capture method: a repeatable script `scripts/record_fixtures.py` that calls the live API and writes to `tests/fixtures/` (same shape the production client returns). Re-runnable — do not hand-edit captured JSON.
- **D-08:** Fixture season: **2026** (current season). Matches what the running app queries; means Phase 2 calibration uses the same coord system the app actually serves.

### gameType Scope

- **D-09:** gameLog and HR-pipeline filter include **regular season only** (`gameType=R`). Excludes spring training (S), postseason (F/D/L/W), All-Star (A), exhibition (E).
- **D-10:** Single source of truth: whatever passes the gameType filter is both what appears in the HR list and what gets the park-verdict treatment. No split filters.

### Claude's Discretion

- HTTP timeout, retry policy, and User-Agent string — not asked; use reasonable defaults (10s timeout, retry-once on network error, `User-Agent: mlb-park-explorer/0.1 (+https://github.com/local/hobby)`).
- Exact log-level / logging library choice for the scratch validation script.
- File naming inside `tests/fixtures/` (suggest: `teams.json`, `roster_{team_id}.json`, `gamelog_{player_id}_{season}.json`, `feed_{gamePk}.json`, `venue_{venue_id}.json`).
- Whether to include a `Makefile` or `justfile` helper for `record_fixtures` / `smoke` tasks.
- Test framework (pytest was flagged as deferred — Phase 1 can ship with just a scratch smoke script; pytest scaffolding can wait for Phase 2 where pure-function tests actually add value).
</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project-Level
- `.planning/PROJECT.md` — locked decisions (direct HTTP, Streamlit, current season, no wrappers)
- `.planning/REQUIREMENTS.md` — v1 REQ-IDs; Phase 1 owns DATA-04 (cached HTTP wrappers)
- `.planning/ROADMAP.md` §Phase 1 — goal and 5 success criteria

### Research
- `.planning/research/STACK.md` — pinned versions (Python 3.12 / uv / streamlit 1.56 / requests 2.32 / plotly 6.7 / pandas 2.2), per-endpoint TTL guide, rejected alternatives
- `.planning/research/ARCHITECTURE.md` — module layout, `mlb_api.py` as sole home of `requests` + `@st.cache_data`, 5-endpoint contract
- `.planning/research/PITFALLS.md` — rate limiting, `hitData` nullability, same-name players, Streamlit version skew, `st.cache_data` unhashable-arg traps
- `.planning/research/SUMMARY.md` — synthesized guidance

### External (MLB StatsAPI)
- `https://statsapi.mlb.com/api/v1/teams?sportId=1` — all 30 teams
- `https://statsapi.mlb.com/api/v1/teams/{teamId}/roster` — per-team roster
- `https://statsapi.mlb.com/api/v1/people/{personId}/stats?stats=gameLog&group=hitting&season={year}` — hitter game log
- `https://statsapi.mlb.com/api/v1.1/game/{gamePk}/feed/live` — play-by-play with `hitData` (note: v1.1, not v1)
- `https://statsapi.mlb.com/api/v1/venues/{venueId}?hydrate=location,fieldInfo` — stadium dimensions

### Streamlit Docs
- `https://docs.streamlit.io/develop/api-reference/caching-and-state/st.cache_data` — TTL semantics, `_`-prefix unhashable args
- `https://docs.streamlit.io/develop/concepts/architecture/caching` — cache architecture
</canonical_refs>

<code_context>
## Existing Code Insights

Greenfield — no existing code.

### Integration Points

- None yet; this phase establishes them.
- Downstream modules (Phases 2-6) will import from `mlb_park.services.mlb_api`, so the wrapper signatures chosen in Phase 1 are load-bearing.
</code_context>

<specifics>
## Specific Ideas

- Aaron Judge (personId: 592450) is the calibration player. Verify personId during planning by calling `/api/v1/teams/147/roster` (Yankees) and filtering by name.
- Gameday feed lives at `/api/v1.1/game/{gamePk}/feed/live` (note: `v1.1`, not `v1`) — important detail flagged in the Schedule exploration earlier in the session.
- Disk cache policy: on read, if file mtime > 30 days old, invalidate and re-fetch. On write, write atomically (tmp + rename) to avoid partial-write corruption.
- Scratch validation (`scripts/smoke.py` or similar): hits all five endpoints once, prints shape summary, confirms disk cache file appears after first venue fetch.
</specifics>

<deferred>
## Deferred Ideas

- **pytest + formal unit test suite** — user selected only 3 of 4 gray areas; testing framework discussion skipped. Will be addressed in Phase 2 where pure-function geometry actually benefits from unit tests.
- **Concurrent feed fetching (ThreadPoolExecutor)** — research flagged this as a potential future optimization; v1 is sequential + cached.
- **Postseason HR inclusion** — explicitly deferred via D-09; revisit after v1 if user wants playoff data.
- **Career history / multi-season** — out of scope per PROJECT.md.
</deferred>

---

*Phase: 01-foundation-api-layer*
*Context gathered: 2026-04-14*
