# Phase 1: Foundation & API Layer - Research

**Researched:** 2026-04-14
**Domain:** Python package scaffolding + cached HTTP wrappers over `statsapi.mlb.com` + disk-backed venue cache + JSON fixture capture
**Confidence:** HIGH (response shapes verified live against the API; `st.cache_data` semantics verified from official Streamlit docs). Two items are LOW/MEDIUM and flagged for user confirmation in the Assumptions Log.

## Summary

Everything about Phase 1's surface area is *already decided* — what this research does is nail down the specific JSON shapes, the surprising details (5 fieldInfo distance keys, not 6–7; game feeds are ~760 KB not 1–5 MB; only a specific `playEvents` entry carries `hitData`), and the small gotchas that bite if missed (`st.cache_data` silently no-ops with a `ScriptRunContext` warning when called from a plain Python script; Windows `os.replace` semantics for atomic writes; an `src/` layout *requires* a `pyproject.toml` even with "requirements.txt only" style because editable installs are how Python finds `src/`-layout packages).

All five endpoints were probed live today against real 2026-season data for Aaron Judge (personId 592450, verified via Yankees roster lookup — 26 active roster members, Judge present, jersey #99, position RF). He has 5 HR games across 17 played so far in 2026, all `gameType=R`. The server-side `gameType=R` filter on the gameLog endpoint works; no client-side filtering needed. Game feeds live at `/api/v1.1/game/{gamePk}/feed/live` and return ~760 KB compressed JSON — five times smaller than the PITFALLS.md worst-case estimate — so the fan-out concern for fixture capture is mild.

**Primary recommendation:** Build exactly six Python files (`config.py`, `services/mlb_api.py`, `scripts/record_fixtures.py`, `scripts/smoke.py`, `pyproject.toml`, `requirements.txt`), one function per endpoint, TTLs as strings ("7d"/"6h"/"1h"/"24h"), keep the disk-cache concern inside a single `load_all_parks()` helper, and expose a `streamlit run scripts/smoke_app.py` as the smoke validation (running smoke as plain Python will appear to work but `@st.cache_data` silently degrades). Fixture recording uses the same `mlb_api` functions with a test-only cache-bypass flag, and writes raw JSON to `tests/fixtures/` with the filename convention the CONTEXT.md §Claude's Discretion already suggests.

## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01:** `src/` layout. Package at `src/mlb_park/` with submodules per `research/ARCHITECTURE.md`. Requires `pyproject.toml` for editable install (`uv pip install -e .`).
- **D-02:** Streamlit entry point is `src/mlb_park/app.py`. Run with `streamlit run src/mlb_park/app.py`. Single-page — no `pages/` directory.
- **D-03:** JSON fixtures live at `tests/fixtures/` (repo-root, outside the package). Loaded by tests via relative path.
- **D-04:** Runtime disk cache at `data/venues_cache.json` (repo-root). Gitignored. Directory auto-created on first use.
- **D-05:** Calibration target: an Aaron Judge 2026 regular-season HR with complete `hitData` (non-ITP, distance present, coordinates present). Used in Phase 2.
- **D-06:** Fixture scope: all 2026 regular-season games in which Aaron Judge hit at least one HR. Commit raw JSON for each game feed plus teams, roster, gameLog, and all 30 venue responses.
- **D-07:** Capture method: repeatable `scripts/record_fixtures.py` that calls the live API and writes to `tests/fixtures/`. Re-runnable, no hand-editing.
- **D-08:** Fixture season: **2026** (current season).
- **D-09:** gameLog and HR-pipeline filter include **regular season only** (`gameType=R`). Excludes S/F/D/L/W/A/E.
- **D-10:** Single source of truth: whatever passes the gameType filter is both the HR list and the park-verdict list. No split filters.

### Claude's Discretion

- HTTP timeout, retry policy, and User-Agent string — use reasonable defaults (10 s timeout, retry once on network error, `User-Agent: mlb-park-explorer/0.1 (+https://github.com/local/hobby)`).
- Exact log-level / logging library choice for the scratch validation script.
- File naming inside `tests/fixtures/` (suggest: `teams.json`, `roster_{team_id}.json`, `gamelog_{player_id}_{season}.json`, `feed_{gamePk}.json`, `venue_{venue_id}.json`).
- Whether to include a `Makefile` or `justfile` helper for `record_fixtures` / `smoke` tasks.
- Test framework — pytest is deferred to Phase 2; Phase 1 ships with a scratch smoke script only.

### Deferred Ideas (OUT OF SCOPE)

- **pytest + formal unit test suite** — deferred to Phase 2.
- **Concurrent feed fetching (ThreadPoolExecutor)** — v1 is sequential + cached.
- **Postseason HR inclusion** — explicitly deferred via D-09.
- **Career history / multi-season** — out of scope per PROJECT.md.

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| DATA-04 | API fetches are cached via `st.cache_data` with per-endpoint TTLs (venues long, gameLog hourly, completed game feeds daily+) | "Standard Stack" pins streamlit ≥1.55 with native `ttl=` string support; "Code Examples §Five Cached Wrappers" shows the exact decorator pattern; "Pitfalls §ScriptRunContext" flags the smoke-script failure mode that can silently mask whether caching is actually working |

## Project Constraints (from CLAUDE.md)

CLAUDE.md embeds `research/STACK.md` verbatim and adds these enforcement rules:

- **Tech stack is fixed:** Python + Streamlit + `requests` + Plotly. Do not introduce new top-level deps.
- **API source:** Direct HTTP to `statsapi.mlb.com/api/v1` only. No `MLB-StatsAPI`, `pybaseball`, or similar wrappers.
- **Rate discipline:** Aggressive caching; never iterate all 162 games per team.
- **Scope:** Current season, single-user local app.
- **Caching:** `@st.cache_data` only. Do *not* add `requests-cache`. Do *not* use `st.cache_resource` for JSON return values — it's reserved for connections/singletons.
- **GSD workflow enforcement:** File edits must go through a GSD command. Phase 1 execution will come from `/gsd-execute-phase`.

## Standard Stack

### Core

| Library | Version (verified) | Purpose | Why Standard |
|---------|-------------------|---------|--------------|
| python | 3.12 | Runtime | `[CITED: research/STACK.md]` — mainstream target in April 2026; 3.13 still has sporadic wheel gaps for niche C-ext libs |
| streamlit | `>=1.55,<2.0` (1.56.0 released 2026-03-31) | UI + caching | `[VERIFIED: PyPI via research/STACK.md]` — 1.55 added `on_change` on tabs/popover/expander and `bind=` URL-state (useful in Phase 4, not here) |
| requests | `>=2.32,<3.0` (2.32.x) | HTTP client to `statsapi.mlb.com` | `[CITED: research/STACK.md]` — sync matches Streamlit rerun model |
| plotly | `>=6.0,<7.0` (6.7.0 released 2026-04-09) | Spray chart rendering (Phase 5) | `[VERIFIED: PyPI via research/STACK.md]` — not used in Phase 1 but pinned now to keep the env reproducible |
| pandas | `>=2.2,<3.0` | Tabular data (Phase 3+) | `[CITED: research/STACK.md]` — not used in Phase 1 but pinned now |

### Supporting

None to add in Phase 1. `numpy` arrives transitively via pandas/plotly; `python-dateutil` via pandas.

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| requirements.txt + pyproject.toml (both) | pyproject.toml alone (PEP 621 `[project]`) | `[ASSUMED]` Either works with `uv`, but the ROADMAP success criterion #5 explicitly says *"`requirements.txt` pins streamlit>=1.55,<2.0, ..."* — dropping `requirements.txt` would fail that criterion literally. Recommended: keep both. `pyproject.toml` declares the `mlb_park` package (needed for `src/` layout + editable install). `requirements.txt` pins runtime deps and is what ROADMAP tests against. |
| disk cache on every endpoint | disk cache on venues only | `[CITED: research/ARCHITECTURE.md §Pattern 3]` — venues change on decade timescales; gameLog/feed are already `@st.cache_data`-cached and rebuilding them from disk adds staleness bugs. Venues-only is the right scope. |

**Installation:**

```bash
# 1) Install uv once
pip install uv  # or: winget install --id=astral-sh.uv

# 2) Create venv and install
uv venv
uv pip install -r requirements.txt
uv pip install -e .   # editable install so `from mlb_park.services import mlb_api` resolves
```

**Version verification performed 2026-04-14:**
- `streamlit 1.56.0` published 2026-03-31 `[VERIFIED: PyPI via research/STACK.md]`
- `plotly 6.7.0` published 2026-04-09 `[VERIFIED: PyPI via research/STACK.md]`
- `requests 2.32.x` is the long-stable line `[CITED: research/STACK.md]`
- `pandas 2.2.x` is the PyArrow-dtype-capable line `[CITED: research/STACK.md]`

## Endpoint Contracts (verified live 2026-04-14)

All five endpoints were called against the production API today. Shapes documented below are **verified**, not assumed. URL base: `https://statsapi.mlb.com`.

### 1. `GET /api/v1/teams?sportId=1`

**Optional params:** `season={year}` — verified to return the same 30 teams with or without it. Recommendation: **omit**; the API defaults to current season.

**Response top-level:** `{"copyright": str, "teams": [...30 items]}`

**Per-team keys (verified):**
```
['abbreviation', 'active', 'allStarStatus', 'clubName', 'division',
 'fileCode', 'firstYearOfPlay', 'franchiseName', 'id', 'league',
 'link', 'locationName', 'name', 'season', 'shortName', 'sport',
 'springLeague', 'springVenue', 'teamCode', 'teamName', 'venue']
```

**`team.venue` sub-keys:** `['id', 'link', 'name']` — this is the *home* venue reference used to seed the venue cache (30 unique venue IDs across 30 teams).

**TTL:** `"24h"` (per ROADMAP success criterion #2; research/STACK.md originally suggested `"7d"` — go with ROADMAP's 24h to stay literal to the phase success criteria).

### 2. `GET /api/v1/teams/{teamId}/roster`

**Optional params:** `rosterType` — verified options:
- `active` → 26 players (default if omitted appears to also return active roster) `[VERIFIED: live against Yankees (147)]`
- `40Man` → 39 players
- Other documented values exist (`fullSeason`, `depthChart`) but untested in this session.

**Recommendation:** Use `rosterType=active` explicitly. The `active` set is what's playing and hitting HRs right now. Phase 4's hitter dropdown needs non-pitcher filter — that filter happens downstream, not here.

**Response top-level:** `{"copyright", "roster": [...], "link", "teamId", "rosterType"}`

**Per-roster-entry keys:**
```
['jerseyNumber', 'parentTeamId', 'person', 'position', 'status']
```
- `person`: `{'id': int, 'fullName': str, 'link': str}`
- `position`: `{'code': str, 'name': str, 'type': str, 'abbreviation': str}`
- `status`: `{'code': str, 'description': str}`

Judge verified present: `{'id': 592450, 'fullName': 'Aaron Judge', ..., 'jerseyNumber': '99', 'position.abbreviation': 'RF'}`. **personId 592450 confirmed via live Yankees roster fetch.**

**TTL:** `"6h"` (per ROADMAP criterion #2).

### 3. `GET /api/v1/people/{personId}/stats?stats=gameLog&group=hitting&season={year}&gameType=R`

**The `gameType=R` server-side filter works** `[VERIFIED: 2026-04-14]`. All 17 returned splits for Judge 2026 had `gameType: 'R'` both with and without the filter (because the season hasn't yet entered postseason). Server-side filtering is still safer for later-season queries — use it.

**Optional params beyond the four above:** `startDate`/`endDate` exist per community docs but unnecessary given season scoping.

**Response top-level:** `{"copyright", "stats": [one item]}`. `stats[0]` keys: `['exemptions', 'group', 'splits', 'type']`. `splits` is the per-game list.

**Per-split keys:**
```
['date', 'game', 'gameType', 'isHome', 'isWin', 'league', 'opponent',
 'player', 'positionsPlayed', 'season', 'sport', 'stat', 'team']
```
- `split.game`: `{'content': {...}, 'dayNight': str, 'gameNumber': int, 'gamePk': int, 'link': str}` — **`gamePk` lives here** (split.game.gamePk)
- `split.stat`: hitting stat line for that game; includes `homeRuns` as an **int** (verified: `sp['stat']['homeRuns']` is `0` for non-HR games, `1+` for HR games). Full stat keys include: `atBats, hits, homeRuns, doubles, triples, rbi, baseOnBalls, strikeOuts, avg, obp, slg, ops, ...` (40+ keys).

**HR-game filter:** `[sp for sp in splits if int(sp['stat']['homeRuns']) >= 1]` — Judge 2026 yields 5 games.

**TTL:** `"1h"` (per ROADMAP criterion #2).

### 4. `GET /api/v1.1/game/{gamePk}/feed/live`  ⚠ note: `v1.1` not `v1`

**Verified size:** 760,212 bytes (~742 KB) for Judge's 2026-03-27 game (gamePk 823243). This is 5× smaller than PITFALLS.md's "1–5 MB" worst-case. Fan-out concern for fixture capture: 5 games × ~750 KB = ~3.7 MB total — negligible.

**No query parameters needed.**

**Response top-level keys:** `['copyright', 'gameData', 'gamePk', 'liveData', 'link', 'metaData']`

**Keys we care about in Phase 3 but should fixture now:**
- `gamePk` (top-level int)
- `gameData.venue` → contains `{id, name, location: {azimuthAngle, elevation, ...}, fieldInfo: {...}, ...}` **inline**. Note: `fieldInfo` is duplicated here (the feed has the stadium's dimensions without a separate venue call), but we still call the venue endpoint separately for the 30-venue cache per ARCHITECTURE Pattern 3.
- `gameData.teams` → home/away team metadata
- `liveData.plays.allPlays` → list of play dicts (67 plays in the sample game)

**Per-play shape (for HR plays):**
```python
play = {
    'about': {'atBatIndex': int, 'halfInning': str, 'inning': int,
              'startTime': ISO-datetime, 'endTime': ISO-datetime,
              'isComplete': bool, 'isScoringPlay': bool, 'hasReview': bool,
              'captivatingIndex': int, ...},
    'result': {'type': 'atBat', 'event': 'Home Run',
               'eventType': 'home_run',          # <-- filter key
               'description': str, 'rbi': int, 'awayScore': int, 'homeScore': int, ...},
    'matchup': {'batter': {'id': int, 'fullName': str, 'link': str}, ...},
    'playEvents': [...],   # N events; the ball-in-play event carries hitData
}
```

**`hitData` location (critical for Phase 3):** On a HR play, exactly one `playEvents` entry carries `hitData`. In the verified sample it was the **last** entry (`playEvents[-1]` — `ev[7]` of 8). Keys present on that event: `['count', 'details', 'endTime', 'hitData', 'index', 'isPitch', 'pitchData', 'pitchNumber', 'playId', 'startTime', 'type']`.

**`hitData` sample (Judge 2026-03-27 HR):**
```json
{
  "launchSpeed": 109.1,
  "launchAngle": 37.0,
  "totalDistance": 405.0,
  "trajectory": "fly_ball",
  "hardness": "medium",
  "location": "7",
  "coordinates": {"coordX": 12.7, "coordY": 78.83}
}
```

This is a **complete calibration-eligible HR** (D-05 target) — non-ITP, distance present, coordinates present. `(coordX=12.7, coordY=78.83)` with totalDistance=405 to LF is the kind of point Phase 2 will back-solve the coord-to-feet transform against.

**TTL:** `"7d"` (per ROADMAP criterion #2 — "completed feeds 7d"). Note that for in-progress games the feed is mutable; Phase 1 doesn't need to distinguish — Phase 3 can add a shorter TTL for in-progress if needed.

### 5. `GET /api/v1/venues/{venueId}?hydrate=location,fieldInfo`

**Response top-level:** `{"copyright", "venues": [one item]}`. Unwrap with `response["venues"][0]`.

**Per-venue keys (verified):** `['active', 'fieldInfo', 'id', 'link', 'location', 'name', 'season']`

**`fieldInfo` keys ⚠ CORRECTION of research/PITFALLS.md:**

PITFALLS.md claims "6 or 7 distance labels: `leftLine, left, leftCenter, center, rightCenter, right, rightLine`." **Live verification of two venues today returned 5 distance labels only:** `leftLine, leftCenter, center, rightCenter, rightLine`. There is no `left` or `right` intermediate point.

Verified samples:
- Yankee Stadium (id 3313): `{leftLine: 318, leftCenter: 399, center: 408, rightCenter: 385, rightLine: 314}` plus `capacity, turfType, roofType`.
- Daikin Park / Houston (id 2392): `{leftLine: 315, leftCenter: 362, center: 409, rightCenter: 373, rightLine: 326}` plus same three non-distance keys.
- Oracle Park fieldInfo (seen inline in game feed): `{leftLine: 339, leftCenter: 399, center: 391, rightCenter: 415, rightLine: 309}`.

**Implication for Phase 2:** The angle-to-distance table is **5 points, not 6–7**. Phase 2's `park_model.py` should handle 5 points as the base case. The extra `left`/`right` labels PITFALLS.md mentioned may be historical or may appear on some venues — Phase 1 fixture capture across all 30 venues will answer this definitively. If any venue returns a richer key set, document it in the fixture diff.

**`location` keys:** `['address1', 'azimuthAngle', 'city', 'country', 'defaultCoordinates', 'elevation', 'phone', 'postalCode', 'state', 'stateAbbrev']` — `azimuthAngle` is ballpark orientation (home-plate-to-center-field compass bearing, degrees). Not needed in Phase 1 but it will matter in Phase 5 for correct LF/CF/RF labeling.

**Non-MLB venues:** Not a concern. Venue IDs we call are the 30 home venues discovered via `/teams?sportId=1`, all of which returned full `fieldInfo` in prior research. `[ASSUMED]` No non-MLB venue will be queried in this phase — spring-training / minor-league venues are excluded by `gameType=R` filter upstream.

**TTL:** `"24h"` in-memory (per ROADMAP criterion #2). **30-day on-disk fallback** (per ROADMAP criterion #2 and D-04).

## Architecture Patterns

### Recommended Project Structure

```
streamlit-mlb-api/                # repo root (CWD)
├── pyproject.toml                # PEP 621 — declares mlb_park package, needed for src/ layout
├── requirements.txt              # ROADMAP-mandated pin file
├── .gitignore                    # includes data/ and .streamlit/ and tmp
├── README.md
├── src/
│   └── mlb_park/
│       ├── __init__.py
│       ├── app.py                # EMPTY stub in Phase 1 (Streamlit entry — filled Phase 4)
│       ├── config.py             # BASE_URL, TTL_*, HTTP_TIMEOUT, USER_AGENT, VENUES_FILE
│       └── services/
│           ├── __init__.py
│           └── mlb_api.py        # THE Phase 1 deliverable: 5 cached functions + load_all_parks()
├── scripts/
│   ├── smoke.py                  # Runs INSIDE streamlit: `streamlit run scripts/smoke.py`
│   └── record_fixtures.py        # Plain python: captures fixtures, bypasses cache
├── tests/
│   └── fixtures/
│       ├── teams.json
│       ├── roster_147.json       # Yankees
│       ├── gamelog_592450_2026.json
│       ├── feed_823243.json      # + one file per HR game
│       └── venue_3313.json       # + one file per unique venue (30 total)
└── data/                         # gitignored, auto-created
    └── venues_cache.json
```

### Pattern 1: Five Cached Endpoint Wrappers (ONE function per endpoint)

**What:** Each endpoint is one top-level function in `services/mlb_api.py` decorated with `@st.cache_data(ttl=...)`.

**When to use:** Always. Never call `requests.get` outside this module.

**Example:**

```python
# src/mlb_park/services/mlb_api.py
# Source: research/ARCHITECTURE.md §Pattern 1, verified shape from live API probe 2026-04-14
import json, time, os, tempfile
from pathlib import Path
import requests
import streamlit as st
from mlb_park.config import (
    BASE_URL_V1, BASE_URL_V11, HTTP_TIMEOUT, USER_AGENT,
    TTL_TEAMS, TTL_ROSTER, TTL_GAMELOG, TTL_VENUE, TTL_FEED,
    VENUES_FILE, VENUES_STALE_DAYS,
)

_session = requests.Session()
_session.headers["User-Agent"] = USER_AGENT

class MLBAPIError(RuntimeError):
    pass

def _get(url: str, params: dict | None = None) -> dict:
    """Shared GET with timeout, one retry, consistent error shape. NOT cached here —
    cache decorator is applied at the endpoint-function level so cache keys are
    typed by endpoint+ids, not by URL string."""
    try:
        r = _session.get(url, params=params, timeout=HTTP_TIMEOUT)
        r.raise_for_status()
        return r.json()
    except requests.RequestException as e:
        # one retry
        time.sleep(1.0)
        try:
            r = _session.get(url, params=params, timeout=HTTP_TIMEOUT)
            r.raise_for_status()
            return r.json()
        except requests.RequestException as e2:
            raise MLBAPIError(f"GET {url} failed: {e2}") from e2

@st.cache_data(ttl=TTL_TEAMS, show_spinner=False)   # "24h"
def get_teams() -> list[dict]:
    return _get(f"{BASE_URL_V1}/teams", params={"sportId": 1})["teams"]

@st.cache_data(ttl=TTL_ROSTER, show_spinner=False)  # "6h"
def get_roster(team_id: int) -> list[dict]:
    return _get(f"{BASE_URL_V1}/teams/{team_id}/roster",
                params={"rosterType": "active"})["roster"]

@st.cache_data(ttl=TTL_GAMELOG, show_spinner=False) # "1h"
def get_game_log(person_id: int, season: int) -> list[dict]:
    resp = _get(f"{BASE_URL_V1}/people/{person_id}/stats",
                params={"stats": "gameLog", "group": "hitting",
                        "season": season, "gameType": "R"})
    stats = resp.get("stats", [])
    if not stats:
        return []
    return stats[0].get("splits", [])

@st.cache_data(ttl=TTL_FEED, show_spinner=False)    # "7d"
def get_game_feed(game_pk: int) -> dict:
    return _get(f"{BASE_URL_V11}/game/{game_pk}/feed/live")

@st.cache_data(ttl=TTL_VENUE, show_spinner=False)   # "24h"
def get_venue(venue_id: int) -> dict:
    return _get(f"{BASE_URL_V1}/venues/{venue_id}",
                params={"hydrate": "location,fieldInfo"})["venues"][0]
```

### Pattern 2: Disk-Backed Venue Cache with Atomic Write

**What:** `load_all_parks()` reads `data/venues_cache.json` if fresh (< 30 days); else fetches all 30 venues and writes atomically.

**Why:** `@st.cache_data` is in-memory per Streamlit process — restart the app and it's cold. Venues change rarely. Disk cache eliminates 30 network calls per cold start.

**Atomic write on Windows** `[VERIFIED: Python docs — `os.replace` is atomic on Windows and POSIX]`:

```python
def _atomic_write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    # Write to a temp file in the SAME directory, then os.replace().
    # os.replace is atomic on Windows (PEP 428) and POSIX.
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".tmp-", suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f)
        os.replace(tmp, path)
    except Exception:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise

def load_all_parks() -> dict[int, dict]:
    """Return {venue_id: venue_dict} for all 30 team home venues.
    Reads from disk cache if present + fresh; otherwise rebuilds from API."""
    if VENUES_FILE.exists():
        age_days = (time.time() - VENUES_FILE.stat().st_mtime) / 86400
        if age_days < VENUES_STALE_DAYS:
            raw = json.loads(VENUES_FILE.read_text(encoding="utf-8"))
            return {int(k): v for k, v in raw.items()}
    # Rebuild
    team_venues = {t["venue"]["id"] for t in get_teams()}
    result = {vid: get_venue(vid) for vid in sorted(team_venues)}
    _atomic_write_json(VENUES_FILE, {str(k): v for k, v in result.items()})
    return result
```

**Cross-process write gotcha on Windows:** If the Streamlit server is running AND `record_fixtures.py` also runs, both processes could try to write. Phase 1 does not need concurrent-write safety — the scripts are manually-invoked and not long-running. Document this as a known limitation: **do not run `record_fixtures.py` while a Streamlit session is actively refetching venues.**

### Pattern 3: Smoke Script via `streamlit run` (not plain python)

**Critical gotcha:** Running a script that imports `streamlit` and calls `@st.cache_data`-decorated functions via `python scripts/smoke.py` emits repeated `"missing ScriptRunContext"` warnings and **the cache silently no-ops** — every call hits the network. The function still returns correctly, so "the smoke script returned JSON" would be a false success for ROADMAP criterion #2.

**Recommendation:** The smoke validation *must* run under `streamlit run`. Create `scripts/smoke.py` as a minimal Streamlit page that calls all five endpoints and renders shape summaries via `st.json` / `st.write`, so criterion #2 is verifiable by visual inspection plus a network inspector showing a cold-then-warm call pattern.

Template:

```python
# scripts/smoke.py — invoke with: streamlit run scripts/smoke.py
import streamlit as st
from mlb_park.services import mlb_api

st.title("Phase 1 Smoke Validation")

st.header("1. Teams")
teams = mlb_api.get_teams()
st.write(f"Got {len(teams)} teams. Sample:", teams[0]["name"])

st.header("2. Roster (Yankees)")
roster = mlb_api.get_roster(147)
st.write(f"Got {len(roster)} roster entries. Judge present:",
         any(p["person"]["id"] == 592450 for p in roster))

st.header("3. GameLog (Judge 2026)")
log = mlb_api.get_game_log(592450, 2026)
hr_games = [g for g in log if int(g["stat"]["homeRuns"]) >= 1]
st.write(f"Got {len(log)} games, {len(hr_games)} with HRs")

st.header("4. Game Feed (first HR game)")
if hr_games:
    feed = mlb_api.get_game_feed(hr_games[0]["game"]["gamePk"])
    st.write("Feed gamePk:", feed["gamePk"], "venue:", feed["gameData"]["venue"]["name"])

st.header("5. All 30 Parks (disk cache)")
parks = mlb_api.load_all_parks()
st.write(f"Got {len(parks)} parks. Sample fieldInfo:",
         next(iter(parks.values()))["fieldInfo"])
st.success("Re-run to verify the second load is from disk (check file mtime vs. logs).")
```

### Pattern 4: Fixture Recording Script

**What:** `scripts/record_fixtures.py` is a plain python script (runnable as `python scripts/record_fixtures.py`) that captures raw JSON to `tests/fixtures/` *without going through `@st.cache_data`*.

**Why not through the decorators:** (a) The script runs outside `streamlit run` so decorators silently no-op anyway (Pattern 3). (b) We want to guarantee a fresh fetch — stale cached data would become a baked-in fixture. (c) The decorators' pickle-based cache doesn't match the raw-JSON fixture format Phase 2+ tests expect.

**Recommendation:** Factor the raw HTTP calls into private helpers (`_raw_teams`, `_raw_roster`, `_raw_game_log`, `_raw_game_feed`, `_raw_venue`) that are wrapped by the public `@st.cache_data`-decorated functions. `record_fixtures.py` imports the private helpers. The decorated public API stays clean.

Flow:

1. Call `_raw_teams(sportId=1)` → write `tests/fixtures/teams.json`.
2. Extract Yankees (team id 147) — call `_raw_roster(147)` → write `tests/fixtures/roster_147.json`.
3. Call `_raw_game_log(592450, 2026)` → write `tests/fixtures/gamelog_592450_2026.json`.
4. Filter to `homeRuns >= 1` games (expect 5 as of 2026-04-14). For each, `_raw_game_feed(gamePk)` → write `tests/fixtures/feed_{gamePk}.json`.
5. For each of the 30 team home venue IDs (dedup from step 1): `_raw_venue(vid)` → write `tests/fixtures/venue_{vid}.json`.
6. Log summary to stdout (counts per file type).

**Edge case for D-10 / ROADMAP criterion #4:** Criterion #4 requires fixtures for "at least one team, roster, gameLog, game feed, and venue". **Today (2026-04-14) Judge has 5 HRs, so 5 game feeds is fine.** If the script is run on a date when Judge has 0 HRs (e.g., a slump week, or early April of a future re-run), capture an **empty fixture** (`tests/fixtures/feeds_empty.note.txt` with date + "Judge had 0 HRs on this capture date") rather than silently skipping — criterion #4 says "at least one" which is satisfied by the 5 existing; re-runs should not delete older HR-game fixtures. **Recommendation: `record_fixtures.py` writes HR-game feeds as additive, never deletes existing ones.** Document this in the script docstring.

**Judge personId resolution:** D-05 says "verify personId during planning by calling `/teams/147/roster` (Yankees) and filtering by name." This has been done this session: **592450 confirmed.** Hardcode `JUDGE_PERSON_ID = 592450` in `scripts/record_fixtures.py` but include a verification line at script start:
```python
roster = _raw_roster(147)
judge = next((p for p in roster if p["person"]["id"] == JUDGE_PERSON_ID), None)
assert judge and "Judge" in judge["person"]["fullName"], "personId 592450 no longer matches Aaron Judge"
```

### Anti-Patterns to Avoid

- **`requests.get(url)` without timeout** — one stalled call hangs the whole Streamlit rerun. Always pass `timeout=HTTP_TIMEOUT`.
- **Caching the `requests.Session` as a decorator arg** — `UnhashableParamError`. Session is a module-level singleton, never a parameter.
- **`@st.cache_resource` for JSON return values** — that decorator is for connection/model singletons; use `@st.cache_data` for dicts.
- **Pickling the Session inside `@st.cache_data` returns** — never return the Session; return the parsed dict/list.
- **Running smoke as plain python** — silently no-ops the cache decorators (see Pattern 3).
- **Writing fixtures through `@st.cache_data`-decorated functions** — stale cache poisons fixtures (see Pattern 4).
- **Non-atomic write to `venues_cache.json`** — a SIGTERM mid-write leaves the next run reading truncated JSON. Use `_atomic_write_json`.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| HTTP caching across processes | Custom file-per-URL hash cache | `@st.cache_data` + disk venue file | Two invalidation models = bugs; research/STACK.md locked this decision |
| Retry logic with backoff | Manual `for i in range(3): try: ...` | One retry after 1s (it's enough for transient MLB CDN blips) + `requests.Session` default connection pooling | For a hobby app's ~40 calls/session, anything more is theater |
| Atomic file write | `open("file", "w")` and hope | `tempfile.mkstemp(dir=same-parent)` + `os.replace()` | `os.replace` is documented atomic on Windows + POSIX |
| JSON dict-of-ints ↔ file roundtrip | Custom serializer | `json.dumps({str(k): v, ...})` and `{int(k): v for k, v in ...}` on load | JSON keys must be strings; just convert at the boundary |
| Venue-freshness check | `datetime` diff math | `time.time() - path.stat().st_mtime` / 86400 | One-liner, no imports of `datetime` needed for this purpose |
| Fixture diffing | Custom diff tool | `git diff tests/fixtures/` | Git is the diff tool; re-run the script and commit |

**Key insight:** Phase 1's complexity is *entirely* in getting the five endpoint shapes right and the caching behavior provably correct. Every other line of code in the phase should be boring.

## Runtime State Inventory

N/A — greenfield phase. No prior runtime state exists; no renames/refactors involved.

## Common Pitfalls

### Pitfall 1: `st.cache_data` silently no-ops outside `streamlit run`

**What goes wrong:** `python scripts/smoke.py` emits `missing ScriptRunContext` warnings but still returns real data. ROADMAP criterion #2 says "Every endpoint wrapper is decorated with `@st.cache_data`" — this is trivially satisfied by the decorator being present, but *verifying caching is working* requires a Streamlit context.
**Why it happens:** `st.cache_data` needs a ScriptRunContext from the Streamlit runtime; plain Python has none.
**How to avoid:** Smoke runs via `streamlit run scripts/smoke.py`. Fixture recording runs as plain python against private un-decorated helpers.
**Warning signs:** "missing ScriptRunContext" warnings in console; every call hits the network even on "cold second run"; ROADMAP criterion #3 silently fails (second run re-fetches all 30 venues).

### Pitfall 2: `fieldInfo` has 5 distance keys, not 6 or 7

**What goes wrong:** Code written against the PITFALLS.md description (expects `left` and `right` alongside `leftCenter`, `leftLine`) raises KeyError on every venue.
**Why it happens:** research/PITFALLS.md's 6-label claim appears to pre-date the current API shape (or refers to a different hydrate option). Live verification of Yankee Stadium, Houston, and Oracle Park shows 5 keys consistently: `leftLine, leftCenter, center, rightCenter, rightLine`.
**How to avoid:** Code defensively: `fieldInfo.get("left")` returns None. Phase 2's park_model handles 5 labeled angles by default, and during fixture capture record ALL 30 venues so any variation surfaces immediately in the JSON.
**Warning signs:** KeyError on `fieldInfo["left"]`. Phase 2 tests failing on specific venues. Fixture-diff showing different key sets between venues.

### Pitfall 3: `gamePk` is nested under `split.game.gamePk`, not `split.gamePk`

**What goes wrong:** `[g["gamePk"] for g in splits]` raises KeyError. The key is at `g["game"]["gamePk"]`.
**Why it happens:** The gameLog response nests per-game metadata under a `game` sub-object alongside `stat`, `team`, `opponent`, etc.
**How to avoid:** Always reach via `split["game"]["gamePk"]`. Type-hint helpers that extract this to avoid typos.
**Warning signs:** KeyError in Phase 3's extraction loop; or worse, silently returning zero HR games because the wrong key is checked.

### Pitfall 4: `hitData` lives on a specific `playEvents` entry, not on the play

**What goes wrong:** `play["hitData"]` is never present. The HR play has an `allPlays` entry; `hitData` is on one of its `playEvents` children — specifically the ball-in-play event (in the verified sample, `playEvents[-1]`).
**Why it happens:** The StatsAPI represents at-bat events as an outer "play" with an inner sequence of `playEvents` (pitches, balls in play, reviews). Hit tracking attaches to the contact event, not the at-bat summary.
**How to avoid:** In Phase 3 (not Phase 1), iterate `play["playEvents"]` and pick the one where `"hitData" in ev`. For Phase 1 fixture capture, the raw JSON just needs to be saved intact — Phase 3 parses it.
**Warning signs:** Phase 3 extraction returning empty coordinates; `hitData is None` on every HR. (Flagged here because Phase 1 fixtures must contain the nesting correctly — don't try to "flatten" them on capture.)

### Pitfall 5: `src/` layout without editable install → ImportError

**What goes wrong:** With `src/mlb_park/` layout, running `streamlit run src/mlb_park/app.py` may import successfully *due to path shenanigans* but running `python scripts/smoke.py` fails: `ModuleNotFoundError: No module named 'mlb_park'`.
**Why it happens:** Python doesn't auto-add `src/` to `sys.path`. The fix is `pip install -e .`, which requires a `pyproject.toml` declaring the package.
**How to avoid:** `pyproject.toml` must have `[project]` with `name = "mlb-park"` and a `[tool.setuptools.packages.find]` (or equivalent) pointing at `src`. Install step is `uv pip install -e .`.
**Warning signs:** ImportError on any invocation outside `streamlit run` from repo root. README must document the `pip install -e .` step explicitly.

### Pitfall 6: Streamlit pins vs. ROADMAP literal criterion

**What goes wrong:** ROADMAP criterion #5 says `plotly 6.7`. That reads as `==6.7.x`. But research/STACK.md says `>=6.0,<7.0`. An exact pin of `6.7` would fail once `6.8` ships.
**Why it happens:** Casual language in the ROADMAP.
**How to avoid:** Interpret ROADMAP criterion #5 charitably: pin ranges that include the named versions (`plotly>=6.7,<7.0` is the faithful translation). Confirm with user during planning — this is in the Assumptions Log.
**Warning signs:** None until plotly 6.8 ships and users of the repo can't get exact matches.

## Code Examples

See `Pattern 1` (five cached wrappers) and `Pattern 2` (disk cache + atomic write) above for verified code. Additional config template:

### `src/mlb_park/config.py`

```python
# Source: research/STACK.md TTL guide + ROADMAP §Phase 1 success criteria
from pathlib import Path

BASE_URL_V1  = "https://statsapi.mlb.com/api/v1"
BASE_URL_V11 = "https://statsapi.mlb.com/api/v1.1"

HTTP_TIMEOUT = (5, 15)   # (connect, read) — research/PITFALLS.md §7
USER_AGENT   = "mlb-park-explorer/0.1 (+https://github.com/local/hobby)"

# TTLs — strings per st.cache_data native format, per ROADMAP criterion #2
TTL_TEAMS    = "24h"
TTL_ROSTER   = "6h"
TTL_GAMELOG  = "1h"
TTL_VENUE    = "24h"
TTL_FEED     = "7d"

# Disk cache
_ROOT = Path(__file__).resolve().parents[2]  # src/mlb_park/config.py -> repo root
VENUES_FILE        = _ROOT / "data" / "venues_cache.json"
VENUES_STALE_DAYS  = 30

# Known IDs (verified 2026-04-14)
YANKEES_TEAM_ID    = 147
JUDGE_PERSON_ID    = 592450
```

### `pyproject.toml` (minimal)

```toml
[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[project]
name = "mlb-park"
version = "0.1.0"
requires-python = ">=3.12"
# Runtime deps mirrored in requirements.txt for ROADMAP criterion #5
dependencies = [
    "streamlit>=1.55,<2.0",
    "requests>=2.32,<3.0",
    "plotly>=6.7,<7.0",
    "pandas>=2.2,<3.0",
]

[tool.setuptools.packages.find]
where = ["src"]
```

### `requirements.txt`

```
streamlit>=1.55,<2.0
requests>=2.32,<3.0
plotly>=6.7,<7.0
pandas>=2.2,<3.0
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `st.cache` (unified cache) | `st.cache_data` / `st.cache_resource` split | Streamlit 1.18 (2023); `st.cache` removed in 1.45 | Only `st.cache_data` applies here |
| `st.experimental_rerun()` | `st.rerun()` | Streamlit 1.40 (2024) | Not used in Phase 1 but avoid the old name in any scaffolding |
| `requests-cache` or custom file cache for API data | `@st.cache_data(ttl=...)` | Streamlit's split in 2023 made this canonical | Locked in STACK.md |

**Deprecated/outdated:**
- `st.cache` — removed as of 1.45.
- `datetime.utcnow()` — `datetime.now(timezone.utc)` in Python 3.13+; we use `time.time()` for venue mtime math so this doesn't touch us.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `plotly>=6.7,<7.0` faithfully translates ROADMAP criterion #5's "`plotly 6.7`" | Endpoint Contracts → Standard Stack → pyproject.toml | LOW — if user wanted an exact `==6.7.x` pin they should say so; `<7.0` is the literally safer upper bound |
| A2 | A `pyproject.toml` + `requirements.txt` pair is acceptable (CONTEXT.md and STACK.md disagree — CONTEXT §D-01 says pyproject is required for src/ layout; STACK says "Keep it a flat requirements.txt"; ROADMAP criterion #5 tests requirements.txt). Recommended: keep BOTH. | Architecture Patterns → Project Structure | LOW — redundant pins are a minor maintenance papercut, not a bug |
| A3 | All 30 MLB venues return `fieldInfo` with exactly 5 distance keys (verified: 3 of 30 — Yankee Stadium, Houston, Oracle via feed). The remaining 27 may include a `left`/`right` intermediate. | Endpoint Contracts #5 | MEDIUM — Phase 2's `park_model` assumption of 5 points would need extension if some venues have 6+. **Phase 1 fixture capture (all 30 venues) resolves this.** |
| A4 | MLB StatsAPI has no formal rate limit; community reports suggest >20 req/s sustained triggers throttling. We make ~40 calls in a full fixture capture over several seconds — well below any threshold. | Pattern 4 (fixture recording) | LOW — if throttled, sequential capture + one retry handles it |
| A5 | PITFALLS.md's "6 or 7 fieldInfo keys" claim is outdated rather than venue-specific. Resolution via fixture capture of all 30 venues. | Pitfall #2 | MEDIUM — see A3 |
| A6 | `scripts/record_fixtures.py` should be **additive** on re-run (never delete older feed fixtures even if Judge has fewer HRs on a later run). CONTEXT.md §D-07 says "re-runnable, do not hand-edit" but doesn't specify additive vs. replace-all behavior. **User confirmation recommended.** | Pattern 4 | LOW-MEDIUM — replacing rather than adding would cause a re-run on 2026-04-20 to wipe earlier-April fixtures if Judge's HR set changed, potentially destroying the Phase 2 calibration target |
| A7 | `rosterType=active` (26 players) is the correct default for Phase 1 fixture capture. The Phase 4 dropdown will also use `active`. `40Man` would include minor-league rehab assignments. | Endpoint Contracts #2 | LOW — can switch later without schema impact |
| A8 | Smoke validation runs via `streamlit run scripts/smoke.py`, not plain python. ROADMAP criterion #1 says "Running a scratch script" — user might expect plain python. **Flagged for user confirmation.** | Pattern 3 | MEDIUM — if user insists on plain-python smoke, we need a fallback shim: `try: from streamlit.runtime.scriptrunner import get_script_run_ctx; if get_script_run_ctx() is None: wrap with dict` — not complicated but worth explicit agreement |

## Open Questions

1. **Fixture-recording re-run semantics (A6): additive or replace-all?**
   - What we know: CONTEXT.md §D-07 says re-runnable, no hand-editing. Doesn't specify idempotency semantics.
   - What's unclear: If 2026-04-14 capture yields feeds for gamePks `[823243, 824011, 824112, 824217, 824333]` and a 2026-05-01 re-run yields feeds for a different set (game corrections, reclassifications), should old files stay?
   - Recommendation: Additive by default. If user wants clean re-capture, delete `tests/fixtures/feed_*.json` manually before rerun. Document in the script docstring.

2. **Smoke-script execution model (A8): `streamlit run` or plain python?**
   - What we know: `@st.cache_data` silently no-ops outside streamlit. ROADMAP uses the word "scratch script" (ambiguous).
   - What's unclear: User preference for the validation UX.
   - Recommendation: `streamlit run scripts/smoke.py` (renders a page with visible checkmarks). Plain-python smoke as a bonus, marked as "cache-bypass mode."

3. **Venue-key variation across 30 venues (A3/A5).**
   - What we know: 3/30 verified with exactly 5 keys.
   - What's unclear: Are there venues with more?
   - Recommendation: Phase 1 fixture capture will answer this empirically. No action needed during planning.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|-------------|-----------|---------|----------|
| Python 3.12+ | Runtime | `[ASSUMED: ✓]` — not verified in this session | — | Python 3.11 per STACK.md minimum |
| uv | Install step (STACK.md) | `[ASSUMED: ✓]` | — | `pip install -r requirements.txt` works identically |
| Network to statsapi.mlb.com | Live API probes, fixture capture | ✓ | — (verified via 5 successful probes today) | Offline: use fixtures (after Phase 1 completes) |
| git | Fixture commit (ROADMAP criterion #4) | `[ASSUMED: ✓]` | — | — |

**Skip:** No other external dependencies. No Docker, no databases, no message queues.

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | **None in Phase 1 — deferred to Phase 2 per CONTEXT.md §Deferred Ideas** |
| Config file | none (will be `pyproject.toml` `[tool.pytest.ini_options]` in Phase 2) |
| Quick run command | `streamlit run scripts/smoke.py` then visually verify 5 green sections |
| Full suite command | same as above (no test suite yet) |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|--------------|
| DATA-04 | Each of 5 endpoint wrappers is `@st.cache_data`-decorated with correct TTL | manual-inspection | `grep -n 'st.cache_data' src/mlb_park/services/mlb_api.py` — expect exactly 5 matches with TTLs from config | ❌ Wave 0 |
| DATA-04 (runtime) | Cold 2nd run uses disk venue cache, no network hits for venues | manual-smoke | `streamlit run scripts/smoke.py` twice; on 2nd run, `data/venues_cache.json` mtime unchanged, page renders in <500 ms | ❌ Wave 0 |
| ROADMAP #1 | All 5 endpoints return parsed JSON | manual-smoke | `streamlit run scripts/smoke.py` — all 5 sections show non-empty data | ❌ Wave 0 |
| ROADMAP #3 | 2nd run loads 30 venues from disk without network | manual-smoke | Delete `data/venues_cache.json`; run smoke → file created. Re-run smoke → file mtime unchanged | ❌ Wave 0 |
| ROADMAP #4 | `tests/fixtures/` contains required files | filesystem check | `ls tests/fixtures/ \| wc -l` should exceed 35 (1 teams + 1 roster + 1 gamelog + ~5 feeds + 30 venues) | ❌ Wave 0 (fixture-record script produces) |
| ROADMAP #5 | `requirements.txt` installs cleanly | install-smoke | `uv venv && uv pip install -r requirements.txt && uv pip install -e .` exits 0 | ❌ Wave 0 |

### Sampling Rate

- **Per task commit:** `grep 'st.cache_data' src/mlb_park/services/mlb_api.py \| wc -l` should equal 5; `python -c "import mlb_park.services.mlb_api"` should succeed after `uv pip install -e .`.
- **Per wave merge:** `streamlit run scripts/smoke.py` — all 5 sections green; `python scripts/record_fixtures.py --dry-run` (optional) lists all expected fixture files.
- **Phase gate:** `streamlit run scripts/smoke.py` cold+warm run; `ls tests/fixtures/` confirms files per ROADMAP #4; `git status` shows `data/venues_cache.json` absent (gitignored).

### Wave 0 Gaps

- [ ] `src/mlb_park/__init__.py` — empty package marker
- [ ] `src/mlb_park/services/__init__.py` — empty package marker
- [ ] `src/mlb_park/app.py` — empty stub placeholder (filled Phase 4)
- [ ] `src/mlb_park/config.py` — constants per "Code Examples"
- [ ] `src/mlb_park/services/mlb_api.py` — five wrappers + `load_all_parks`
- [ ] `scripts/smoke.py` — Streamlit smoke page
- [ ] `scripts/record_fixtures.py` — fixture capture
- [ ] `pyproject.toml` — package declaration
- [ ] `requirements.txt` — pinned deps
- [ ] `.gitignore` — includes `data/`, `.streamlit/`, `__pycache__`, `*.egg-info`
- [ ] Framework install: `pip install uv; uv venv; uv pip install -r requirements.txt; uv pip install -e .`

*(pytest install deferred to Phase 2)*

## Security Domain

`security_enforcement` not present in `.planning/config.json` — treat as enabled. Threat surface is small (local hobby app, read-only API, no auth).

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|------------------|
| V2 Authentication | no | N/A — no auth; statsapi.mlb.com is public/unauth |
| V3 Session Management | no | N/A |
| V4 Access Control | no | N/A — single-user local |
| V5 Input Validation | yes | Validate `team_id`, `person_id`, `venue_id`, `game_pk`, `season` are integers before URL-formatting. Prevents SSRF in the theoretical case that a selector ever templates user input |
| V6 Cryptography | no | N/A — no secrets, no crypto primitives |
| V12 Files & Resources | yes | Atomic write to `data/venues_cache.json`; path joining via `pathlib.Path`, not string concat |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| SSRF via unvalidated ID in URL template | Tampering | Enforce `isinstance(id, int)` at the wrapper boundary; all five wrappers in Pattern 1 annotate types — add `assert isinstance(team_id, int)` to be explicit |
| Partial-write corruption of `venues_cache.json` | Availability (DoS of the cache path) | `tempfile.mkstemp` + `os.replace()` (see Pattern 2) |
| Log/UA leaking personal email | Information Disclosure | User-Agent in `config.py` uses a generic GitHub URL, no email (per Claude's Discretion) |
| MLB API TOS breach via sharing publicly | Legal | App is local-only per PROJECT.md; if ever shared, add auth + rate limiting (out of scope Phase 1) |

## Sources

### Primary (HIGH confidence)

- **Live MLB StatsAPI probes 2026-04-14** — 5 endpoints, 3 venues, Judge gameLog, one full feed (760 KB). All response shapes in the "Endpoint Contracts" section are first-hand verified.
- [Streamlit `st.cache_data` docs](https://docs.streamlit.io/develop/api-reference/caching-and-state/st.cache_data) — TTL accepts string ("1d"), seconds (numeric), or `timedelta`; verified via WebFetch 2026-04-14.
- `.planning/research/STACK.md` — version pins, rejected alternatives, TTL guide.
- `.planning/research/ARCHITECTURE.md` — module layout, Patterns 1–3, component boundaries.
- `.planning/research/PITFALLS.md` — version skew, ScriptRunContext, cache hashing traps (noting the `fieldInfo` key-count correction found today).
- `.planning/ROADMAP.md` §Phase 1 — the 5 success criteria, the literal pin text for criterion #5.
- `.planning/phases/01-foundation-api-layer/01-CONTEXT.md` — D-01 through D-10.

### Secondary (MEDIUM confidence)

- `.planning/research/SUMMARY.md` — cross-validation of phase ordering rationale.
- `CLAUDE.md` — enforcement directives (GSD workflow, tech stack constraints).

### Tertiary (LOW confidence — flagged in Assumptions Log)

- Community-reported MLB StatsAPI rate limit (~20 req/s) — A4; not hit at Phase 1 volume.
- Additive vs. replace-all fixture re-run semantics — A6; awaiting user confirmation.
- `plotly 6.7` interpretation — A1; recommended `>=6.7,<7.0`.

## Metadata

**Confidence breakdown:**
- Endpoint contracts: **HIGH** — all five verified live today with real 2026 data.
- Architecture patterns: **HIGH** — all three patterns (cached wrappers, disk cache, smoke script) have precedent in ARCHITECTURE.md; the Pattern 3 ScriptRunContext caveat is new/specific and verified via Streamlit docs + training knowledge.
- Pitfalls: **HIGH** — 6 pitfalls each have a clear mitigation and a live-verified signal; the `fieldInfo` 5-vs-6 correction is HIGH-confidence from three independent venue fetches.
- Stack / pinning: **HIGH** — inherited from STACK.md plus PyPI verification.
- Validation architecture: **MEDIUM** — no test framework in Phase 1 by design; smoke-script sampling is the only signal. This is intentional (CONTEXT.md defers pytest to Phase 2) but worth user reconfirmation.

**Research date:** 2026-04-14
**Valid until:** 2026-05-14 (30 days — API shapes stable, stack versions pinned. The 2026 season may shift Judge's HR count but fixture capture is additive and re-runnable).
