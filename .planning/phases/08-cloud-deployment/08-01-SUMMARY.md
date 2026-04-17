---
phase: 08-cloud-deployment
plan: 01
subsystem: infra
tags: [streamlit-cloud, config, deployment-prep, gitignore]

# Dependency graph
requires:
  - phase: 07-multi-season
    provides: "Season-parameterized app with venues_cache.json"
provides:
  - "Streamlit config.toml with MLB theme and headless server settings"
  - "Narrowed .gitignore allowing config.toml and venues_cache.json tracking"
  - "st.set_page_config with wide layout and browser tab title"
  - "Cloud-ready requirements.txt (no pytest)"
  - "pytest moved to pyproject.toml optional-dependencies"
affects: [08-02-cloud-deployment]

# Tech tracking
tech-stack:
  added: []
  patterns: ["Streamlit config.toml for Cloud deployment settings", "optional-dependencies for dev tools"]

key-files:
  created: [".streamlit/config.toml"]
  modified: [".gitignore", "src/mlb_park/app.py", "requirements.txt", "pyproject.toml", "data/venues_cache.json"]

key-decisions:
  - "MLB theme primaryColor #002D72 (navy) matches MLB branding"
  - "pytest in optional-dependencies avoids unnecessary Cloud install"

patterns-established:
  - "config.toml for Streamlit Cloud server/theme settings"
  - "optional-dependencies.dev for test-only packages"

requirements-completed: [DEPLOY-02, DEPLOY-03, DEPLOY-04]

# Metrics
duration: 2min
completed: 2026-04-16
---

# Phase 8 Plan 1: Cloud Deployment Prep Summary

**Streamlit config.toml with MLB theme, wide layout via set_page_config, narrowed .gitignore, and pytest moved to optional-dependencies for clean Cloud install**

## Performance

- **Duration:** 2 min
- **Started:** 2026-04-16T21:19:06Z
- **Completed:** 2026-04-16T21:21:00Z
- **Tasks:** 2
- **Files modified:** 6

## Accomplishments
- Created .streamlit/config.toml with headless=true, gatherUsageStats=false, and MLB navy theme
- Added st.set_page_config(page_title="MLB HR Park Explorer", layout="wide") as first st.* call in app.py
- Narrowed .gitignore from blocking all of .streamlit/ and data/ to only .streamlit/secrets.toml
- Removed pytest from requirements.txt, moved to pyproject.toml [project.optional-dependencies].dev
- Git-tracked data/venues_cache.json (17KB, 30 venues) for cold-start elimination

## Task Commits

Each task was committed atomically:

1. **Task 1: Narrow .gitignore, create config.toml, add set_page_config, track venues cache** - `591c2b4` (feat)
2. **Task 2: Clean requirements.txt and pyproject.toml for Cloud** - `c728095` (chore)

## Files Created/Modified
- `.streamlit/config.toml` - Streamlit server, browser, and theme configuration for Cloud
- `.gitignore` - Narrowed to exclude only .streamlit/secrets.toml (not all of .streamlit/ or data/)
- `src/mlb_park/app.py` - Added st.set_page_config as first st.* call for wide layout + tab title
- `requirements.txt` - 4 runtime deps only (streamlit, requests, plotly, pandas)
- `pyproject.toml` - pytest moved to [project.optional-dependencies].dev
- `data/venues_cache.json` - Now git-tracked for Cloud cold-start elimination

## Decisions Made
- MLB theme primaryColor set to #002D72 (navy) to match MLB branding
- pytest kept in optional-dependencies (not removed entirely) so local dev can still `pip install -e ".[dev]"`

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
- venues_cache.json was not present in the worktree (gitignored by `data/` rule); copied from main repo before narrowing .gitignore. Expected behavior given the old .gitignore rules.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Repository is Cloud-ready: config.toml committed, requirements.txt clean, venues_cache.json tracked
- Ready for Plan 02: GitHub push and Streamlit Cloud deployment
- All 127 tests pass

---
*Phase: 08-cloud-deployment*
*Completed: 2026-04-16*
