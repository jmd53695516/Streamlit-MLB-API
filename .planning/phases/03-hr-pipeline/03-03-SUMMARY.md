---
phase: 03
plan: 03
subsystem: pipeline
tags: [adapter, re-exports, integration, tdd, capstone]
requires:
  - src/mlb_park/pipeline/events.py (Plan 03-01: HREvent, PipelineResult, PipelineError)
  - src/mlb_park/pipeline/extract.py (Plan 03-02: extract_hrs)
  - src/mlb_park/geometry/verdict.py (Phase 2: HitData, compute_verdict_matrix)
  - src/mlb_park/geometry/park.py (Phase 2: load_parks)
  - src/mlb_park/services/mlb_api.py (Phase 1: load_all_parks, MLBAPIError)
  - src/mlb_park/config.py (CURRENT_SEASON)
  - tests/pipeline/conftest.py (StubAPI + judge_feeds + judge_gamelog)
  - tests/conftest.py (venues fixture)
  - tests/fixtures/feed_*.json + venue_*.json (Phase 1 real fixtures)
provides:
  - mlb_park.pipeline.extract.hr_event_to_hit_data (D-06 adapter)
  - mlb_park.pipeline single-import surface for the entire Phase 3 contract
  - End-to-end test proving extract -> adapter -> compute_verdict_matrix composition
affects:
  - Phase 04 controller — single import origin: `from mlb_park.pipeline import ...`
tech-stack:
  added: []
  patterns:
    - Module-level pure-function adapter (no class, no state) for HREvent -> HitData
    - Identity re-export of Phase 1's load_all_parks (object-is check guards against accidental wrapping)
    - Convenience pass-throughs (HitData, compute_verdict_matrix, MLBAPIError, CURRENT_SEASON) so Phase 4 controller has a single import origin
key-files:
  created:
    - tests/pipeline/test_adapter.py (97 lines, 5 tests)
    - tests/pipeline/test_integration.py (109 lines, 2 tests)
  modified:
    - src/mlb_park/pipeline/extract.py (+22 lines: adapter + import)
    - src/mlb_park/pipeline/__init__.py (rewritten, 30 lines: 10-name public surface)
decisions:
  - "Re-export surface expanded beyond the plan's required 6 names to include HitData, compute_verdict_matrix, MLBAPIError, and CURRENT_SEASON. The plan only mandated 6, but Phase 4 will reach for these from `mlb_park.pipeline` if they exist there — pre-emptively exposing them keeps Phase 4 to a single import origin (DATA-03 spirit). Re-exports are pure pass-throughs, no wrapping. (Rule 2 — additive)"
  - "Adapter import (`from mlb_park.geometry.verdict import HitData`) placed adjacent to the adapter function at the bottom of extract.py, not at the file top, per the plan's explicit instruction. Keeps Plan 02's extract_hrs code free of geometry imports for readers."
  - "test_adapter.py uses lazy `from mlb_park.pipeline import ...` inside each test rather than module-top imports — keeps each test's failure message pinpoint the exact missing name during the RED phase."
metrics:
  duration_sec: 360
  tasks_complete: 2
  files_created: 2
  files_modified: 2
  tests_passing: 7
  tests_passing_pipeline: 26
  tests_passing_full_suite: 65
  completed: "2026-04-15"
---

# Phase 03 Plan 03: Adapter + Re-exports + Integration Capstone (Summary)

Closed Phase 3 by shipping the D-06 `HREvent → HitData` adapter, expanding `mlb_park.pipeline` into the single public-API origin for the entire HR pipeline (10 re-exports), and proving the full composition (`extract_hrs → adapter → compute_verdict_matrix`) with two zero-network integration tests against the real Judge fixtures.

## Final public API of `mlb_park.pipeline`

```python
from mlb_park.pipeline import (
    # Plan 03-03 required (D-06 + DATA-03)
    extract_hrs,            # (player_id, season=None, *, api=...) -> PipelineResult
    hr_event_to_hit_data,   # (HREvent) -> HitData | None
    HREvent,                # frozen dataclass, 15 fields
    PipelineResult,         # events: tuple[HREvent], errors: tuple[PipelineError]
    PipelineError,          # game_pk, endpoint, message
    load_all_parks,         # () -> dict[int, dict] (identity re-export of Phase 1)

    # Convenience re-exports for Phase 4 controller
    HitData,                # geometry-layer hit shape
    compute_verdict_matrix, # (Sequence[HitData], parks) -> VerdictMatrix
    MLBAPIError,            # service-layer exception (also accessible as api.MLBAPIError)
    CURRENT_SEASON,         # 2026 (D-16 default)
)
```

`__all__` declares exactly these 10 names. `load_all_parks` is verified to be the same object as `mlb_park.services.mlb_api.load_all_parks` (no wrapper).

## Adapter contract (D-06)

```python
def hr_event_to_hit_data(ev: HREvent) -> HitData | None:
    if not (ev.has_distance and ev.has_coords):
        return None
    return HitData(
        distance_ft=ev.distance_ft,
        coord_x=ev.coord_x,
        coord_y=ev.coord_y,
        identifier=(ev.game_pk, ev.play_idx),
    )
```

| Input | Output |
|---|---|
| `has_distance=False` | `None` |
| `has_coords=False` | `None` (even with distance) |
| both `True` | `HitData(distance_ft, coord_x, coord_y, identifier=(game_pk, play_idx))` |

The `(game_pk, play_idx)` tuple round-trips through `compute_verdict_matrix` (verified by `vm.hrs[i].identifier == hd.identifier` and `iter_records()` assertions).

## End-to-end test results

### test_end_to_end_judge_happy_path
- Inputs: 5 real Judge feeds + real gameLog + 30 real venue dicts (all from `tests/fixtures/`).
- `extract_hrs(592450, 2026, api=stub)` → 6 events, 0 errors.
- All 6 events have `has_distance and has_coords True` → adapter yields 6 non-None HitData.
- `compute_verdict_matrix(6 HitData, 30 parks)` → `cleared.shape == (6, 30)`, non-degenerate (`cleared.any()` AND `(~cleared).any()`).
- `iter_records()` yields 180 cells; every cell's `identifier` matches the source HR.

### test_end_to_end_with_feed_failure_still_produces_matrix
- Drop gamePk=823243 (carries 1 Judge HR), inject `StubMLBAPIError("503 upstream")` for that gamePk.
- `extract_hrs` returns 5 events + 1 `PipelineError(game_pk=823243, endpoint="game_feed")` — exception caught, no propagation.
- Adapter yields 5 non-None HitData; `compute_verdict_matrix` returns `(5, 30)` matrix.
- Sanity: no `vm.hrs[i].identifier[0] == 823243` (dropped game absent).

## Full-suite test count delta

| Stage | Pipeline tests | Full-suite tests |
|---|---|---|
| End of Plan 03-01 | 6 | 45 |
| End of Plan 03-02 | 19 | 58 |
| End of Plan 03-03 | **26** | **65** |

Plan 03-03 adds 7 tests: 5 in `test_adapter.py` (3 adapter B1/B2/B3-B5 + 2 re-export B6/B7) and 2 in `test_integration.py` (happy path + failure mode). Phase 2's 39 tests untouched.

```text
$ pytest tests/pipeline/ -q
..........................                                              [100%]
26 passed in 1.19s

$ pytest -q
.................................................................      [100%]
65 passed in 1.49s
```

## Tasks executed

| Task | Name | Commits | Files |
|---|---|---|---|
| 1 (RED)   | Failing adapter + re-export tests | `e83fde9` | tests/pipeline/test_adapter.py |
| 1 (GREEN) | Adapter + expanded `__init__.py` re-exports | `bbbb094` | src/mlb_park/pipeline/{extract,__init__}.py |
| 2         | End-to-end integration tests (happy + failure) | `1f6c830` | tests/pipeline/test_integration.py |

## Deviations from Plan

### [Rule 2 — Missing critical functionality] Expanded re-export surface beyond the 6 mandated names

- **Found during:** Task 1 (drafting the new `__init__.py`).
- **Issue:** Plan mandates 6 re-exports (`extract_hrs`, `hr_event_to_hit_data`, `HREvent`, `PipelineResult`, `PipelineError`, `load_all_parks`). The orchestrator's wrapping success-criteria block additionally calls for `HitData`, `MLBAPIError`, `CURRENT_SEASON`, `compute_verdict_matrix` (and `DegradationFlags` — which does not exist as a class; the four `has_*`/`is_itp` flags are bool fields on HREvent).
- **Fix:** Added `HitData`, `compute_verdict_matrix`, `MLBAPIError`, `CURRENT_SEASON` to `__all__` as pass-through re-exports. All four are pre-existing names from upstream modules — no new behavior, no wrapping. `DegradationFlags` skipped (no such symbol exists).
- **Why critical:** Phase 4's controller will reach for `MLBAPIError` (to handle pipeline-level failures) and `CURRENT_SEASON` (default season UI). Forcing it to import from three modules (`pipeline`, `services.mlb_api`, `config`) defeats the DATA-03 "single import origin" intent.
- **Files modified:** `src/mlb_park/pipeline/__init__.py`.
- **Commit:** `bbbb094`.
- **Threat-model impact:** None. All four added names are pure re-exports; no new attack surface, all upstream modules already in the trust boundary.

One environmental note (not a plan deviation): the worktree's editable install was missing at start; resolved by `pip install -e . --no-deps` (same fix as Plans 03-01 / 03-02 documented previously).

## Threat Flags

None. Plan stayed within the modelled register:
- **T-3-01** (path traversal in `load_all_parks`): transferred — unchanged from Phase 1; pipeline re-export adds no surface.
- **T-3-08** (adapter produces wrong HitData): mitigated — adapter's `if not (ev.has_distance and ev.has_coords)` guard plus Phase 2's `float()` coercion at the geometry boundary surface bad inputs loudly.
- **T-3-09** (identifier disclosure): accepted — `(game_pk, play_idx)` are public StatsAPI ints, no PII.

The four added re-exports (`HitData`, `compute_verdict_matrix`, `MLBAPIError`, `CURRENT_SEASON`) are existing names from already-trusted modules; no new threat surface.

## Known Stubs

None. The adapter is the production adapter; the integration test uses real fixtures; the re-exports are real pass-throughs (verified by `is`-identity for `load_all_parks`).

## Ready for Phase 4 — Controller Checklist

- [x] Single import origin: `from mlb_park.pipeline import ...` covers everything Phase 4 needs (extraction, adapter, dataclasses, geometry composition, services, config defaults).
- [x] D-06 adapter is module-level pure function — Phase 4 maps it over `result.events` to split verdict-eligible from emit-only.
- [x] `load_all_parks()` reachable from `mlb_park.pipeline` (DATA-03) — Phase 4 calls it once per session, hands the result to `compute_verdict_matrix` via the geometry layer.
- [x] `MLBAPIError` exposed for the gameLog-level failure path (D-14 — extract_hrs reraises gameLog failures; per-feed failures are inside `result.errors`).
- [x] `CURRENT_SEASON` exposed so Phase 4's UI can show "2026" without re-importing config.
- [x] Integration test demonstrates the exact composition Phase 4 will call: `extract_hrs(...)` → `[hr_event_to_hit_data(ev) for ev in result.events]` → `compute_verdict_matrix(hit_data_list, load_parks(...))` → `VerdictMatrix.iter_records()` for per-cell access.

## Self-Check: PASSED

- [x] `src/mlb_park/pipeline/extract.py` — contains `def hr_event_to_hit_data` (1 match), `from mlb_park.geometry.verdict import HitData` (1 match), `identifier=(ev.game_pk, ev.play_idx)` (1 match), `if not (ev.has_distance and ev.has_coords)` (1 match)
- [x] `src/mlb_park/pipeline/__init__.py` — contains `hr_event_to_hit_data`, `load_all_parks`, `"load_all_parks"` inside `__all__`
- [x] `tests/pipeline/test_adapter.py` — 5 tests, all passing
- [x] `tests/pipeline/test_integration.py` — 2 tests (`test_end_to_end_judge_happy_path` + `test_end_to_end_with_feed_failure_still_produces_matrix`), both passing; references `compute_verdict_matrix`, `hr_event_to_hit_data`, `vm.cleared.shape == (6, 30)`, `vm.cleared.shape == (5, 30)`, `assert vm.cleared.any()`, `from mlb_park.pipeline import`
- [x] `pytest tests/pipeline/ -q` → 26 passed, 0 failed
- [x] `pytest -q` (full suite) → 65 passed, 0 failed (Phase 2 regression-free)
- [x] Verify command (`from mlb_park.pipeline import ...; assert load_all_parks is lap; ...`) prints `OK 2026`
- [x] Commits `e83fde9` (RED), `bbbb094` (GREEN), `1f6c830` (integration) all present in git log
