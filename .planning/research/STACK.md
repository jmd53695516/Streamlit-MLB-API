# Technology Stack

**Project:** Streamlit MLB HR Park Factor Explorer — v1.1 Multi-Season & Deploy
**Researched:** 2026-04-16
**Scope:** ADDITIONS AND CHANGES ONLY. Existing stack (Python 3.12, Streamlit 1.56, Plotly 6.7, pandas 2.2, requests 2.32, numpy 2.x) is locked — not re-researched here.

---

## What Changes in v1.1

Two discrete concerns:

1. **Multi-season selector** — API layer changes, cache key changes, TTL policy for historical vs. current season data.
2. **Streamlit Community Cloud deployment** — packaging, Python version pinning, src-layout accommodation, secrets, disk-cache incompatibility.

No new libraries are needed for either concern. The changes are configuration and code, not dependency additions.

---

## Multi-Season Support

### API Layer — What Already Works

The existing `mlb_api.py` already accepts `season: int` as a parameter in the two season-sensitive endpoints:

- `get_game_log(person_id, season)` — calls `/people/{id}/stats?stats=gameLog&season={season}` — VERIFIED: returns historical data (tested against Ohtani 2022 via direct HTTP call during this research).
- `get_team_hitting_stats(team_id, season)` — calls `/teams/{team_id}/roster?hydrate=person(stats(type=statsSingleSeason,season={season},...))`.
- `get_game_feed(game_pk)` — game PKs are globally unique across seasons; no season param needed.
- `get_teams()`, `get_venue()` — season-agnostic.

The `season` integer flows through the call stack already. `CURRENT_SEASON = 2026` in `config.py` is the only hardcoded constant to expose in the UI.

### Roster Endpoint — Historical Season Caveat

`/teams/{id}/roster?rosterType=active` returns the CURRENT active roster regardless of any season parameter. For historical seasons (2022–2025), querying "active" roster will show 2026 players, not the players who were on that team in the selected season.

**Implication:** The player selector must change behavior for past seasons. Two options:

| Option | Endpoint | Tradeoff |
|--------|----------|----------|
| Keep active roster, let user pick any player, filter on HRs found | `/teams/{id}/roster` (existing) | Simple, but lists 2026 players for past seasons — confusing if a player was traded |
| Use season-appropriate roster | `/teams/{id}/roster?season={year}&rosterType=fullSeason` | Returns players who appeared on that team during that season — more correct |

**Recommendation: `rosterType=fullSeason&season={year}`** for historical seasons (2021–2025). The API accepts a `season` query parameter on the roster endpoint. Use `rosterType=active` (no season param) for the current season (2026) only, since "full season" for an in-progress year may be incomplete. Confidence: MEDIUM — verified that `season` is a documented roster param via endpoint inspection; behavior for in-progress seasons is inferred.

### TTL Policy — Historical vs. Current Season

Historical seasons (any year before current) are immutable. A game from 2022 will never change. Current TTLs are conservative (`1h` for gameLogs, `7d` for feeds) because today's data updates.

| Endpoint | Current Season TTL | Historical Season TTL | Rationale |
|----------|-------------------|----------------------|-----------|
| `get_game_log(person_id, season)` | `"1h"` | `"7d"` or `None` (infinite) | 2022 gameLogs are frozen |
| `get_game_feed(game_pk)` | `"7d"` | `"7d"` (already good) | Completed feeds are immutable |
| `get_team_hitting_stats(team_id, season)` | `"1h"` | `"7d"` | Historical stats don't change |
| `get_teams()` | `"24h"` | same | Season-agnostic |
| `get_venue()` | `"24h"` | same | Season-agnostic |

**Implementation note:** `st.cache_data` does not support conditional TTLs based on argument values — the TTL is fixed at decoration time. Two patterns to handle this:

- **Pattern A — Two decorated functions:** `get_game_log_current(person_id)` with `ttl="1h"`, `get_game_log_historical(person_id, season)` with `ttl="7d"`. Clean but adds surface area.
- **Pattern B — One function, short TTL:** Keep `ttl="1h"` on all season-aware endpoints. Historical data re-caches after every hour but that's just a Streamlit process restart — the cache is ephemeral anyway. For a hobby app with no persistent cache between deploys, this is fine.

**Recommendation: Pattern B.** The cache eviction cost on a hobby app is negligible. Avoid two nearly-identical functions per endpoint. If the venue disk cache (`data/venues_cache.json`) is ported to cover game feeds, Pattern A becomes worth it — but that's a future concern.

### Season Range

Last 5 complete seasons plus current: **2022, 2023, 2024, 2025, 2026**. The 2020 COVID season (60 games) and 2021 are within range but data quality varies for 2020. A dropdown of `[2026, 2025, 2024, 2023, 2022]` ordered most-recent-first is the correct default.

**Note on 2020:** The `statsapi.mlb.com` gameLog endpoint returns 2020 data correctly (it existed), but the season had no spring training and altered schedules. Including 2022+ and excluding 2020–2021 keeps the dataset clean. Include 2021 if you want 5 full seasons; exclude 2020.

Confidence: MEDIUM — API behavior for 2020/2021 based on general knowledge of the API and the COVID season; not directly tested.

---

## Streamlit Community Cloud Deployment

### Python Version

Community Cloud supports all Python versions still receiving security updates. As of April 2026, that is Python 3.9 through 3.13. Python 3.12 (the project's current runtime) is fully supported.

**Version pinning:** Python version is set in the **Advanced settings UI** during initial deployment — NOT via `runtime.txt`. Multiple 2025 community reports confirm `runtime.txt` is ignored or unreliable on Community Cloud; the UI dialog is the only reliable mechanism. Python cannot be changed after deployment without deleting and redeploying. Select **3.12** explicitly in Advanced settings.

Confidence: HIGH (official docs confirm UI-based selection; MEDIUM on runtime.txt deprecation — multiple forum reports but no official deprecation notice found).

### Dependency File

Community Cloud checks for dependency files in this priority order: `uv.lock` > `Pipfile` > `environment.yml` > `requirements.txt` > `pyproject.toml`.

**The project already has both `requirements.txt` and `pyproject.toml`.** Community Cloud will pick up `requirements.txt` first (it's higher priority than `pyproject.toml`) and install from it. This is the correct behavior — `requirements.txt` is the deployment artifact.

**Action required:** The existing `requirements.txt` lists only the four runtime deps and `pytest`. For Cloud deployment:
- Remove `pytest` from `requirements.txt` — test-only dep, wastes install time on Cloud.
- Do NOT add `pytest` to a separate file; it's already in `pyproject.toml` under `dependencies` (which Cloud won't read). Better: move pytest to a `[project.optional-dependencies]` group in `pyproject.toml` and keep `requirements.txt` clean for production.

Current `requirements.txt`:
```
streamlit>=1.55,<2.0
requests>=2.32,<3.0
plotly>=6.7,<7.0
pandas>=2.2,<3.0
pytest>=8.0,<9.0    ← remove for Cloud
```

### src/ Layout — Package Installation

The app uses a `src/mlb_park/` layout with `app.py` importing from `mlb_park.*`. On local dev, the package is installed via `pip install -e .` (editable) which puts `mlb_park` on `sys.path`. Community Cloud does NOT run `pip install -e .` — it only installs from the dependency file.

**Two viable solutions:**

**Option A — Add `sys.path` shim in `app.py` (simplest):**
```python
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent / "src"))
```
Add at the top of `src/mlb_park/app.py` before any `mlb_park` imports. Works on Cloud without any packaging changes. Verified approach from community discussion.

**Option B — Add `.` to `requirements.txt`:**
```
.
streamlit>=1.55,<2.0
...
```
Community Cloud will `pip install .` which triggers setuptools to build and install `mlb_park` from `pyproject.toml`. Cleaner but less battle-tested on Cloud's uv-first install path.

**Recommendation: Option B** — it's the correct Python packaging approach and `pyproject.toml` already has the right `[tool.setuptools.packages.find] where = ["src"]` config. The `sys.path` shim is a fallback if Option B fails during deploy testing. Add `.` as the FIRST line of `requirements.txt` so it installs before the other packages resolve.

Confidence: MEDIUM — both options reported working in community discussions; Option B is the standard approach but Cloud's handling of local `.` installs via uv has some edge cases.

### Entry Point

Community Cloud runs `streamlit run <entrypoint>` from the repo root. The entry point is configured during deployment. For this project, set it to `src/mlb_park/app.py`. Paths use forward slashes even on the UI.

### Disk Cache — Incompatibility

The existing `load_all_parks()` writes `data/venues_cache.json` to the repo root. On Community Cloud:

1. `data/` is gitignored — it will NOT be present in the deployed repo clone.
2. The Cloud filesystem is **ephemeral** — files written during a session do not persist across app restarts/sleeps.
3. Every cold start will call the API to rebuild `venues_cache.json`, then lose it on restart.

**The disk cache is a local-only optimization.** On Cloud it degrades silently to "rebuild every cold start" — that's acceptable (30 venue calls, each cached in `st.cache_data` for 24h within a session). No code change is strictly required; `load_all_parks()` will just always take the "rebuild from API" branch.

**Optional improvement:** Remove the disk-write branch entirely for Cloud by checking an env var, or simply accept the behavior. For a hobby app shared with friends, the occasional 30-venue cold-start fetch (~5 seconds) is tolerable.

Confidence: HIGH — ephemeral filesystem is documented behavior for container-based cloud deployments; gitignore of `data/` is confirmed in the repo.

### Secrets Management

This app makes no authenticated API calls (statsapi.mlb.com is public). No secrets are required for v1.1.

If a future version adds any private keys (e.g., a paid stats provider), use:
- Local: `.streamlit/secrets.toml` (already gitignored)
- Cloud: paste contents into "Advanced settings > Secrets" during deployment
- Code: `st.secrets["key_name"]`

No action needed for v1.1.

### Sleep Behavior

Community Cloud hibernates inactive apps after **12 hours** of no traffic. On wake, Streamlit restarts the Python process — the `st.cache_data` in-memory cache is cleared, and the disk cache (`data/venues_cache.json`) is lost. First user after sleep sees a cold start.

For a hobby app with occasional traffic, this is expected and acceptable. The warm-up fetch (teams + 30 venues) takes ~5–10 seconds on first load.

### Resource Limits (Free Tier)

Community reports (verified across multiple forum threads) indicate:

| Resource | Limit | Notes |
|----------|-------|-------|
| Memory | ~1 GB guaranteed, up to ~3 GB | App is evicted if it exceeds available memory |
| CPU | Shared, undisclosed | Not a bottleneck for this app |
| Storage | Ephemeral filesystem | No persistent disk |
| Concurrent users | Unlimited (free tier) | Each user gets a separate Python session |
| App sleep | After 12h inactivity | Cold start on next visit |
| Deploy updates | Max 5 per minute from GitHub | Not a concern for a hobby app |

This app's peak memory footprint: ~50 HRs × 30 parks = 1,500 rows in pandas, plus Plotly figure JSON, plus Streamlit overhead. Total well under 100 MB per session. The 1 GB limit is not a concern.

Confidence: MEDIUM — memory figures from community forum posts (Feb 2024 reference); not found in official docs. Conservative figure of 1 GB is the widely-cited practical floor.

### App URL Structure

Streamlit Community Cloud apps are deployed at `https://{subdomain}.streamlit.app`. The subdomain can be customized during deployment. Apps under a free account are **public** (no auth). For a hobby app shared with friends, this is fine.

---

## Summary: What to Do for v1.1

| Task | Action | Confidence |
|------|--------|------------|
| Season selector UI | Add `st.selectbox` for year in `app.py`, propagate to all season-aware calls | HIGH |
| Historical roster | Use `rosterType=fullSeason&season={year}` for non-current seasons | MEDIUM |
| TTL for historical data | Keep existing TTLs (Pattern B — acceptable for hobby app) | HIGH |
| `requirements.txt` | Add `.` as first line; remove `pytest` | MEDIUM |
| Entry point | Set to `src/mlb_park/app.py` in Cloud deploy dialog | HIGH |
| Python version | Select 3.12 in Cloud Advanced settings (NOT runtime.txt) | HIGH |
| Disk cache | No change needed; degrades gracefully on Cloud | HIGH |
| Secrets | None required for v1.1 | HIGH |
| `.streamlit/config.toml` | Create for any Cloud-overrideable settings (optional) | MEDIUM |

## What NOT to Add

| Avoid | Why |
|-------|-----|
| `runtime.txt` | Ignored on Community Cloud; use Advanced settings UI instead |
| New library for season support | The API already supports `season` param; no new dep needed |
| `requests-cache` or database | `st.cache_data` is sufficient; disk cache degrades gracefully on Cloud |
| Auth layer | App is intentionally public; hobby app shared with friends |
| `poetry` / lockfile | Already using `requirements.txt`; no reason to migrate |

---

## Sources

- [Streamlit Community Cloud: App dependencies](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/app-dependencies) — HIGH; dependency file priority order, Python version selection.
- [Streamlit Community Cloud: File organization](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/file-organization) — HIGH; entry point, working directory behavior.
- [Streamlit Community Cloud: Secrets management](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/secrets-management) — HIGH; TOML format, `st.secrets` access.
- [Streamlit Community Cloud: Status and limitations](https://docs.streamlit.io/deploy/streamlit-community-cloud/status) — HIGH; Python version policy (security-supported only), Debian 11 runtime, config.toml overrides.
- [Upgrade Python version on Community Cloud](https://docs.streamlit.io/deploy/streamlit-community-cloud/manage-your-app/upgrade-python) — HIGH; UI-based Python selection, delete-and-redeploy to change version.
- [runtime.txt ignored by Community Cloud (forum thread, 2025)](https://discuss.streamlit.io/t/streamlit-cloud-using-python-3-13-despite-runtime-txt-specifying-3-11/113759) — MEDIUM; confirms runtime.txt unreliable; Advanced settings is the correct mechanism.
- [src layout deployment discussion](https://discuss.streamlit.io/t/src-layout-for-deployment/88617) — MEDIUM; `sys.path` shim verified working; `.` in requirements.txt as alternative.
- [uv + pyproject.toml on Community Cloud (forum thread)](https://discuss.streamlit.io/t/install-dependencies-in-streamlit-cloud-based-on-uv-pyproject-toml/79557) — MEDIUM; native uv/pyproject.toml without Poetry not supported; requirements.txt workaround.
- [Community Cloud memory/compute specs (forum thread)](https://discuss.streamlit.io/t/streamlitcloud-computer-specs/35821) — MEDIUM; ~1 GB guaranteed memory floor.
- [Community Cloud sleep behavior (forum thread)](https://discuss.streamlit.io/t/sleep/80085) — MEDIUM; 12-hour inactivity sleep confirmed.
- [MLB StatsAPI gameLog endpoint — live test](https://statsapi.mlb.com/api/v1/people/660271/stats?stats=gameLog&group=hitting&season=2022) — HIGH; confirmed historical season data returned correctly (tested Ohtani 2022).
- [MLB Data API community docs](https://appac.github.io/mlb-data-api-docs/) — MEDIUM; roster endpoint `season` parameter documented.

---
*Stack research for: v1.1 Multi-Season & Deploy milestone*
*Researched: 2026-04-16*
