---
phase: 04-controller-selectors-ui
reviewed: 2026-04-15T00:00:00Z
depth: standard
files_reviewed: 11
files_reviewed_list:
  - src/mlb_park/app.py
  - src/mlb_park/controller.py
  - src/mlb_park/pipeline/__init__.py
  - src/mlb_park/services/mlb_api.py
  - tests/controller/conftest.py
  - tests/controller/test_build_view.py
  - tests/controller/test_callbacks.py
  - tests/controller/test_helpers.py
  - tests/controller/test_purity.py
  - tests/controller/test_view_model.py
  - tests/services/test_team_hitting_stats.py
findings:
  critical: 0
  warning: 3
  info: 4
  total: 7
status: issues_found
---

# Phase 4: Code Review Report

**Reviewed:** 2026-04-15
**Depth:** standard
**Files Reviewed:** 11
**Status:** issues_found

## Summary

Phase 4 (controller + selectors UI) is in good shape overall. The controller/app split enforced by D-23 is clean, purity guards (`tests/controller/test_purity.py`) are enforced at both source and namespace level, and the injectable `api=` parameter in `build_view` keeps the composition testable without monkeypatching `requests`. SSRF-style `isinstance` guards on raw helpers and the atomic-write venue cache are conscientious.

Three warnings stand out: two are unguarded `next(...)` generator lookups inside `build_view` that turn a stale-or-bogus ID into an opaque `RuntimeError` (PEP 479), and one is an asymmetric redundancy in defensive extraction. None are security or correctness issues in the happy path — they are robustness gaps against malformed/stale inputs. A handful of minor info items round out the report.

Tests are comprehensive: happy path, zero-HR, missing hitData, feed-failure isolation, stadium flip, totals arithmetic, selection fields, callback monkeypatching, and purity are all covered. No issues found in test files.

## Warnings

### WR-01: `build_view` raises opaque `RuntimeError` on unknown `team_id` / `player_id`

**File:** `src/mlb_park/controller.py:289` and `src/mlb_park/controller.py:294`
**Issue:** Both `next(t for t in teams if t["id"] == team_id)` and `next(e for e in roster if e["person"]["id"] == player_id)` use `next()` on a generator without a default. When the id is not found (stale `session_state` after a roster change, a fixture mismatch, or a URL-state bind feeding a deleted player), Python 3.7+ converts the resulting `StopIteration` into a `RuntimeError: generator raised StopIteration` (PEP 479). Callers get no actionable context — not the id that was missing, not which lookup failed.

The UI hits this if a user's session_state retains a player_id whose roster entry rotated off the 40-man between reruns; the exception bubbles into Streamlit's red box with no useful message.

**Fix:**
```python
team = next((t for t in teams if t["id"] == team_id), None)
if team is None:
    raise ValueError(f"team_id {team_id} not found in get_teams() response")
team_abbr = team.get("abbreviation", "") or ""
player_home_venue_id = int(team.get("venue", {}).get("id", 0) or 0)

roster = api.get_team_hitting_stats(team_id, season)
player_entry = next(
    (e for e in roster if e["person"]["id"] == player_id), None
)
if player_entry is None:
    raise ValueError(
        f"player_id {player_id} not found in roster for team {team_id}"
    )
```

Alternatively, catch at the app.py boundary and surface a "Selection expired — pick again" banner; either way, surface a real message.

### WR-02: `_hr_of` will crash on malformed `person.stats` that is not a list

**File:** `src/mlb_park/controller.py:156-166`
**Issue:** `stats = entry.get("person", {}).get("stats") or []` correctly normalizes None/missing/empty to `[]`. But the subsequent `stats[0].get("splits") or []` presumes `stats[0]` is a dict. If the hydrated response ever returns `stats` as a non-list (e.g., a dict from an error response, or a scalar) or if `stats[0]` is not a dict, `.get(...)` raises `AttributeError`. The try/except at the end only covers `homeRuns` coercion, not structural access.

Given this is consumed during selectbox rendering, a single malformed roster entry takes down the whole Player dropdown.

**Fix:** Guard each layer, or wrap the whole extraction:
```python
def _hr_of(entry: dict) -> int:
    try:
        stats = entry.get("person", {}).get("stats") or []
        if not stats or not isinstance(stats[0], dict):
            return 0
        splits = stats[0].get("splits") or []
        if not splits or not isinstance(splits[0], dict):
            return 0
        raw = splits[0].get("stat", {}).get("homeRuns", 0)
        return int(raw or 0)
    except (TypeError, ValueError, AttributeError):
        return 0
```

### WR-03: `build_view` `player_home_venue_id` silently defaults to 0 on malformed team payload

**File:** `src/mlb_park/controller.py:291`
**Issue:** `int(team.get("venue", {}).get("id", 0) or 0)` returns `0` when the team dict lacks `venue.id`. Downstream, `player_home_venue_id=0` looks like a legitimate venue identifier in the ViewModel/JSON dump but is semantically "unknown." Callers (Phase 5 chart) will have no way to distinguish "home venue genuinely missing" from "venue id 0."

**Fix:** Make absence explicit — either make the field `int | None` and default to `None`, or raise when the real StatsAPI payload is malformed (teams always have a venue):
```python
venue_blob = team.get("venue") or {}
if "id" not in venue_blob:
    raise ValueError(f"team {team_id} response missing venue.id")
player_home_venue_id = int(venue_blob["id"])
```

This also lets you drop the second `or 0` which is dead code once the `.get("id", 0)` default fires.

## Info

### IN-01: `# noqa: F811` on rebinding `api` parameter inside `build_view`

**File:** `src/mlb_park/controller.py:283`
**Issue:** `from mlb_park.services import mlb_api as api  # noqa: F811` rebinds the function parameter named `api`. It works, but reusing the parameter name for the fallback import reads ambiguously. A reader has to pause to confirm there's no shadowing bug.
**Fix:** Rename the local to `api_module`, or — simpler — bind to a distinct name and reassign: `from mlb_park.services import mlb_api; api = mlb_api`. Purely a readability nudge; no behavioral change.

### IN-02: `field` re-export comment references an unimplemented follow-up

**File:** `src/mlb_park/controller.py:344-351`
**Issue:** `__all__` includes `"field"` with the comment "re-exported for downstream helpers in Plan 04-02 (pre-empts an import churn commit)." Plan 04-02 appears complete in this phase. If no helper actually consumes `controller.field`, the re-export is dead surface area.
**Fix:** If no consumer exists, drop `"field"` from `__all__` and the `field` import. If something does use it, update the comment to name the consumer so future reviewers don't re-raise this.

### IN-03: `_on_player_change` re-fetches teams list on every player change

**File:** `src/mlb_park/app.py:47`
**Issue:** `teams = get_teams()` is called inside the callback to look up the selected team's home venue. `get_teams` is `@st.cache_data`'d so this is not a network hit, but the O(30) linear `next(...)` scan runs on every player selection. The team is already available in-scope at the time the player selectbox is rendered (same script pass sorts the teams).
**Fix:** Either store the selected team dict in `session_state` when team changes, or accept this as cheap and inline a comment noting the cache hit. Not a correctness issue; flag for Phase 6 polish.

### IN-04: Tests import private `ControllerStubAPI` inside the test body

**File:** `tests/controller/test_build_view.py:258`
**Issue:** `from tests.controller.conftest import ControllerStubAPI` is done inside `test_one_feed_fails` rather than at module top. Works, but the factory fixture `make_controller_stub_api` exists precisely to avoid this; the test could accept the fixture and call it with `feed_errors=...` like every other test in this file.
**Fix:** Use `make_controller_stub_api(feed_errors={bad_game_pk: ...})` to keep construction uniform. The `MLBAPIError` class attribute is still accessible via the stub instance or via `mlb_park.pipeline.MLBAPIError`.

---

_Reviewed: 2026-04-15_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
