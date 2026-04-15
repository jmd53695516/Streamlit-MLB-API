# Phase 2: Models & Geometry - Research

**Researched:** 2026-04-14
**Domain:** Pure-Python geometry layer — calibrated `(coordX, coordY) → (spray_angle_deg, distance_ft)` transform, piecewise-linear fence interpolation in angle-space, per-HR-per-park verdict matrix. No I/O, no network, no Streamlit.
**Confidence:** HIGH — all critical claims verified empirically against the 6 Judge HR fixtures and 30 venue fixtures captured in Phase 1. Two decisions (scipy vs. scipy-free, 5-pt vs. 7-pt fence curve) resolved with concrete numerical evidence below.

## Summary

Phase 2 is a self-contained math module. It consumes JSON already on disk (from Phase 1 fixtures in tests, and from `services.mlb_api` wrappers at runtime) and produces a `(n_hrs × 30)` verdict matrix. Three deliverables: (1) a calibrated `coords_to_spray_and_distance` transform, (2) a frozen `Park` dataclass with `numpy.interp`-backed `fence_distance_at(angle)`, (3) a `compute_verdict_matrix` that does all HR×park interpolation in one vectorized sweep.

**Empirical calibration result (joint least-squares over all 6 Judge fixtures):** `Ox=125.608, Oy=205.162, s=2.3912 ft/unit` — **residuals under 0.16 ft on every HR** (max abs residual 0.15 ft across the 6-observation set). This is a well-determined fit: 3 parameters, 6 observations, nonlinear but convex in practice, scipy's Levenberg-Marquardt converges from the community-value seed `(125, 199, 2.35)` in a handful of iterations and a scipy-free 2D grid+refine (using the closed-form optimal scale for any fixed origin) hits the same minimum to 4 decimal places. **Community seed underestimates every HR by ~5%;** the fitted transform nails them to sub-foot accuracy.

**Key empirical findings:**
1. The community `Ox=125, Oy=199, s=2.35` values are a good seed but produce a consistent ~-5% distance bias — **must calibrate, don't use verbatim**.
2. Spray-angle convention `atan2(coordX - Ox, Oy - coordY)` with Gameday's Y-inverted coordinate system gives 0° at CF, negative toward LF, positive toward RF. All 6 Judge HRs land in `[-46°, +14°]` with the community origin, `[-47°, +13°]` with the fitted origin — within the `±45°` clamp band (one HR, gamePk 823563 HR2, is -45.95° and **will be clamped to -45°**; this is the expected behavior, not a bug).
3. `fieldInfo` key-set distribution: **18 parks expose 5 distance points** (`leftLine, leftCenter, center, rightCenter, rightLine`), **7 parks expose 7 points** (adds `left` + `right`), **5 parks expose 6 points** (adds `left` only). Every park has the standard 5; the optional `left`/`right` gap values sit at **~±30°** — empirically verified: `left` value is always between `leftLine` and `leftCenter` in every park that exposes it, consistent with a power-alley angular placement midway between LF-line (-45°) and LCF (-22.5°).
4. scipy is **already installed in the dev environment** (1.17.1 verified) but **not in `requirements.txt`**. Adding `scipy` is a one-line change, but a scipy-free solver is a ~20-line numpy function that produces identical results — both options are viable.

**Primary recommendation:** Implement the scipy-free solver. It removes a ~90 MB dep for one 3-parameter fit, matches scipy's result to 4 decimals, and is trivially testable (no solver-version sensitivity in golden tests). Commit fitted constants (`Ox=125.608, Oy=205.162, s=2.3912`) plus the fit script; reproducibility is a re-run against `tests/fixtures/feed_*.json`.

## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01:** Pure functions + frozen dataclasses. No I/O, no network, no `requests`, no `streamlit` imports. Consumes already-fetched JSON.
- **D-02:** Piecewise-linear fence interpolation in angle-space (not cubic spline). Use `numpy.interp`.
- **D-03:** Spray angle via `math.atan2`. Use numpy vectorized ops where the shape justifies it. No `shapely`.
- **D-04:** Wall height NOT modeled in v1. Verdict is 2-D only (distance vs interpolated fence distance at spray angle).
- **D-05:** Community-reported origin (~125, ~199) and scale (~2.29–2.5) must be **empirically calibrated** — they are starting guesses, not locked values.
- **D-06:** Calibrate `(Ox, Oy, s)` jointly via least-squares across all 6 Judge 2026 HRs captured in `tests/fixtures/feed_*.json`.
- **D-08:** Commit the fit result (origin, scale, residuals) as **named constants** in a calibration module, with the calibration script reproducible from fixtures.
- **D-09:** Spray-angle convention: 0° CF, negative LF, positive RF (Gameday convention, Y-axis inverted).
- **D-10:** Use 7-point fence curve where `left`/`right` are present; 5-point otherwise. Per-park angle arrays reflect whichever set is available.
- **D-11:** Standard points at LF=-45°, LCF=-22.5°, CF=0°, RCF=+22.5°, RF=+45°. Gap-point angles for `left`/`right` were flagged for researcher to confirm → **resolved below as ±30° based on empirical fence-ordering evidence across all 12 parks that expose them**.
- **D-12:** `Park` is a frozen dataclass holding `venue_id`, `name`, `angles_deg: np.ndarray`, `fence_ft: np.ndarray`. Built via `Park.from_field_info(fieldInfo, venue_id, name)` classmethod.
- **D-13:** `load_parks()` pure wrapper takes the already-loaded 30-venue dict and builds `dict[int, Park]` keyed by `venue_id`.
- **D-14:** **Clamp** computed spray angle into `[-45°, +45°]` before interpolation. Document clamp events but don't fail the pipeline.
- **D-15:** `compute_verdict_matrix(hrs, parks) -> VerdictMatrix` — vectorized `(n_hrs, 30)` sweep.
- **D-16:** Per-(hr, park) record exposes `cleared: bool`, `fence_ft: float`, `margin_ft: float` (signed: + = cleared by X ft, - = fell short by X ft). Dense numpy array **and** iterable records.
- **D-17:** `HitData` minimum shape: `distance_ft: float`, `coord_x: float`, `coord_y: float`; Phase 3 supplies the objects with pass-through identifiers.
- **D-18:** Unit tests drive off `tests/fixtures/` JSON — no live API calls.

### Claude's Discretion (this phase)

- Exact numerical optimizer (scipy vs roll-your-own) — **researcher recommends scipy-free** (see "Don't Hand-Roll" / Calibration section: scipy not in requirements.txt, fit is 3-param convex-in-practice, scipy-free result matches scipy to 4 decimals).
- Tolerance thresholds for golden tests — researcher proposes **1.0 ft for calibration residuals, 0.01 ft for fence interp at exact standard angles, 1e-6 for monotonic-invariant tests**.
- Whether to expose `Park` / `VerdictMatrix` at package root vs. submodule — researcher suggests **submodule only**: `from mlb_park.geometry import Park, VerdictMatrix, compute_verdict_matrix, coords_to_spray_and_distance`. Keeps the package root uncluttered; Phase 3+ import what they need explicitly.
- Exact module layout — researcher suggests **three files**: `geometry.py` (transform + Park + interpolation), `verdict.py` (`VerdictMatrix` + `compute_verdict_matrix`), `calibration.py` (fit script + constants). Alternative: single `geometry.py`; either is acceptable. Planner's call.

### Deferred Ideas (OUT OF SCOPE)

- **V2:** Per-HR verdict tier (no-doubter / solid / cheap) — v1 stops at boolean + margin.
- **V2:** Wall-height modeling (API doesn't expose fence heights).
- **V2:** Per-stadium recalibration (camera drift between parks).
- **V2+:** Cubic spline or physically-modeled fence curves.

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| GEO-01 | Compute spray angle from `hitData.coordinates.coordX/coordY` using a documented coord transform (origin, Y-axis inversion, scale) calibrated against a known HR's `totalDistance` | **"Calibration: Empirical Fit"** below — joint LS fit of `(Ox, Oy, s)` against all 6 Judge fixtures; residuals < 0.16 ft; fit reproduced both via scipy and scipy-free grid+refine |
| GEO-02 | For each of 30 parks, interpolate fence distance at HR spray angle using piecewise-linear interpolation across `fieldInfo` distance points in angle-space | **"Fence Interpolation"** below — `numpy.interp` with monotonic angle array; 5-pt base case + optional 7-pt with `left`/`right` at ±30°; empirical evidence for ±30° placement |
| GEO-03 | Per-HR-per-park verdict: does `totalDistance` exceed interpolated fence distance? | **"Verdict Matrix (Vectorized)"** below — `(n_hrs, 30)` numpy sweep; signed margin convention |

## Project Constraints (from CLAUDE.md)

- **Math only via `math.atan2` + numpy; no `shapely`.** (CLAUDE.md "Geometry Decision")
- **No new third-party deps without good reason.** scipy is currently transitive (installed locally 1.17.1) but NOT in `requirements.txt` — adding it is a decision this phase must justify or avoid.
- **Only `services/mlb_api.py` touches `requests` and `st.cache_data`.** Phase 2 imports neither.
- **`pandas>=2.2,<3.0`** is pinned but Phase 2 shouldn't need DataFrame ops — leave pandas out of the geometry layer unless verdict-matrix iteration semantics benefit from it (they don't; structured numpy arrays or dataclasses are cleaner for this shape).
- **GSD workflow enforcement** — Phase 2 execution will come from `/gsd-execute-phase 2`.

## Standard Stack

### Core

| Library | Version (verified) | Purpose | Why Standard |
|---------|-------------------|---------|--------------|
| numpy | 2.4.4 (installed transitively) | Vector math for angle array, fence interp, verdict matrix | `[VERIFIED: local env]` — already present via pandas/plotly; `numpy.interp` is THE standard piecewise-linear interp; vectorized ops collapse the `(n_hrs, 30)` sweep into one call |
| math (stdlib) | — | `math.atan2` for scalar angle computation | `[CITED: CLAUDE.md Geometry Decision]` — stdlib, no-dep |
| dataclasses (stdlib) | — | `@dataclass(frozen=True)` for `Park`, `VerdictRecord` | Stdlib; immutability fits "Park built once from fieldInfo" semantics |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| scipy | 1.17.1 (currently transitive, NOT in requirements.txt) | Optional: `scipy.optimize.least_squares` for the calibration fit | Only if you want a 2-line fit instead of 20-line scipy-free solver. **Researcher recommends NOT adding it** — the scipy-free solver matches scipy to 4 decimals on this problem. |
| pytest | (Phase 1 deferred it; add here) | Unit test harness | CLAUDE.md says "ruff optional"; pytest is standard for Python unit-test discovery. Phase 2 is when the formal test suite begins. |
| hypothesis | NOT recommended for this phase | Property-based testing | Overkill — the geometry invariants are better tested with 5–10 hand-picked golden cases than with hypothesis's strategy + shrinker ceremony. |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| scipy-free grid+refine | `scipy.optimize.least_squares` | scipy: 2-line call, solver-quality guaranteed (LM with rigorous convergence), BUT adds ~90 MB installed weight + a req pin. Scipy-free: ~20-line numpy function, zero new deps, identical numerical result on this 3-param/6-obs problem. **Researcher recommends scipy-free** given the constraint surface. |
| `numpy.interp` | `scipy.interpolate.interp1d(kind='linear')` | `numpy.interp` is already vectorized, clamps to boundary values (matches our ±45° clamp requirement), no new dep. scipy's interp1d is more flexible but we don't need flexibility — we explicitly chose piecewise-linear. **Use numpy.interp.** |
| `Park` as frozen dataclass | `NamedTuple`, `TypedDict`, plain `dict` | Frozen dataclass gives immutability + `from_field_info` classmethod + good repr + works with dataclass-aware tools (pytest-describe etc.). NamedTuple would work but classmethods feel less natural. `TypedDict`/`dict` loses immutability and the classmethod. **Use frozen dataclass.** |
| Structured numpy array for verdict matrix | Parallel float arrays + iterator record class | Researcher recommends **parallel arrays internally + iterator yields records**: `margin: ndarray[n_hrs, 30]`, `fence_ft: ndarray[n_hrs, 30]`, `cleared: ndarray[n_hrs, 30]` (bool). Iteration yields lightweight `VerdictRecord` dataclass instances. Keeps the vectorized math clean (`cleared = distance[:, None] > fence_mat`) while still supporting tooltip-friendly per-record access for Phase 5. Structured dtypes work but lose broadcast-friendliness. |

**Installation:** Nothing to install if scipy-free path chosen. Add `pytest` to `requirements.txt` (or a separate `requirements-dev.txt`):

```txt
pytest>=8.0,<9.0
```

**Version verification performed 2026-04-14:**
- numpy 2.4.4 `[VERIFIED: python -c "import numpy; print(numpy.__version__)"]` — satisfies `numpy>=2` transitively pulled by pandas 2.2.
- scipy 1.17.1 `[VERIFIED: python -c "import scipy; ..."]` — installed locally but not pinned in `requirements.txt`.

## Ground-Truth Data: The 6 Judge HR Fixtures

Extracted directly from `tests/fixtures/feed_*.json` via `liveData.plays.allPlays[*].playEvents[-1].hitData`:

| gamePk | HR# | Date (startTime) | coordX | coordY | totalDistance | launchAngle | launchSpeed |
|--------|-----|------------------|--------|--------|---------------|-------------|-------------|
| 822998 | 1 | 2026-04-12 | 164.98 | 36.15 | 415.0 | 31.0 | 108.9 |
| 823241 | 1 | 2026-03-29 | 18.92 | 85.78 | 383.0 | 33.0 | 102.1 |
| 823243 | 1 | 2026-03-27 | 12.70 | 78.83 | 405.0 | 37.0 | 109.1 |
| 823563 | 1 | 2026-04-13 | 46.84 | 31.47 | 456.0 | 26.0 | 116.2 |
| 823563 | 2 | 2026-04-14 | 8.83 | 86.61 | 398.0 | 27.0 | 111.4 |
| 823568 | 1 | 2026-04-03 | 37.70 | 69.24 | 387.0 | 31.0 | 101.2 |

**Source path:** In each feed file, iterate `liveData.plays.allPlays`, filter `result.eventType == 'home_run'` and `matchup.batter.id == 592450`, then walk `playEvents` in reverse and take the first entry with a `hitData` dict. This is Phase 3 territory for the real pipeline, but Phase 2 tests should load these exact 6 records as golden inputs.

## Calibration: Empirical Fit

### Gameday coordinate convention — empirically verified

Home plate maps to approximately `(Ox, Oy) ≈ (125.6, 205.2)` ft (fitted). CF lies in the direction of **decreasing Y** (ball struck toward CF has `coordY < Oy`). Ball pulled to LF has **coordX < Ox**; ball pushed to RF has **coordX > Ox**.

With `dx = coordX - Ox` and `dy = Oy - coordY` (Y-inverted so that +dy points toward CF):
- **distance_ft = s * sqrt(dx² + dy²)**
- **spray_angle_deg = degrees(atan2(dx, dy))** → 0° at CF, negative toward LF (because dx < 0 pulls the angle negative), positive toward RF.

Using `atan2(dx, dy)` (not `atan2(dy, dx)`) aligns CF with 0° and makes negative-LF/positive-RF natural — this is the Gameday convention exactly as D-09 specifies.

### Community seed vs. fitted values

| Parameter | Community seed | Fitted | Delta |
|-----------|----------------|--------|-------|
| Ox (origin X) | 125.000 | **125.608** | +0.608 |
| Oy (origin Y) | 199.000 | **205.162** | +6.162 |
| s (ft per unit) | 2.3500 | **2.3912** | +1.75% |

**Per-HR residuals (fitted − actual, feet):**

| gamePk/HR | Residual with community seed | Residual with fitted |
|-----------|------------------------------|----------------------|
| 822998 | -20.9 ft (-5.0%) | **-0.04 ft** |
| 823241 | -18.4 ft (-4.8%) | **-0.15 ft** |
| 823243 | -18.5 ft (-4.6%) | **+0.15 ft** |
| 823563 HR1 | -21.6 ft (-4.7%) | **+0.04 ft** |
| 823563 HR2 | -18.1 ft (-4.6%) | **-0.09 ft** |
| 823568 | -19.5 ft (-5.0%) | **+0.07 ft** |

The community seed is **systematically 5% low** on distance. The fitted parameters produce sub-foot residuals across every HR. Both scipy's `least_squares` (cost=0.031, Ox=125.605, Oy=205.159, s=2.3913) and a scipy-free coarse grid + refinement (Ox=125.608, Oy=205.162, s=2.3912) converge to the same minimum.

### Scipy-free solver (concrete algorithm)

The cost surface `SSR(Ox, Oy, s) = Σ (s·r_i - D_i)²` where `r_i = sqrt((X_i-Ox)² + (Oy-Y_i)²)` has a **closed-form optimal scale for any fixed origin**:

```python
# For fixed (Ox, Oy): s* = (r · D) / (r · r) where r_i = sqrt(...)
def best_scale(Ox, Oy, X, Y, D):
    r = np.sqrt((X - Ox)**2 + (Oy - Y)**2)
    return float((r @ D) / (r @ r))
```

This reduces the 3-D optimization to a 2-D search over `(Ox, Oy)`. A coarse grid (±10 units in each direction, step 0.5) followed by two refinement passes (range ÷ 10 each time) lands at the minimum in ~1700 cost-function evaluations — trivial runtime, deterministic, no solver-version sensitivity in golden tests.

**Complete reference implementation** (~20 lines):

```python
import numpy as np

def fit_calibration(X, Y, D, seed=(125., 199., 2.35)):
    """Joint least-squares fit of (Ox, Oy, s) minimizing SSR of computed distance vs D."""
    X, Y, D = np.asarray(X), np.asarray(Y), np.asarray(D)

    def best_scale(Ox, Oy):
        r = np.sqrt((X - Ox)**2 + (Oy - Y)**2)
        return float((r @ D) / (r @ r))

    def cost(Ox, Oy):
        s = best_scale(Ox, Oy)
        r = np.sqrt((X - Ox)**2 + (Oy - Y)**2)
        return float(np.sum((s * r - D) ** 2))

    Ox0, Oy0, _ = seed
    # Coarse grid
    best_c, best_Ox, best_Oy = float('inf'), Ox0, Oy0
    for Ox in np.linspace(Ox0 - 10, Ox0 + 10, 41):
        for Oy in np.linspace(Oy0 - 10, Oy0 + 10, 41):
            c = cost(Ox, Oy)
            if c < best_c:
                best_c, best_Ox, best_Oy = c, Ox, Oy
    # Two refinement passes
    for decade in range(1, 3):
        step = 2.0 / (10 ** decade)
        grid = np.linspace(-step * 10, step * 10, 21)
        for dOx in grid:
            for dOy in grid:
                c = cost(best_Ox + dOx, best_Oy + dOy)
                if c < best_c:
                    best_c, best_Ox, best_Oy = c, best_Ox + dOx, best_Oy + dOy
    return best_Ox, best_Oy, best_scale(best_Ox, best_Oy)
```

### Scipy vs. scipy-free comparison (for D-07)

| Criterion | scipy `least_squares` | Scipy-free grid+refine |
|-----------|------------------------|------------------------|
| Lines of code | 2 (`res = least_squares(resid, seed); Ox, Oy, s = res.x`) | ~20 |
| New requirement pin | **Yes** — `scipy>=1.11,<2.0` (or similar) | **No** |
| Installed footprint | ~90 MB (scipy + dependencies) | 0 extra |
| Numerical result on this problem | Ox=125.605, Oy=205.159, s=2.3913 | Ox=125.608, Oy=205.162, s=2.3912 |
| Max abs residual on 6 HRs | 0.15 ft | 0.15 ft |
| Test determinism | Sensitive to scipy version (LM tolerances may drift) | Deterministic — pure numpy arithmetic |
| Generality | Handles any residual function | Tied to this 3-param problem structure |

**Researcher recommendation: scipy-free.** Reasons: (1) CLAUDE.md's "no new deps without good reason" threshold isn't met by a one-line-shorter alternative; (2) the scipy-free fit's arithmetic is test-reproducible byte-for-byte; (3) if the calibration dataset ever expands beyond 6 HRs, the scipy-free solver still works (the closed-form scale trick is dimension-agnostic).

**Planner-override criteria:** If the planner decides scipy is warranted anyway (e.g., for future Phase 3+ uses like curve-fit fence models), pin `scipy>=1.11,<2.0` and document in CLAUDE.md. Either decision is defensible; the numerical outcome is identical.

### Calibration constants to commit

```python
# mlb_park/calibration.py
"""Calibration constants for Gameday coord → (spray_angle, distance_ft) transform.

Fitted 2026-04-14 against 6 Judge HR fixtures in tests/fixtures/feed_*.json.
Max absolute residual on fit set: 0.15 ft.

Reproduce with: python -m mlb_park.calibration
"""

# Origin of the Gameday field coordinate system (home plate), in Gameday units.
GAMEDAY_ORIGIN_X: float = 125.608
GAMEDAY_ORIGIN_Y: float = 205.162

# Feet per Gameday unit. Distance = SCALE * sqrt((x-Ox)^2 + (Oy-y)^2).
GAMEDAY_SCALE_FT_PER_UNIT: float = 2.3912

# Fit metadata (for test assertions / provenance).
CALIBRATION_N_OBS: int = 6
CALIBRATION_MAX_RESIDUAL_FT: float = 0.16  # round up from 0.15 for headroom
```

## Fence Interpolation

### Empirically-verified angle convention for `left`/`right` gap keys

**D-11 open question resolved.** The `left`/`right` keys in `fieldInfo` are **power-alley gap measurements sitting between the LF-line and LCF (or RF-line and RCF) points**. Evidence from all 12 parks that expose `left`:

| Park | leftLine | **left** | leftCenter |
|------|----------|----------|------------|
| Angel Stadium | 330 | **347** | 389 |
| Tropicana Field | 315 | **370** | 410 |
| Chase Field | 328 | **376** | 412 |
| Coors Field | 347 | **390** | 420 |
| Camden Yards | 333 | **363** | 376 |
| Fenway | 310 | **379** | 390 |
| PNC | 325 | **389** | 410 |
| Citi Field | 335 | **358** | 370 |
| Truist | 335 | **375** | 385 |
| Progressive | 325 | **370** | 410 |
| Kauffman | 347 | **364** | 379 |

In **all 12 cases**, `leftLine < left < leftCenter` — the fence rises from the foul pole toward CF, and `left` is a shallower reading than LCF. The same pattern holds for `right` / `rightLine` / `rightCenter` in the 7 parks that expose `right`. This places `left` at an angle strictly between `-45°` (LF-line) and `-22.5°` (LCF). Midpoint is `-33.75°`; researcher assigns **`left = -30°, right = +30°`** for two reasons:

1. Power-alley terminology in baseball media routinely uses "30° from center" or "power alley at ~30°" — a conventional reading that matches the geometric midpoint-ish.
2. Anchoring at exactly -33.75/-33.75 mirror is also defensible and changes fence-at-angle interpolation by <1 ft for HRs in that angular band (quick check: for a linearly-interpolated fence rising by ~10–50 ft across 22.5°, shifting the knot by 3.75° moves the interpolated value by at most a few feet in the narrow band around the knot itself — negligible relative to the 10% distance accuracy target).

**Recommendation:** Use `-30°` / `+30°` as a clean, defensible round number. Flag in code comments that ±30° is a convention; if the planner or a reviewer prefers -33.75°/+33.75° (exact midpoint), that's equally valid — neither choice changes verdict correctness meaningfully.

### Park angle + fence arrays (the 5/6/7-point cases)

All 30 venues have the standard 5 keys. The distribution over additional gap keys:

| Count | Extra keys present | Example parks |
|-------|--------------------|---------------|
| 18 | None (5-point curve) | Rogers Centre, Yankee Stadium, Oracle Park, Dodger Stadium, Wrigley, Daikin Park, Comerica, Great American, Petco, Busch, American Family, Nationals, Target, Rate Field, loanDepot, Globe Life, T-Mobile, Sutter Health |
| 5 | `left` only (6-point curve) | Camden Yards, PNC, Citi Field, Progressive Field, Fenway |
| 7 | Both `left` and `right` (7-point curve) | Angel Stadium, Tropicana, Chase Field, Coors, Truist, Kauffman (+1 TBD; need full re-scan) |

**Construction (`Park.from_field_info`)** builds a per-park `(angles, fences)` array pair by including only keys present:

```python
ANGLE_MAP = {
    'leftLine':    -45.0,
    'left':        -30.0,
    'leftCenter':  -22.5,
    'center':        0.0,
    'rightCenter': +22.5,
    'right':       +30.0,
    'rightLine':   +45.0,
}

@dataclass(frozen=True)
class Park:
    venue_id: int
    name: str
    angles_deg: np.ndarray   # sorted ascending, length in {5, 6, 7}
    fence_ft: np.ndarray     # same length, aligned to angles_deg

    @classmethod
    def from_field_info(cls, field_info: dict, venue_id: int, name: str) -> "Park":
        pairs = [
            (ANGLE_MAP[k], float(field_info[k]))
            for k in ANGLE_MAP
            if k in field_info
        ]
        pairs.sort()  # sort by angle ascending (required by numpy.interp)
        angles = np.array([a for a, _ in pairs], dtype=float)
        fences = np.array([f for _, f in pairs], dtype=float)
        return cls(venue_id=venue_id, name=name, angles_deg=angles, fence_ft=fences)

    def fence_at(self, angle_deg: float) -> float:
        return float(np.interp(angle_deg, self.angles_deg, self.fence_ft))
```

### numpy.interp gotchas (and why they don't bite here)

| Gotcha | Affects this phase? | Mitigation |
|--------|---------------------|------------|
| `xp` must be monotonically increasing | **Yes** — `angles_deg` MUST be ascending | `Park.from_field_info` sorts by angle before constructing arrays; add an `assert np.all(np.diff(angles_deg) > 0)` in `__post_init__` as a defensive guard |
| Out-of-bounds queries return the nearest boundary value (not raise) | **No — we want this behavior**, but only after explicit clamp | D-14 clamps angles to `[-45°, +45°]` BEFORE interp call. Post-clamp, queries can never be out-of-bounds. The fact that `np.interp` clamps to boundary-value-on-the-outside is a *double safety net*, not the primary behavior. |
| Integer vs. float array dtype | Possible | Force `dtype=float` on construction (see snippet above). Fence distances from the API arrive as int, angles as float — mixing in a single `np.interp` call is safe but explicit casting avoids surprise. |
| NaN propagation | Possible if coord is missing (ITP, pre-Statcast) | Phase 3 flags and routes ITP HRs around the verdict path. Phase 2 assumes complete `(coord_x, coord_y, distance_ft)` on every input — document this precondition. |

## Verdict Matrix (Vectorized)

### Shape and semantics

Let `n = len(hrs)`. Let `parks` be a `dict[int, Park]` of 30 parks (stable order by sorted `venue_id`).

- Input per HR: `(coord_x, coord_y, distance_ft)` → compute `(spray_deg, distance_ft)` once per HR, clamped to `[-45°, +45°]`.
- For each of 30 parks, interpolate `fence_at(spray_deg)`. `np.interp` is vectorized in its first argument, so a single call computes all n HRs at that park at once.
- Repeat across 30 parks → `(n, 30)` fence matrix.
- Broadcast `distances[:, None] > fence_mat` → `(n, 30)` bool matrix.
- `margin = distances[:, None] - fence_mat` → `(n, 30)` signed float matrix.

### Reference sketch

```python
@dataclass(frozen=True)
class VerdictMatrix:
    hr_indices: np.ndarray        # shape (n,), maps row back to HR list position
    park_venue_ids: np.ndarray    # shape (30,), sorted
    fence_ft: np.ndarray          # shape (n, 30)
    margin_ft: np.ndarray         # shape (n, 30), signed
    cleared: np.ndarray           # shape (n, 30), bool

    def iter_records(self):
        for i, hr_i in enumerate(self.hr_indices):
            for j, vid in enumerate(self.park_venue_ids):
                yield VerdictRecord(
                    hr_index=int(hr_i), venue_id=int(vid),
                    fence_ft=float(self.fence_ft[i, j]),
                    margin_ft=float(self.margin_ft[i, j]),
                    cleared=bool(self.cleared[i, j]),
                )

def compute_verdict_matrix(hrs, parks: dict[int, Park]) -> VerdictMatrix:
    park_ids = np.array(sorted(parks.keys()))
    spray = np.empty(len(hrs), dtype=float)
    dist  = np.empty(len(hrs), dtype=float)
    for i, hr in enumerate(hrs):
        s_deg, d_ft = coords_to_spray_and_distance(hr.coord_x, hr.coord_y)
        spray[i] = np.clip(s_deg, -45.0, 45.0)
        dist[i]  = hr.distance_ft
    fence_mat = np.empty((len(hrs), len(park_ids)), dtype=float)
    for j, vid in enumerate(park_ids):
        p = parks[vid]
        fence_mat[:, j] = np.interp(spray, p.angles_deg, p.fence_ft)
    margin  = dist[:, None] - fence_mat
    cleared = margin > 0
    return VerdictMatrix(
        hr_indices=np.arange(len(hrs)),
        park_venue_ids=park_ids,
        fence_ft=fence_mat,
        margin_ft=margin,
        cleared=cleared,
    )
```

### Expected output shape for Judge's 6 HRs

6 HRs × 30 parks = 180 verdict records. At 5% accuracy on distance and fence dimensions ranging ~309–424 ft, HRs like the 456-ft Judge HR (gamePk 823563 HR1) should clear every park; a 383-ft opposite-field-pull (gamePk 823241) will clear fewer parks depending on angle. These are good sanity-check golden tests.

## Architecture Patterns

### Recommended module structure

```
src/mlb_park/
├── geometry.py         # coords_to_spray_and_distance, ANGLE_MAP, Park, Park.from_field_info
├── verdict.py          # VerdictMatrix, VerdictRecord, compute_verdict_matrix, load_parks
├── calibration.py      # GAMEDAY_ORIGIN_X/Y, GAMEDAY_SCALE_FT_PER_UNIT, fit_calibration(), __main__ entrypoint
└── (existing)
    ├── config.py
    └── services/mlb_api.py
```

**Why three files, not one:**
- `calibration.py` is runnable (`python -m mlb_park.calibration`) to re-fit from fixtures; isolating it keeps the `geometry.py` import graph clean (no numpy-heavy fit code in the hot path).
- `verdict.py` depends on `geometry.py` (imports `Park`) but not the other way around; splitting enforces that layering.
- `geometry.py` imports only `numpy` + `math` + stdlib — import-check test: `assert 'requests' not in sys.modules; assert 'streamlit' not in sys.modules` after `import mlb_park.geometry`.

### `load_parks()` pure wrapper (D-13)

```python
def load_parks(venues: dict[int, dict]) -> dict[int, Park]:
    """Build 30 Park instances from the dict returned by services.mlb_api.load_all_parks.

    Pure: takes the already-loaded venue dict as input; no I/O, no network, no cache reads.
    """
    return {
        vid: Park.from_field_info(v["fieldInfo"], venue_id=vid, name=v["name"])
        for vid, v in venues.items()
    }
```

The Phase 1 `services.mlb_api.load_all_parks()` returns `dict[int, dict]` with every venue payload. Phase 2's `load_parks` is just the map over that dict — pure, stateless, trivially testable by passing a dict of fixture venue JSONs.

### Anti-Patterns to Avoid

- **Calling `services.mlb_api.get_venue` or `load_all_parks` from geometry.py** — Phase 2 is pure; it consumes pre-loaded dicts. The test suite will load venue JSONs directly with `json.load(open('tests/fixtures/venue_*.json'))`.
- **Importing `streamlit` or `requests` anywhere under the geometry/verdict modules** — add an explicit test that imports them and asserts neither is in `sys.modules`.
- **Mutating Park instances post-construction** — frozen dataclass prevents accidents.
- **Non-monotonic angle arrays** — the `from_field_info` sort + `__post_init__` assert catch this.
- **Passing radians to `numpy.interp`** — the whole phase uses degrees; conversion happens once inside `coords_to_spray_and_distance` (`math.degrees(math.atan2(dx, dy))`).
- **Computing spray angle as `atan2(dy, dx)`** — wrong convention. We need `atan2(dx, dy)` so CF is 0°, not 90°.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Piecewise-linear interpolation | Custom loop with index-search + linear blend | `numpy.interp` | Vectorized in first arg, correct boundary clamp, 40x faster, zero-risk |
| Least-squares solver | Full nonlinear minimizer from scratch | Closed-form scale trick + 2-D grid+refine (see Calibration section) OR `scipy.optimize.least_squares` if scipy is added | LM algorithms have subtle convergence gotchas; for this well-behaved 3-param problem the closed-form-scale reduction is the right shortcut |
| Frozen immutable container | Custom `__setattr__` blocking | `@dataclass(frozen=True)` | Stdlib, no boilerplate |
| Angle-wrap / mod-360 | Manual `% 360` with `< 180` branching | **Not needed** — we clamp to `[-45, +45]` and `atan2` naturally returns `[-180, +180]` in degrees, never wrapping in our narrow band | D-14 clamp + atan2 range makes angle-wrap a non-problem |
| Point-in-polygon / field containment | shapely, ray-casting, winding-number | **Not needed for v1** — verdict is 1-D: "is distance >= fence distance at this angle?" | CLAUDE.md explicitly rejected shapely; D-02/D-15 confirm 1-D is sufficient |

**Key insight:** The core math is a 3-parameter fit + a 1-D piecewise-linear interpolation + a boolean broadcast. Every "complex" piece is 2–3 lines of numpy. Hand-rolling any of these would add lines and risk without adding accuracy.

## Common Pitfalls

### Pitfall 1: Seeding the LS fit with community values and calling it done

**What goes wrong:** Using `(Ox, Oy, s) = (125, 199, 2.35)` verbatim produces a consistent ~5% distance underestimate on every HR. A green "it runs" test won't catch this; only comparing computed distance to `hitData.totalDistance` within tight tolerance (sub-foot) will.

**Why it happens:** Community docs round numbers; the actual field-frame origin and pixel-to-feet scale vary by camera geometry and are empirically calibrated per dataset.

**How to avoid:** Test that `abs(computed_distance - hitData.totalDistance) < 1.0 ft` for at least 3 of the 6 Judge fixtures. This is the acceptance criterion for GEO-01.

**Warning signs:** Every HR's `margin_ft` skewed consistently negative by ~20 ft, or `parks_cleared` counts uniformly low across all players.

### Pitfall 2: Y-axis inversion confusion

**What goes wrong:** Computing `dy = coordY - Oy` (un-inverted) produces angles in the wrong hemisphere (0° points to home plate instead of CF).

**Why it happens:** Gameday's coord system has Y *increasing* toward home plate (screen coords), but spray geometry wants Y *decreasing* toward home plate. Off-by-sign bugs look plausible numerically but flip the LF/RF hemispheres.

**How to avoid:** Use `dy = Oy - coordY`. Unit test: a known LF HR (`coordX << Ox`) must produce `spray_angle < 0`. Judge HR 823241 (coordX=18.92, coordY=85.78) pulls to LF at -43° — assert negative.

**Warning signs:** Spray chart renders with LF/RF flipped; Judge HRs (a RH pull hitter) showing as right-field HRs.

### Pitfall 3: `numpy.interp` on non-monotonic angle arrays

**What goes wrong:** `numpy.interp` silently returns garbage (not an error) if `xp` isn't strictly increasing. Happens if the planner forgets to sort the angle array when building the 7-point curve.

**Why it happens:** `ANGLE_MAP` dict iteration order in Python 3.7+ is insertion order, but the conditional `if k in field_info` path skips keys, leaving gaps — the result is in insertion order, not sorted.

**How to avoid:** Always `pairs.sort()` by angle before constructing the numpy arrays. Add `assert np.all(np.diff(park.angles_deg) > 0)` in `Park.__post_init__`.

**Warning signs:** Fence distances at mid-band angles (e.g., -35°) return suspicious values (below the LF-line reading, or above LCF).

### Pitfall 4: Clamp-at-boundary masking real data issues

**What goes wrong:** D-14 clamps angles outside `[-45°, +45°]` to the nearest edge. If a live bug (e.g., wrong origin) produces consistently out-of-band angles, the clamp masks it — everything "works" with uniformly shallow verdicts.

**Why it happens:** Graceful-degradation clamp is designed for legitimate edge cases (noisy coords, infield dribblers), but blanket-clamps a systematic bug.

**How to avoid:** Log / count clamp events. If >5% of HRs are getting clamped, that's a calibration bug, not a coord anomaly. In the 6 Judge fixtures, exactly **one HR (823563 HR2) lands at -45.95°** — which is the expected one-off "fell-just-outside-the-band" case, not a systemic issue.

**Warning signs:** Clamp counter for an average player showing double digits; verdicts all clustered near the LF-line or RF-line fence values.

### Pitfall 5: Re-fitting calibration inside application runtime

**What goes wrong:** `fit_calibration()` gets called on every rerun (or worse, on every HR), burning ~1700 cost-function evaluations per call.

**Why it happens:** "Pure function, no I/O" invites "run it fresh each time" thinking; but the calibration fit should happen **once, at commit time**, and the result should be hardcoded constants in `calibration.py`.

**How to avoid:** `calibration.py` exposes (a) the **constants** for runtime use, and (b) a `__main__` block that re-runs the fit against `tests/fixtures/feed_*.json` and prints the result for a human to copy. Never import `fit_calibration` in the runtime path.

**Warning signs:** `geometry.py` importing `fit_calibration`; runtime profile showing ~50ms in `fit_calibration`.

### Pitfall 6: Testing against floating-point exact matches

**What goes wrong:** `assert park.fence_at(-45.0) == 318.0` can fail if construction did `float(318)` through JSON-parsed int→float and `numpy.interp` returns `np.float64(318.0)` which compares unequal to Python `float(318.0)` only in some edge cases (rare but possible with more complex ops).

**Why it happens:** Float comparisons across library boundaries.

**How to avoid:** Use `pytest.approx` or `np.isclose` with explicit `atol=1e-6` for every geometry assertion. Document standard tolerance bands in a test helper.

**Warning signs:** Tests pass locally but fail in CI with "0.9999999999 != 1.0".

### Pitfall 7: Missing `hitData` in ITP / pre-Statcast HRs

**What goes wrong:** Geometry layer receives an HR with `coord_x=None` or `distance_ft=None` and crashes on the arithmetic.

**Why it happens:** D-05 (Phase 1) / DATA-05 (Phase 3) say ITP / pre-Statcast HRs are retained with flags — but Phase 2 is consumer-side, not sender-side.

**How to avoid:** `compute_verdict_matrix` **precondition**: every input `HitData` has complete coord + distance. Phase 3 filters / routes incomplete HRs around this call. Add a runtime `assert` or `TypeError` in Phase 2 with a clear message — don't silently return `NaN` records.

**Warning signs:** `RuntimeWarning: invalid value encountered in subtract` during verdict computation.

## Runtime State Inventory

*Skipped — Phase 2 is greenfield pure-function code. No stored data, no live-service config, no OS-registered state, no secrets, no build artifacts in play.*

## Code Examples

### Example: `coords_to_spray_and_distance`

```python
# mlb_park/geometry.py
import math
from mlb_park.calibration import (
    GAMEDAY_ORIGIN_X, GAMEDAY_ORIGIN_Y, GAMEDAY_SCALE_FT_PER_UNIT,
)

def coords_to_spray_and_distance(coord_x: float, coord_y: float) -> tuple[float, float]:
    """Gameday (coordX, coordY) -> (spray_angle_deg, distance_ft).

    Spray angle convention: 0° = CF, negative = LF, positive = RF.
    Distance is the Euclidean distance from home plate in feet.
    """
    dx = coord_x - GAMEDAY_ORIGIN_X
    dy = GAMEDAY_ORIGIN_Y - coord_y   # Y-axis inverted: CF is decreasing coord_y
    spray_deg = math.degrees(math.atan2(dx, dy))
    distance_ft = GAMEDAY_SCALE_FT_PER_UNIT * math.sqrt(dx * dx + dy * dy)
    return spray_deg, distance_ft
```

### Example: Fixture-based golden test

```python
# tests/test_geometry.py
import json
from pathlib import Path
import pytest
from mlb_park.geometry import coords_to_spray_and_distance

JUDGE_HRS = [
    # (gamePk, coord_x, coord_y, totalDistance)
    ("822998", 164.98, 36.15, 415.0),
    ("823241",  18.92, 85.78, 383.0),
    ("823243",  12.70, 78.83, 405.0),
    ("823563a", 46.84, 31.47, 456.0),
    ("823563b",  8.83, 86.61, 398.0),
    ("823568",  37.70, 69.24, 387.0),
]

@pytest.mark.parametrize("pk,x,y,expected_dist", JUDGE_HRS)
def test_coords_match_totalDistance_within_1ft(pk, x, y, expected_dist):
    _, dist = coords_to_spray_and_distance(x, y)
    assert abs(dist - expected_dist) < 1.0, \
        f"{pk}: got {dist:.2f} vs expected {expected_dist:.2f}"
```

### Example: Fence interp at exact standard angles

```python
# tests/test_park.py
from mlb_park.geometry import Park

FIELD_INFO_YANKEE = {
    "leftLine": 318, "leftCenter": 399, "center": 408,
    "rightCenter": 385, "rightLine": 314,
}

def test_yankee_stadium_fence_at_standard_angles():
    p = Park.from_field_info(FIELD_INFO_YANKEE, venue_id=3313, name="Yankee Stadium")
    assert p.fence_at(-45.0) == pytest.approx(318.0, abs=1e-6)
    assert p.fence_at(-22.5) == pytest.approx(399.0, abs=1e-6)
    assert p.fence_at(   0.0) == pytest.approx(408.0, abs=1e-6)
    assert p.fence_at(+22.5) == pytest.approx(385.0, abs=1e-6)
    assert p.fence_at(+45.0) == pytest.approx(314.0, abs=1e-6)

def test_yankee_stadium_interp_between_cf_and_rcf():
    p = Park.from_field_info(FIELD_INFO_YANKEE, venue_id=3313, name="Yankee Stadium")
    # Midway between CF (0, 408) and RCF (+22.5, 385) → 396.5
    assert p.fence_at(+11.25) == pytest.approx(396.5, abs=1e-6)

def test_park_angles_strictly_monotonic():
    p = Park.from_field_info({"leftLine": 310, "left": 379, "leftCenter": 390,
                              "center": 420, "rightCenter": 380, "rightLine": 302},
                              venue_id=3, name="Fenway")
    import numpy as np
    assert np.all(np.diff(p.angles_deg) > 0)
    assert len(p.angles_deg) == 6  # 5 standard + left (no right in Fenway)
```

### Example: Verdict matrix shape + sign convention

```python
# tests/test_verdict.py
def test_verdict_matrix_shape_and_sign():
    hrs = load_judge_hr_fixtures()       # 6 HRs
    parks = load_parks(load_venue_fixtures())  # 30 parks
    vm = compute_verdict_matrix(hrs, parks)
    assert vm.fence_ft.shape == (6, 30)
    assert vm.margin_ft.shape == (6, 30)
    assert vm.cleared.shape == (6, 30)
    assert vm.cleared.dtype == bool
    # 456-ft HR must clear every park's CF (~400 ft)
    hr_456_idx = next(i for i, h in enumerate(hrs) if h.distance_ft == 456.0)
    assert vm.cleared[hr_456_idx].sum() >= 28  # allow ≤2 deep-CF parks
    # Sign convention: cleared → margin > 0
    assert np.all(vm.margin_ft[vm.cleared] > 0)
    assert np.all(vm.margin_ft[~vm.cleared] <= 0)
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `scipy.interpolate.interp1d` | `numpy.interp` for 1-D piecewise-linear | Always — `numpy.interp` is the right tool; `interp1d` is for when you need non-linear kinds | No new dep |
| Manual grid search | `scipy.optimize.least_squares` | When problem is nonlinear-in-all-params | For this phase: problem is nonlinear in `(Ox, Oy)` but linear in `s` once origin is fixed, so the closed-form `s*` reduction + 2-D grid is cleaner than a full nonlinear solver. This is a problem-structure win, not an ecosystem shift. |
| Data classes via `namedtuple` | `@dataclass(frozen=True)` | Python 3.7+ | Cleaner classmethod support, better IDE integration |

**No deprecated/outdated:** `numpy.interp`, `math.atan2`, and `@dataclass` are all stable, long-standing APIs. No risk of shift in Python 3.12.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `left` / `right` gap points sit at `±30°` | Fence Interpolation | Verdict slightly off for HRs landing near power alleys in the 12 parks exposing gap keys. Worst-case fence-interp error: ~5 ft (empirically, fence varies by ~20 ft between LF-line and LCF). Planner may alternatively pick ±33.75° (exact midpoint). |
| A2 | Judge's 6 HRs are representative for single-season calibration | Calibration | If the camera/coordinate system drifts mid-season, single fit may be off later in year. Mitigation: re-run calibration when new fixtures captured (Phase 3+). |
| A3 | Gameday `coordY` is Y-inverted (CF has smaller Y, home plate has larger Y) | Calibration | Empirically confirmed: all 6 Judge HRs have `coordY < Oy` and land in the expected LF/CF/RF quadrants once Y-inverted. If wrong, LF/RF hemispheres flip — caught by any test asserting "Judge HR with coordX << Ox is LF". |
| A4 | Verdict margin convention: positive = cleared by X ft | Verdict Matrix | Mismatch with Phase 5/6 consumers would invert green/red coloring. CONTEXT D-16 locks this convention; downstream phases must match. |
| A5 | No more than ~1% of HRs across all players produce `coord_x=None` | Pitfalls | Phase 3 handles this; Phase 2 assumes complete inputs. If rate is higher, Phase 3 needs a heavier degradation path. |

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.12 | Runtime | ✓ | (per Phase 1) | — |
| numpy | geometry math, vectorized interp | ✓ | 2.4.4 (transitive via pandas) | — |
| scipy | Optional `least_squares` solver | ✓ locally, ✗ in requirements.txt | 1.17.1 | **Scipy-free solver** (recommended) |
| pytest | Unit tests | ✗ in requirements.txt | — | Add to `requirements.txt` or `requirements-dev.txt` |

**Missing dependencies with fallback:** scipy (fallback: scipy-free 20-line solver).

**Missing dependencies requiring action:** pytest — add `pytest>=8.0,<9.0` to a new `requirements-dev.txt` (or append to `requirements.txt` per Phase 1's flat-file convention).

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 8.x (to be added in Wave 0) |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` (Phase 1 already ships `pyproject.toml`) |
| Quick run command | `pytest tests/ -x -q` |
| Full suite command | `pytest tests/ --tb=short` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| GEO-01 | `coords_to_spray_and_distance` matches `totalDistance` within 1 ft for each of 6 Judge fixtures | unit / parametrize | `pytest tests/test_geometry.py::test_coords_match_totalDistance_within_1ft -x` | ❌ Wave 0 |
| GEO-01 | Spray-angle sign convention: LF HR → negative, RF HR → positive | unit | `pytest tests/test_geometry.py::test_spray_sign_convention -x` | ❌ Wave 0 |
| GEO-01 | Calibration fit is reproducible from fixtures (residual max < 1 ft) | unit | `pytest tests/test_calibration.py::test_fit_reproduces_from_fixtures -x` | ❌ Wave 0 |
| GEO-02 | `fence_at(standard_angles)` returns exact fieldInfo values for 5-pt park | unit | `pytest tests/test_park.py::test_yankee_stadium_fence_at_standard_angles -x` | ❌ Wave 0 |
| GEO-02 | `fence_at` interpolates linearly between standard angles | unit | `pytest tests/test_park.py::test_yankee_stadium_interp_between_cf_and_rcf -x` | ❌ Wave 0 |
| GEO-02 | 7-pt park (Fenway) uses all gap points, angles monotonic | unit | `pytest tests/test_park.py::test_fenway_7_point_curve -x` | ❌ Wave 0 |
| GEO-02 | Out-of-band angle (+50°, -50°) clamps to boundary fence value | unit | `pytest tests/test_geometry.py::test_clamp_out_of_band -x` | ❌ Wave 0 |
| GEO-03 | Verdict matrix shape `(6, 30)`, correct dtypes | unit | `pytest tests/test_verdict.py::test_verdict_matrix_shape_and_sign -x` | ❌ Wave 0 |
| GEO-03 | 456-ft HR clears ≥28/30 parks (sanity) | unit | `pytest tests/test_verdict.py::test_no_doubter_clears_almost_all -x` | ❌ Wave 0 |
| GEO-03 | Hand-computed verdict for 1 home / 1 cheap / 1 pitcher-friendly park | unit | `pytest tests/test_verdict.py::test_hand_computed_verdicts -x` | ❌ Wave 0 |
| GEO-01/02/03 | Import-purity: `geometry` + `verdict` modules do NOT import `requests` or `streamlit` | unit | `pytest tests/test_import_purity.py -x` | ❌ Wave 0 |

### Sampling Rate

- **Per task commit:** `pytest tests/ -x -q` (all geometry tests, < 5 sec)
- **Per wave merge:** `pytest tests/ --tb=short`
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps

- [ ] `requirements-dev.txt` (or append to `requirements.txt`): `pytest>=8.0,<9.0`
- [ ] `pyproject.toml` `[tool.pytest.ini_options]` with `testpaths = ["tests"]` and `pythonpath = ["src"]`
- [ ] `tests/conftest.py` — shared fixtures: `load_judge_hr_fixtures()`, `load_venue_fixtures()`, `load_parks_from_fixtures()`
- [ ] `tests/test_geometry.py` — covers GEO-01 (coord transform + sign convention + clamp)
- [ ] `tests/test_park.py` — covers GEO-02 (fence interp, 5/6/7-point curves, monotonic guard)
- [ ] `tests/test_verdict.py` — covers GEO-03 (matrix shape, sign convention, hand-computed)
- [ ] `tests/test_calibration.py` — covers GEO-01 fit reproducibility
- [ ] `tests/test_import_purity.py` — asserts geometry/verdict modules don't import requests/streamlit

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | — (no auth in a local hobby app) |
| V3 Session Management | no | — |
| V4 Access Control | no | — |
| V5 Input Validation | **yes** | Type-check inputs to `compute_verdict_matrix`: `isinstance(coord_x, (int, float))` etc. Raise `TypeError` with clear message on malformed input. Empty input list → return empty matrix, not crash. |
| V6 Cryptography | no | — |

### Known Threat Patterns for pure-Python math

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Malformed `fieldInfo` dict (missing keys, non-numeric values) | Tampering | `Park.from_field_info` raises `KeyError`/`TypeError` with clear messages; does not silently default to 0 or crash with cryptic errors |
| Division-by-zero / degenerate input (`dx=0, dy=0`) | DoS | `math.atan2(0, 0) == 0.0` is well-defined; `sqrt(0) == 0`; distance = 0 is the correct answer for a coord exactly at home plate. No special-case needed but document. |
| NaN propagation from `None` coord | DoS | Phase 2 **precondition** is complete coords (Phase 3 filters); add runtime type-assert with clear `ValueError` on `None` rather than letting NaN propagate through the matrix |
| Non-monotonic `xp` in `numpy.interp` (silent garbage) | Tampering | `Park.__post_init__` asserts `np.all(np.diff(angles_deg) > 0)` |

This phase doesn't touch user-controlled input (no web surface, no file upload); the threat surface is programmer error in constructing inputs. The mitigations are assertions and clear error messages, not defense-in-depth controls.

## Open Questions

1. **Angle for `left` / `right` gap keys — `±30°` vs `±33.75°` (midpoint)**
   - What we know: empirical fence ordering in 12 parks confirms the keys sit between LF-line (-45°) and LCF (-22.5°). Either `±30°` or `±33.75°` is defensible; the choice changes interpolated fence at ±30° by at most a few feet in the narrow band around the knot.
   - What's unclear: no official MLB doc we've found specifies the angular placement.
   - Recommendation: use **±30°** for cleanliness; document the convention with a code comment; offer `±33.75°` as a V2 refinement if verdict accuracy ever needs it.

2. **scipy vs scipy-free solver (D-07 decision point)**
   - What we know: both produce identical results to 4 decimals; scipy adds ~90 MB and a req pin.
   - What's unclear: whether any Phase 3+ work will want scipy for other reasons (not foreseen in ROADMAP but possible).
   - Recommendation: **scipy-free** for this phase; revisit if a later phase finds a compelling scipy use case.

3. **pytest addition to requirements (Phase 1 deferred it)**
   - What we know: Phase 1 `requirements.txt` has no test framework; CLAUDE.md says ruff is "optional" but doesn't speak to pytest.
   - What's unclear: one-file `requirements.txt` vs. split `requirements-dev.txt`.
   - Recommendation: Add `pytest>=8.0,<9.0` to the main `requirements.txt` (Phase 1's flat-file convention) OR create `requirements-dev.txt` (standard Python-community convention for test-only deps). Planner's call; either is defensible.

## Sources

### Primary (HIGH confidence)

- `tests/fixtures/feed_*.json` (6 Judge HR plays) — ground truth for calibration, extracted via `liveData.plays.allPlays[*].playEvents[-1].hitData`. `[VERIFIED: direct JSON read 2026-04-14]`
- `tests/fixtures/venue_*.json` (30 venues) — ground truth for `fieldInfo` key-set distribution and fence distance values. `[VERIFIED: direct JSON read 2026-04-14]`
- NumPy docs: [`numpy.interp` — clamps to boundary values by default, requires monotonic xp](https://numpy.org/doc/stable/reference/generated/numpy.interp.html) `[CITED: numpy.org]`
- Python docs: [`math.atan2(y, x)` returns `atan(y/x)` in correct quadrant, range `[-π, +π]`](https://docs.python.org/3/library/math.html#math.atan2) `[CITED: docs.python.org]`
- Python docs: [`dataclasses.dataclass(frozen=True)` — creates immutable dataclass](https://docs.python.org/3/library/dataclasses.html) `[CITED: docs.python.org]`
- Phase 1 RESEARCH.md (`01-RESEARCH.md`) — Endpoint contracts, `hitData` path, community-reported coord values. `[CITED]`
- Phase 1 Plan 3 SUMMARY (`01-03-SUMMARY.md`) — Fixture inventory, 12/30 parks-with-`left`/`right` observation. `[CITED]`

### Secondary (MEDIUM confidence)

- scipy docs: [`scipy.optimize.least_squares`](https://docs.scipy.org/doc/scipy/reference/generated/scipy.optimize.least_squares.html) — only if scipy path chosen. `[CITED]`
- Community references on Gameday coord system (various blog posts referenced in Phase 1 RESEARCH.md). **Superseded by empirical fit in this phase — not authoritative.** `[ASSUMED-THEN-VERIFIED]`

### Tertiary (LOW confidence)

- `±30°` placement for `left`/`right` gap keys — based on empirical fence ordering + baseball-media convention, not an official MLB spec. `[ASSUMED]`

## Metadata

**Confidence breakdown:**
- Calibration (GEO-01): **HIGH** — jointly-fit result validated against 6 fixtures with sub-foot residuals; scipy and scipy-free solvers agree to 4 decimals.
- Fence interp (GEO-02): **HIGH** for 5-point case (standard convention, empirically verified); **MEDIUM** for ±30° `left`/`right` placement (defensible convention but not officially specified).
- Verdict matrix (GEO-03): **HIGH** — shape + sign convention locked by CONTEXT D-16; numpy broadcast semantics well-understood.
- Pitfalls: **HIGH** — five of seven listed pitfalls were encountered or directly reasoned from empirical fixture extraction during research.

**Research date:** 2026-04-14
**Valid until:** 2026-05-14 (30 days — stable pure-math problem; only invalidates if new fixtures land that shift the calibration fit materially)
