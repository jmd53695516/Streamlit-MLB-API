---
phase: 03
plan: 01
subsystem: pipeline
tags: [scaffold, dataclasses, fixtures, tdd]
requires:
  - src/mlb_park/config.py (existing, appended)
  - src/mlb_park/geometry/verdict.py::HitData (D-02 contract consumed by Plan 03)
  - tests/fixtures/feed_*.json + gamelog_592450_2026.json (for judge_feeds/judge_gamelog loaders)
provides:
  - mlb_park.config.CURRENT_SEASON = 2026 (D-16)
  - mlb_park.pipeline package with HREvent, PipelineResult, PipelineError frozen dataclasses (D-05, D-13, D-18)
  - 6 synthetic feed fixtures + 1 synthetic gameLog (D-19 degradation coverage)
  - StubAPI class + make_stub_api factory fixture (D-17 dependency injection)
  - synthetic_feed / synthetic_gamelog / judge_feeds / judge_gamelog pytest fixtures
affects:
  - Plan 03-02 (consumes HREvent contract + StubAPI + synthetic fixtures)
  - Plan 03-03 (consumes judge_feeds / judge_gamelog for happy-path integration)
tech-stack:
  added: []
  patterns:
    - Frozen dataclasses with PEP 604 Optional types (float | None)
    - Class-attribute stub exception (StubAPI.MLBAPIError) for `except api.MLBAPIError:` pattern
    - Session-scoped fixture loaders keyed off Path(__file__).parent constants (T-3-05 path-traversal guard)
key-files:
  created:
    - src/mlb_park/pipeline/__init__.py
    - src/mlb_park/pipeline/events.py
    - tests/pipeline/__init__.py
    - tests/pipeline/test_events.py
    - tests/pipeline/conftest.py
    - tests/pipeline/fixtures/feed_missing_hitdata.json
    - tests/pipeline/fixtures/feed_itp.json
    - tests/pipeline/fixtures/feed_partial_hitdata.json
    - tests/pipeline/fixtures/feed_non_batter_hr.json
    - tests/pipeline/fixtures/feed_terminal_lacks_hitdata.json
    - tests/pipeline/fixtures/feed_count_mismatch.json
    - tests/pipeline/fixtures/gamelog_count_mismatch.json
  modified:
    - src/mlb_park/config.py (appended CURRENT_SEASON = 2026)
decisions:
  - "Kept events.py pure data (no to_hit_data method) — adapter lives in Plan 03 per D-06 Claude-discretion"
  - "StubAPI.MLBAPIError written as plain class attribute (no annotation) so the acceptance-criterion grep pattern matches literally; also avoids import cycles"
metrics:
  duration_sec: 294
  tasks_complete: 3
  files_created: 12
  files_modified: 1
  tests_passing: 6
  completed: "2026-04-15"
---

# Phase 03 Plan 01: Scaffold — Dataclasses, Fixtures, Stub API (Summary)

Landed the Phase 3 data contracts (`HREvent`, `PipelineResult`, `PipelineError` as frozen dataclasses), the `mlb_park.pipeline` package skeleton, `CURRENT_SEASON = 2026`, six synthetic JSON fixtures covering every D-19 degradation path, and a `StubAPI` + pytest fixture surface so Plans 03-02/03-03 can test extraction purely from fixtures.

## What shipped

### Dataclasses (D-05, D-13) — `src/mlb_park/pipeline/events.py`

```python
@dataclass(frozen=True)
class HREvent:                 # 15 fields: 6 identity, 5 measurements (Optional), 4 flags
    game_pk: int; game_date: datetime.date; opponent_abbr: str
    inning: int; half_inning: str; play_idx: int
    distance_ft: float | None; coord_x: float | None; coord_y: float | None
    launch_speed: float | None; launch_angle: float | None
    has_distance: bool; has_coords: bool; has_launch_stats: bool; is_itp: bool

@dataclass(frozen=True)
class PipelineError:
    game_pk: int | None; endpoint: str; message: str

@dataclass(frozen=True)
class PipelineResult:
    events: tuple[HREvent, ...]; errors: tuple[PipelineError, ...]
    season: int; player_id: int
```

Pure data — no parsing, no logging, no `requests` / `streamlit` imports (D-01 preserved).

### Config (D-16)

Appended to `src/mlb_park/config.py`:
```python
# Current season — Phase 3 entry point default (D-16).
CURRENT_SEASON = 2026
```

### Synthetic fixture inventory (D-19)

| Fixture | gamePk | Purpose |
|---------|--------|---------|
| `feed_missing_hitdata.json` | 900001 | HR play with no `hitData` on any playEvent → all flags False, event still emitted |
| `feed_itp.json` | 900002 | `result.description` contains literal `"inside-the-park"` → `is_itp=True`, hitData also populated |
| `feed_partial_hitdata.json` | 900003 | `totalDistance=410.0` present, `coordinates.coordX/Y=null` → `has_distance=True, has_coords=False` |
| `feed_non_batter_hr.json` | 900004 | HR by batter id `999999` (not Judge) → D-08 batter filter must exclude |
| `feed_terminal_lacks_hitdata.json` | 900005 | Terminal `playEvents[-1]` has no `hitData`; earlier event carries it → D-10 fallback |
| `feed_count_mismatch.json` | 900006 | 1 Judge HR play in feed |
| `gamelog_count_mismatch.json` | 900006, 900007 | gameLog row claims `homeRuns=2` for 900006 → D-09 warning, still emit 1 event |

All seven files are valid JSON minimum-viable subsets of the real feed/gameLog shapes verified in Phase 1.

### StubAPI contract (D-17) — `tests/pipeline/conftest.py`

Plan 02/03 depend on this exact surface:

```python
class StubAPI:
    MLBAPIError = type("StubMLBAPIError", (RuntimeError,), {})  # class attribute — Pitfall 6
    def __init__(self, *, game_log=None, feeds=None, feed_errors=None, parks=None): ...
    def get_game_log(person_id: int, season: int) -> list[dict]
    def get_game_feed(game_pk: int) -> dict      # raises MLBAPIError if game_pk in feed_errors
    def load_all_parks() -> dict[int, dict]
```

Plus pytest fixtures: `make_stub_api` (factory, function-scoped), `synthetic_feed(name)`, `synthetic_gamelog(name)`, `judge_feeds`, `judge_gamelog`.

Zero imports of `mlb_park.services.mlb_api` — extraction code in Plan 02 will accept an `api=` kwarg defaulting to the real module, and tests pass a `StubAPI` instance instead.

## Tasks executed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 (RED)   | Failing contract tests                         | `586a99e` | tests/pipeline/__init__.py, tests/pipeline/test_events.py |
| 1 (GREEN) | Dataclasses + CURRENT_SEASON                   | `00c9fda` | src/mlb_park/config.py, src/mlb_park/pipeline/{__init__,events}.py |
| 2         | 6 synthetic feeds + 1 count-mismatch gameLog   | `cffd9c4` | tests/pipeline/fixtures/*.json (7 files) |
| 3         | StubAPI + loaders in tests/pipeline/conftest.py | `e9a65b4` | tests/pipeline/conftest.py |

Final verification:
- `pytest tests/pipeline/ -q` → **6 passed**
- `python -c "from mlb_park.pipeline import HREvent, PipelineResult, PipelineError; from mlb_park.config import CURRENT_SEASON; assert CURRENT_SEASON == 2026"` → **OK**
- `grep -rn "import requests" src/mlb_park/pipeline/ tests/pipeline/` → **zero matches**
- `grep -rn "import streamlit" src/mlb_park/pipeline/ tests/pipeline/` → **zero matches**

## Deviations from Plan

**None — plan executed exactly as written.**

One environmental note (not a plan deviation): the worktree's editable install was initially pointing at the main repo's `src/mlb_park`, so `from mlb_park.pipeline import ...` failed until `pip install -e . --no-deps` was re-run in the worktree. This is a worktree-tooling concern, not a plan defect; no code change was required.

## Threat Flags

None. Plan stayed within the modelled threat register (T-3-01, T-3-03, T-3-04, T-3-05 all accept/mitigate per plan). No new network endpoints, no trust-boundary changes.

## Known Stubs

None. The three dataclasses are complete data contracts consumed by Plan 02 — they are not UI placeholders.

## What Plan 02 / Plan 03 can assume

- `from mlb_park.pipeline import HREvent, PipelineResult, PipelineError` works.
- `from mlb_park.config import CURRENT_SEASON` returns `2026`.
- A pytest test file under `tests/pipeline/` can request `make_stub_api`, `synthetic_feed`, `synthetic_gamelog`, `judge_feeds`, `judge_gamelog` as fixtures.
- StubAPI's four attributes are named identically to the real module, so production code writing `api.get_game_feed(...)` / `except api.MLBAPIError:` works against both.
- The six synthetic feed fixtures + one gameLog mismatch fixture exist on disk under `tests/pipeline/fixtures/` and are valid JSON.

## Self-Check: PASSED

- [x] `src/mlb_park/config.py` — contains `CURRENT_SEASON = 2026`
- [x] `src/mlb_park/pipeline/__init__.py` — re-exports 3 names
- [x] `src/mlb_park/pipeline/events.py` — 3 frozen dataclasses, all 15 HREvent fields
- [x] `tests/pipeline/__init__.py` — package marker
- [x] `tests/pipeline/test_events.py` — 6 tests, 6/6 passing
- [x] `tests/pipeline/conftest.py` — StubAPI + 5 fixtures, no `mlb_park.services.mlb_api` import
- [x] 7 fixture JSON files present under `tests/pipeline/fixtures/`
- [x] Commits 586a99e, 00c9fda, cffd9c4, e9a65b4 all exist in git log
