---
phase: 07-multi-season-selector
reviewed: 2026-04-16T00:00:00Z
depth: standard
files_reviewed: 10
files_reviewed_list:
  - pyproject.toml
  - scripts/test_historical_roster.py
  - src/mlb_park/app.py
  - src/mlb_park/config.py
  - src/mlb_park/pipeline/__init__.py
  - src/mlb_park/services/mlb_api.py
  - tests/controller/test_callbacks.py
  - tests/services/test_mlb_api_season.py
  - tests/services/test_team_hitting_stats.py
  - tests/test_config_season.py
findings:
  critical: 0
  warning: 3
  info: 4
  total: 7
status: issues_found
---

# Phase 7: Code Review Report

**Reviewed:** 2026-04-16T00:00:00Z
**Depth:** standard
**Files Reviewed:** 10
**Status:** issues_found

## Summary

Phase 7 introduces multi-season support: a dynamic `AVAILABLE_SEASONS` constant,
a Season selectbox with cascade-reset callbacks, conditional `rosterType` dispatch
(`active` vs `fullSeason`), and split cached wrappers with different TTLs for
current vs historical data. The core logic is sound and the architecture is well
structured. Three issues warrant attention: a semantic boundary error in the
`rosterType` dispatcher that permits future-season requests through the wrong
path, a time-bomb test assertion that will fail silently after 2026 becomes a
past season, and a source-text test that doesn't actually verify the specific
function it claims to check.

---

## Warnings

### WR-01: `rosterType` dispatcher uses `>=` instead of `==`, allowing future seasons to use `active`

**File:** `src/mlb_park/services/mlb_api.py:116`
**Issue:** The condition `season >= CURRENT_SEASON` routes any season value at
or above the current year to `rosterType=active`. A caller passing `season=2027`
when `CURRENT_SEASON=2026` would request an active roster for a season that
hasn't started, silently returning wrong or empty data. The intent is clearly
"current season only uses active," so the comparison should be equality.

**Fix:**
```python
# Before
roster_type = "active" if season >= CURRENT_SEASON else "fullSeason"

# After
roster_type = "active" if season == CURRENT_SEASON else "fullSeason"
```

The same pattern applies to the parallel dispatcher functions `get_game_log`
(line 170) and `get_team_hitting_stats` (line 195), which use `season < CURRENT_SEASON`
for the historical branch. Those are logically equivalent to `!= CURRENT_SEASON`
for the historical side, so they're correct as written — but `_raw_team_hitting_stats`
at line 116 is the one that needs fixing since it will construct a live API
request with the wrong `rosterType`.

---

### WR-02: Hardcoded season `2026` in test will silently assert wrong `rosterType` after this year

**File:** `tests/services/test_team_hitting_stats.py:71,75`
**Issue:** `test_raw_helper_builds_expected_url` calls `_raw_team_hitting_stats(147, 2026)`
and asserts `rosterType == "active"`. This relies on `2026` being
`CURRENT_SEASON`. When 2027 arrives, `CURRENT_SEASON` becomes 2027, the
`_raw_team_hitting_stats` logic routes season 2026 as historical, and the
assertion `params.get("rosterType") == "active"` fails. The test will
start failing in CI without any code change.

**Fix:**
```python
from mlb_park.config import CURRENT_SEASON

# Replace hardcoded year with the dynamic constant
mlb_api._raw_team_hitting_stats(147, CURRENT_SEASON)

# ...
assert params.get("rosterType") == "active"
```

---

### WR-03: `test_game_feed_ttl_is_30d` source-text check is too broad — passes even if `get_game_feed` TTL is wrong

**File:** `tests/services/test_mlb_api_season.py:172-179`
**Issue:** The test scans the entire source file for the string `'ttl="30d"'`.
Because `get_team_hitting_stats_historical` and `get_game_log_historical` also
use `ttl="30d"`, this assertion passes even if `get_game_feed`'s decorator is
changed to a different value. The test title says it is checking `get_game_feed`
specifically, but the check does not enforce that.

**Fix:** Narrow the match to the lines that belong to `get_game_feed`. A robust
approach is to parse only the relevant decorator lines:
```python
import re

lines = Path(mlb_api.__file__).read_text(encoding="utf-8").splitlines()
# Find the get_game_feed function and inspect its decorator
in_target = False
for line in lines:
    if "def get_game_feed" in line:
        in_target = True
    if in_target and '@st.cache_data' in line:
        assert 'ttl="30d"' in line, "get_game_feed must have ttl='30d'"
        break
```
Or, simpler — check for `max_entries=200` (which is already uniquely present on
`get_game_feed`) as an anchor and assert both attributes appear on the same
decorator line.

---

## Info

### IN-01: `pytest` declared as a runtime dependency

**File:** `pyproject.toml:14`
**Issue:** `pytest` is listed under `[project] dependencies` alongside `streamlit`,
`requests`, etc. This means pytest ships as a runtime requirement of the package.
It should be in a dev/optional-dependencies section.

**Fix:**
```toml
[project.optional-dependencies]
dev = [
    "pytest>=8.0,<9.0",
]
```

Or, since this project uses a flat `requirements.txt` and `pyproject.toml` only
for the build system, you can leave pytest in `requirements.txt` and remove it
from `pyproject.toml` dependencies entirely.

---

### IN-02: Deferred `CURRENT_SEASON` import inside three functions gives a false impression of dynamic re-evaluation

**File:** `src/mlb_park/services/mlb_api.py:115,169,194`
**Issue:** All three dispatcher functions re-import `CURRENT_SEASON` from
`mlb_park.config` on every call with `from mlb_park.config import CURRENT_SEASON`.
Since `CURRENT_SEASON` is a module-level constant set once at import time, this
import returns the same frozen value every time. The deferred import pattern is
typically used to avoid circular imports or to defer evaluation, neither of which
applies here. It gives the misleading impression the value is re-evaluated per call.

**Fix:** Move the import to the module top-level alongside the other config imports:
```python
from mlb_park.config import (
    ...
    CURRENT_SEASON,  # add here
)
```
Then remove the three inline `from mlb_park.config import CURRENT_SEASON` lines.

---

### IN-03: Check 4 in `test_historical_roster.py` is a duplicate of Check 1 with no new coverage

**File:** `scripts/test_historical_roster.py:69-75`
**Issue:** Check 4 makes an identical HTTP request (same URL and identical `params`
dict) to Check 1. The intent noted in the comment is to verify that the explicit
`season` query param is accepted, but Check 1 already sends `season=SEASON` in its
params and calls `raise_for_status()`. Check 4 only adds a redundant network round-trip.

**Fix:** Remove the duplicate request and strengthen Check 1's comment to note
that the `season` param is included and accepted:
```python
# Check 1 verifies the season param is accepted — resp.raise_for_status() already
# confirms status 200. No separate check needed.
```

---

### IN-04: Commented-out / dead validation code note in `test_historical_roster.py`

**File:** `scripts/test_historical_roster.py:56-66`
**Issue:** The fallback branch starting at line 56 (`if not found_hr`) prints
a `FAIL` message and calls `sys.exit(1)`, but the preceding loop at line 57
actually sets `found_hr = True` if *any* entry has a `stats` key (even if `homeRuns`
is 0 or absent), and then `breaks`. If that inner loop also finds nothing, the
`sys.exit(1)` path is reached, but the intermediate print (`print(f"  Stats
structure sample: ...")`) before setting `found_hr = True` means the exit only
fires in the truly empty case. The logic is correct but the two-level fallback is
harder to read than necessary. Low priority for a one-shot diagnostic script.

---

_Reviewed: 2026-04-16T00:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
