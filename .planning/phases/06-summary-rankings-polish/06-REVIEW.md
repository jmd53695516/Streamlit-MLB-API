---
phase: 06-summary-rankings-polish
reviewed: 2026-04-16T12:00:00Z
depth: standard
files_reviewed: 5
files_reviewed_list:
  - src/mlb_park/app.py
  - src/mlb_park/chart.py
  - src/mlb_park/controller.py
  - tests/controller/test_build_view.py
  - tests/controller/test_helpers.py
findings:
  critical: 0
  warning: 2
  info: 2
  total: 4
status: issues_found
---

# Phase 6: Code Review Report

**Reviewed:** 2026-04-16
**Depth:** standard
**Files Reviewed:** 5
**Status:** issues_found

## Summary

Reviewed the Phase 6 additions: summary metrics in `app.py`, park ranking table with highlight styling in `app.py`, `build_park_ranking` in `controller.py`, and their corresponding tests. The code is generally well-structured with good defensive programming. No critical issues found. Two warnings relate to potential edge-case bugs in the highlight styling logic and a silent-truncation risk in a `zip` call. Two informational items note minor code quality concerns.

## Warnings

### WR-01: _highlight_top_bottom row.name assumption is fragile

**File:** `src/mlb_park/app.py:192-204`
**Issue:** The `_highlight_top_bottom` function uses `row.name` as a positional integer index into `ranking_df` via `.iloc[idx]`. This works only because `build_park_ranking` calls `.reset_index(drop=True)`, but the coupling is implicit. If `build_park_ranking` ever changes its index handling (e.g., returns a named index or skips `reset_index`), the styling function will silently produce wrong highlights or raise `IndexError`. Additionally, re-looking up `clears_val = ranking_df["Clears"].iloc[idx]` when `row["Clears"]` is already available in the `row` Series is unnecessary indirection.
**Fix:** Use `row["Clears"]` directly instead of re-indexing into the DataFrame:
```python
def _highlight_top_bottom(row):
    n = len(ranking_df)
    if n == 0:
        return [""] * len(row)
    top_cutoff = ranking_df["Clears"].iloc[min(2, n - 1)]
    bot_cutoff = ranking_df["Clears"].iloc[max(n - 3, 0)]
    clears_val = row["Clears"]
    if clears_val >= top_cutoff and top_cutoff > bot_cutoff:
        return ["background-color: rgba(44, 160, 44, 0.15)"] * len(row)
    elif clears_val <= bot_cutoff and top_cutoff > bot_cutoff:
        return ["background-color: rgba(214, 39, 40, 0.15)"] * len(row)
    return [""] * len(row)
```

### WR-02: zip without length assertion risks silent data truncation

**File:** `src/mlb_park/app.py:213`
**Issue:** `zip(view.plottable_events, view.clears_selected_park)` silently truncates if the two sequences have different lengths. While the controller currently guarantees alignment, a future refactor could break this invariant without any error surfacing. The table would silently display fewer rows than expected.
**Fix:** Add an assertion before the zip, or use `zip(..., strict=True)` (Python 3.10+):
```python
for ev, clears in zip(view.plottable_events, view.clears_selected_park, strict=True):
```

## Info

### IN-01: Broad exception catch in app.py error handler

**File:** `src/mlb_park/app.py:142`
**Issue:** `except Exception as e:` catches all exceptions including programming errors (e.g., `TypeError`, `AttributeError`) that should propagate during development. The error message tells the user "The MLB API may be temporarily unavailable" even for non-network bugs. During development this can mask real bugs behind a misleading user-facing message.
**Fix:** Consider catching a narrower set of exceptions (e.g., `requests.RequestException`, `MLBAPIError`, `ValueError`) and letting unexpected errors propagate with a full traceback during development. Alternatively, log the full exception before showing the user-friendly message:
```python
import logging
log = logging.getLogger(__name__)
# ...
except Exception as e:
    log.exception("build_view failed")
    st.error(...)
```

### IN-02: Unused re-exports in controller.py import block

**File:** `src/mlb_park/controller.py:19-30`
**Issue:** `HitData`, `MLBAPIError`, and `load_all_parks` are imported from `mlb_park.pipeline` with a `noqa: F401` annotation as "re-exports primed for Plan 04-02," but none of these symbols are used at runtime in this module. `load_all_parks` is called as `api.load_all_parks()` via dependency injection, not through the top-level import. If these are genuinely intended as re-exports for downstream consumers, adding them to `__all__` would make the intent explicit. Otherwise they are dead imports.
**Fix:** Either add the re-exported names to `__all__` to formalize the public re-export contract, or remove the unused imports if no downstream module imports them from `controller`.

---

_Reviewed: 2026-04-16_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
