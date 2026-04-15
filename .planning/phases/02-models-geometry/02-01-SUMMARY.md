---
phase: 02-models-geometry
plan: 01
subsystem: geometry
tags: [geometry, calibration, testing, pytest, numpy]
requires:
  - tests/fixtures/feed_822998.json
  - tests/fixtures/feed_823241.json
  - tests/fixtures/feed_823243.json
  - tests/fixtures/feed_823563.json
  - tests/fixtures/feed_823568.json
provides:
  - mlb_park.geometry (subpackage marker, D-01 I/O-free)
  - mlb_park.geometry.calibration.fit_calibration
  - mlb_park.geometry.calibration.extract_hrs_from_feeds
  - mlb_park.geometry.calibration.CALIB_OX
  - mlb_park.geometry.calibration.CALIB_OY
  - mlb_park.geometry.calibration.CALIB_S
  - mlb_park.geometry.calibration.CALIB_RESIDUALS_FT
  - tests/conftest.py::judge_hrs fixture
  - tests/conftest.py::venues fixture
  - tests/conftest.py::fixtures_dir fixture
affects:
  - Phase 2 Plan 02 (Park model) consumes venues fixture + calibration constants
  - Phase 2 Plan 03 (verdict matrix) consumes judge_hrs + calibration constants
tech-stack:
  added: [pytest>=8.0]
  patterns:
    - Scipy-free least-squares via closed-form optimal scale + 2-D grid/refine search
    - Pure-function geometry layer (module top-level has only constants + function defs)
    - Conftest fixtures as session-scoped JSON loaders
key-files:
  created:
    - src/mlb_park/geometry/__init__.py
    - src/mlb_park/geometry/calibration.py
    - tests/__init__.py
    - tests/conftest.py
    - tests/test_calibration.py
  modified:
    - requirements.txt
    - pyproject.toml
decisions:
  - Kept pytest in a single requirements.txt (CLAUDE.md single-file hobby-app convention; no requirements-dev.txt split)
  - Chose scipy-free solver (20-line grid+refine) over adding scipy — honors D-07 and keeps the dep tree lean
  - Duplicated JUDGE_PERSON_ID=592450 into calibration.py rather than importing mlb_park.config, preserving D-01 (geometry has no intra-package coupling to the I/O layer)
metrics:
  duration: ~10 minutes
  completed: 2026-04-14
  tasks: 2
  files_changed: 7
  tests_passing: 6
---

# Phase 2 Plan 01: Calibration + Test Harness Summary

Wired pytest into the project and shipped the empirically calibrated Gameday→(r,distance) transform — scipy-free, reproducible from fixtures, and provably I/O-free at import time.

## What Shipped

**Calibration constants** (committed in `src/mlb_park/geometry/calibration.py`):

| Constant | Value | Meaning |
|----------|-------|---------|
| `CALIB_OX` | `125.608` | Origin X (Gameday units) |
| `CALIB_OY` | `205.162` | Origin Y (Gameday units; CF lies in direction of decreasing Y) |
| `CALIB_S`  | `2.3912` | Feet per Gameday unit |
| `CALIB_RESIDUALS_FT` | `(0.04, 0.15, 0.15, 0.04, 0.09, 0.07)` | Per-HR `|fitted − totalDistance|` on the 6 Judge fixtures |

**Fit reproducibility:** `python -m mlb_park.geometry.calibration` regenerates these from `tests/fixtures/feed_*.json`. Fitted output converges to `Ox=125.605, Oy=205.160, s=2.3912` — within the 0.01/0.01/0.001 tolerance the tests enforce. Max residual: **0.153 ft** (well under the 1.0 ft test budget, matching RESEARCH.md §Calibration predictions).

**Solver choice — why no scipy:** The joint 3-parameter fit reduces to a 2-D search because the optimal scale `s` for any fixed `(Ox, Oy)` has a closed form: `s* = (r · D) / (r · r)` where `r = sqrt((X-Ox)² + (Oy-Y)²)`. That collapses the problem to a grid search over 2 parameters, run at two refinement scales (41×41 coarse ±10 units, then 21×21 ±0.5, then 21×21 ±0.05). Total runtime under 50 ms. Adding scipy for this would have been a 10 MB dependency for 20 lines of code — honors D-07 and the CLAUDE.md "keep it boring" directive.

**Test harness** (`tests/conftest.py`):
- `fixtures_dir` — session-scoped Path to `tests/fixtures/`
- `judge_hrs` — 6 HR records `{gamePk, coordX, coordY, totalDistance}` extracted from 5 feed fixtures (game 823563 contributes 2 HRs)
- `venues` — `{venue_id: venue_dict}` for all 30 parks, ready for Plan 02 consumption

## Deviations from Plan

None — plan executed exactly as written. Committed constants matched the fitted output within tolerance on first run; no adjustment needed.

## Verification Results

- `pytest -q` → **6 passed in 0.30s**
- `python -m mlb_park.geometry.calibration` → fitted values match committed constants
- `requirements.txt` contains `pytest>=8.0,<9.0`; does **not** contain `scipy`
- No `import requests` / `import streamlit` / `import scipy` anywhere under `src/mlb_park/geometry/` (enforced by `test_geometry_imports_are_io_free` and `test_scipy_not_in_requirements`)

## Commits

| Task | Commit | Description |
|------|--------|-------------|
| 1 | `fcce8a7` | `chore(02-01): add pytest and scaffold tests/ package` |
| 2 | `ea020c0` | `feat(02-01): add geometry subpackage with calibrated coord transform` |

## Self-Check: PASSED

- `src/mlb_park/geometry/__init__.py` — FOUND
- `src/mlb_park/geometry/calibration.py` — FOUND
- `tests/__init__.py` — FOUND
- `tests/conftest.py` — FOUND
- `tests/test_calibration.py` — FOUND
- Commit `fcce8a7` — FOUND
- Commit `ea020c0` — FOUND
- `pytest` pin present in `requirements.txt` — FOUND
- `scipy` absent from `requirements.txt` — CONFIRMED
- 6/6 tests passing — CONFIRMED
