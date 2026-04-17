# Phase 8: Cloud Deployment - Research

**Researched:** 2026-04-16
**Domain:** Streamlit Community Cloud deployment, git branch management, dependency cleanup
**Confidence:** HIGH

## Summary

Phase 8 is primarily a configuration and housekeeping phase, not a code-logic phase. The work breaks into four distinct streams: (1) write and commit `.streamlit/config.toml` with layout, theme, and server settings; (2) clean `requirements.txt` and `pyproject.toml` by moving `pytest` to an optional dev extra; (3) narrow `.gitignore` so `data/venues_cache.json` and `.streamlit/config.toml` are tracked; and (4) create a `main` branch and walk the user through the Streamlit Community Cloud UI to connect and deploy.

All four streams are well-understood, low-risk, and fully constrained by the locked decisions in CONTEXT.md. No new libraries are introduced. The only non-autonomous step is the browser-based Streamlit Community Cloud setup — the plan must deliver a precise click-by-click guide for that step.

**Primary recommendation:** Execute the four streams in dependency order — gitignore first (unlocks tracking), then config.toml + deps cleanup, then cache commit, then branch + deploy guide.

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Streamlit Config**
- D-01: Layout mode is `wide` — spray charts and side-by-side content need full browser width
- D-02: Theme uses classic MLB branding — primary `#002D72` (navy), accent `#D50032` (red), white background
- D-03: Browser tab title is "MLB HR Park Explorer"
- D-04: `.streamlit/config.toml` includes `[server] headless = true` and `[browser] gatherUsageStats = false`

**Dependency Cleanup**
- D-05: Remove `pytest` from `requirements.txt` — Cloud should not install test dependencies
- D-06: Keep `pyproject.toml` — move `pytest` from `dependencies` to `[project.optional-dependencies]` under a `dev` extra (e.g., `pip install -e ".[dev]"`)
- D-07: `requirements.txt` remains the primary file Streamlit Cloud reads; `pyproject.toml` is for local dev tooling

**Venues Cache**
- D-08: Keep `venues_cache.json` at `data/venues_cache.json` (current `VENUES_FILE` path in `config.py` unchanged)
- D-09: Narrow `.gitignore` — stop excluding all of `data/`, instead only exclude runtime files. `data/venues_cache.json` must be tracked by git
- D-10: Generate the cache by running the app locally once, then `git add data/venues_cache.json`

**Deploy Workflow**
- D-11: Deploy from `main` branch — merge `master` into `main` before connecting Cloud
- D-12: No secrets needed — `statsapi.mlb.com` is a public API with no auth
- D-13: `.gitignore` should exclude `.streamlit/secrets.toml` only (not all of `.streamlit/`)
- D-14: Plan includes a non-autonomous task with step-by-step Streamlit Community Cloud setup instructions (user does the clicking, plan provides the guide)

### Claude's Discretion
- Exact `.streamlit/config.toml` structure and any additional Streamlit server settings for Cloud
- Whether to add a `runtime.txt` or `packages.txt` for Cloud (likely not needed)
- Git merge strategy for master→main (fast-forward vs merge commit)

### Deferred Ideas (OUT OF SCOPE)
None — discussion stayed within phase scope
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| DEPLOY-01 | App is deployed to Streamlit Community Cloud with a shareable URL | D-11/D-14: create main branch, user clicks through share.streamlit.io |
| DEPLOY-02 | `requirements.txt` is cleaned up for Cloud (remove pytest, add editable install) | D-05/D-06/D-07: pytest → optional-dependencies, requirements.txt stays primary |
| DEPLOY-03 | `.streamlit/config.toml` is committed with app config; `.gitignore` narrowed to exclude only `secrets.toml` | D-01–D-04, D-13: exact toml structure verified below |
| DEPLOY-04 | `venues_cache.json` is committed to the repo to eliminate cold-start venue fetches on Cloud | D-08/D-09/D-10: gitignore narrowing + git add data/venues_cache.json |
</phase_requirements>

---

## Standard Stack

### Core (no new libraries — configuration only)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| streamlit | >=1.55,<2.0 | Already in use | `[client]` layout is set via config.toml, not a new API |
| pytest | >=8.0,<9.0 | Dev-only test runner | Moves to `[project.optional-dependencies]` — not installed on Cloud |

**No new packages to install.** This phase is pure configuration.

### Files Created or Modified

| File | Action | Purpose |
|------|--------|---------|
| `.streamlit/config.toml` | Create | Layout, theme, server settings for Cloud |
| `requirements.txt` | Edit | Remove `pytest` line |
| `pyproject.toml` | Edit | Move pytest to `[project.optional-dependencies].dev` |
| `.gitignore` | Edit | Narrow `data/` and `.streamlit/` exclusions |
| `data/venues_cache.json` | Git-track | Eliminate cold-start venue fetch on Cloud |

---

## Architecture Patterns

### Recommended Project Structure (post-phase)

```
.
├── .streamlit/
│   └── config.toml          # committed — layout, theme, server
│   # secrets.toml           # gitignored if it ever exists
├── data/
│   └── venues_cache.json    # NOW committed (was gitignored)
│   # other runtime files    # still gitignored
├── src/mlb_park/
│   └── config.py            # VENUES_FILE path unchanged
├── requirements.txt         # Cloud reads this — no pytest
└── pyproject.toml           # local dev only — pytest under [dev] extra
```

### Pattern 1: config.toml for Streamlit Community Cloud

**What:** A committed `.streamlit/config.toml` controls layout, theme, and server behavior consistently across local and Cloud environments.

**When to use:** Always for deployed apps — without it, Cloud uses defaults (narrow layout, light theme with no brand colors).

**Exact file content (discretion area — fully resolved here):**

```toml
# Source: docs.streamlit.io/develop/api-reference/configuration/config.toml
[server]
headless = true

[browser]
gatherUsageStats = false

[client]
showSidebarNavigation = true

[theme]
base = "light"
primaryColor = "#002D72"
backgroundColor = "#FFFFFF"
secondaryBackgroundColor = "#F0F2F6"
textColor = "#262730"

[app]
# Page config is set via st.set_page_config() in app.py, not config.toml.
# layout="wide" and page_title="MLB HR Park Explorer" go there.
```

**IMPORTANT distinction:** `layout="wide"` and `page_title` are NOT config.toml keys. [VERIFIED: docs.streamlit.io/develop/api-reference/configuration/config.toml] They are controlled by `st.set_page_config()` in `app.py`. The existing call at `app.py:62` sets `st.title()` but `set_page_config()` must be confirmed/updated to include `layout="wide"` and `page_title="MLB HR Park Explorer"`.

**config.toml keys that DO control layout/title:** There are none. `[client]` has `showSidebarNavigation`, `toolbarMode`, `showErrorDetails` — not layout width. [VERIFIED: docs.streamlit.io/develop/api-reference/configuration/config.toml]

### Pattern 2: pyproject.toml optional-dependencies

**What:** Move dev-only tools out of `dependencies` into `[project.optional-dependencies]` so `requirements.txt` (which Cloud reads) doesn't need to list them.

**Exact change:**

```toml
# BEFORE — pytest in main dependencies (wrong)
[project]
dependencies = [
    "streamlit>=1.55,<2.0",
    "requests>=2.32,<3.0",
    "plotly>=6.7,<7.0",
    "pandas>=2.2,<3.0",
    "pytest>=8.0,<9.0",    # <-- remove from here
]

# AFTER — pytest in optional dev extra
[project]
dependencies = [
    "streamlit>=1.55,<2.0",
    "requests>=2.32,<3.0",
    "plotly>=6.7,<7.0",
    "pandas>=2.2,<3.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0,<9.0",
]
```

Local install command: `pip install -e ".[dev]"` or `uv pip install -e ".[dev]"` [ASSUMED — standard Python packaging convention, not Cloud-specific]

### Pattern 3: Narrowing .gitignore

**What:** Replace broad directory exclusions with precise file/pattern exclusions.

**Exact change:**

```gitignore
# BEFORE (current)
.streamlit/
data/

# AFTER (narrowed)
.streamlit/secrets.toml
data/*.json.tmp
# data/venues_cache.json is now TRACKED — do not exclude it
```

**Note:** If there are no other runtime files in `data/` beyond `venues_cache.json`, the `data/` line can simply be removed entirely. The file itself being committed takes precedence over a directory exclusion only if the directory exclusion is removed first. [VERIFIED: git behavior — gitignore directory entries block all contents; narrowing is required before `git add` will work]

### Pattern 4: Creating main branch and merging master

**What:** The repo currently has only `master`. Streamlit Community Cloud works with any branch, but the decision is to deploy from `main`.

**Commands:**
```bash
git checkout -b main          # create main from current master HEAD
git push -u origin main       # push to GitHub
# In GitHub settings: optionally set main as default branch
```

**Strategy:** Fast-forward is implicit here since `main` is being created fresh from `master` HEAD — there is no divergence. No `--ff-only` flag needed, no merge commit created. [VERIFIED: git-scm.com/docs/git-merge — creating a new branch from HEAD is inherently a fast-forward start point]

### Anti-Patterns to Avoid

- **Setting `layout="wide"` in config.toml:** There is no such key. It belongs in `st.set_page_config(layout="wide")` in `app.py`. Putting it in config.toml does nothing.
- **Committing secrets.toml:** If ever created (not needed here per D-12), it must be gitignored before creation.
- **Using `runtime.txt` to pin Python version:** As of 2025-2026, Streamlit Community Cloud appears to ignore `runtime.txt`. Python version must be set in the Cloud UI "Advanced settings" during deploy. [VERIFIED: multiple community forum reports 2025; official docs make no mention of runtime.txt]
- **Adding `packages.txt`:** Only needed for Linux system packages (apt-get). This app has no C extensions or system deps beyond what pip wheels provide. Not needed. [VERIFIED: docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/app-dependencies]
- **Including requirements.txt AND pyproject.toml for Cloud to read:** Cloud reads only the highest-priority file found. Since `requirements.txt` exists at repo root and takes priority over `pyproject.toml` (for non-Poetry format), Cloud will read `requirements.txt`. This matches D-07. [VERIFIED: docs.streamlit.io — priority order: uv.lock > Pipfile > environment.yml > requirements.txt > pyproject.toml]

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Theming | Custom CSS injection | `[theme]` in config.toml | Native Streamlit theming is applied before page render; CSS injection is fragile across Streamlit versions |
| Python version pin | `runtime.txt` | Cloud UI "Advanced settings" | runtime.txt is ignored in 2025-2026 Cloud deployments |
| Cache warming script | Separate Python script | Run the app locally once | `load_all_parks()` already handles write-on-miss atomically; no extra tooling needed |

---

## Runtime State Inventory

Not applicable — this is a configuration/deployment phase, not a rename/refactor phase. No stored data, live service config, OS registrations, secrets, or build artifacts reference names being changed.

**One item to verify:** `data/venues_cache.json` currently exists on disk (confirmed by `ls data/` output). It was generated by the app's `load_all_parks()` function. Committing it is a git operation only — no data migration required.

---

## Common Pitfalls

### Pitfall 1: .gitignore directory exclusion blocks `git add`

**What goes wrong:** Developer removes `data/` from gitignore, runs `git add data/venues_cache.json`, and git silently refuses to stage it if `data/` is still in gitignore as a directory pattern.

**Why it happens:** Git processes gitignore rules before staging. A directory exclusion (`data/`) blocks all files under it regardless of explicit `git add`.

**How to avoid:** Edit `.gitignore` to remove `data/` (or narrow it) BEFORE running `git add data/venues_cache.json`. Verify with `git check-ignore -v data/venues_cache.json`.

**Warning signs:** `git status` doesn't show `data/venues_cache.json` as untracked after editing gitignore — means the exclusion is still active.

### Pitfall 2: config.toml not found because .streamlit/ was gitignored

**What goes wrong:** Developer creates `.streamlit/config.toml` locally but forgets to update `.gitignore`. The file exists locally but is excluded from git. Cloud never sees it.

**Why it happens:** Current `.gitignore` has `.streamlit/` (whole directory). The file must be committed for Cloud to read it.

**How to avoid:** Narrow `.gitignore` to `.streamlit/secrets.toml` BEFORE creating `config.toml`. Then `git add .streamlit/config.toml` will work.

**Warning signs:** `git status` shows `.streamlit/config.toml` is not listed (not untracked, not staged) — it is being ignored.

### Pitfall 3: layout="wide" placed in config.toml

**What goes wrong:** Developer puts `layout = "wide"` under some config.toml section. Streamlit silently ignores unknown keys. App deploys with narrow layout.

**Why it happens:** Confusion between `st.set_page_config(layout="wide")` (the correct location) and config.toml (which has no layout key).

**How to avoid:** Set layout in `app.py`: `st.set_page_config(layout="wide", page_title="MLB HR Park Explorer")`. Confirm this call exists and precedes all other `st.*` calls.

**Warning signs:** App is narrow after deploy despite config.toml edits.

### Pitfall 4: venues_cache.json stale or missing at commit time

**What goes wrong:** Developer commits `venues_cache.json` before running the app (file is empty, zero-byte, or from a prior season). Cloud gets a stale cache; `load_all_parks()` will refetch — defeating DEPLOY-04.

**Why it happens:** The cache was gitignored; it may have been generated at an old timestamp or not at all.

**How to avoid:** Run the app locally (with the current season active), navigate past the team selector (which triggers `load_all_parks()`), verify `data/venues_cache.json` has recent mtime and non-zero size, then commit.

**Warning signs:** `venues_cache.json` is < 1KB or has a mtime from months ago.

### Pitfall 5: Streamlit Community Cloud picking wrong entry point

**What goes wrong:** Cloud is pointed at the wrong file (e.g., repo root `app.py` doesn't exist; actual entry point is `src/mlb_park/app.py`).

**Why it happens:** Cloud UI asks for "main file path" — default assumption is `app.py` at root.

**How to avoid:** In the Cloud deploy dialog, set main file path to `src/mlb_park/app.py`. This is non-obvious since the file is in `src/`.

---

## Code Examples

### Verified: complete config.toml

```toml
# .streamlit/config.toml
# Source: docs.streamlit.io/develop/api-reference/configuration/config.toml

[server]
headless = true

[browser]
gatherUsageStats = false

[theme]
base = "light"
primaryColor = "#002D72"
backgroundColor = "#FFFFFF"
secondaryBackgroundColor = "#F0F2F6"
textColor = "#262730"
```

Note: `secondaryBackgroundColor` and `textColor` are defaults for the light theme. Including them makes the theme explicit and immune to future Streamlit default changes. [VERIFIED: config.toml docs — these are valid theme keys]

### Verified: st.set_page_config call in app.py

```python
# src/mlb_park/app.py — must be the FIRST Streamlit call
st.set_page_config(
    page_title="MLB HR Park Explorer",
    layout="wide",
)
```

This must appear before any other `st.*` call in the module. The current `app.py` has `st.title()` at line 62 without a preceding `set_page_config()` — this needs to be added.

### Verified: requirements.txt (post-cleanup)

```
streamlit>=1.55,<2.0
requests>=2.32,<3.0
plotly>=6.7,<7.0
pandas>=2.2,<3.0
```

Exactly four lines — pytest removed.

### Verified: pyproject.toml optional-dependencies section

```toml
[project.optional-dependencies]
dev = [
    "pytest>=8.0,<9.0",
]
```

### Verified: .gitignore (post-narrowing)

```gitignore
# Python
__pycache__/
*.py[cod]
*.egg-info/
.venv/
venv/

# Streamlit — track config.toml, ignore secrets only
.streamlit/secrets.toml

# App runtime state — track venues_cache.json, ignore nothing else in data/
# data/ line removed entirely — venues_cache.json is now committed

# OS
.DS_Store
Thumbs.db
```

### Verified: git commands for main branch creation

```bash
# From master, create and push main
git checkout -b main
git push -u origin main
```

No merge needed — `main` is created at `master` HEAD. Both branches point to the same commit. [VERIFIED: standard git branch creation behavior]

### Verified: check gitignore before staging

```bash
git check-ignore -v data/venues_cache.json
# Should return nothing (no rule ignoring it) after .gitignore edit
git check-ignore -v .streamlit/config.toml
# Should return nothing after .gitignore edit
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `runtime.txt` to pin Python | Cloud UI "Advanced settings" | 2025 | runtime.txt is ignored; must use UI |
| Deploy from any branch | Any branch works; `main`/`master` excluded from URL slug | Current | Deploy from `main` keeps URL clean |

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `pip install -e ".[dev]"` is the correct local install command for optional-dependencies | Architecture Patterns §2 | Minimal — standard Python packaging; alternative is `pip install -e ".[dev]" --no-build-isolation` |
| A2 | `secondaryBackgroundColor = "#F0F2F6"` is a reasonable sidebar/widget background for a light theme | Code Examples | Cosmetic only — user can adjust |
| A3 | `app.py` currently does NOT have `st.set_page_config()` — only `st.title()` | Code Examples | If wrong, the existing set_page_config just needs `layout="wide"` added to it, not created |

**Lowest-risk assumption:** A3 carries implementation impact. The planner should include a task that checks for `set_page_config` and adds/updates it.

---

## Open Questions

1. **Does `app.py` have a `st.set_page_config()` call?**
   - What we know: `app.py` line 62 has `st.title(...)`. The read was truncated at line 70.
   - What's unclear: Whether `set_page_config()` exists earlier in the file (it would have to be before line 62).
   - Recommendation: Plan task should read the full `app.py` and either add `set_page_config()` at the top or update an existing call to add `layout="wide"` and `page_title`.

2. **Are there other files in `data/` besides `venues_cache.json`?**
   - What we know: `ls data/` returned only `venues_cache.json`.
   - What's unclear: Whether the app could create other files there at runtime.
   - Recommendation: Safe to remove `data/` from gitignore entirely and add `data/*.log` or similar if needed in future.

3. **Does GitHub repo have `origin` remote configured?**
   - What we know: `git remote -v` returned no output (no remote configured).
   - What's unclear: Whether the user has a GitHub remote set up at all.
   - Recommendation: Plan must include a step to add GitHub remote (`git remote add origin <url>`) before pushing `main`. This is a prerequisite for Streamlit Cloud deploy.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| git | Branch creation, push to GitHub | ✓ | (in use) | — |
| GitHub remote | `git push origin main` | ✗ | — | User must create GitHub repo and add remote |
| Streamlit Community Cloud account | DEPLOY-01 | Unknown | — | User must sign up at share.streamlit.io |
| `data/venues_cache.json` | DEPLOY-04 | ✓ | (exists locally) | Run app once to generate |

**Missing dependencies with no fallback:**
- GitHub remote (`origin`): The repo has no remote configured. The user must create a GitHub repository and run `git remote add origin <url>` before `git push origin main` will work. Plan must include this step.

**Missing dependencies with fallback:**
- Streamlit Community Cloud account: If user doesn't have one, the plan guide must include "sign up at share.streamlit.io with GitHub OAuth" as step 0.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 8.x |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` |
| Quick run command | `pytest tests/ -x -q` |
| Full suite command | `pytest tests/` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| DEPLOY-01 | App deploys with shareable URL | manual | N/A — browser action | N/A |
| DEPLOY-02 | requirements.txt has no pytest line | smoke | `grep -c pytest requirements.txt` returns 0 | ✅ (shell check) |
| DEPLOY-03 | config.toml exists and has correct keys | smoke | `python -c "import tomllib; d=tomllib.load(open('.streamlit/config.toml','rb')); assert d['server']['headless']"` | ❌ Wave 0 |
| DEPLOY-04 | venues_cache.json is git-tracked | smoke | `git ls-files data/venues_cache.json` returns non-empty | ✅ (shell check) |

### Sampling Rate
- **Per task commit:** `pytest tests/ -x -q` (existing suite — verify nothing broken by config edits)
- **Per wave merge:** `pytest tests/` full suite
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] Smoke check for config.toml presence and key values — one-liner assertion or small test

*(Existing 110-test suite covers all business logic; no new test files needed for this phase beyond the config.toml smoke check.)*

---

## Security Domain

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | No | Public API, no auth |
| V3 Session Management | No | Streamlit stateless reruns |
| V4 Access Control | No | Single-user local/Cloud app |
| V5 Input Validation | No | No user-supplied data reaches API as unvalidated input |
| V6 Cryptography | No | No secrets, no encryption needed |

**D-12 confirmed:** `statsapi.mlb.com` is a public API. No `secrets.toml` is needed. The only security action is ensuring `secrets.toml` is in `.gitignore` as a precaution (D-13).

---

## Sources

### Primary (HIGH confidence)
- [docs.streamlit.io/develop/api-reference/configuration/config.toml](https://docs.streamlit.io/develop/api-reference/configuration/config.toml) — all config.toml sections, key names, and valid values verified
- [docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/app-dependencies](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/app-dependencies) — requirements.txt location, priority order, packages.txt behavior
- [docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/deploy](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/deploy) — exact deploy steps, branch handling, main file path entry

### Secondary (MEDIUM confidence)
- [git-scm.com/docs/git-merge](https://git-scm.com/docs/git-merge) — fast-forward merge semantics; `--ff-only` flag
- Streamlit community forums (2025) — runtime.txt being ignored confirmed by multiple independent reports

### Tertiary (LOW confidence)
- None — all critical claims verified from primary sources

---

## Metadata

**Confidence breakdown:**
- config.toml structure: HIGH — verified from official docs; all key names confirmed
- Dependency cleanup: HIGH — standard Python packaging convention
- .gitignore narrowing: HIGH — git behavior is well-defined
- Branch creation: HIGH — git fundamentals
- Community Cloud deploy steps: HIGH — verified from official deploy guide
- runtime.txt behavior: MEDIUM — official docs silent; community forum evidence strong

**Research date:** 2026-04-16
**Valid until:** 2026-07-16 (Streamlit Cloud deployment mechanics are stable; config.toml schema changes with major releases)
