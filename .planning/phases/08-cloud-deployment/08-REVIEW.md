---
phase: 08-cloud-deployment
reviewed: 2026-04-16T12:00:00Z
depth: standard
files_reviewed: 6
files_reviewed_list:
  - .gitignore
  - .streamlit/config.toml
  - data/venues_cache.json
  - pyproject.toml
  - requirements.txt
  - src/mlb_park/app.py
findings:
  critical: 0
  warning: 2
  info: 2
  total: 4
status: issues_found
---

# Phase 8: Code Review Report

**Reviewed:** 2026-04-16T12:00:00Z
**Depth:** standard
**Files Reviewed:** 6
**Status:** issues_found

## Summary

This changeset prepares the project for Streamlit Cloud deployment. Key changes:
1. `.gitignore` updated to track `.streamlit/config.toml` and `data/venues_cache.json` (previously both directories were fully ignored).
2. New `.streamlit/config.toml` with server/browser/theme settings.
3. Pre-populated `data/venues_cache.json` with 30 MLB venue records for zero-network cold start.
4. `pyproject.toml` moves `pytest` from core deps to `[project.optional-dependencies] dev`.
5. `requirements.txt` removes `pytest` to match.
6. `app.py` adds `sys.path` manipulation for Streamlit Cloud and calls `st.set_page_config`.

The changes are well-scoped and purposeful. Two warnings relate to the `sys.path` hack (fragile import mechanism) and missing newline in the venues cache file. No security issues found.

## Warnings

### WR-01: sys.path.insert at module level is fragile and runs on every rerun

**File:** `src/mlb_park/app.py:19`
**Issue:** The `sys.path.insert(0, ...)` call prepends `src/` to the Python path on every Streamlit rerun. This works but has two concerns: (a) it mutates global interpreter state repeatedly (the same path gets inserted multiple times across reruns, growing `sys.path`), and (b) it can mask import errors by silently resolving to unexpected modules if another `mlb_park` package exists on the system.
**Fix:** Guard the insertion to avoid duplicates:
```python
_src = str(Path(__file__).resolve().parent.parent)
if _src not in sys.path:
    sys.path.insert(0, _src)
```
Alternatively, Streamlit Cloud supports a `packages.txt` or a top-level `setup.py`/`pyproject.toml` with `pip install -e .` in a `packages.txt` or via the app config. However, given this is a hobby project and the `sys.path` approach is documented, the guard is the pragmatic fix.

### WR-02: venues_cache.json missing trailing newline

**File:** `data/venues_cache.json:1`
**Issue:** The file is a single line with no trailing newline (git shows `\ No newline at end of file`). While JSON parsers handle this fine, it causes noisy diffs if the file is ever regenerated (the last line shows as changed even if content is identical) and violates POSIX text file conventions.
**Fix:** Ensure the file ends with a newline. In the code that writes this file (in `mlb_api.py`), append `"\n"` after `json.dump` or use `json.dumps(...) + "\n"` when writing.

## Info

### IN-01: Dependency version ranges diverge between pyproject.toml and requirements.txt

**File:** `pyproject.toml:9-14` / `requirements.txt:1-4`
**Issue:** Both files specify the same four runtime dependencies with the same version ranges. This duplication means version constraints must be updated in two places. The CLAUDE.md explicitly recommends `requirements.txt` as the primary dependency file, and `pyproject.toml` exists for the package metadata / pytest config. This is not a bug but a maintenance burden; if one file is updated and the other is not, Streamlit Cloud (which reads `requirements.txt`) and local `pip install -e .` (which reads `pyproject.toml`) could diverge.
**Fix:** Consider generating `requirements.txt` from `pyproject.toml` or adding a comment in both files noting the other must be kept in sync. Given CLAUDE.md guidance to keep `requirements.txt` as the canonical source, this is acceptable as-is but worth noting.

### IN-02: st.set_page_config must be the first Streamlit command

**File:** `src/mlb_park/app.py:68`
**Issue:** `st.set_page_config()` is correctly placed before any other `st.*` calls in the current code, which is required by Streamlit. However, it appears after the callback function definitions (lines 38-64) which do reference `st.session_state`. This works because function definitions are not calls -- the `st.session_state` accesses inside callbacks only execute when a widget fires, not at definition time. This is correct but worth documenting for future maintainers who might add a top-level `st.*` call above `set_page_config`.
**Fix:** No code change needed. The current placement is correct. The existing comment on line 67 (`# --- Page chrome`) sufficiently marks this boundary.

---

_Reviewed: 2026-04-16T12:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
