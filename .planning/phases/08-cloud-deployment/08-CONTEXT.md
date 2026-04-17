# Phase 8: Cloud Deployment - Context

**Gathered:** 2026-04-16
**Status:** Ready for planning

<domain>
## Phase Boundary

Deploy the Streamlit MLB HR Park Factor Explorer to Streamlit Community Cloud with a shareable URL. Visitors can use the full app without local setup. Cold-start venue fetch is eliminated by committing the venues cache. Dependencies are cleaned for Cloud, and app config is committed.

</domain>

<decisions>
## Implementation Decisions

### Streamlit Config
- **D-01:** Layout mode is `wide` — spray charts and side-by-side content need full browser width
- **D-02:** Theme uses classic MLB branding — primary `#002D72` (navy), accent `#D50032` (red), white background
- **D-03:** Browser tab title is "MLB HR Park Explorer"
- **D-04:** `.streamlit/config.toml` includes `[server] headless = true` and `[browser] gatherUsageStats = false`

### Dependency Cleanup
- **D-05:** Remove `pytest` from `requirements.txt` — Cloud should not install test dependencies
- **D-06:** Keep `pyproject.toml` — move `pytest` from `dependencies` to `[project.optional-dependencies]` under a `dev` extra (e.g., `pip install -e ".[dev]"`)
- **D-07:** `requirements.txt` remains the primary file Streamlit Cloud reads; `pyproject.toml` is for local dev tooling

### Venues Cache
- **D-08:** Keep `venues_cache.json` at `data/venues_cache.json` (current `VENUES_FILE` path in `config.py` unchanged)
- **D-09:** Narrow `.gitignore` — stop excluding all of `data/`, instead only exclude runtime files. `data/venues_cache.json` must be tracked by git
- **D-10:** Generate the cache by running the app locally once, then `git add data/venues_cache.json`

### Deploy Workflow
- **D-11:** Deploy from `main` branch — merge `master` into `main` before connecting Cloud
- **D-12:** No secrets needed — `statsapi.mlb.com` is a public API with no auth
- **D-13:** `.gitignore` should exclude `.streamlit/secrets.toml` only (not all of `.streamlit/`)
- **D-14:** Plan includes a non-autonomous task with step-by-step Streamlit Community Cloud setup instructions (user does the clicking, plan provides the guide)

### Claude's Discretion
- Exact `.streamlit/config.toml` structure and any additional Streamlit server settings for Cloud
- Whether to add a `runtime.txt` or `packages.txt` for Cloud (likely not needed)
- Git merge strategy for master→main (fast-forward vs merge commit)

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

No external specs — requirements fully captured in decisions above and REQUIREMENTS.md.

### Project Config
- `CLAUDE.md` — Tech stack constraints, caching decisions, dependency pinning strategy
- `.planning/REQUIREMENTS.md` — DEPLOY-01 through DEPLOY-04 acceptance criteria

### Source Files (integration points)
- `src/mlb_park/config.py` — `VENUES_FILE` path at line 27 (must remain compatible)
- `requirements.txt` — Current dependency list (has pytest to remove)
- `pyproject.toml` — Current project config (pytest in wrong section)
- `.gitignore` — Current exclusions (blocks data/ and .streamlit/)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `src/mlb_park/services/mlb_api.py:load_all_parks()` ��� already handles venues_cache.json read/write with atomic file operations and staleness check (30-day TTL)
- `src/mlb_park/config.py:VENUES_FILE` — path constant at `_ROOT / "data" / "venues_cache.json"`

### Established Patterns
- `@st.cache_data` used for all API caching — no changes needed for Cloud
- `st.set_page_config()` called in `app.py` — will need `layout="wide"` added
- All HTTP goes through `mlb_api.py` — no direct `requests` calls elsewhere

### Integration Points
- `.gitignore` currently blocks `data/` and `.streamlit/` — both need narrowing
- `requirements.txt` is read by Streamlit Community Cloud during deploy
- `app.py` entry point — Cloud needs `[server] headless = true` in config.toml

</code_context>

<specifics>
## Specific Ideas

- Classic MLB color palette: navy `#002D72`, red `#D50032`, white background
- Tab title: "MLB HR Park Explorer"
- No secrets.toml needed — public API

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 08-cloud-deployment*
*Context gathered: 2026-04-16*
