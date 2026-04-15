---
phase: 01-foundation-api-layer
plan: 02
subsystem: api-layer
tags: [http, caching, statsapi, venues]
requires:
  - mlb_park.config constants (Plan 01-01)
provides:
  - mlb_park.services.mlb_api (5 cached wrappers + 5 raw helpers + MLBAPIError + load_all_parks + _atomic_write_json)
  - Disk-backed venue cache at data/venues_cache.json (30-day staleness)
  - Hook points (_raw_*) for Plan 01-03 fixture recorder to bypass cache
affects:
  - Plan 01-03 (will import _raw_* helpers for fixture capture)
  - Phase 2+ (will import get_game_log / get_game_feed for HR pipeline)
  - Phase 4 (will import get_teams / get_roster / load_all_parks for selectors)
tech-stack:
  added: []
  patterns:
    - Raw/cached factoring: private _raw_* (un-cached) + public @st.cache_data thin-alias wrapper
    - Module-level requests.Session (never passed as cache arg → no UnhashableParamError)
    - TTLs sourced from config constants, never inlined in decorators
    - Atomic disk write via tempfile.mkstemp(dir=same-parent) + os.replace (Windows-safe)
    - Integer-only SSRF guards on each _raw_* helper (assert isinstance)
key-files:
  created:
    - src/mlb_park/services/mlb_api.py
  modified: []
decisions:
  - Single shared _get() helper owns timeout + 1-retry policy; no per-endpoint retry config
  - _session is module-level and reused across calls — pools connections to statsapi.mlb.com
  - load_all_parks() is NOT @st.cache_data decorated — the disk file IS the cross-process cache; the public get_teams/get_venue calls it orchestrates provide the in-memory layer
  - Rebuild path calls public wrappers (get_teams/get_venue), not _raw_*, so warm-session re-invocations benefit from the in-memory cache
  - JSON keys stringified on write, int-coerced on read (JSON requires string keys)
metrics:
  tasks_completed: 2
  files_created: 1
  files_modified: 0
  completed: 2026-04-14
---

# Phase 01 Plan 02: StatsAPI HTTP Wrapper Layer Summary

Five `@st.cache_data`-decorated HTTP wrappers over `statsapi.mlb.com` plus a disk-backed 30-venue cache — the sole home of `requests` in the repo.

## What Was Built

**Task 1 — Five cached wrappers + five raw helpers** (commit `d6a098d`)

Created `src/mlb_park/services/mlb_api.py` with:
- `MLBAPIError(RuntimeError)` — sentinel for API failures after retry
- Module-level `_session = requests.Session()` with `USER_AGENT` header
- `_get(url, params)` — shared GET with `HTTP_TIMEOUT` + one retry on `RequestException`
- Five private `_raw_*` helpers (no cache), each with `assert isinstance(..., int)` SSRF guard:
  - `_raw_teams()` — `/api/v1/teams?sportId=1` → `teams[]`
  - `_raw_roster(team_id)` — `/api/v1/teams/{id}/roster?rosterType=active` → `roster[]`
  - `_raw_game_log(person_id, season)` — `/api/v1/people/{id}/stats?stats=gameLog&group=hitting&season=YYYY&gameType=R` → `stats[0].splits[]` (empty list if absent)
  - `_raw_game_feed(game_pk)` — `/api/v1.1/game/{pk}/feed/live` (note v1.1, per RESEARCH.md §Endpoint Contracts #4)
  - `_raw_venue(venue_id)` — `/api/v1/venues/{id}?hydrate=location,fieldInfo` → `venues[0]`
- Five `@st.cache_data(ttl=..., show_spinner=False)` public wrappers, thin aliases over raw helpers, with TTLs sourced entirely from `config.py` (no inline string literals in decorators):
  - `get_teams` — `TTL_TEAMS` (24h)
  - `get_roster` — `TTL_ROSTER` (6h)
  - `get_game_log` — `TTL_GAMELOG` (1h)
  - `get_game_feed` — `TTL_FEED` (7d)
  - `get_venue` — `TTL_VENUE` (24h)

**Task 2 — Disk-backed venue cache** (commit `4f1aa2f`)

Appended to the same file:
- `_atomic_write_json(path, data)` — `path.parent.mkdir(parents=True, exist_ok=True)` → `tempfile.mkstemp(dir=str(path.parent), prefix=".tmp-", suffix=".json")` → write via `os.fdopen` → `os.replace(tmp, path)`; cleans up tempfile on any exception.
- `load_all_parks() -> dict[int, dict]`:
  - If `VENUES_FILE.exists()` and `(time.time() - stat.st_mtime) / 86400 < VENUES_STALE_DAYS` (30), reads disk and returns `{int(k): v for k, v in raw.items()}`.
  - Else rebuilds: calls `get_teams()` (public/cached), dedups `{t["venue"]["id"] for t in teams}`, iterates in sorted order calling `get_venue(vid)` (public/cached), writes result atomically with string-coerced keys.
  - NOT `@st.cache_data`-decorated — disk file is the cross-process cache; in-memory caching is delegated to the underlying public wrappers.

## File Line Counts

| File | Lines |
|---|---|
| src/mlb_park/services/mlb_api.py | 197 |

## Counted Decorators

`grep -c '^@st.cache_data' src/mlb_park/services/mlb_api.py` → **5** (exact count enforced by plan must-haves).

## Verification

Plan-specified `<verify>` commands — all pass:

| Check | Result |
|---|---|
| `test -f src/mlb_park/services/mlb_api.py` | exists |
| `grep -c '^@st.cache_data' ...` | `5` |
| `grep -c '^def _raw_' ...` | `5` |
| `grep -q 'BASE_URL_V11' ...` | present (game-feed uses v1.1) |
| `grep -q 'gameType.*R' ...` | present (regular season only) |
| `grep -q 'rosterType.*active' ...` | present |
| `grep -q 'hydrate.*location,fieldInfo' ...` | present |
| `grep -q 'class MLBAPIError' ...` | present |
| `grep -q 'os.replace' ...` | present |
| `grep -q 'tempfile.mkstemp' ...` | present |
| `grep -q 'VENUES_STALE_DAYS' ...` | present |
| `python -c "import ast; ast.parse(open(...).read())"` | `parse ok` |

**CLAUDE.md invariant — only `mlb_api.py` imports `requests`:**
```
$ grep -rn 'import requests' src/
src/mlb_park/services/mlb_api.py:21:import requests
```
One hit. Invariant holds.

No inline TTL string literals inside decorator lines — all TTLs come from `config.py` imports (`TTL_TEAMS`, `TTL_ROSTER`, `TTL_GAMELOG`, `TTL_FEED`, `TTL_VENUE`).

## Deviations from Plan

None — plan executed exactly as written. Both task `<action>` code templates were used verbatim. No Rule 1/2/3 auto-fixes required; no architectural questions (Rule 4) hit.

## Threat Model Compliance

| Threat ID | Disposition | Status |
|---|---|---|
| T-01-05 (SSRF via non-int ID) | mitigate | Done — each `_raw_*` has `assert isinstance(..., int)` before URL templating |
| T-01-06 (CDN stall hangs rerun) | mitigate | Done — all calls go through `_get()` with `timeout=HTTP_TIMEOUT=(5, 15)`; no naked `requests.get` |
| T-01-07 (partial venues_cache.json write) | mitigate | Done — `_atomic_write_json` via `tempfile.mkstemp(dir=parent)` + `os.replace` |
| T-01-08 (PII in UA) | mitigate | Done (inherited) — `USER_AGENT` imported from config, set to generic hobby GitHub URL |
| T-01-09 (schema drift) | accept | Fixture capture in Plan 01-03 is the long-term detection surface |
| T-01-10 (session kept forever) | accept | Module-level `_session` is the intended pattern |

## Self-Check: PASSED

Files verified:
- FOUND: src/mlb_park/services/mlb_api.py

Commits verified:
- FOUND: d6a098d (Task 1 — feat(01-02): add 5 cached HTTP wrappers + raw helpers for statsapi)
- FOUND: 4f1aa2f (Task 2 — feat(01-02): add disk-backed venue cache (load_all_parks + atomic write))
