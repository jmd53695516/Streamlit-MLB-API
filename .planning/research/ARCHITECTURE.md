# Architecture Research — v1.1 Multi-Season & Streamlit Cloud

**Domain:** Streamlit single-user data-viz app over MLB StatsAPI (read-only HTTP)
**Researched:** 2026-04-16
**Milestone focus:** Multi-season selector + Streamlit Community Cloud deployment
**Confidence:** HIGH for API season threading and caching strategy; HIGH for Cloud deployment requirements; MEDIUM for src-layout deployment workaround (community-confirmed, not official docs)

---

## Starting Point: What v1.0 Built

The existing architecture is:

```
app.py
  → controller.build_view(team_id, player_id, venue_id, season=None)
      → mlb_api.get_team_hitting_stats(team_id, season)   [cached 1h]
      → extract_hrs(player_id, season, api)
          → mlb_api.get_game_log(player_id, season)        [cached 1h]
          → mlb_api.get_game_feed(game_pk)                 [cached 7d]
      → compute_verdict_matrix(...)
  → chart.build_figure(view, park)
```

Season is already threaded as a parameter through `controller.build_view`, `extract_hrs`, `get_game_log`, and `get_team_hitting_stats`. The `season` arg flows all the way down to the API layer, where it is part of the `@st.cache_data` cache key (Streamlit hashes all positional + keyword args).

The only place `season` is hardcoded is `app.py`, which imports `CURRENT_SEASON` from `config.py` and passes it directly to `get_team_hitting_stats(team_id, CURRENT_SEASON)`. The controller default also falls back to `CURRENT_SEASON` when `season=None`.

---

## Multi-Season Support

### What needs to change

**Season selector in `app.py`** — one new `st.selectbox` (or `st.radio` for 5 options) before the Team selector, bound to `st.session_state["season"]`. Season change must null out `player_id` and `venue_id` (same cascade as team change).

**`app.py` passes `season` down** — replace the two hardcoded `CURRENT_SEASON` references:
- Line 79: `get_team_hitting_stats(team_id, CURRENT_SEASON)` → `get_team_hitting_stats(team_id, season)`
- Line `controller.build_view(team_id, player_id, venue_id)` call → add `season=season`

**No changes needed in the service layer.** `get_game_log`, `get_team_hitting_stats`, `get_game_feed`, and `extract_hrs` already accept `season` as a parameter, and `@st.cache_data` already keys on it. The pipeline is fully parametric.

**`config.py` change** — `CURRENT_SEASON = 2026` stays as the default fallback. No change required, but add a `AVAILABLE_SEASONS` list (e.g., `list(range(2022, CURRENT_SEASON + 1))`) to drive the selectbox options. This is the single source of truth for which seasons are available.

### Cascade behavior with season change

When the user changes the season, the player selector must reset. A player active in 2024 may not have been on the same team roster in 2022. The selector cascade is:

```
Season changes → null player_id, null venue_id
Team changes   → null player_id, null venue_id   (unchanged)
Player changes → set venue_id to home park       (unchanged)
```

A `_on_season_change` callback mirrors `_on_team_change`.

### Session state key addition

Add `"season"` to the session-state keys. The selectbox `key="season"` bound pattern matches how `team_id`, `player_id`, and `venue_id` already work.

### Historical roster endpoint

The `/teams/{team_id}/roster?rosterType=active&hydrate=person(stats(...))` call already passes `season` to the hydrate clause. For past seasons this returns whoever was on the active roster at the end of that season (or at season close). MEDIUM confidence — community-confirmed the `season` param works on roster/gameLog endpoints for past seasons; no official MLB API docs. Fixture-test against one past season before shipping.

---

## Caching Strategy: Historical vs. Current Season

This is the most important architectural decision for multi-season.

### Rule: completed season feeds are immutable forever

A game played in 2022 will never change. `get_game_feed(game_pk)` currently has `TTL_FEED = "7d"`. For historical seasons every game feed is already final — 7 days is undershooting; `"365d"` or even no TTL would be correct. However:

- `@st.cache_data` has an in-memory lifetime bounded by the process. On Streamlit Cloud, the process restarts when the app sleeps (idle timeout) or redeploys. The in-memory cache is gone either way.
- For a hobby app without a disk-backed HTTP cache, the practical impact is: every cold start re-fetches all game feeds for whichever player was viewed last session. This is the same as today.

**Recommendation:** Raise `TTL_FEED` to `"30d"` (from `"7d"`). This is safe because: (a) completed feeds are immutable, (b) current-season feeds finalize within hours of game end, (c) a 30-day in-memory TTL is effectively "forever" for a single-process Streamlit app.

### Rule: historical game logs are also immutable

`TTL_GAMELOG = "1h"` made sense for the current season. For a completed season, the game log for a player never changes. A simple improvement: if `season < CURRENT_SEASON`, use a longer TTL. However, `@st.cache_data` TTL is set at decoration time (it's a decorator argument, not a runtime argument), so you cannot vary TTL by argument value with a single decorated function.

**Two clean options:**

Option A — Two functions, separate TTLs:

```python
@st.cache_data(ttl="1h", show_spinner=False)
def get_game_log_current(person_id: int, season: int) -> list[dict]:
    return _raw_game_log(person_id, season)

@st.cache_data(ttl="30d", show_spinner=False)
def get_game_log_historical(person_id: int, season: int) -> list[dict]:
    return _raw_game_log(person_id, season)
```

A dispatcher in `extract_hrs` or `mlb_api.py` chooses which to call based on whether `season == CURRENT_SEASON`.

Option B — Single function, runtime TTL hint via a boolean flag (not supported by `@st.cache_data` — TTL is fixed at decoration time).

Option C — Accept the current 1h TTL for all seasons. For a hobby app with ~5 users, re-fetching a 2022 game log once per hour costs one HTTP call and is negligible. The caching architecture is correct; the TTL is merely suboptimal.

**Recommended for v1.1: Option C (accept 1h for all seasons).** Rationale: the app is not under load. Option A adds two functions to maintain and a dispatch branch, which is overhead disproportionate to the benefit. Revisit if Streamlit Cloud shows slow cold starts due to rate-limiting on historical season fetches.

### Venues: no change needed

Park dimensions don't vary by season. `load_all_parks()` and the disk-backed `venues_cache.json` are season-agnostic. No change required.

### Summary: caching changes for v1.1

| Change | Required? | Recommendation |
|--------|-----------|---------------|
| `TTL_FEED` 7d → 30d | No, but beneficial | YES — raise it |
| Separate TTL for historical game logs | No | Defer to v1.2+ |
| Venues cache season-parameterize | No | Unchanged |
| Team cache | No | Unchanged |

---

## Data Flow Change: Season as First Selector

Current flow (v1.0):
```
[Team] → [Player] → [Stadium] → build_view(team, player, venue, season=CURRENT_SEASON)
```

New flow (v1.1):
```
[Season] → [Team] → [Player] → [Stadium] → build_view(team, player, venue, season=selected_season)
```

Season is read from `st.session_state["season"]` immediately after it is rendered, before any downstream fetches. The season value gates all subsequent selectors (same lazy-fetch pattern already in place for team/player/venue).

No new modules are required. No geometry or chart changes. No changes to `controller.py` or `extract_hrs`.

---

## Streamlit Community Cloud Deployment

### Required files

| File | Status | Notes |
|------|--------|-------|
| `requirements.txt` | EXISTS at repo root | Must NOT include pytest in production; separate dev deps |
| `.streamlit/config.toml` | MISSING — create | Theme, server settings |
| `README.md` | MISSING — create | Required for shareable app context |
| `.streamlit/secrets.toml` | LOCAL ONLY — never commit | Not needed for this app (no secrets) |

### The src layout problem

The project uses a src layout: `src/mlb_park/` is the package, `pyproject.toml` declares it, and locally it is installed via `pip install -e .`. Streamlit Community Cloud runs `streamlit run` from the repo root. The Cloud environment will NOT automatically do `pip install -e .` unless told to.

**Two confirmed-working options:**

Option A — Add `-e .` to `requirements.txt`:
```
streamlit>=1.55,<2.0
requests>=2.32,<3.0
plotly>=6.7,<7.0
pandas>=2.2,<3.0
-e .
```
Community Cloud processes `requirements.txt` with uv (falling back to pip), and `-e .` triggers editable install of the `mlb_park` package from `src/`. This is the cleanest approach because it doesn't modify application code.

Option B — Add `sys.path` manipulation to `app.py`:
```python
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "src"))
```
Community forum confirmed this works but is fragile — it hard-codes a path assumption and runs on every Streamlit rerun. Not recommended if Option A works.

**Recommended: Option A (`-e .` in requirements.txt).** Remove `pytest` from `requirements.txt` (it is a dev dep; Cloud doesn't need it). The `pyproject.toml` already correctly declares the package. Cloud's uv/pip invocation will install it.

Revised `requirements.txt` for Cloud:
```
streamlit>=1.55,<2.0
requests>=2.32,<3.0
plotly>=6.7,<7.0
pandas>=2.2,<3.0
-e .
```

### `.streamlit/config.toml`

Minimal config needed for Cloud. The file must be at `.streamlit/config.toml` in the repo root (not inside `src/`):

```toml
[server]
headless = true
enableCORS = false
enableXsrfProtection = true

[browser]
gatherUsageStats = false

[theme]
# optional: set base theme
base = "light"
```

Community Cloud reads this file automatically. `headless = true` suppresses the "Open in browser" behavior that makes no sense in Cloud.

### Python version

Community Cloud uses Python 3.12 by default (as of early 2026). This project targets Python 3.12. No explicit version pin needed in the UI. If the Cloud default ever shifts, add a `.python-version` file containing `3.12` at the repo root — uv reads this natively.

### Secrets

This app makes no authenticated API calls (MLB StatsAPI is public, no key). No secrets management needed for v1.1. The `.streamlit/secrets.toml` mechanism exists but is unused here.

### Data directory and venues cache on Cloud

`data/venues_cache.json` is the disk-backed venue cache. It is gitignored. On Community Cloud:
- The filesystem is ephemeral — the cache does not persist between deploys or app sleeps.
- On every cold start, `load_all_parks()` will miss the disk cache and make ~30 venue API calls.
- This is acceptable for a hobby app. The `@st.cache_data(ttl="24h")` on `get_venue` still helps within a session.

**Do NOT commit `data/venues_cache.json` to the repo.** The current `.gitignore` already excludes `data/`. Keep it that way.

If cold-start venue fetching becomes a problem: bundle a snapshot `data/venues_cache.json` committed to the repo (rename it to something like `data/venues_seed.json` so it is not gitignored), and update `load_all_parks()` to fall back to the bundled seed when no runtime cache exists.

### Entrypoint path

Community Cloud requires specifying the entrypoint file path during deployment. The entrypoint is `src/mlb_park/app.py`. When prompted during Cloud app creation, enter this path. Community Cloud runs `streamlit run src/mlb_park/app.py` from the repo root.

---

## New vs. Modified Components

### Modified (touch existing files)

| File | Change |
|------|--------|
| `src/mlb_park/app.py` | Add season selectbox, `_on_season_change` callback, thread `season` to `get_team_hitting_stats` and `build_view` |
| `src/mlb_park/config.py` | Add `AVAILABLE_SEASONS = list(range(2022, CURRENT_SEASON + 1))` |
| `requirements.txt` | Remove `pytest`, add `-e .` |

### New files (create)

| File | Purpose |
|------|---------|
| `.streamlit/config.toml` | Cloud server settings, optional theme |
| `README.md` | App description, shareable context for the Cloud URL |

### Unchanged

Everything else: `controller.py`, `mlb_api.py`, `extract_hrs`, geometry modules, `chart.py`, all tests. The service layer already accepts `season` as a parameter.

---

## Build Order

1. **Update `config.py`** — add `AVAILABLE_SEASONS`. No deps. Testable with a one-liner assert.

2. **Update `app.py`** — add season selector and cascade callback. Thread `season` through `get_team_hitting_stats` and `build_view` calls. Run locally, verify selectors cascade correctly for at least two different seasons.

3. **Raise `TTL_FEED`** in `config.py` from `"7d"` to `"30d"`. One-line change, no risk.

4. **Fixture-test one past season** — pick a known player (e.g., Aaron Judge 2024), run `extract_hrs(judge_id, 2024)` in a scratch script, confirm the game log and feed fetch succeed and HR counts match Baseball Reference. This is the highest-risk step (undocumented API behavior for historical seasons).

5. **Prep deployment files** — create `.streamlit/config.toml`, create `README.md`, update `requirements.txt`.

6. **Deploy to Community Cloud** — push to GitHub, connect repo, specify entrypoint `src/mlb_park/app.py`, deploy. Verify cold start, venue fetch, season selector, and spray chart render.

---

## Pitfalls Specific to This Milestone

### Historical roster may return empty for past seasons

`/teams/{team_id}/roster?rosterType=active&hydrate=person(stats(...,season=2022,...))` may return an empty list or a different shape for seasons where the `active` roster type has no data. The current `controller.py` raises `ValueError` if `player_id` is not found in the roster response. For past seasons, you may need to use `rosterType=fullRoster` or handle the empty-roster case gracefully.

Mitigation: in the season-fixture test (step 4 above), verify the roster endpoint for a past season before building the selector UI.

### Disk cache is ephemeral on Cloud

`venues_cache.json` starts fresh on every Cloud cold start. 30 venue calls on cold start is fine under hobby load but worth knowing. If MLB API is briefly unavailable during a cold start, the app will show an error. The existing retry-and-raise logic in `_get()` handles this.

### `.streamlit/` is gitignored

The current `.gitignore` has `.streamlit/` listed. This will prevent committing `.streamlit/config.toml`. Remove `.streamlit/` from `.gitignore` (or add an exception: `!.streamlit/config.toml`) before the deployment commit. `secrets.toml` must remain gitignored — be precise.

Gitignore fix:
```gitignore
# Streamlit
.streamlit/secrets.toml
# (removed the blanket .streamlit/ exclusion)
```

### Season selector position: before or after Team?

Season should be the first selector. Team rosters and player HR counts are season-specific — showing a 2022 roster when the user selected "current 2026 season" would be confusing. Season → Team → Player → Stadium is the correct cascade order.

### `get_team_hitting_stats` for past seasons with HR sort

The player selector sorts by `homeRuns` from the hydrated roster stats. For past seasons this still works — the `season` parameter is already threaded to the hydrate clause. For completed seasons, a player with 0 HR in that season will appear at the bottom, which is correct behavior.

---

## Component Boundary Diagram (updated for v1.1)

```
st.session_state
  "season"   ← NEW
  "team_id"
  "player_id"
  "venue_id"

app.py (ONLY file that reads session_state)
  │
  ├─ season selectbox → st.session_state["season"]  ← NEW
  ├─ team   selectbox → st.session_state["team_id"]
  ├─ player selectbox → get_team_hitting_stats(team_id, season)  ← season threaded
  ├─ venue  selectbox → load_all_parks()             (season-agnostic, unchanged)
  │
  └─ controller.build_view(team_id, player_id, venue_id, season=season)  ← season arg added
       │
       ├─ get_team_hitting_stats(team_id, season)   [cache: 1h]
       ├─ extract_hrs(player_id, season, api)
       │    ├─ get_game_log(player_id, season)      [cache: 1h]
       │    └─ get_game_feed(game_pk)               [cache: 30d]  ← TTL raised
       ├─ compute_verdict_matrix(...)               [no network]
       └─ ViewModel(season=season, ...)
```

---

## Sources

- [Streamlit Community Cloud — App dependencies](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/app-dependencies) — HIGH; confirms `requirements.txt` at root or alongside entrypoint; uv/pip fallback.
- [Streamlit Community Cloud — File organization](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/file-organization) — HIGH; confirms `.streamlit/config.toml` must be at repo root; Cloud runs `streamlit run` from repo root.
- [Streamlit — Src layout for deployment (forum)](https://discuss.streamlit.io/t/src-layout-for-deployment/88617) — MEDIUM; community-confirmed `sys.path` workaround; also establishes that src layout requires explicit action.
- [Streamlit — uv pyproject.toml on Cloud (forum)](https://discuss.streamlit.io/t/install-dependencies-in-streamlit-cloud-based-on-uv-pyproject-toml/79557) — MEDIUM; confirms `-e .` in requirements.txt workaround for local packages.
- Existing codebase: `mlb_api.py`, `app.py`, `controller.py`, `config.py` — HIGH (direct inspection); season parameter already threaded through all service-layer functions.

---

*Architecture research for: MLB HR Park Factor Explorer v1.1 milestone*
*Researched: 2026-04-16*
