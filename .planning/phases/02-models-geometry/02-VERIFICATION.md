---
phase: 02-models-geometry
verified: 2026-04-14T00:00:00Z
status: passed
score: 8/8 must-haves verified
overrides_applied: 0
---

# Phase 2: Models & Geometry Verification Report

**Phase Goal:** Pure-function Park dataclass, empirically-calibrated coord-to-feet transform, piecewise-linear fence interpolation, per-park HR verdict. Unit-tested, no I/O.
**Verified:** 2026-04-14
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Calibration committed + reproducible (GEO-01) | VERIFIED | `python -m mlb_park.geometry.calibration` prints `Fitted: Ox=125.605 Oy=205.160 s=2.3912` against committed `125.608 / 205.162 / 2.3912` — within test tolerance 0.01/0.01/0.001. Max residual 0.153 ft (test_fit_reproduces_committed_constants, test_fit_beats_community_seed). |
| 2 | gameday_to_spray_and_distance transform correct (GEO-01) | VERIFIED | `transform.py:44-49` uses `dx=coordX-CALIB_OX`, `dy=CALIB_OY-coordY`, `atan2(dx, dy)` — D-09 convention (0°=CF, neg=LF, pos=RF). All 6 Judge HRs within 1.0 ft of reported totalDistance (test_all_judge_hrs_distance_within_1ft). |
| 3 | Spray angle clamp [-45°, +45°] with both raw+clamped exposed | VERIFIED | `transform.py:22-34` defines SPRAY_MIN_DEG/SPRAY_MAX_DEG and `clamp_spray_angle` handling scalar+ndarray. `gameday_to_spray_and_distance` returns 3-tuple `(raw, clamped, distance)`. Vectorized clamp test passes. |
| 4 | Park is frozen dataclass with 5-pt/7-pt construction (GEO-02) | VERIFIED | `park.py:29` `@dataclass(frozen=True) class Park`. `from_field_info` uses 7-pt iff BOTH `left` AND `right` present; else 5-pt (park.py:51-64). Angles: 5-pt `(-45,-22.5,0,+22.5,+45)`; 7-pt `(-45,-30,-22.5,0,+22.5,+30,+45)`. GAP_ANGLE_DEG=30.0. test_park_is_frozen raises FrozenInstanceError. |
| 5 | Fence interpolation via np.interp, clamped at ±45° (GEO-02) | VERIFIED | `park.py:78` `return np.interp(angle_deg, self.angles_deg, self.fence_ft)` — np.interp natively clamps to endpoint values outside bounds. Exact-at-angle and midpoint-linear tests pass. |
| 6 | Verdict matrix vectorized with margin-sign convention (GEO-03) | VERIFIED | `verdict.py:144-150`: one `np.interp` per park (n_parks numpy calls), zero nested (hr, park) Python loops. `margin_ft = reported[:, None] - fence_ft`; `cleared = margin_ft > 0` — positive = cleared. test_timing_guard_for_vectorization caps 6×30 under 100ms. Invariant `cleared == (margin_ft > 0)` asserted over all 180 cells. |
| 7 | HitData / VerdictRecord / VerdictMatrix all frozen dataclasses | VERIFIED | `verdict.py:21,35,47` all marked `@dataclass(frozen=True)`. test_hitdata_is_frozen and test_iter_records_yields_frozen_records both assert FrozenInstanceError on mutation. |
| 8 | All 30 fixture venues load into Park objects; geometry I/O-free | VERIFIED | `load_parks(venues)` → 30 parks, 7 seven-pt + 23 five-pt (matches RESEARCH.md prediction). `sys.modules` check after `import mlb_park.geometry.*` confirms `requests`, `streamlit`, `scipy` NOT loaded. |

**Score:** 8/8 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `src/mlb_park/geometry/__init__.py` | Re-exports Park, HitData, VerdictMatrix, compute_verdict_matrix, gameday_to_spray_and_distance, clamp_spray_angle, load_parks, VerdictRecord | VERIFIED | All 8 exports in `__all__`; clean imports from submodules. |
| `src/mlb_park/geometry/calibration.py` | fit_calibration + CALIB_OX/OY/S constants + extract_hrs_from_feeds + __main__ CLI | VERIFIED | 141 lines; committed constants match fit within tolerance; `python -m mlb_park.geometry.calibration` works. |
| `src/mlb_park/geometry/transform.py` | gameday_to_spray_and_distance + clamp_spray_angle + SPRAY_MIN/MAX_DEG | VERIFIED | 50 lines; imports only math+typing+numpy+calibration (no requests/streamlit). |
| `src/mlb_park/geometry/park.py` | Park frozen dataclass + from_field_info + fence_distance_at + load_parks + FENCE_ANGLES_*/GAP_ANGLE_DEG | VERIFIED | 96 lines; frozen dataclass; np.interp used for interpolation (park.py:78). |
| `src/mlb_park/geometry/verdict.py` | HitData + VerdictRecord + VerdictMatrix + compute_verdict_matrix | VERIFIED | 163 lines; vectorized; only stdlib+numpy+mlb_park.geometry imports. |
| `tests/conftest.py` + fixtures | judge_hrs (6), venues (30) | VERIFIED | Loaded via session-scoped fixtures from tests/fixtures/. |
| `tests/test_calibration.py`, `test_transform.py`, `test_park.py`, `test_verdict.py`, `test_geometry_integration.py` | Full test coverage | VERIFIED | 39/39 tests passing. |
| `requirements.txt` | contains pytest, NOT scipy | VERIFIED | `pytest>=8.0,<9.0` present (line 5); no scipy entry. |

### Key Link Verification

| From | To | Via | Status | Details |
|------|-----|-----|--------|---------|
| transform.py | calibration.CALIB_OX/OY/S | import | WIRED | `transform.py:20` `from mlb_park.geometry.calibration import CALIB_OX, CALIB_OY, CALIB_S` |
| park.py | numpy.interp | np.interp call | WIRED | `park.py:78` `return np.interp(angle_deg, self.angles_deg, self.fence_ft)` |
| verdict.py | transform.gameday_to_spray_and_distance | import + per-HR call | WIRED | `verdict.py:18` import; `verdict.py:137` call in compute_verdict_matrix |
| verdict.py | park.Park + np.interp vectorization | import + np.interp per park | WIRED | `verdict.py:17` import Park; `verdict.py:146` `fence_ft[:, j] = np.interp(clamped, park.angles_deg, park.fence_ft)` |
| __init__.py | all submodules | re-export | WIRED | All 8 public names re-exported and in `__all__`. |

### Data-Flow Trace (Level 4)

| Artifact | Data | Source | Produces Real Data | Status |
|----------|------|--------|-------------------|--------|
| calibration.CALIB_* | 3 floats | committed constants, reproducible from fixtures via fit_calibration | Yes — fit converges to committed values | FLOWING |
| Park.fence_ft | numpy array | constructed from fieldInfo dict in `from_field_info` | Yes — 30 parks with 250<fence<500 ft | FLOWING |
| VerdictMatrix.margin_ft | (n_hrs, n_parks) numpy array | `reported[:, None] - fence_ft` | Yes — 180 finite cells, hand-verified against Yankee Stadium | FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Full test suite passes | `pytest -q tests/` | 39 passed in 0.41s | PASS |
| Calibration re-derivable | `python -m mlb_park.geometry.calibration` | Fitted matches committed (Δ<0.003 on all 3 params); max residual 0.153 ft | PASS |
| Import purity (no requests/streamlit/scipy loaded) | `python -c "import mlb_park.geometry.*; check sys.modules"` | All three forbidden modules: False | PASS |
| 30 venues load | `load_parks(venues)` | 30 parks built; 7 seven-point + 23 five-point | PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| GEO-01 | 02-01-PLAN, 02-02-PLAN | Coord transform with calibrated origin/scale | SATISFIED | Calibration constants committed + reproducible; gameday_to_spray_and_distance delivers <1ft accuracy on 6 Judge HRs. |
| GEO-02 | 02-02-PLAN | Per-park piecewise-linear fence interpolation in angle-space | SATISFIED | Park.fence_distance_at uses np.interp over 5-pt or 7-pt angle/fence arrays; exact-at-angle + midpoint-linear tests pass. |
| GEO-03 | 02-03-PLAN | Per-HR-per-park verdict (distance vs interpolated fence) | SATISFIED | compute_verdict_matrix returns (n_hrs, n_parks) cleared/fence/margin arrays; margin sign invariant holds over all 180 fixture cells. |

No orphaned requirements for Phase 2.

### Anti-Patterns Found

None. No TODO/FIXME/HACK comments in `src/mlb_park/geometry/`. No empty-return stubs. No console.log-only handlers. File I/O in `extract_hrs_from_feeds` is correctly gated behind a function call (only invoked by tests and `__main__`) — module top-level is I/O-free, confirmed by sys.modules check on plain `import mlb_park.geometry.*`.

### Invariants Confirmed

- No imports of `requests`, `streamlit`, or file I/O at module top-level anywhere in `src/mlb_park/geometry/` — VERIFIED (grep empty for forbidden imports; sys.modules clean post-import; the one `read_text` call in calibration.py:95 is inside `extract_hrs_from_feeds` function body, not import-time).
- `scipy` NOT in requirements.txt; `pytest` IS in requirements.txt — VERIFIED (grep scipy → no match; pytest>=8.0,<9.0 on line 5).
- Calibration constants committed + re-derivable via `python -m mlb_park.geometry.calibration` — VERIFIED (printed Fitted vs Committed both matching within tolerance).
- `compute_verdict_matrix` vectorized (one np.interp per park across all HRs) — VERIFIED (verdict.py:144-146; timing guard passes).
- Margin sign: positive = cleared — VERIFIED (`margin_ft = reported - fence_ft`; `cleared = margin_ft > 0`).
- Park, HitData, VerdictRecord, VerdictMatrix all frozen — VERIFIED (all four have `@dataclass(frozen=True)`).
- 7-point curve used only when both `left` AND `right` present — VERIFIED (park.py:54; fixture distribution: 7 seven-pt + 23 five-pt = 30).
- Spray angle clamp [-45°, +45°] — VERIFIED (SPRAY_MIN_DEG=-45.0, SPRAY_MAX_DEG=+45.0 in transform.py).
- All 30 fixture venues load into Park without error — VERIFIED.

### Documented Deviation (Accepted)

Plan 02 `test_judge_hrs_angle_band` asserts `clamp_events == 0` rather than `== 1`. This is documented in 02-02-SUMMARY.md as a Rule 1 auto-fix: the original RESEARCH.md figure (one clamp at -45.95°) was computed against the *community* origin (125/199). With Plan 01's *fitted* origin (125.608/205.162), the near-edge HR (823563 HR2) moves to -44.568° — still the closest to the boundary but inside the ±45° band. The test preserves intent via a `near_edge_seen` check asserting at least one HR lands within 1° of the edge. This is a correct empirical finding from improved calibration, not a weakening of the test.

### Gaps Summary

None. All observable truths verified, all artifacts substantive and wired, data flows through from calibration → transform → park → verdict → public API, and the 39-test suite passes cleanly with no imports of `requests`, `streamlit`, or `scipy` reaching sys.modules. Phase 2 goal met: pure-function, empirically calibrated, unit-tested geometry layer ready for Phase 3 consumption.

---

_Verified: 2026-04-14_
_Verifier: Claude (gsd-verifier)_
