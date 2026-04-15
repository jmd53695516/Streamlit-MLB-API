---
phase: 03-hr-pipeline
reviewed: 2026-04-15T00:00:00Z
depth: standard
files_reviewed: 11
files_reviewed_list:
  - src/mlb_park/config.py
  - src/mlb_park/pipeline/__init__.py
  - src/mlb_park/pipeline/events.py
  - src/mlb_park/pipeline/extract.py
  - tests/pipeline/conftest.py
  - tests/pipeline/test_events.py
  - tests/pipeline/test_extract_hrs.py
  - tests/pipeline/test_degradation.py
  - tests/pipeline/test_error_handling.py
  - tests/pipeline/test_adapter.py
  - tests/pipeline/test_integration.py
findings:
  critical: 0
  warning: 2
  info: 4
  total: 6
status: issues_found
---

# Phase 3: Code Review Report

**Reviewed:** 2026-04-15
**Depth:** standard
**Files Reviewed:** 11
**Status:** issues_found

## Summary

Phase 3 delivers a well-structured HR extraction pipeline with clean dependency injection, frozen dataclasses, and thorough test coverage (happy path, degradation flags, error handling, adapter contract, end-to-end integration). The implementation faithfully follows the locked CONTEXT decisions (D-05..D-18) and PITFALLS guidance.

No security issues, no hardcoded secrets, no dangerous functions. The code is idiomatic Python with appropriate `.get()` guards on untrusted JSON. Coverage for DATA-01/02/05 and error propagation paths is strong.

Two Warning-level issues relate to brittle dictionary access on gameLog rows after the filter step — a malformed row that passed the `stat.homeRuns >= 1` filter will crash the entire pipeline rather than being skipped. Four Info-level items concern code organization (mid-module import) and defensive-coding opportunities.

## Warnings

### WR-01: Unguarded key access on gameLog rows can crash the entire pipeline

**File:** `src/mlb_park/pipeline/extract.py:58-60`
**Issue:** The filter at line 52 uses defensive `.get()` chains (`r.get("stat", {}).get("homeRuns", 0)`), but once a row passes, lines 58-60 switch to bracket-subscription:
```python
game_pk = int(row["game"]["gamePk"])
expected = int(row["stat"]["homeRuns"])
batter_team_id = int(row["team"]["id"])
```
If any real gameLog row has `homeRuns >= 1` but is missing `game.gamePk` or `team.id` (malformed response, API schema drift, partial hydrate), a `KeyError` or `TypeError` escapes the per-game `try/except api.MLBAPIError` — it's raised outside the except clause — and aborts the whole extraction. This violates the D-14 spirit of "per-feed failures are collected, not fatal."

**Fix:** Wrap the row-unpacking in a try/except that records a `PipelineError` and continues, or use `.get()` with explicit validation:
```python
for row in hr_rows:
    try:
        game_pk = int(row["game"]["gamePk"])
        expected = int(row["stat"]["homeRuns"])
        batter_team_id = int(row["team"]["id"])
    except (KeyError, TypeError, ValueError) as exc:
        errors.append(PipelineError(
            game_pk=None, endpoint="game_log",
            message=f"malformed gameLog row: {exc}",
        ))
        continue
    try:
        feed = api.get_game_feed(game_pk)
    except api.MLBAPIError as exc:
        ...
```

### WR-02: Unguarded feed-shape access in `_walk_feed_for_hrs` / `_opponent_abbr` can crash extraction

**File:** `src/mlb_park/pipeline/extract.py:106-109`
**Issue:** `_walk_feed_for_hrs` unconditionally reads `feed["gamePk"]` and `feed["gameData"]["datetime"]["officialDate"]`. A feed whose shape is partially missing (e.g., postponed games with truncated `gameData`, or a future MLB API change) raises `KeyError` synchronously inside the for-loop — bypassing the MLBAPIError catch at line 63 and aborting the whole extract.

`datetime.date.fromisoformat(...)` at line 107 will also raise `ValueError` if `officialDate` is malformed, with the same impact.

**Fix:** Either (a) let `_walk_feed_for_hrs` raise a specific `PipelineFeedShapeError` that the caller catches alongside `api.MLBAPIError` and records as a `PipelineError`, or (b) guard the accesses and record an error:
```python
try:
    matched = _walk_feed_for_hrs(feed, player_id, batter_team_id)
except (KeyError, ValueError, TypeError) as exc:
    errors.append(PipelineError(
        game_pk=game_pk, endpoint="game_feed",
        message=f"malformed feed: {exc}",
    ))
    continue
```
This parallels the defensive style already used elsewhere (lines 112, 115, 118, 123).

## Info

### IN-01: Mid-module `import` inside `extract.py` violates PEP 8

**File:** `src/mlb_park/pipeline/extract.py:207`
**Issue:** `from mlb_park.geometry.verdict import HitData` sits between comment blocks near the bottom of the file, not with the other top-of-module imports (lines 8-13). PEP 8 requires module imports at the top. There is no circular-import justification here (the package already re-exports `HitData` via `pipeline/__init__.py` without issue).

**Fix:** Move the import to the top with the others:
```python
# top of file
from mlb_park.geometry.verdict import HitData
from mlb_park.pipeline.events import HREvent, PipelineError, PipelineResult
from mlb_park.services import mlb_api as _default_api
```
Then delete line 207.

### IN-02: `_extract_hit_data` inspects `events[-1]` twice on the fallback path

**File:** `src/mlb_park/pipeline/extract.py:167-173`
**Issue:** When the terminal playEvent carries `hitData`, it's returned on line 169. When it doesn't, the reversed loop at line 170 starts from `events[-1]` again — re-checking a slot just proven absent. Minor, but the intent (D-10: "prefer terminal; fall back to last-with-hitData") reads more clearly as:
```python
if isinstance(last.get("hitData"), dict):
    return last["hitData"]
for e in reversed(events[:-1]):
    if isinstance(e.get("hitData"), dict):
        return e["hitData"]
return None
```

**Fix:** Slice `events[:-1]` in the fallback loop, or simply iterate `reversed(events)` once without the special-case (the two branches collapse into a single reverse scan).

### IN-03: `int(about.get("inning", 0))` silently substitutes 0 for missing inning

**File:** `src/mlb_park/pipeline/extract.py:142`
**Issue:** Inning `0` is not a real baseball value; using it as a default masks upstream data problems. A home run without an `about.inning` key is anomalous enough to deserve a log warning or a degradation flag, not a silent zero.

**Fix:** Either log a warning when the field is missing, or use `None` plus make `inning` optional in `HREvent`. Low priority — in practice MLB feeds always carry `inning` for HR plays.

### IN-04: `api: Any` type hint discards a usable structural contract

**File:** `src/mlb_park/pipeline/extract.py:22`
**Issue:** `extract_hrs(..., *, api: Any = _default_api)` is permissive by design (dependency injection), but `Any` disables type checking entirely — including the `api.MLBAPIError` / `api.get_game_log` / `api.get_game_feed` references the function actually relies on. A `typing.Protocol` would document the contract and still accept both the real module and the `StubAPI`.

**Fix:** Optional refinement — define a Protocol near the top of `extract.py`:
```python
from typing import Protocol

class _APIModule(Protocol):
    MLBAPIError: type[Exception]
    def get_game_log(self, person_id: int, season: int) -> list[dict]: ...
    def get_game_feed(self, game_pk: int) -> dict: ...
```
Then annotate `api: _APIModule = _default_api`. Pure documentation/type-safety improvement; no runtime change.

---

_Reviewed: 2026-04-15_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
