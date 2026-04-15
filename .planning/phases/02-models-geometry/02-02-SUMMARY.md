---
phase: 02-models-geometry
plan: 02
subsystem: geometry
tags: [geometry, park, interpolation, numpy, transform]
requires:
  - mlb_park.geometry.calibration.CALIB_OX
  - mlb_park.geometry.calibration.CALIB_OY
  - mlb_park.geometry.calibration.CALIB_S
  - tests/conftest.py::judge_hrs fixture
  - tests/conftest.py::venues fixture
  - tests/fixtures/venue_*.json (30 venues)
  - tests/fixtures/feed_*.json (5 feeds, 6 Judge HRs)
provides:
  - mlb_park.geometry.transform.gameday_to_spray_and_distance
  - mlb_park.geometry.transform.clamp_spray_angle
  - mlb_park.geometry.transform.SPRAY_MIN_DEG
  - mlb_park.geometry.transform.SPRAY_MAX_DEG
  - mlb_park.geometry.park.Park (frozen dataclass)
  - mlb_park.geometry.park.Park.from_field_info
  - mlb_park.geometry.park.Park.fence_distance_at
  - mlb_park.geometry.park.load_parks
  - mlb_park.geometry.park.FENCE_ANGLES_5PT
  - mlb_park.geometry.park.FENCE_ANGLES_7PT
  - mlb_park.geometry.park.GAP_ANGLE_DEG
affects:
  - Phase 2 Plan 03 (verdict matrix) consumes transform + Park directly
  - Phase 3 (pipeline) consumes load_parks(venues) + gameday_to_spray_and_distance
tech-stack:
  added: []
  patterns:
    - Pure-function geometry layer (stdlib math + numpy + calibration only)
    - Frozen dataclass for immutable stadium model
    - numpy.interp for vectorized piecewise-linear interpolation with native boundary clamping
    - Scalar-or-ndarray overload for clamp_spray_angle
key-files:
  created:
    - src/mlb_park/geometry/transform.py
    - src/mlb_park/geometry/park.py
    - tests/test_transform.py
    - tests/test_park.py
  modified: []
decisions:
  - "D-10 applied empirically: 7-pt iff BOTH `left` AND `right` present; left-only (5 venues) falls back to 5-pt. Yields exactly 7 seven-pt + 23 five-pt parks across the 30 captured fixtures (matches RESEARCH.md prediction)."
  - "D-11 locked: GAP_ANGLE_DEG = 30.0. Researcher-verified in 02-RESEARCH.md §Fence Interpolation."
  - "D-14 dual-exposure: gameday_to_spray_and_distance returns (raw, clamped, distance). Raw enables clamp-event logging; clamped feeds interpolation."
  - "Rule 1 deviation: test_judge_hrs_angle_band originally asserted clamp_events == 1 (per RESEARCH.md based on *community* origin 125/199). With Plan 01's *fitted* origin (125.608/205.162), the near-edge HR (gamePk 823563 HR2) lands at -44.568° — inside the band. Test updated to assert clamp_events == 0 and document the near-edge HR is still within 1° of the boundary."
metrics:
  duration: ~15 minutes
  completed: 2026-04-14
  tasks: 2
  files_changed: 4
  tests_passing: 25
---

# Phase 2 Plan 02: Transform + Park Model Summary

Pure-function Gameday→spray-angle transform and frozen `Park` fence model — the two primitives every downstream verdict, pipeline, and visualization consumer reads from.

## What Shipped

**Transform layer** (`src/mlb_park/geometry/transform.py`):
- `gameday_to_spray_and_distance(coord_x, coord_y) -> (raw_angle_deg, clamped_angle_deg, distance_ft)` — D-09 convention: 0°=CF, negative=LF, positive=RF. `dx = coordX - Ox`; `dy = Oy - coordY`; `atan2(dx, dy)`; `distance = s * hypot(dx, dy)`.
- `clamp_spray_angle(angle)` — scalar or `np.ndarray`, clamps to `[-45°, +45°]` per D-14.
- Constants: `SPRAY_MIN_DEG = -45.0`, `SPRAY_MAX_DEG = +45.0`.

**Park model** (`src/mlb_park/geometry/park.py`):
- `@dataclass(frozen=True) class Park`: `venue_id, name, angles_deg, fence_ft`.
- `Park.from_field_info(field_info, venue_id, name)` — 7-pt iff `left` AND `right` present; else 5-pt. Raises `KeyError` on missing canonical keys.
- `park.fence_distance_at(angle_deg)` — `np.interp` against (angles, fences); clamps outside ±45° to boundary fence.
- `load_parks(venues)` — builds `{venue_id: Park}` from the Phase 1 venues dict. No I/O.
- Constants: `FENCE_ANGLES_5PT = (-45, -22.5, 0, +22.5, +45)`, `FENCE_ANGLES_7PT = (-45, -30, -22.5, 0, +22.5, +30, +45)`, `GAP_ANGLE_DEG = 30.0`.

## Fixture observations

Across 30 captured venues:

| fieldInfo shape | count | treated as |
|---|---|---|
| Has `left` AND `right` | 7 | 7-point curve |
| Has `left` only | 5 | 5-point (D-10 v1 fallback) |
| Has neither gap key | 18 | 5-point |

No venue has `right` without `left`. No venue is missing any of the 5 canonical keys (`leftLine`, `leftCenter`, `center`, `rightCenter`, `rightLine`) — `Park.from_field_info` never raised `KeyError` across the 30 fixtures. The 7-count matches the RESEARCH.md "5-9 expected range" prediction and the plan's asserted target of exactly 7.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Corrected `test_judge_hrs_angle_band` clamp-event assertion (0 vs 1)**
- **Found during:** Task 1 GREEN phase
- **Issue:** Plan's test body asserted `clamp_events == 1`, citing RESEARCH.md §Key empirical findings #2 which flagged gamePk 823563 HR2 at `-45.95°` as the single clamp event. That -45.95° figure was computed with the **community** origin (Ox=125, Oy=199). Plan 01's fitted origin (Ox=125.608, Oy=205.162) pulls that HR to **-44.568°** — still the nearest-to-edge HR, but inside the ±45° band.
- **Fix:** Updated the test to (a) assert `clamp_events == 0` matching the fitted reality, and (b) add a `near_edge_seen` check that confirms at least one HR lands within 1° of the -45° edge, preserving the intent of documenting the near-edge HR.
- **Files modified:** `tests/test_transform.py`
- **Commit:** `3e9a553`

### Blocking issues fixed

**2. [Rule 3 - Blocker] Editable install pointed at a stale worktree**
- **Found during:** Task 1 RED phase (pytest couldn't import `mlb_park`)
- **Issue:** The project's editable install (`__editable__.mlb_park-0.1.0.pth`) resolved to a different worktree (`agent-a0920783`). From the `agent-a97a2904` worktree, `import mlb_park` failed.
- **Fix:** Ran `python -m pip install -e . --quiet` from this worktree. No code change; no commit. Future worktrees may need the same one-time step.
- **Files modified:** none (environment-only)

## Verification Results

- `pytest -q` → **25 passed in 0.40s** (6 calibration + 7 transform + 12 park)
- `python -c "from mlb_park.geometry.park import Park, load_parks; from mlb_park.geometry.transform import gameday_to_spray_and_distance"` → no import errors
- `grep -rn "import requests\|import streamlit" src/mlb_park/geometry/transform.py src/mlb_park/geometry/park.py` → empty
- 30 venues load without error; 7 are 7-point parks as predicted.

## Commits

| Task | Commit | Description |
|------|--------|-------------|
| 1 RED   | `339c5ce` | `test(02-02): add failing tests for gameday→spray transform` |
| 1 GREEN | `3e9a553` | `feat(02-02): implement gameday→spray transform (D-09 convention)` |
| 2 RED   | `decb01e` | `test(02-02): add failing tests for Park model + fence interpolation` |
| 2 GREEN | `90e31db` | `feat(02-02): implement Park model + fence interpolation (D-10/D-11/D-12)` |

## Self-Check: PASSED

- `src/mlb_park/geometry/transform.py` — FOUND
- `src/mlb_park/geometry/park.py` — FOUND
- `tests/test_transform.py` — FOUND
- `tests/test_park.py` — FOUND
- Commit `339c5ce` — FOUND
- Commit `3e9a553` — FOUND
- Commit `decb01e` — FOUND
- Commit `90e31db` — FOUND
- `pytest -q` 25/25 passing — CONFIRMED
- No `requests` / `streamlit` imports under `src/mlb_park/geometry/` — CONFIRMED
