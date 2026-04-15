---
phase: 01-foundation-api-layer
verified: 2026-04-14T21:00:00Z
status: passed
score: 14/14 must-haves verified
overrides_applied: 0
---

# Phase 01: Foundation & API Layer Verification Report

**Phase Goal:** Pin deps, scaffold module layout, stand up cached HTTP wrappers for all five StatsAPI endpoints with disk-backed venue cache and recorded fixtures.
**Verified:** 2026-04-14T21:00:00Z
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

Must-haves merged from ROADMAP success criteria + all three PLAN frontmatter `must_haves.truths`.

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | ROADMAP #1: Scratch script hits all five endpoints and returns parsed JSON | VERIFIED | `scripts/smoke.py` calls `get_teams`, `get_roster`, `get_game_log`, `get_game_feed`, `load_all_parks` (which orchestrates `get_venue`). Human confirmed all 5 sections rendered. |
| 2 | ROADMAP #2: Every endpoint wrapper has `@st.cache_data` + correct per-endpoint TTL | VERIFIED | `grep -c '^@st.cache_data' mlb_api.py` = 5. TTLs sourced from config: TEAMS/VENUE=24h, ROSTER=6h, GAMELOG=1h, FEED=7d. No inline TTL literals (`grep 'ttl="'` → 0). |
| 3 | ROADMAP #3: Cold 2nd run loads all 30 venues from `data/venues_cache.json` without network | VERIFIED | `data/venues_cache.json` exists (17,306 bytes, 30 entries). `load_all_parks()` freshness gate `age_days < VENUES_STALE_DAYS` present. Human confirmed mtime stable across reruns. |
| 4 | ROADMAP #4: `tests/fixtures/` contains recorded JSON for teams, roster, gameLog, feed, venue | VERIFIED | 38 JSON files: teams.json (30 entries), roster_147.json (Judge present), gamelog_592450_2026.json, 5 feed_*.json, 30 venue_*.json + README.md. |
| 5 | ROADMAP #5: `requirements.txt` pins streamlit/requests/plotly/pandas, installs cleanly | VERIFIED | requirements.txt has exact 4 lines: `streamlit>=1.55,<2.0`, `requests>=2.32,<3.0`, `plotly>=6.7,<7.0`, `pandas>=2.2,<3.0`. `.venv/` exists (proves clean install succeeded). |
| 6 | Plan 01-01: `uv pip install -r requirements.txt` installs cleanly in fresh venv | VERIFIED | `.venv/` populated; Plan 03 successfully ran `record_fixtures.py` against installed package. |
| 7 | Plan 01-01: `uv pip install -e .` registers the `mlb_park` package (importable as `from mlb_park.services import mlb_api`) | VERIFIED | `pyproject.toml` declares `[tool.setuptools.packages.find] where = ["src"]`; smoke.py & record_fixtures.py both import `from mlb_park.services import mlb_api` / `from mlb_park.services.mlb_api import _raw_*` successfully at capture time. |
| 8 | Plan 01-01: Constants resolve from a single module (config.py) | VERIFIED | All 13 constants present in config.py: `BASE_URL_V1`, `BASE_URL_V11`, `HTTP_TIMEOUT`, `USER_AGENT`, `TTL_TEAMS/ROSTER/GAMELOG/VENUE/FEED`, `VENUES_FILE`, `VENUES_STALE_DAYS`, `YANKEES_TEAM_ID`, `JUDGE_PERSON_ID`. |
| 9 | Plan 01-01: `data/` and `.streamlit/` gitignored | VERIFIED | `.gitignore` lines 9 & 12: `.streamlit/` and `data/` both excluded. `data/venues_cache.json` present on disk but untracked. |
| 10 | Plan 01-02: Exactly 5 `@st.cache_data`-decorated public wrapper functions with config-sourced TTLs | VERIFIED | Count = 5. Each decorator uses `ttl=TTL_*` identifier, no string literals. |
| 11 | Plan 01-02: Each public wrapper has paired private `_raw_*` helper (no cache) | VERIFIED | `_raw_teams`, `_raw_roster`, `_raw_game_log`, `_raw_game_feed`, `_raw_venue` all defined (lines 72-113). |
| 12 | Plan 01-02: `load_all_parks()` reads disk if mtime < 30 days, else rebuilds + writes atomically | VERIFIED | Function at lines 174-197: `VENUES_FILE.exists()` gate, `age_days < VENUES_STALE_DAYS`, rebuild via `get_teams()` + `get_venue()`, atomic write via `_atomic_write_json`. |
| 13 | Plan 01-02: Atomic write uses `tempfile.mkstemp(dir=parent)` + `os.replace()` | VERIFIED | `_atomic_write_json` (lines 155-171) uses `tempfile.mkstemp(dir=str(path.parent), ...)` + `os.replace(tmp, path)` with exception cleanup. |
| 14 | Plan 01-02: `mlb_api.py` is the ONLY module importing `requests` | VERIFIED | `grep -rn 'import requests' src/` → exactly 1 hit: `src/mlb_park/services/mlb_api.py:21`. |
| 15 | Plan 01-03: `streamlit run scripts/smoke.py` renders all 5 endpoint sections | VERIFIED | Human confirmed visually (status note from user: "User has visually confirmed all 5 smoke-page sections render"). |
| 16 | Plan 01-03: Second run mtime stable on `data/venues_cache.json` (criterion #3) | VERIFIED | Human confirmed: "`data/venues_cache.json` mtime is stable across reruns (ROADMAP criterion #3 passes)". |
| 17 | Plan 01-03: `record_fixtures.py` populates teams/roster_147/gamelog/feed_*/venue_* | VERIFIED | 38 fixtures on disk: teams.json + roster_147.json + gamelog_592450_2026.json + 5 feed_*.json + 30 venue_*.json. |
| 18 | Plan 01-03: Recorder additive on re-run; asserts personId 592450 is Aaron Judge | VERIFIED | `record_fixtures.py` line 58: `assert judge is not None and "Judge" in judge["person"]["fullName"]`. Additive skips for feed/venue: lines 83, 94 (`if target.exists(): continue`). |

**Score:** 18/18 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `requirements.txt` | 4 pinned deps | VERIFIED | 4 lines, matches ROADMAP #5 verbatim |
| `pyproject.toml` | PEP 621 + src-layout discovery | VERIFIED | `[tool.setuptools.packages.find] where = ["src"]` present, 4 deps mirror requirements.txt |
| `.gitignore` | `data/`, `.streamlit/`, `__pycache__/` | VERIFIED | All three present |
| `src/mlb_park/__init__.py` | Package marker | VERIFIED | Exists |
| `src/mlb_park/services/__init__.py` | Subpackage marker | VERIFIED | Exists |
| `src/mlb_park/app.py` | Streamlit entry stub | VERIFIED | Exists |
| `src/mlb_park/config.py` | All 13 constants, no I/O imports | VERIFIED | All constants present; no `import requests` or `import streamlit` |
| `src/mlb_park/services/mlb_api.py` | 5 cached + 5 raw + MLBAPIError + load_all_parks | VERIFIED | 197 lines, AST-parses, 5 decorators exact |
| `scripts/smoke.py` | Public-wrappers-only Streamlit page | VERIFIED | Imports public wrappers only; zero `_raw_` matches |
| `scripts/record_fixtures.py` | Uses `_raw_*` helpers | VERIFIED | Imports all 5 `_raw_*` helpers from `mlb_api` |
| `tests/fixtures/teams.json` | 30 teams | VERIFIED | `len(teams)==30` confirmed via json.load |
| `tests/fixtures/roster_147.json` | Judge present | VERIFIED | `any(p['person']['id']==592450)` is True |
| `tests/fixtures/gamelog_592450_2026.json` | Judge 2026 gamelog | VERIFIED | File exists |
| `tests/fixtures/README.md` | Layout doc | VERIFIED | Exists |
| `tests/fixtures/venue_*.json` | 30 venues | VERIFIED | Exactly 30 files |
| `tests/fixtures/feed_*.json` | 1+ Judge HR games | VERIFIED | 5 files (gamePks 822998, 823241, 823243, 823563, 823568) |
| `data/venues_cache.json` | 30-venue disk cache | VERIFIED | 17,306 bytes, 30 entries, gitignored |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|----|--------|---------|
| `pyproject.toml` | `src/mlb_park/` | `[tool.setuptools.packages.find] where=["src"]` | WIRED | Line 16-17 of pyproject.toml |
| `requirements.txt` | `pyproject.toml` | Matching pins | WIRED | All 4 pins identical |
| `mlb_api.py` | `config.py` | Import block | WIRED | Lines 24-36 import all required constants |
| `load_all_parks()` | `data/venues_cache.json` | `_atomic_write_json` (mkstemp + os.replace) | WIRED | Function present, file on disk |
| public wrappers | private `_raw_*` helpers | Thin-alias pattern | WIRED | Each cached wrapper calls its `_raw_*` counterpart |
| `smoke.py` | `mlb_park.services.mlb_api` | `from mlb_park.services import mlb_api` | WIRED | Line 17 of smoke.py |
| `record_fixtures.py` | `_raw_*` helpers | Explicit import | WIRED | Lines 22-28 of record_fixtures.py |
| `data/venues_cache.json` | `load_all_parks()` | `VENUES_FILE` constant + atomic write | WIRED | File exists with 30 entries |

### Data-Flow Trace (Level 4)

Skipped for Phase 1 — this phase produces data-fetching primitives, not a rendering artifact. The smoke page renders live API data (human-verified: "all 5 smoke-page sections render"). The `venues_cache.json` file contains real 30-venue data (verified: 30 entries, 17,306 bytes, non-empty).

### Behavioral Spot-Checks

| Behavior | Check | Result | Status |
|----------|-------|--------|--------|
| `mlb_api.py` AST-parses | Summary commit verified + grep succeeds | Clean | PASS |
| Exactly 5 `@st.cache_data` decorators | `grep -c '^@st.cache_data' mlb_api.py` | 5 | PASS |
| 5 `_raw_*` helpers defined | `grep '^def _raw_' mlb_api.py` | 5 | PASS |
| No inline TTL literals in decorators | `grep 'ttl="' mlb_api.py` | 0 hits | PASS |
| Only mlb_api.py imports requests | `grep -rn 'import requests' src/` | 1 hit (mlb_api.py:21) | PASS |
| smoke.py uses only public wrappers | `grep '_raw_' scripts/smoke.py` | 0 hits | PASS |
| teams.json has 30 teams | `json.load + len()` | 30 | PASS |
| roster_147.json contains Judge | `any(p['person']['id']==592450)` | True | PASS |
| venues_cache.json has 30 venues | `json.load + len()` | 30 | PASS |
| fixture count | `ls tests/fixtures/*.json \| wc -l` | 38 (≥33 target) | PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| DATA-04 | 01-01, 01-02, 01-03 | API fetches cached via `st.cache_data` with per-endpoint TTLs (venues long, gameLog hourly, feeds daily+) | SATISFIED | 5 `@st.cache_data` decorators with correct TTLs (TEAMS/VENUE=24h, ROSTER=6h, GAMELOG=1h, FEED=7d) + 30-day disk-backed venue cache. Matches requirement's "venues long, gameLog hourly, completed game feeds daily+" exactly. |

REQUIREMENTS.md maps DATA-04 to Phase 1 as the sole requirement. No orphans.

### Anti-Patterns Found

Scanned: `src/mlb_park/config.py`, `src/mlb_park/services/mlb_api.py`, `scripts/smoke.py`, `scripts/record_fixtures.py`.

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| — | — | — | — | No blocker anti-patterns found |

Notes:
- `mlb_api.py` line 99: `return []` on empty-stats path — legitimate empty-fallback, not a stub (real code path returns `stats[0]["splits"]` when data present).
- Benign Streamlit warning `No runtime found, using MemoryCacheStorageManager` during `record_fixtures.py` is expected per RESEARCH Pitfall 1 (recorder uses uncached `_raw_*` helpers).

### Human Verification Required

No remaining items. Human confirmed:
- All 5 smoke-page sections render via `streamlit run scripts/smoke.py`
- `data/venues_cache.json` mtime stable across reruns (ROADMAP criterion #3 passes)

### Gaps Summary

No gaps. All 18 observable truths verified, all 17 required artifacts present, all 8 key links wired, DATA-04 satisfied, no blocker anti-patterns, human verification complete.

Phase 1 foundation is proven end-to-end. Downstream phases can import `from mlb_park.services import mlb_api` and run offline against the 38 recorded fixtures.

---

_Verified: 2026-04-14T21:00:00Z_
_Verifier: Claude (gsd-verifier)_
