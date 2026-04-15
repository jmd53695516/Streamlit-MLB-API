---
phase: 02-models-geometry
plan: 03
subsystem: geometry
tags: [geometry, verdict, matrix, vectorized, integration, phase-capstone]
requires:
  - 02-01-SUMMARY  # calibration constants
  - 02-02-SUMMARY  # transform + Park model
provides:
  - compute_verdict_matrix       # vectorized (n_hrs, n_parks) sweep
  - HitData                      # frozen dataclass (D-17)
  - VerdictRecord                # per-cell iterator record
  - VerdictMatrix                # dense numpy arrays + iter_records()
  - mlb_park.geometry            # package-level re-exports for Phase 3
affects:
  - src/mlb_park/geometry/verdict.py
  - src/mlb_park/geometry/__init__.py
  - tests/test_verdict.py
  - tests/test_geometry_integration.py
tech-stack:
  added: []          # stdlib + numpy only; no new deps
  patterns:
    - "Frozen dataclasses for all public geometry values (HitData, VerdictRecord, VerdictMatrix)"
    - "Vectorization: one np.interp per park across all HRs — n_parks numpy calls, zero nested (hr, park) Python loops"
    - "Margin sign convention D-16: margin_ft = reported_distance - fence_ft; cleared = margin_ft > 0"
    - "Opaque identifier pass-through on HitData so Phase 3/5 can carry gamePk or play UUIDs without geometry coupling"
key-files:
  created:
    - src/mlb_park/geometry/verdict.py
    - tests/test_verdict.py
    - tests/test_geometry_integration.py
  modified:
    - src/mlb_park/geometry/__init__.py      # extend stub into full public-API re-exports
decisions:
  - "D-15 honored: vectorized sweep — one np.interp call per park, none nested"
  - "D-16 honored: margin_ft uses REPORTED totalDistance (MLB's Statcast truth), not the transform-recomputed distance; the transform distance is stored on VerdictMatrix.distance_ft for debug only"
  - "D-17 honored: HitData has exactly distance_ft/coord_x/coord_y required + opaque identifier=None"
  - "Park column order = dict insertion order (Python 3.7+); documented in compute_verdict_matrix docstring"
  - "Empty inputs produce shape (0, n) or (n, 0) matrices instead of raising — Phase 3-friendly"
metrics:
  completed: 2026-04-14
  duration_minutes: ~15
  tasks_completed: 2
  tests_added: 14         # 8 unit + 6 integration
  lines_added: ~404
---

# Phase 02 Plan 03: Verdict Matrix & Geometry Re-exports Summary

Vectorized per-HR-per-park verdict layer (`compute_verdict_matrix`) plus package-level re-exports — the Phase 2 capstone that Phase 3's HR pipeline consumes.

## What Shipped

- **`src/mlb_park/geometry/verdict.py`** — `HitData`, `VerdictRecord`, `VerdictMatrix` frozen dataclasses + `compute_verdict_matrix` vectorized function. One `np.interp` call per park, zero nested Python `(hr, park)` loops.
- **`src/mlb_park/geometry/__init__.py`** — extended from Plan 01 stub into full re-export surface: `Park`, `load_parks`, `HitData`, `VerdictMatrix`, `VerdictRecord`, `compute_verdict_matrix`, `gameday_to_spray_and_distance`, `clamp_spray_angle`.
- **`tests/test_verdict.py`** — 8 unit tests (frozen invariants, margin sign, shape, iter_records, parks_cleared, empty-input handling, 6×30 timing guard).
- **`tests/test_geometry_integration.py`** — 6 integration tests over 6 Judge HRs × 30 fixture venues.

## Observed Matrix Stats (Judge 2025 fixtures × 30 MLB venues)

| Metric | Value |
|---|---|
| Matrix shape | `(6, 30)` |
| Per-HR parks cleared | `[29, 30, 30, 30, 30, 30]` |
| Reported distances (ft) | `[415, 383, 405, 456, 398, 387]` |
| Clamped spray angles (°) | `[13.1, -41.8, -41.8, -24.4, -44.6, -32.9]` |
| No-NaN check | pass (all 180 cells finite) |
| Fence range | 250ft < min, max < 500ft (all physical) |

Every Judge HR clears ≥29 of 30 MLB parks — consistent with these all being real MLB HRs (Judge hits bombs). One HR clears only 29/30 (the 383ft shot at −42° — a near-line shot where park-specific LF dimensions matter). No HR cleared fewer than 10/30, so the "anomaly flag" threshold in the plan's output spec is not triggered.

## Invariants Verified

- `cleared == (margin_ft > 0)` element-wise across all 180 cells (unit test + integration test)
- `margin_ft[i, j] == hit[i].distance_ft - fence_ft[i, j]` (hand-computed Yankee Stadium cells across all 6 HRs, abs tol 1e-6)
- `HitData`, `VerdictRecord`, `VerdictMatrix` all frozen (`FrozenInstanceError` on mutation)
- Identifier round-trips from `HitData.identifier` through `iter_records()` — all 180 records carry their source `{"gamePk": ...}` dict, and the 5 unique gamePks `{822998, 823241, 823243, 823563, 823568}` round-trip (6 HRs, 5 games — one game has 2 Judge HRs)
- Timing guard: 6 × 30 completes under 100ms after warm-up (sub-millisecond in practice)

## Phase 2 Module Graph (final)

```
calibration.py         (CALIB_OX, CALIB_OY, CALIB_S)
      │
      ▼
transform.py           (gameday_to_spray_and_distance, clamp_spray_angle)
      │
      ├──────────────▶ park.py      (Park, load_parks)
      │                    │
      ▼                    ▼
            verdict.py     (HitData, VerdictRecord, VerdictMatrix,
                            compute_verdict_matrix)
                              │
                              ▼
                      __init__.py  (public re-exports)
                              │
                              ▼
                     mlb_park.geometry  ←  consumed by Phase 3
```

## Test Results

```
pytest -q tests/
.......................................          [100%]
39 passed in 0.42s
```

Breakdown: `test_calibration` + `test_transform` + `test_park` + `test_verdict` (8) + `test_geometry_integration` (6) = 39 passing.

## Import Hygiene

- `grep -rn "import requests\|import streamlit" src/mlb_park/geometry/` → empty
- `import mlb_park.geometry` does NOT load `requests` or `streamlit` (confirmed via `sys.modules` check)
- Threat `T-02-14` mitigated

## Deviations from Plan

Minor — none affecting behavior:

**1. [Rule 3 - Blocking] Reinstalled editable package at worktree start.**
- **Found during:** Pre-execution setup (per 02-02 deviation note)
- **Issue:** Editable install can point at stale worktree path; `pip install -e .` in the current worktree ensures `mlb_park.geometry.verdict` resolves correctly before tests run.
- **Fix:** Ran `pip install -e .` once at executor start; all subsequent tests pass.
- **Files modified:** none
- **Commit:** n/a (env-only fix)

**2. Unused import removed.** The plan's sample `verdict.py` imported `clamp_spray_angle` alongside `gameday_to_spray_and_distance`, but `verdict.py` only calls the latter (clamping happens inside `gameday_to_spray_and_distance`). Dropped the unused import; no behavior change.

**3. Unused import of `field` removed.** Plan's sample imported `dataclasses.field` without using it. Dropped.

No Rule 1, Rule 2, or Rule 4 deviations.

## Threat Model Status

| Threat ID | Disposition | Verification |
|-----------|-------------|--------------|
| T-02-10 (vectorization regression) | mitigated | `test_timing_guard_for_vectorization` — 6×30 in <100ms |
| T-02-11 (margin sign flip) | mitigated | Hand-computed Yankee cells + `assert_array_equal(cleared, margin > 0)` over 180 cells |
| T-02-12 (identifier loss) | mitigated | `test_iter_records_count` asserts identifier round-trip |
| T-02-13 (empty-input DoS) | mitigated | `test_empty_inputs_produce_shaped_empty_matrix` |
| T-02-14 (forbidden imports) | mitigated | `sys.modules` check + grep — both clean |

No new threat flags introduced.

## Commits

| Hash | Message |
|------|---------|
| `1cc35f2` | test(02-03): add failing tests for verdict matrix |
| `0e7abeb` | feat(02-03): implement vectorized verdict matrix (D-15/D-16/D-17) |
| `6697c68` | feat(02-03): re-export geometry API + end-to-end integration test |

## Phase 2 Goal: Met

Pure-function geometry layer, calibrated transform, piecewise-linear fence interp, per-park HR verdict — fully unit-tested, zero network, Phase 3-ready.

## Known Stubs

None. No placeholder data, no TODOs, no mock-only paths. Every value in `VerdictMatrix` is computed from real inputs (HitData + Park).

## Self-Check: PASSED

- `src/mlb_park/geometry/verdict.py` — FOUND
- `src/mlb_park/geometry/__init__.py` — FOUND (extended)
- `tests/test_verdict.py` — FOUND
- `tests/test_geometry_integration.py` — FOUND
- Commit `1cc35f2` — FOUND
- Commit `0e7abeb` — FOUND
- Commit `6697c68` — FOUND
- `pytest -q tests/` — 39 passed
- No `requests`/`streamlit` imports under `src/mlb_park/geometry/` — confirmed
