# Phase 2: Models & Geometry - Context

**Gathered:** 2026-04-15
**Status:** Ready for planning

<domain>
## Phase Boundary

Pure-function `Park` dataclass, empirically-calibrated Gameday-coordinate → (spray-angle, distance) transform, piecewise-linear fence interpolation in angle-space, and per-HR-per-park verdict matrix. Unit-tested with zero I/O — consumes JSON that Phase 1 already fetches, produces values Phase 3 feeds into the pipeline.

Satisfies GEO-01 (coord transform), GEO-02 (fence interpolation), GEO-03 (per-HR-per-park verdict).
</domain>

<decisions>
## Implementation Decisions

### Locked from prior phases / roadmap / CLAUDE.md

- **D-01:** Pure functions + frozen dataclasses. No I/O, no network, no `requests`, no `streamlit` imports. Consumes already-fetched JSON.
- **D-02:** Piecewise-linear fence interpolation in angle-space (not cubic spline). Use `numpy.interp`.
- **D-03:** Spray angle via `math.atan2`. Use numpy vectorized ops where the shape justifies it. No `shapely`.
- **D-04:** Wall height NOT modeled in v1. Verdict is 2-D only (distance vs interpolated fence distance at spray angle).
- **D-05:** Community-reported origin (~125, ~199) and scale (~2.29–2.5) must be **empirically calibrated** — they are starting guesses, not locked values.

### Calibration (GEO-01)

- **D-06:** Calibrate coord origin `(Ox, Oy)` AND ft-per-unit scale `s` jointly via **least-squares fit** across all 6 Judge 2026 HRs captured in `tests/fixtures/feed_*.json`. Minimize squared error between computed distance `s * sqrt((coordX-Ox)^2 + (coordY-Oy)^2)` and `hitData.totalDistance`.
- **D-07:** Seed the optimizer at community values (Ox=125, Oy=199, s≈2.35). Use `scipy.optimize.least_squares` if scipy is available; otherwise implement a simple closed-form or gradient descent variant. **Discretion:** planner/researcher decides whether to add scipy or roll a minimal solver — `scipy` is not in `requirements.txt` today and adding it is a 1-line change.
- **D-08:** Commit the fit result (origin, scale, residuals) as **named constants** in a calibration module, with the calibration script reproducible from fixtures. The 6-HR input set is the authoritative ground truth for v1; if fixtures grow in future phases, re-run calibration.
- **D-09:** Expose the transform as a pure function: `gameday_to_spray_and_distance(coordX, coordY) -> (angle_deg, distance_ft)`. Spray angle convention: 0° is straight to CF, negative is toward LF, positive toward RF (Gameday convention, Y-axis inverted).

### Park Geometry & Gap Points (GEO-02)

- **D-10:** Use the **7-point fence curve** `[LF, L, LCF, CF, RCF, R, RF]` for the 12 parks that expose `left`/`right` gap distances in `fieldInfo`. Use the 5-point curve `[LF, LCF, CF, RCF, RF]` for the other 18. Per-park angle arrays reflect whichever set is available.
- **D-11:** Angle positions for the 5 standard points (well-established): LF=-45°, LCF=-22.5°, CF=0°, RCF=+22.5°, RF=+45°. Angles for the `left`/`right` gap points need to be confirmed empirically — **researcher flag**: are gap measurements at the ~-30°/+30° positions, or somewhere else? Check `fieldInfo` docs or infer from geometry.
- **D-12:** `Park` is a frozen dataclass holding `venue_id`, `name`, `angles_deg: np.ndarray` (5 or 7 entries), `fence_ft: np.ndarray` (same length). Built once from a `fieldInfo` dict via a `Park.from_field_info(fieldInfo, venue_id, name)` classmethod.
- **D-13:** A module-level `load_parks()` (pure wrapper, still no I/O — takes the already-loaded 30-venue dict from Phase 1's `load_all_parks` and builds 30 `Park` instances) returns `dict[int, Park]` keyed by venue_id.

### Spray Angle Bounds (GEO-02/03)

- **D-14:** **Clamp** computed spray angle into `[-45°, +45°]` before interpolation. Any HR whose raw angle falls outside this band (edge cases: infield dribblers, ITP, noisy coords) gets clamped to the nearest edge so every HR receives a verdict. Document clamp events (count) for debug visibility but don't fail the pipeline.

### Verdict Matrix (GEO-03)

- **D-15:** Per-HR-per-park output is a **vectorized matrix** computed in one call: `compute_verdict_matrix(hrs: list[HitData], parks: dict[int, Park]) -> VerdictMatrix`. Internally uses numpy to interpolate all HR angles against all parks' fences in a single `(n_hrs, 30)` sweep.
- **D-16:** `VerdictMatrix` exposes per-(hr, park) records with `cleared: bool`, `fence_ft: float`, `margin_ft: float` (signed: positive = cleared by X ft, negative = fell short by X ft). Accessible both as a dense numpy array (for aggregate ops like "parks cleared out of 30") and as iterable records (for Phase 5 hover tooltips).
- **D-17:** `HitData` input contract: `distance_ft: float`, `coord_x: float`, `coord_y: float`, plus any pass-through identifiers Phase 3 decides it needs (gamePk, batter, etc.). Phase 2 defines the minimum shape it reads from; Phase 3 supplies the objects.

### Testing

- **D-18:** Unit tests drive off `tests/fixtures/` JSON captured in Phase 1 — no live API calls. Golden tests for (a) calibration reproduces expected origin/scale within tolerance, (b) known 5-point park interpolates within 1 ft at standard angles, (c) 7-point park uses gap points when present, (d) clamp behavior at ±45° boundaries, (e) verdict matrix shape + dtype + margin sign convention.

### Claude's Discretion

- Exact numerical optimizer (scipy vs roll-your-own) — pick whichever is simpler to write AND test.
- Tolerance thresholds for golden tests (ft-level accuracy is the target; set something reasonable).
- Whether to expose `Park` and `VerdictMatrix` at the package root (`mlb_park.Park`) or only under a `geometry` submodule.
- Exact module layout under `src/mlb_park/` (e.g., `geometry.py` + `park.py` + `calibration.py` vs a single `geometry.py`).
</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project instructions
- `CLAUDE.md` — Locked decisions: math.atan2 + numpy over shapely; only `services/mlb_api.py` touches requests/st.cache_data; plotly 6; pandas 2.2.

### Planning artifacts
- `.planning/REQUIREMENTS.md` — GEO-01/02/03 acceptance criteria; v1 out-of-scope list (esp. wall height).
- `.planning/ROADMAP.md` §Phase 2 — Phase goal and success criteria.
- `.planning/PROJECT.md` — Core value, evolution rules.

### Phase 1 artifacts (inputs Phase 2 depends on)
- `.planning/phases/01-foundation-api-layer/01-RESEARCH.md` — Known community coord origin/scale values (must be calibrated, not used verbatim).
- `.planning/phases/01-foundation-api-layer/01-03-SUMMARY.md` — Fixture inventory and the fieldInfo key-set finding that motivated D-10 (12/30 parks have `left`/`right`).
- `src/mlb_park/services/mlb_api.py` — `get_venue`, `load_all_parks`, public HitData-carrying `get_game_feed`. Phase 2 consumes these outputs; does not import `requests`.
- `src/mlb_park/config.py` — Constants to reuse; Phase 2 may add CALIBRATION_* constants here or in its own module.
- `tests/fixtures/feed_*.json` — 5 game feeds × 6 total Judge HR plays. Ground truth for calibration.
- `tests/fixtures/venue_*.json` — 30 venues' `fieldInfo`. Ground truth for fence interpolation.

### External references
- No external ADRs. Community references (e.g., blog posts on Gameday coords) are starting points but NOT authoritative — the least-squares fit against Judge fixtures is.
</canonical_refs>

<specifics>
## Specific Ideas

- Verdict margin sign convention: **positive = cleared by X ft, negative = fell short by X ft**. Consistent across all consumers.
- Spray angle convention: **0°=CF, negative=LF, positive=RF** (Gameday-native; also how `hitData` is described in community docs).
- Calibration ground truth = all 6 Judge 2026 HRs captured in `tests/fixtures/feed_{822998,823241,823243,823563,823568}.json`. Fit both origin and scale jointly (3 parameters) against 6 observations — well-determined.
- Clamp events are interesting for debug but MUST NOT drop HRs. Every HR in scope produces a verdict row.
</specifics>

<deferred>
## Deferred Ideas

- **V2:** Per-HR verdict tier (no-doubter / solid / cheap) — v1 stops at boolean + margin; Phase 6 derives "cheap HR" counts from the margin matrix at the aggregate level.
- **V2:** Wall-height modeling (Requirements Out of Scope) — waits on an external data source.
- **V2:** Recalibrate origin/scale per-stadium (camera drift between parks). Out of scope for v1; single global transform.
- **V2+:** Cubic spline or physically modeled fence curves. Piecewise-linear is sufficient for v1.
</deferred>

---

*Phase: 02-models-geometry*
*Context gathered: 2026-04-15 via /gsd-discuss-phase*
