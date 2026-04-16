# Phase 7: Multi-Season Selector - Research

**Researched:** 2026-04-16
**Domain:** Streamlit session-state cascade, `st.cache_data` TTL/max_entries, MLB StatsAPI historical roster endpoint, dynamic year computation
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01:** Season selectbox placed BEFORE the Team selector — cascade order: Season → Team → Player → Stadium
- **D-02:** Changing season resets ALL downstream selectors (Team, Player, Stadium) to blank — full cascade reset, not partial
- **D-03:** For past seasons, use `rosterType=fullSeason&season=YYYY` instead of `rosterType=active`. Returns everyone who appeared on the team that season — historically accurate
- **D-04:** For the current season, keep `rosterType=active` (existing behavior)
- **D-05:** Past-season API responses cached with 30d TTL (immutable data). Current season retains existing TTLs (teams 24h, roster 6h, gameLog 1h, feed 7d)
- **D-06:** Conditional TTL logic: check if `season < current_year` → use 30d TTL, otherwise use existing per-endpoint TTLs
- **D-07:** Available seasons computed dynamically: `range(current_year, current_year - 5, -1)` — always 5 seasons, no hardcoded list to maintain
- **D-08:** Default season is the current year (most users want current season data)

### Claude's Discretion

- Game feed `max_entries` cap value — Claude picks an appropriate value to prevent OOM on Streamlit Community Cloud (~1GB memory limit)

### Deferred Ideas (OUT OF SCOPE)

None — discussion stayed within phase scope
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| SEASON-01 | User can select any MLB season from the past 5 years (2022-2026) via a selectbox | D-07/D-08: `range(current_year, current_year - 5, -1)` drives options; selectbox defaults to index 0 (current year) |
| SEASON-02 | Changing the season resets the player and stadium selectors | D-01/D-02: `_on_season_change` callback mirrors `_on_team_change`; nulls `team_id`, `player_id`, `venue_id` |
| SEASON-03 | Historical seasons use fullSeason roster so traded/retired players appear for the year they played | D-03/D-04: conditional `rosterType` in `_raw_team_hitting_stats`; verified endpoint exists [ASSUMED] |
| SEASON-04 | Past-season API responses are cached with 30d TTL; current season retains 1h TTL | D-05/D-06: two-function split pattern for `get_game_log` and `get_team_hitting_stats`; `get_game_feed` raised to 30d |
| SEASON-05 | Game feed cache is capped at max_entries to prevent OOM on Community Cloud | `max_entries` confirmed available in Streamlit 1.56.0 [VERIFIED: running interpreter]; recommended cap = 200 |
</phase_requirements>

---

## Summary

Phase 7 is a targeted wiring exercise — not new architecture. The v1.0 codebase already threads `season` as an explicit parameter all the way from `app.py` through `controller.build_view` → `extract_hrs` → `get_game_log` and `get_team_hitting_stats`. `st.cache_data` automatically keys on all function arguments, so separate per-season cache entries already exist — no cache logic changes are needed beyond TTL adjustments and a `max_entries` cap.

The two non-trivial decisions are (1) the two-function TTL split for endpoints that need different TTLs on historical vs. current season data (since `@st.cache_data` TTL is fixed at decoration time), and (2) the `rosterType=fullSeason&season=YYYY` switch for historical rosters, which is community-confirmed but not officially documented and therefore must be fixture-tested before shipping.

The remaining work is mechanical: add a season selectbox to `app.py` before the Team selector, write a `_on_season_change` callback that nulls all four downstream keys, replace the two hardcoded `CURRENT_SEASON` references in `app.py` with `st.session_state["season"]`, replace the hardcoded `CURRENT_SEASON = 2026` in `config.py` with a dynamic `datetime.datetime.now()` computation, add `AVAILABLE_SEASONS` to `config.py`, and touch `mlb_api.py` for the TTL split and `max_entries` cap.

**Primary recommendation:** Implement exactly what CONTEXT.md describes — no architecture invention needed. Every integration point is identified in `07-CONTEXT.md §code_context`.

---

## Project Constraints (from CLAUDE.md)

- Tech stack: Python + Streamlit + `requests` + plotly — stay lightweight
- MLB data source: direct HTTP to `statsapi.mlb.com/api/v1` only; no third-party wrappers
- No `st.cache_resource` for API data — use `st.cache_data` only
- All `st.session_state` access in `app.py` only (D-23)
- All HTTP + caching in `mlb_api.py` only
- Cascade callbacks null downstream selectors (established pattern)
- No `requests-cache` — `st.cache_data` is the sole caching layer

---

## Standard Stack

No new dependencies for this phase. All changes are within the existing stack.

### Relevant Existing Libraries (no additions)

| Library | Version | Relevant to Phase 7 |
|---------|---------|---------------------|
| streamlit | 1.56.0 [VERIFIED: running interpreter] | `st.selectbox`, `st.session_state`, `@st.cache_data(max_entries=...)` |
| requests | 2.32.x | No change — all HTTP in `mlb_api.py` |
| pandas | 2.2.x | No change |
| plotly | 6.7.0 | No change |

**`max_entries` availability confirmed:**
`st.cache_data` signature at Streamlit 1.56.0: `(func=None, *, ttl=None, max_entries=None, show_spinner=True, show_time=False, persist=None, hash_funcs=None, scope='global')` [VERIFIED: running interpreter]

---

## Architecture Patterns

### Cascade Reset Pattern (established in v1.0)

Existing pattern to follow exactly — new `_on_season_change` mirrors `_on_team_change`:

```python
# Source: src/mlb_park/app.py (existing)
def _on_team_change() -> None:
    st.session_state["player_id"] = None
    st.session_state["venue_id"] = None

# New callback — same structure, nulls MORE keys (season resets everything)
def _on_season_change() -> None:
    st.session_state["team_id"] = None
    st.session_state["player_id"] = None
    st.session_state["venue_id"] = None
```

**Why reset `team_id` too:** A user on "NYY 2022" who switches to 2024 season should re-select their team — the roster and HR totals changed. D-02 specifies full cascade reset.

### Season Selectbox Pattern

```python
# Source: pattern from existing selectboxes in app.py
AVAILABLE_SEASONS = list(range(current_year, current_year - 5, -1))

st.selectbox(
    "Season",
    options=AVAILABLE_SEASONS,
    key="season",
    index=0,           # defaults to current year (D-08) — index 0 = first item
    on_change=_on_season_change,
)
```

`index=0` is correct because `range(current_year, current_year - 5, -1)` starts with the current year. No `placeholder` or `index=None` — a season must always be selected to avoid `None` propagating through all downstream calls.

### Dynamic `CURRENT_SEASON` Computation

Replace `CURRENT_SEASON = 2026` in `config.py` with:

```python
# Source: Pitfall 16 in PITFALLS.md; pattern verified against Python stdlib
import datetime

def _current_season() -> int:
    now = datetime.datetime.now()
    # MLB regular season typically opens in late March / early April.
    # If month < 3 (January or February), still show previous season as default.
    return now.year if now.month >= 3 else now.year - 1

CURRENT_SEASON: int = _current_season()
AVAILABLE_SEASONS: list[int] = list(range(CURRENT_SEASON, CURRENT_SEASON - 5, -1))
```

`CURRENT_SEASON` is still useful as a module constant — `extract_hrs` and `controller.build_view` use it as a `season=None` fallback in tests. Keep it; just make it dynamic.

### Two-Function TTL Split Pattern (for SEASON-04)

`@st.cache_data` TTL is fixed at decoration time — you cannot vary it by argument value. D-05/D-06 require 30d TTL for past seasons vs. 1h for current.

**Pattern A — two decorated functions sharing a raw helper (recommended):**

```python
# Source: ARCHITECTURE.md §Caching Strategy Option A
def _raw_game_log(person_id: int, season: int) -> list[dict]:
    # ... existing HTTP logic ...

@st.cache_data(ttl="1h", show_spinner=False)
def get_game_log_current(person_id: int, season: int) -> list[dict]:
    return _raw_game_log(person_id, season)

@st.cache_data(ttl="30d", show_spinner=False)
def get_game_log_historical(person_id: int, season: int) -> list[dict]:
    return _raw_game_log(person_id, season)

def get_game_log(person_id: int, season: int) -> list[dict]:
    """Dispatcher: 30d TTL for past seasons, 1h for current."""
    if season < CURRENT_SEASON:
        return get_game_log_historical(person_id, season)
    return get_game_log_current(person_id, season)
```

Apply the same split to `get_team_hitting_stats`. The public function names (`get_game_log`, `get_team_hitting_stats`) are unchanged — callers see no difference.

**Why not Option C (accept 1h for all seasons):** CONTEXT.md D-05 locked this decision. Option C is not available.

### Conditional rosterType for Historical Seasons (SEASON-03)

D-03 requires `rosterType=fullSeason&season=YYYY` for past seasons. The change is in `_raw_team_hitting_stats`:

```python
def _raw_team_hitting_stats(team_id: int, season: int) -> list[dict]:
    assert isinstance(team_id, int) and isinstance(season, int)
    from mlb_park.config import CURRENT_SEASON
    roster_type = "active" if season >= CURRENT_SEASON else "fullSeason"
    hydrate = f"person(stats(type=statsSingleSeason,season={season},group=hitting))"
    resp = _get(
        f"{BASE_URL_V1}/teams/{team_id}/roster",
        params={"rosterType": roster_type, "season": season, "hydrate": hydrate},
    )
    return resp.get("roster", [])
```

Note: add `"season": season` to params for both `active` (current) and `fullSeason` (historical) to be explicit about which season's roster the API should return. The existing code omits `season` from the params dict (only passes it via `hydrate`); adding it explicitly is safer for historical queries.

### `max_entries` Cap for SEASON-05

```python
# Existing:
@st.cache_data(ttl=TTL_FEED, show_spinner=False)
def get_game_feed(game_pk: int) -> dict:

# Phase 7:
@st.cache_data(ttl="30d", max_entries=200, show_spinner=False)
def get_game_feed(game_pk: int) -> dict:
```

**Rationale for 200 cap (Claude's discretion):** Each game feed is 1–5 MB of raw JSON pickled in memory. At the median 2 MB/feed × 200 entries = ~400 MB baseline. Community Cloud limit is ~1 GB. 200 leaves 600 MB headroom for Streamlit runtime, pandas DataFrames, plotly figures, and the rest of the process. A typical power user exploring 3 players × 3 seasons × ~25 HR-games/season = ~225 feeds — the LRU eviction kicks in near the cap, which is the correct behavior. Raising to 300 would risk OOM for sustained multi-season browsing; lowering to 100 would cause excess cache misses for moderate use. 200 is the recommended value.

Historical game feeds are also immutable, so raising `TTL_FEED` from `"7d"` to `"30d"` is safe and reduces unnecessary re-fetches on process restart. Both changes go on the same decorator.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Per-argument TTL | Runtime TTL dispatch logic in a single function | Two decorated functions + dispatcher | `@st.cache_data` TTL is fixed at decoration time — any other pattern is undefined behavior |
| Cache memory limit | Manual cache eviction or size tracking | `max_entries=200` on `@st.cache_data` | Streamlit uses LRU eviction when `max_entries` is set; it's built in [VERIFIED: interpreter] |
| Season list | Hardcoded `[2022, 2023, 2024, 2025, 2026]` | `range(CURRENT_SEASON, CURRENT_SEASON - 5, -1)` | D-07 — hardcoded list requires annual maintenance |
| Dynamic year | `datetime.date.today().year` alone | `_current_season()` with month check | Off-season (Jan–Feb) should default to previous season, not the upcoming one |

**Key insight:** Every custom solution here has a Streamlit-native counterpart that's already available. The phase is wiring, not invention.

---

## Common Pitfalls

### Pitfall 1: Split-Brain Season — `CURRENT_SEASON` constant not replaced at all call sites
**What goes wrong:** The season selector shows "2022" but data comes from 2026 because one call site still passes `CURRENT_SEASON`.
**Why it happens:** `CURRENT_SEASON` is imported in 4 places in `app.py` and `controller.py`; static imports don't remind you to update them.
**How to avoid:** After wiring, grep for `CURRENT_SEASON` in `app.py`. The only remaining reference should be in `controller.build_view`'s `season=None` fallback (acceptable — tests use it) and in `config.py`'s definition. Any reference in `app.py` that is not the import statement is a bug.
**Current call sites to update:**
- `app.py` line 20: `from mlb_park.pipeline import CURRENT_SEASON` — keep the import (still used by controller/extract as fallback), but stop passing it to functions
- `app.py` line 79: `get_team_hitting_stats(team_id, CURRENT_SEASON)` → `get_team_hitting_stats(team_id, season)` where `season = st.session_state["season"]`
- `controller.build_view(team_id, player_id, venue_id)` call → add `season=season`
[VERIFIED: grep of src/ confirms exactly these 2 active references in app.py]

### Pitfall 2: Historical Roster Returns Wrong Shape
**What goes wrong:** `rosterType=fullSeason` may return a different JSON shape than `rosterType=active` — different keys, missing `person.stats`, empty list.
**Why it happens:** The endpoint is undocumented; community reports suggest it works, but the response schema may vary by season or team.
**How to avoid:** Fixture-test `_raw_team_hitting_stats(team_id=147, season=2024)` (NYY 2024) in a scratch script before wiring the UI. Confirm `roster` key exists, entries have `person.id`, HR counts match Baseball Reference. If `fullSeason` returns an empty list, fall back to `active` + log a warning rather than crashing.
**Confidence:** MEDIUM — community-confirmed endpoint, not officially documented [ASSUMED].

### Pitfall 3: Season Selectbox with `index=None` Breaks Downstream Code
**What goes wrong:** If `key="season"` starts as `None` (no default), all downstream selectors that read `st.session_state["season"]` receive `None` and must guard against it — significant code smell compared to always having a valid season.
**How to avoid:** Use `index=0` (not `index=None`) on the season selectbox. Season is not optional — there's always a valid season. The existing Team/Player/Venue boxes use `index=None` because those can be unset; season cannot.

### Pitfall 4: `_on_season_change` Fires Before Session State Is Updated
**What goes wrong:** Streamlit fires `on_change` after the widget value is committed to session state. Code that reads `st.session_state["season"]` inside the callback gets the NEW value, not the old one — this is correct and expected, but easy to confuse.
**How to avoid:** The callback only NULLS downstream state; it does not read the season value. No issue if the pattern mirrors `_on_team_change` exactly.

### Pitfall 5: Two-Function TTL Split — Wrong Function Called for Current Season
**What goes wrong:** The dispatcher `get_game_log(person_id, season)` compares `season < CURRENT_SEASON`. If `CURRENT_SEASON` is computed dynamically (good) but the comparison happens at module import time (bad), an app started in December 2026 might route 2026 data to the historical function.
**How to avoid:** The dispatcher imports `CURRENT_SEASON` from `config.py` at call time (inside the function body), not at module level. Since `CURRENT_SEASON` is now computed at module load, it's stable for the process lifetime — but accessing it via `from mlb_park.config import CURRENT_SEASON` at the top of the dispatcher function body is clear and idiomatic.

### Pitfall 6: `pyproject.toml` Has `pytest` as a Runtime Dependency
**What goes wrong:** `pyproject.toml` (confirmed in codebase) lists `pytest` under `[project.dependencies]`. If Community Cloud (Phase 8) installs from `pyproject.toml`, it will install pytest into the production environment — wasted space but not a runtime error. However, Phase 8 (deployment) specifically calls out removing pytest. Flag this for Phase 8, not Phase 7.
**How to avoid:** Phase 7 is local only — no deployment work. Leave this for Phase 8 per REQUIREMENTS.md scope.

---

## Code Examples

### Complete `_on_season_change` Callback

```python
# Source: mirrors _on_team_change pattern from app.py
def _on_season_change() -> None:
    """Season change resets ALL downstream selectors (D-02: full cascade)."""
    st.session_state["team_id"] = None
    st.session_state["player_id"] = None
    st.session_state["venue_id"] = None
```

### Season Selectbox (before Team selector)

```python
# Source: pattern from existing selectboxes in app.py; index=0 for current year default
season = st.selectbox(
    "Season",
    options=AVAILABLE_SEASONS,   # from config.py
    key="season",
    index=0,
    help="Select a season to explore.",
    on_change=_on_season_change,
)
```

Read back immediately: `season = st.session_state.get("season", CURRENT_SEASON)` before any downstream call.

### `config.py` Season Constants

```python
import datetime

def _current_season() -> int:
    now = datetime.datetime.now()
    return now.year if now.month >= 3 else now.year - 1

CURRENT_SEASON: int = _current_season()
AVAILABLE_SEASONS: list[int] = list(range(CURRENT_SEASON, CURRENT_SEASON - 5, -1))
```

### `get_game_feed` with `max_entries`

```python
# Source: PITFALLS.md §19; max_entries confirmed in Streamlit 1.56.0 [VERIFIED]
@st.cache_data(ttl="30d", max_entries=200, show_spinner=False)
def get_game_feed(game_pk: int) -> dict:
    """Live/completed game feed. TTL 30d (immutable after game end). Max 200 entries (OOM guard)."""
    return _raw_game_feed(game_pk)
```

---

## Runtime State Inventory

This phase involves a rename/change to `CURRENT_SEASON` from a hardcoded int to a dynamic computation, and adding `AVAILABLE_SEASONS`. No external runtime state holds the `CURRENT_SEASON` value — it is only a Python constant read at import time.

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | None — no database, no Mem0, no external store | None |
| Live service config | None — no external services configured | None |
| OS-registered state | None — no Task Scheduler, pm2, or systemd units | None |
| Secrets/env vars | None — no secrets reference `CURRENT_SEASON` | None |
| Build artifacts | `data/venues_cache.json` (disk cache, gitignored) — season-agnostic, no change needed | None |

**`st.cache_data` in-memory cache:** Changing `CURRENT_SEASON` from `2026` (hardcoded) to a dynamic value does not affect existing cache entries — `st.cache_data` keys on function arguments, not on module constants. No cache invalidation needed.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python | Runtime | Yes | 3.12 [VERIFIED: pyproject.toml] | — |
| Streamlit | UI + caching | Yes | 1.56.0 [VERIFIED: interpreter] | — |
| `max_entries` kwarg | SEASON-05 | Yes | Available in 1.56.0 [VERIFIED: interpreter signature] | — |
| statsapi.mlb.com `rosterType=fullSeason` | SEASON-03 | Unknown | — | Fall back to `active` + log warning; flag for manual fixture test |

**Missing dependencies with no fallback:** None.

**Items requiring pre-implementation validation:**
- `rosterType=fullSeason&season=YYYY` endpoint behavior — MEDIUM confidence [ASSUMED], must fixture-test with NYY 2024 before shipping SEASON-03. A scratch script call to `_raw_team_hitting_stats(147, 2024)` will confirm the response shape.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 8.x [VERIFIED: pyproject.toml] |
| Config file | `pyproject.toml` (no `pytest.ini` found) |
| Quick run command | `python -m pytest tests/ -x -q` |
| Full suite command | `python -m pytest tests/ -q` |

Existing suite: 110 tests passing (v1.0 baseline per STATE.md).

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| SEASON-01 | `AVAILABLE_SEASONS` contains 5 seasons starting with current year | unit | `pytest tests/test_config.py -x -q` | No — Wave 0 |
| SEASON-01 | Season selectbox renders with index 0 defaulting to current year | manual | visual check in running app | N/A |
| SEASON-02 | `_on_season_change` nulls team_id, player_id, venue_id | unit | `pytest tests/controller/test_callbacks.py -x -q` | Partial — file exists, new test needed |
| SEASON-03 | `_raw_team_hitting_stats` passes `fullSeason` for past seasons | unit | `pytest tests/services/test_team_hitting_stats.py -x -q` | Partial — file exists, extend |
| SEASON-03 | Historical season returns correct player list (not current roster) | integration (scratch script) | `python scripts/test_historical_roster.py` | No — Wave 0 (scratch script) |
| SEASON-04 | `get_game_log_historical` is called for `season < CURRENT_SEASON` | unit | `pytest tests/services/test_mlb_api_ttl.py -x -q` | No — Wave 0 |
| SEASON-04 | `get_game_log_current` is called for current season | unit | `pytest tests/services/test_mlb_api_ttl.py -x -q` | No — Wave 0 |
| SEASON-05 | `get_game_feed` decorator has `max_entries=200` | unit (introspection) | `pytest tests/services/test_mlb_api_ttl.py -x -q` | No — Wave 0 |
| SEASON-05 | OOM not triggered under multi-player multi-season exploration | manual / post-deploy | — | N/A |

### Sampling Rate

- **Per task commit:** `python -m pytest tests/ -x -q` (full suite, ~110 tests, runs in seconds)
- **Per wave merge:** `python -m pytest tests/ -q`
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps

- [ ] `tests/test_config.py` — covers SEASON-01: `AVAILABLE_SEASONS` length, current year at index 0, `CURRENT_SEASON` matches `AVAILABLE_SEASONS[0]`
- [ ] `tests/services/test_mlb_api_ttl.py` — covers SEASON-04 and SEASON-05: TTL dispatcher routing, `max_entries` introspection
- [ ] `tests/controller/test_callbacks.py` — extend with `test_on_season_change_nulls_all_three_children`
- [ ] `tests/services/test_team_hitting_stats.py` — extend with `test_historical_season_uses_full_season_roster_type`
- [ ] Scratch script `scripts/test_historical_roster.py` — live API validation of `rosterType=fullSeason&season=2024` response shape (not a pytest test — requires network, used once for D-03 validation)

---

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | No | Not applicable (no auth) |
| V3 Session Management | No | Streamlit session state is local; no session tokens |
| V4 Access Control | No | Single-user local app |
| V5 Input Validation | Yes | `season` must be int in `AVAILABLE_SEASONS`; existing `assert isinstance(season, int)` in `_raw_*` helpers handles SSRF guard |
| V6 Cryptography | No | No credentials in this phase |

### Threat Patterns for This Phase

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Malformed season value injected into URL | Tampering | `assert isinstance(season, int)` already in `_raw_team_hitting_stats`, `_raw_game_log`; season constrained to `AVAILABLE_SEASONS` list by selectbox |
| Season outside `AVAILABLE_SEASONS` range (e.g., 1900) | Tampering | Selectbox enforces the valid set; raw helpers have int-type assert |

No new security surface is introduced. The `season` parameter is already guarded by the existing SSRF assertions in `mlb_api.py`.

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `rosterType=fullSeason&season=YYYY` returns a populated roster with `person.stats` hydration for historical seasons | Architecture Patterns, SEASON-03 | Historical player dropdown shows wrong players or is empty; mitigation: fixture-test before shipping |
| A2 | Adding `"season": season` to the `params` dict alongside `hydrate` is accepted by the roster endpoint for both `active` and `fullSeason` roster types | Architecture Patterns | API ignores or errors on the explicit season param; mitigation: test in scratch script |

---

## Open Questions

1. **Does `rosterType=fullSeason&season=2024` return `person.stats` hydration the same way `rosterType=active` does?**
   - What we know: `active` roster with hydrate returns `person.stats[0].splits[0].stat.homeRuns`. `fullSeason` is community-confirmed to exist but schema is not verified.
   - What's unclear: Whether the hydrate query `person(stats(type=statsSingleSeason,season=YYYY,group=hitting))` works identically for `fullSeason`.
   - Recommendation: Scratch script test against NYY 2024 before writing the Wave 1 implementation task. If hydrate fails, fallback is `active` + filter by `homeRuns >= 1` from existing stats.

2. **Should season selectbox reset trigger a `st.rerun()` or is `on_change` sufficient?**
   - What we know: Existing `_on_team_change` uses `on_change` only (no explicit `st.rerun()`), and Streamlit reruns automatically after any widget change.
   - What's unclear: Nothing — the existing pattern is confirmed to work.
   - Recommendation: Use `on_change` only, no `st.rerun()`. Mirrors established pattern.

---

## Sources

### Primary (HIGH confidence)

- Existing codebase: `src/mlb_park/app.py`, `src/mlb_park/config.py`, `src/mlb_park/services/mlb_api.py`, `src/mlb_park/pipeline/extract.py`, `src/mlb_park/controller.py` [VERIFIED: direct read in this session]
- Streamlit 1.56.0 `st.cache_data` signature [VERIFIED: running interpreter — `max_entries`, `persist`, `ttl` all confirmed]
- `.planning/phases/07-multi-season-selector/07-CONTEXT.md` — locked decisions D-01 through D-08 [VERIFIED: read in this session]
- `.planning/research/ARCHITECTURE.md` — caching strategy, two-function TTL split, season threading analysis [VERIFIED: read in this session]
- `.planning/research/PITFALLS.md` — Pitfalls 10–16 covering multi-season wiring hazards [VERIFIED: read in this session]

### Secondary (MEDIUM confidence)

- `.planning/research/SUMMARY.md` — overall architecture and established patterns [VERIFIED: read in this session]
- ARCHITECTURE.md §Historical roster endpoint — "community-confirmed the `season` param works on roster/gameLog endpoints for past seasons; no official MLB API docs" [CITED: .planning/research/ARCHITECTURE.md]

### Tertiary (LOW confidence — validate during implementation)

- `rosterType=fullSeason` endpoint behavior for past seasons — community reports only, not official docs [ASSUMED]

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — no new dependencies; all library behavior verified against running interpreter
- Architecture patterns: HIGH — all integration points identified from direct codebase read; patterns derived from existing code
- Pitfalls: HIGH — all derived from v1.1 PITFALLS.md (which was researched with direct codebase inspection) plus direct code audit in this session
- Historical roster endpoint: MEDIUM — community-confirmed, requires fixture test before shipping

**Research date:** 2026-04-16
**Valid until:** 2026-05-16 (stable Streamlit API; MLB StatsAPI endpoint behavior could change silently)
