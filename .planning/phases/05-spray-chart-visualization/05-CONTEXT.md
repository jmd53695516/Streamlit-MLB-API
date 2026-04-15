---
phase: 05-spray-chart-visualization
requirements: [VIZ-01, VIZ-02, VIZ-03]
depends_on: [Phase 4 (ViewModel + app.py), Phase 2 (Park, VerdictMatrix), Phase 3 (HREvent)]
captured: 2026-04-15
status: discussed
---

# Phase 5: Spray Chart Visualization — Context

## Phase Boundary

**Goal:** Render the `ViewModel` as a Plotly spray chart below the existing Phase 4 selectors: the selected stadium's outline in feet, every plottable HR as a scatter point color-coded by whether it cleared THAT stadium, with hover tooltips giving per-HR detail.

**In scope:**
- New `src/mlb_park/chart.py` module with pure `build_figure(view_model) -> plotly.graph_objects.Figure`
- Stadium outline: filled fair-territory polygon + infield skin + mound + home plate + 3 bases + baselines
- HR scatter overlay with green/red verdict colors
- Per-HR hover tooltip (date, opponent, distance, EV, LA, parks cleared /30)
- `app.py` invokes `st.plotly_chart(chart.build_figure(view))` in place of (or below) the raw JSON dump

**Out of scope (Phase 6):**
- Summary metrics card (total HRs, avg parks cleared, no-doubters, cheap HRs)
- Best/worst parks ranking
- Loading spinners and friendly error messages (UX-05)
- Per-HR sortable details table (V2-02)

## Implementation Decisions

### Locked from prior phases / roadmap / CLAUDE.md
- **Plotly 6.7.0** is the chart library (CLAUDE.md, stack decision — not matplotlib, not Altair).
- **`st.plotly_chart`** is the render path. No custom HTML/JS component wrappers.
- **Green = clears the selected park / red = doesn't clear** (requirement VIZ-02).
- **Hover fields:** date, opponent, distance, exit velocity, launch angle, parks cleared out of 30 (requirement VIZ-03).
- **Data sources already built:**
  - `ViewModel.plottable_events` — list of HREvents already filtered to `has_coords && has_distance`.
  - `ViewModel.verdict_matrix.cleared` — dense (n_hrs, n_parks) bool array.
  - `ViewModel.parks` — tuple of all 30 `Park` objects (with `angles_deg` + `fence_ft` in feet, home plate at origin).
  - `Park.from_field_info` already converts `fieldInfo` into fence-curve arrays.
- **Coord system:** Cartesian, in **feet**, home plate at `(0, 0)`, y-axis is center-field. `coords_to_feet` from Phase 2 handles the raw-game-day → feet conversion.
- **Chart module purity:** `src/mlb_park/chart.py` must not import `streamlit`. Enforced via the same purity-guard test pattern used for `controller.py` (D-23 style).

### D-01 Stadium outline style
**Decision:** Filled green fair-territory polygon + infield details.

Specifically:
- Fair territory = filled polygon (light green): `home plate → LF foul pole end → 6/7 fence points → RF foul pole end → home plate`. Foul lines = the polygon's outer edges (implicit, no separate traces).
- Infield skin = brown arc, radius ~95 ft from home plate (dirt). Implemented as a filled partial-annulus or a circle clipped to the fair-territory polygon.
- Pitcher's mound = small filled circle at 60.5 ft along the 0° spray line.
- Home plate = pentagon marker at origin.
- Three bases = white diamond markers at canonical MLB positions (90 ft base paths).
- Baselines = thin lines connecting `home → 1B → 2B → 3B → home`.

**Why:** Dense visual context that feels like a real park diagram, with minimal code cost. Separates the in-play area visually so the HR scatter reads cleanly.

### D-02 Infield dimensions
**Decision:** Fixed MLB-standard constants, same for every park (no per-park lookup from `field_info`).
- `MOUND_DISTANCE_FT = 60.5`
- `BASE_DISTANCE_FT = 90.0`
- `INFIELD_SKIN_RADIUS_FT = 95.0`
- `HOME_PLATE_SIZE_FT = 1.5` (marker scale)
- `BASE_MARKER_SIZE_FT = 1.25`

Lives as a constants block in `src/mlb_park/chart.py` (or `config.py` — Claude's discretion).

**Why:** These are regulation dimensions for every MLB park. Zero per-park conditional logic, and the 30 parks all share this infield geometry.

### D-03 Background
**Decision:** White plot background, no foul territory shading.

Only the fair-territory polygon is colored. Outside the polygon (where foul territory would be) is the default white `paper_bgcolor` / `plot_bgcolor`. Max contrast for HR markers.

### D-04 Chart scaling & axes
**Decision:** Fixed viewport across all 30 parks: `x ∈ [-450, +450]`, `y ∈ [0, 500]`.

Axes are **hidden entirely** — no labels, no grid, no tick marks. The scale reads from the fence curve itself.

**Why:** Fixed scale preserves the core value prop — "Fenway really is smaller than Yankee Stadium" — and the user sees each park's true relative size when flipping the stadium selector. Hidden axes give a clean ballpark-diagram look.

### D-05 HR marker styling
**Decision:**
- **Size:** Uniform 12 px (no size-by-distance or size-by-EV).
- **Opacity:** 0.7 (semi-transparent — overlapping HRs get a natural darker cluster).
- **Shape:** Circle (`symbol="circle"`).
- **Border:** Thin white border (`marker.line.color="white"`, `marker.line.width=1`).
- **No jitter** — plotted position matches the actual coords.

**Why:** Color alone carries the verdict signal. Uniform sizing keeps the chart readable; opacity handles overlaps without lying about HR positions.

### D-06 Degraded HR handling
**Decision:** Silently drop HRs that lack coords or distance from the chart.

- `build_figure` iterates only `view_model.plottable_events` (already filtered to `has_coords && has_distance` by Phase 3).
- No caption, no count banner on the chart in Phase 5.
- Phase 6 summary card is free to surface "X HRs without coords" if desired — that's a Phase 6 decision, not this one.

**Why:** Keeps Phase 5 focused on the visualization. The degradation flags are already preserved in `HREvent`; the chart simply reads what Phase 3 already filtered.

### D-07 Hover tooltip content
**Decision:** Per-HR tooltip with all VIZ-03 fields:

```
{date} vs {opponent_abbr}
Distance: {distance_ft} ft
Exit Velocity: {launch_speed} mph
Launch Angle: {launch_angle}°
Clears {cleared_count} / 30 parks
```

Implementation: pass a `customdata` array per HR and build a `hovertemplate` string. `cleared_count` comes from summing `verdict_matrix.cleared[i, :]` for each HR row.

### D-08 Color palette
**Decision:** Explicit hex values in a `chart_theme` constants block at the top of `src/mlb_park/chart.py`:

| Name | Hex | Use |
|------|-----|-----|
| `CLEARS` | `#2ca02c` | HR marker fill when `cleared[i, selected_park_idx]` is True |
| `DOESNT_CLEAR` | `#d62728` | HR marker fill when False |
| `FAIR_TERRITORY` | `#e8f5e9` | Fair polygon fill (very light green) |
| `INFIELD_DIRT` | `#c1a17a` | Infield skin fill |
| `MOUND_DIRT` | `#c1a17a` | Mound fill (same as skin) |
| `BASES_FG` | `#ffffff` | Base marker + baseline stroke |
| `HOME_PLATE_FG` | `#ffffff` | Home plate marker |
| `BORDER` | `#ffffff` | Marker white border |

**Why:** Baseball-themed (greens for grass, browns for dirt), consistent with how spray charts look in broadcasts and on Savant. Having them in a constants block makes Phase 6 theming easy.

### D-09 Module layout
**Decision:** New `src/mlb_park/chart.py` module, pure.

- Public function: `build_figure(view: ViewModel) -> plotly.graph_objects.Figure`.
- Must pass a purity test (`test_chart_purity.py`) modeled on `test_purity.py`: no `import streamlit`, no `st.session_state` references.
- `app.py` imports `from mlb_park import chart` and calls `st.plotly_chart(chart.build_figure(view), use_container_width=True)`.

### D-10 Fair-territory polygon construction
**Decision:** Build the polygon vertex-by-vertex from `Park.angles_deg` + `Park.fence_ft`.

Algorithm:
1. Start at home plate `(0, 0)`.
2. At each `(angle_deg, fence_ft)` pair, compute `(fence_ft * sin(angle), fence_ft * cos(angle))` — angle measured from CF (0°), positive toward right field.
3. First fence point is LF foul pole (negative angle or first index), last is RF foul pole.
4. Close the polygon back to `(0, 0)`.

Traces as a single `Scatter` with `fill="toself"`, `line.color=FAIR_TERRITORY` (same as fill for a clean look), no markers.

**Why:** The fence curve IS the outline. No hard-coded foul pole angles — just use whatever angles `Park.from_field_info` produced (5 or 7 point spec).

### D-11 Sign convention for spray angle
**Locked from Phase 2:** spray angle is measured with 0° = straight-away center, positive = toward right field. This already matches `Park.angles_deg` ordering (left-field-first or right-field-first — inspect `Park.from_field_info` during planning to confirm the exact convention).

### D-12 Empty state
**Decision:** If `view_model.plottable_events` is empty (player has 0 HRs this season, or all HRs are degraded), still render the stadium outline alone. Show a Streamlit-level `st.info("{Player name} has no plottable HRs this season.")` banner above the chart.

**Why:** The stadium outline alone is still informative (tells the user the app is working, shows the selected park), and avoids a jarring blank chart.

### Claude's Discretion
- Exact `Figure.update_layout` settings (margins, title, hovermode) — pick sensible Plotly defaults.
- Whether infield skin is a partial annulus or a quarter-circle filled polygon — whichever is cleanest in code.
- Precise base marker shape (diamond `▲` glyph vs `symbol="diamond"`) — pick what reads cleanly.
- Whether mound is a circle or a slightly-raised visual (small ellipse) — pick what looks reasonable.
- Trace ordering (outline → infield → bases → HRs) must be such that HR markers are on top of everything else.
- How to expose `selected_park_idx` to `build_figure`: take it as a kwarg or derive from `view.venue_id` → index into `view.parks`. Researcher/planner can lock the exact interface.

## Testing

- **Purity test:** `tests/test_chart_purity.py` — greps `src/mlb_park/chart.py` for `import streamlit` and `st.session_state`; fails if found.
- **Structural tests** (unit-level, against a fixture `ViewModel`):
  - `build_figure(view)` returns a `plotly.graph_objects.Figure` (not None).
  - Figure has expected number of traces (≥ 5: outline + infield + mound + bases-group + home + HR scatter). Exact count is researcher/planner decision.
  - HR scatter trace marker colors are all hex `CLEARS` or `DOESNT_CLEAR` — no other values.
  - Fair-territory polygon's first and last `(x, y)` match home plate `(0, 0)` (closed polygon).
  - Fixed layout ranges: `xaxis.range == [-450, 450]`, `yaxis.range == [0, 500]`.
- **Hover template test:** hovertemplate string contains the 6 required VIZ-03 fields (`Distance`, `Exit Velocity`, `Launch Angle`, etc.).
- **Empty-events test:** Given a ViewModel with `plottable_events=[]`, `build_figure` still returns a valid Figure with the stadium outline but an empty HR trace.

## Canonical References

### Project instructions
- `CLAUDE.md` — Plotly 6.7.0 stack decision; `@st.cache_data` as the single caching layer; hobby-app ethos.

### Planning artifacts
- `.planning/ROADMAP.md` — Phase 5 goal and success criteria.
- `.planning/REQUIREMENTS.md` — VIZ-01, VIZ-02, VIZ-03.
- `.planning/PROJECT.md` — core value prop ("cheap vs no-doubt HRs").

### Phase 2 artifacts (geometry the chart consumes)
- `src/mlb_park/geometry/park.py` — `Park` dataclass with `angles_deg` + `fence_ft` (the fence curve in feet).
- `src/mlb_park/geometry/verdict.py` — `VerdictMatrix` with `cleared[i, j]` and `margin_ft[i, j]`.
- `src/mlb_park/geometry/transform.py` — `coords_to_feet` (already applied by pipeline; chart does NOT re-transform).
- `.planning/phases/02-models-geometry/02-CONTEXT.md` — coordinate convention + calibration constants.

### Phase 3 artifacts (HR data the chart scatter)
- `src/mlb_park/pipeline/events.py` — `HREvent` (degradation flags, `coord_x`/`coord_y` in feet post-transform, `distance_ft`, `launch_speed`, `launch_angle`).
- `.planning/phases/03-hr-pipeline/03-CONTEXT.md` — degradation policy (has_coords, has_distance).

### Phase 4 artifacts (ViewModel + app integration)
- `src/mlb_park/controller.py` — `ViewModel` dataclass (`plottable_events`, `verdict_matrix`, `venue_id`, `parks`).
- `src/mlb_park/app.py` — existing Streamlit shell; chart renders inside the `else` branch after `build_view` succeeds.
- `.planning/phases/04-controller-selectors-ui/04-CONTEXT.md` — `ViewModel` shape, controller purity rule to replicate.

### Streamlit references
- [`st.plotly_chart` docs](https://docs.streamlit.io/develop/api-reference/charts/st.plotly_chart) — `use_container_width` behavior, `theme="streamlit"` vs `theme=None`.

### Plotly references
- Plotly `Scatter` with `fill="toself"` for polygons: https://plotly.com/python/filled-area-plots/
- `hovertemplate` + `customdata` for per-point tooltips: https://plotly.com/python/hover-text-and-formatting/
- `Figure.update_layout` to hide axes: `xaxis.visible=False`, `yaxis.visible=False`.

## Specific Ideas

- **Trace z-order matters.** HR scatter must render on top of outline/infield/bases. In Plotly, later `add_trace` calls draw on top. Add HR scatter last.
- **`use_container_width=True`** on `st.plotly_chart` so the chart scales with the Streamlit layout. The fixed aspect ratio is enforced via `xaxis.scaleanchor="y"` + `xaxis.scaleratio=1` inside `update_layout` to keep 1 ft = 1 ft in both axes even when the container stretches.
- **Green-on-green readability:** `CLEARS` markers (`#2ca02c`) on `FAIR_TERRITORY` fill (`#e8f5e9`) should still contrast well — the light fair-territory fill is near-white. The white marker border gives extra separation.

## Deferred Ideas

These came up as interesting but belong to future phases / the backlog:

- **Click-to-pin HR details** — click a marker to open a persistent details panel. Scope creep; hover is sufficient per VIZ-03.
- **Outfield grass-mow pattern** — alternating light/dark green stripes. Looks great in broadcast charts; not worth the code cost for v1.
- **Animated HR plotting** — markers fade in one by one. Cute; not in scope.
- **Comparison mode** — overlay two parks' fence curves on one chart. Future enhancement; not in any existing requirement.
- **Size-by-distance or size-by-EV** — considered and rejected for v1 (color alone is enough). Could be revisited in Phase 6 polish.
- **Per-park foul territory rendering** — some parks have distinctive foul territory shapes. Out of scope — no `field_info` data for it.
