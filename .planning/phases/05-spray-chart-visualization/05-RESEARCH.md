# Phase 5: Spray Chart Visualization — Research

**Researched:** 2026-04-15
**Domain:** Plotly 6.7 figure construction + Streamlit embedding + pytest structural testing
**Confidence:** HIGH

## Summary

Phase 5 is a pure-function rendering layer: take a fully-built `ViewModel` (stable contract from Phase 4) and return a `plotly.graph_objects.Figure`. Every hard architectural question — data shape, coord transform, verdict semantics, module purity rule — is already answered by prior phases or by CONTEXT.md's 12 locked decisions. The remaining research surface is narrow and mechanical: which Plotly idioms to use, which Streamlit interaction flags to set, and how to test a Figure without rendering.

**Primary recommendation:**
1. Build the fair-territory polygon as a single `go.Scatter(fill='toself', mode='lines')` trace from `Park.angles_deg`/`fence_ft` via `x = fence_ft * sin(angle)`, `y = fence_ft * cos(angle)` — closing with `(0, 0)` as both first and last vertex. This matches the verdict-computation coordinate convention exactly (verified from `transform.py`).
2. Render infield skin + mound as `layout.shapes` entries with `layer="below"`; render home plate and bases as small scatter traces so they pick up `zorder` naturally. Add the HR scatter trace **last** — trace draw order is top-of-stack.
3. Use `xaxis.range=[-450, 450]`, `yaxis.range=[0, 500]`, `yaxis.scaleanchor='x'`, `yaxis.scaleratio=1`, **plus `constrain='domain'` on both axes** to prevent Plotly from auto-expanding range to fill the Streamlit container (a known gotcha).
4. Pack 6 hover fields into `customdata` as a `(n_hrs, 6)` ndarray, reference via `%{customdata[i]}` in `hovertemplate` with `<br>` line breaks and `<extra></extra>` to suppress the trace-name box.
5. Pass `selected_park_idx` through `build_figure(view)` by **deriving it inside** from `view.venue_id` scanning `view.verdict_matrix.venue_ids` — the view already owns that mapping and exposing a second kwarg duplicates state. (Justification in §Architecture Patterns.)
6. Test the figure structurally: assert `len(fig.data)`, `fig.data[HR_TRACE_IDX].marker.color` tuple, `fig.layout.xaxis.range`, and `fig.layout.shapes` lengths. No headless-browser rendering needed.

## User Constraints (from CONTEXT.md)

### Locked Decisions

**D-01 Stadium outline:** Filled green fair-territory polygon + infield skin + mound + home plate + 3 bases + baselines. Foul lines are the polygon's outer edges (implicit — no separate traces).

**D-02 Infield dimensions:** Fixed MLB-standard constants, same for every park:
- `MOUND_DISTANCE_FT = 60.5`
- `BASE_DISTANCE_FT = 90.0`
- `INFIELD_SKIN_RADIUS_FT = 95.0`
- `HOME_PLATE_SIZE_FT = 1.5`
- `BASE_MARKER_SIZE_FT = 1.25`

**D-03 Background:** White plot background, no foul-territory shading.

**D-04 Scaling & axes:** Fixed viewport `x ∈ [-450, +450]`, `y ∈ [0, 500]`. Axes hidden entirely (no labels, grid, ticks).

**D-05 HR markers:** Uniform 12 px circles, opacity 0.7, thin white border, no jitter, no size-by-EV.

**D-06 Degraded HR handling:** Silently drop HRs lacking coords/distance. Phase 3 already filters into `ViewModel.plottable_events` — chart trusts that filter.

**D-07 Hover tooltip:** 5-line format —
```
{date} vs {opponent_abbr}
Distance: {distance_ft} ft
Exit Velocity: {launch_speed} mph
Launch Angle: {launch_angle}°
Clears {cleared_count} / 30 parks
```

**D-08 Color palette:** Explicit hex constants (CLEARS `#2ca02c`, DOESNT_CLEAR `#d62728`, FAIR_TERRITORY `#e8f5e9`, INFIELD_DIRT `#c1a17a`, MOUND_DIRT `#c1a17a`, BASES_FG `#ffffff`, HOME_PLATE_FG `#ffffff`, BORDER `#ffffff`).

**D-09 Module layout:** New `src/mlb_park/chart.py`. Pure (`import streamlit` forbidden). Public API: `build_figure(view: ViewModel) -> plotly.graph_objects.Figure`. `app.py` invokes `st.plotly_chart(chart.build_figure(view), use_container_width=True)`.

**D-10 Fair-territory polygon:** Built vertex-by-vertex from `Park.angles_deg` + `Park.fence_ft` via `(fence_ft * sin(angle), fence_ft * cos(angle))`. Closed back to `(0, 0)`. Single `Scatter` trace with `fill="toself"`.

**D-11 Sign convention:** 0° = CF, positive = RF. Matches Phase 2 `transform.py` (verified during this research — see §Coordinate Convention Confirmation).

**D-12 Empty state:** If `plottable_events` is empty, render the stadium outline alone. `st.info("{Player name} has no plottable HRs this season.")` banner is an `app.py` concern (not `chart.py`).

### Claude's Discretion
- Exact `Figure.update_layout` settings (margins, title, hovermode).
- Infield skin as filled partial annulus vs. quarter-circle polygon.
- Base marker shape (symbol glyph vs `symbol="diamond"`).
- Mound shape (circle vs. slight ellipse).
- Trace ordering (HRs must be last / on top).
- How `selected_park_idx` reaches `build_figure` — research recommends deriving from `view.venue_id` internally (see §Architecture Patterns).

### Deferred Ideas (OUT OF SCOPE)
- Click-to-pin HR details panel
- Outfield grass-mow pattern
- Animated HR plotting
- Comparison mode (two parks overlaid)
- Size-by-distance / size-by-EV
- Per-park foul-territory rendering

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| VIZ-01 | Plotly spray chart: selected stadium outline (home → 6 fence points → home) + foul lines, scaled in feet | §Fair-territory polygon construction, §Fixed viewport + aspect ratio lock. `Park.angles_deg`/`fence_ft` handles 5-point (5 venues) and 7-point (25 venues) curves transparently — the polygon loop iterates whatever length the Park supplies. |
| VIZ-02 | All HRs plotted, green=clears / red=doesn't clear the **selected** stadium | §HR scatter trace. `view.clears_selected_park` is a pre-computed per-plottable-HR bool tuple produced by `controller._clears_for_venue` — chart consumes it directly, zero re-computation. |
| VIZ-03 | Hover tooltip shows date, opponent, distance, EV, LA, parks cleared /30 | §Hovertemplate + customdata pattern. `parks_cleared_count[i] = sum(view.verdict_matrix.cleared[i, :])` or use the existing `VerdictMatrix.parks_cleared(i)` helper. |

## Project Constraints (from CLAUDE.md)

- **Plotly 6.7.0** is the chosen viz library; no matplotlib fallback.
- **`@st.cache_data`** is the sole caching layer. Chart module is pure — no caching decorators; if caching the Figure ever makes sense (it doesn't for a 50-HR x 30-park chart), wrap at the `app.py` call site, not in `chart.py`.
- **No heavy new deps.** `chart.py` imports only `plotly.graph_objects`, `numpy` (already pulled by pandas), and `mlb_park.controller.ViewModel` + `mlb_park.geometry.park.Park` types.
- **Hobby-app ethos.** Prefer clarity over cleverness; keep the whole module under ~300 lines.
- **Purity guard mirrors `test_purity.py`.** Forbidden substrings in `chart.py` source: `import streamlit`, `from streamlit`, `st.session_state` (see `tests/controller/test_purity.py` for the exact pattern — replicate it for chart).

## Coordinate Convention Confirmation

**[VERIFIED: src/mlb_park/geometry/transform.py, src/mlb_park/geometry/verdict.py]**

The Phase 2 transform is:

```
dx = coord_x - CALIB_OX
dy = CALIB_OY - coord_y          # Y-inverted: +dy → CF
distance_ft  = CALIB_S * hypot(dx, dy)
angle_deg    = degrees(atan2(dx, dy))   # 0° = CF, +right
```

So in the chart's "feet from home plate" coordinate system:

```
plot_x = CALIB_S * dx = distance_ft * sin(angle_deg)    # + = RF, - = LF
plot_y = CALIB_S * dy = distance_ft * cos(angle_deg)    # + = CF, always ≥ 0 for fair balls
```

**This matches D-10's polygon formula exactly** (`fence_ft * sin(angle)`, `fence_ft * cos(angle)`). The HR scatter and the stadium polygon share one coordinate system with no re-projection.

### How the chart computes HR (x, y)

`HREvent.coord_x`/`coord_y` are the **raw Gameday** values (not yet transformed). The chart must apply `CALIB_OX`/`CALIB_OY`/`CALIB_S` the same way the verdict matrix does. Two clean options:

1. **Re-apply transform directly** — import `CALIB_OX/OY/S` from `mlb_park.geometry.calibration` and compute `x = S * (coord_x - OX)`, `y = S * (OY - coord_y)`. Keeps the chart independent of angle/distance; 3 lines.
2. **Derive from (spray_clamped_deg, reported_distance)** — both are already in `VerdictMatrix.spray_clamped_deg` and `HREvent.distance_ft`. Compute `x = distance * sin(spray)`, `y = distance * cos(spray)`. Note: uses the **clamped** spray (45° cap) and the **reported** distance, so a 472-ft HR at an uncapped 47° angle plots at 45° instead of the true bearing. For v1 this is acceptable (the verdict matrix does the same thing) but it loses the few degrees of raw detail.

**Recommendation: option 1.** The raw `(coord_x, coord_y)` values preserve the true HR bearing exactly, and the calibration constants are already the verdict's source of truth — no new logic or assumption leakage. The verdict's green/red color already rides on the clamped-angle verdict; the marker **position** should use the uncapped geometry.

## Environment Availability

No new external tools required. `plotly>=6.7,<7.0` is already pinned in `requirements.txt` [VERIFIED: requirements.txt]; `pytest>=8.0,<9.0` is present for structural tests. No headless browser, no kaleido, no image export — the chart is rendered client-side by Streamlit.

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| plotly | 6.7 (pinned `>=6.7,<7.0` in requirements.txt) | Figure construction | Locked in CLAUDE.md; `go.Scatter(fill='toself')` + `layout.shapes` cover the entire D-01..D-10 surface with zero extra plotting primitives. [VERIFIED: requirements.txt, plotly 6.6 docs] |
| numpy | 2.x (via pandas 2.2) | Sin/cos polygon vertices, customdata array | Already available; `np.sin`/`np.cos` on `Park.angles_deg` (already ndarray) gives vectorized polygon vertices in one line. [VERIFIED: src/mlb_park/geometry/park.py uses numpy] |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pytest | 8.x | Structural figure tests | For `test_chart.py` (Wave 2 test file). [VERIFIED: requirements.txt] |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `go.Scatter(fill='toself')` for the polygon | `layout.shapes` with `type="path"` and SVG path string | Path strings are opaque in tests; Scatter's `x`/`y` arrays are trivially assertable. Stick with Scatter. |
| `layout.shapes` for mound/infield | A separate `go.Scatter` trace for each circle (drawn via sin/cos) | Shapes with `type="circle"` or `type="path"` are ~2 lines vs. ~10 for a parametric circle trace. Use shapes. |
| `customdata` numpy array | Per-point dict list | Plotly converts list-of-dicts inefficiently; ndarray is the documented path. [CITED: plotly.com/python/hover-text-and-formatting] |
| `scaleanchor` for aspect lock | `layout.yaxis.constrain='range'` only | scaleanchor enforces 1 ft = 1 ft across axes; range-constrain alone doesn't. Use both. |

**Installation:** No new install — `plotly>=6.7,<7.0` is already pinned.

**Version verification:**
```bash
# Not re-verified during this research — pin exists and was confirmed at project init.
# Plotly 6.x API (Scatter, fill='toself', hovertemplate, customdata, layout.shapes, scaleanchor)
# has been stable since 5.x; nothing used here was added or deprecated in 6.x.
```
[VERIFIED: plotly 6.6 python API reference — Scatter and layout.shapes have all fields referenced here]

## Architecture Patterns

### Recommended module layout
```
src/mlb_park/
├── chart.py          # NEW — pure, no streamlit import
```

No submodules. One file, ~250 lines estimated:
- constants block (colors + infield dims)
- `build_figure(view)` — top-level orchestration
- private helpers: `_fair_territory_trace(park)`, `_infield_shapes()`, `_base_markers_trace()`, `_hr_scatter_trace(view, selected_park_idx)`, `_empty_hr_trace()`
- `_resolve_selected_park_idx(view) -> int` — looks up `view.venue_id` in `view.verdict_matrix.venue_ids`; returns the column index.

### Pattern 1: Fair-territory polygon via sin/cos vectorization
**What:** Build the fair polygon from `Park.angles_deg` + `Park.fence_ft` in one vectorized expression.
**When to use:** D-10 — the canonical Phase 5 outline pattern.
**Example:**
```python
# Source: D-10 + src/mlb_park/geometry/park.py (angles_deg is ndarray sorted -45..+45)
import numpy as np
import plotly.graph_objects as go

def _fair_territory_trace(park):
    angles_rad = np.deg2rad(park.angles_deg)        # (-45 .. +45), LF-first → RF-last
    xs = park.fence_ft * np.sin(angles_rad)         # LF pole is negative, RF positive
    ys = park.fence_ft * np.cos(angles_rad)         # always ≥ 0 in fair territory
    # Close polygon: home → LF pole → ... → RF pole → home
    x_closed = np.concatenate(([0.0], xs, [0.0]))
    y_closed = np.concatenate(([0.0], ys, [0.0]))
    return go.Scatter(
        x=x_closed, y=y_closed,
        mode="lines",
        fill="toself",
        fillcolor=FAIR_TERRITORY,
        line=dict(color=FAIR_TERRITORY, width=1),    # same as fill — foul lines visually merge
        hoverinfo="skip",
        showlegend=False,
        name="fair",
    )
```
This transparently handles both 5-point and 7-point curves — `Park.angles_deg.shape` is `(5,)` or `(7,)` per `from_field_info`.

### Pattern 2: Infield skin via `layout.shapes` with layer="below"
**What:** Draw the dirt infield arc (radius ~95 ft) as a shape, not a trace.
**When to use:** D-01 infield skin. Use `type="path"` with an SVG path string for the fan shape, or simpler: clip a full circle via `type="circle"` centered at home plate and accept that it bleeds into the (white) foul territory — only the part inside the fair polygon is visible *if* the fair-territory fill is drawn over it. Alternative: use a clipped quarter-annulus path.

**Simpler approach (D-01 has Claude's discretion on this):** draw a filled circle at home with radius 95 ft, drawn **after** the fair-territory polygon (or with `layer="above"` the fair fill). Since fair territory covers only 90° around home, and the circle only extends 95 ft (well inside the fences), the visible dirt is automatically the fair-territory intersection. The parts of the circle that poke into foul territory will render over the white background — a minor visual asymmetry.

**Cleanest approach:** Build a ~40-vertex polygon (home → arc at 95 ft from -45° to +45° → home) as a second `go.Scatter(fill='toself')` trace, added AFTER the fair polygon. Guaranteed correct clipping, costs ~5 lines.

**Recommendation:** Second approach (polygon trace). Self-contained, testable, no `layer` / z-order subtlety.

```python
def _infield_skin_trace():
    arc_angles = np.linspace(-45.0, +45.0, 33)         # 33 points = smooth arc
    arc_rad = np.deg2rad(arc_angles)
    xs = np.concatenate(([0.0], INFIELD_SKIN_RADIUS_FT * np.sin(arc_rad), [0.0]))
    ys = np.concatenate(([0.0], INFIELD_SKIN_RADIUS_FT * np.cos(arc_rad), [0.0]))
    return go.Scatter(
        x=xs, y=ys, mode="lines", fill="toself",
        fillcolor=INFIELD_DIRT, line=dict(color=INFIELD_DIRT, width=0),
        hoverinfo="skip", showlegend=False, name="infield",
    )
```

### Pattern 3: `hovertemplate` with `customdata` ndarray
**What:** Pack 6 per-HR fields into a `(n, 6)` float/object ndarray and reference via positional indices.
**When to use:** D-07 — the only Phase 5 hover pattern.
**Example:**
```python
# Source: plotly.com/python/hover-text-and-formatting and Plotly 6 reference
customdata = np.column_stack([
    [ev.game_date.isoformat() for ev in view.plottable_events],
    [ev.opponent_abbr for ev in view.plottable_events],
    [ev.distance_ft for ev in view.plottable_events],
    [ev.launch_speed for ev in view.plottable_events],
    [ev.launch_angle for ev in view.plottable_events],
    [int(view.verdict_matrix.cleared[i, :].sum())
     for i in range(len(view.plottable_events))],
])

HOVERTEMPLATE = (
    "%{customdata[0]} vs %{customdata[1]}<br>"
    "Distance: %{customdata[2]:.0f} ft<br>"
    "Exit Velocity: %{customdata[3]:.1f} mph<br>"
    "Launch Angle: %{customdata[4]:.1f}°<br>"
    "Clears %{customdata[5]}/30 parks"
    "<extra></extra>"                                   # suppress trace-name box
)
```

**Important caveats:**
- `np.column_stack` on mixed str/float promotes to object dtype — this is fine for Plotly and is the idiomatic path. [VERIFIED: plotly community forum "Hovertemplate with customdata or hover_data of variable shape"]
- `%{customdata[2]:.0f}` uses d3-format specifiers (NOT Python format specs). `:.0f` for integers, `:.1f` for 1 decimal, `:,` for thousands separators.
- `<br>` for line breaks. Other safe HTML: `<b>`, `<i>`, `<sup>`. User-supplied strings (opponent abbreviations) are uppercase ASCII in MLB data — no XSS surface. No manual escaping needed.
- `<extra></extra>` at the end is **required** to kill Plotly's default right-side "secondary info box" that shows the trace name; otherwise the tooltip shows two boxes.

### Pattern 4: Per-point marker color via explicit list
**What:** D-05 requires uniform size/opacity/border; D-08 requires per-HR green or red based on `view.clears_selected_park[i]`.
```python
colors = [CLEARS if cleared else DOESNT_CLEAR for cleared in view.clears_selected_park]
# All HRs in one trace — one call, one legend entry, one hover config.
go.Scatter(
    x=xs, y=ys, mode="markers",
    marker=dict(
        size=12, opacity=0.7, symbol="circle",
        color=colors,
        line=dict(color=BORDER, width=1),
    ),
    customdata=customdata, hovertemplate=HOVERTEMPLATE,
    showlegend=False, name="hrs",
)
```
**Why one trace, not two (clears/doesn't-clear split):** simpler, one ordered x/y list that maps 1:1 to `plottable_events[i]`, easier to test (assert `len(trace.marker.color) == n_plottable`).

### Pattern 5: Fixed viewport + aspect ratio lock
**What:** D-04 requires fixed `[-450, 450] x [0, 500]` viewport with 1 ft = 1 ft.
```python
fig.update_layout(
    xaxis=dict(
        range=[-450, 450],
        visible=False,                  # no labels, grid, ticks
        fixedrange=True,                # disable user pan/zoom
        constrain="domain",             # CRITICAL — see pitfall #1
    ),
    yaxis=dict(
        range=[0, 500],
        visible=False,
        fixedrange=True,
        scaleanchor="x",                # 1 ft x = 1 ft y
        scaleratio=1,
        constrain="domain",
    ),
    plot_bgcolor="#ffffff",
    paper_bgcolor="#ffffff",
    margin=dict(l=10, r=10, t=10, b=10),
    showlegend=False,
    hovermode="closest",
)
```

### Pattern 6: Trace ordering / z-order
Plotly draws traces in the order they are added to `fig.data`; later = on top. [CITED: plotly.com/python/reference/scatter Scatter.zorder; plotly.com/python/reference/layout/shapes — default layer="above"]. For Phase 5:

```
1. fair_territory_trace        # bottom
2. infield_skin_trace
3. baselines_trace             # lines connecting home→1B→2B→3B→home
4. mound_trace OR mound_shape
5. bases_trace                 # 4 markers: home + 1B + 2B + 3B
6. hr_scatter_trace            # MUST BE LAST
```

If using `layout.shapes` for mound/infield instead of traces, set `layer="below"` on each shape — **otherwise shapes draw above traces by default**, burying the HR markers. [CITED: plotly.com/python/reference/layout/shapes]

### Pattern 7: Empty-events HR trace
D-12 + the empty-events test: `build_figure` must return a valid Figure even when `plottable_events` is empty. Emit an empty HR trace (`go.Scatter(x=[], y=[], mode="markers", ...)`) so the figure structure is identical across empty/non-empty states. Structural tests don't have to special-case len 0.

### Anti-Patterns to Avoid
- **Two traces per HR (one for marker, one for text label)** — wastes 50 traces; use `customdata` + `hovertemplate` instead.
- **`px.scatter` / Plotly Express** — PX is for DataFrames with auto-inferred encodings. Our traces are hand-composed from a dataclass. Stick with `graph_objects`.
- **`fig.add_annotation` for per-HR labels** — annotations are for persistent text, not hover. Don't.
- **Importing `streamlit` or `st.cache_data` in `chart.py`** — violates D-09 purity rule. The figure is cheap to build (~1 ms for 50 HRs); caching is unnecessary.
- **Hard-coded foul-pole angles (±45°)** — always read from `Park.angles_deg[0]` and `[-1]` so if the Park evolves to asymmetric curves later, the polygon follows. Phase 2's 5-point/7-point design already uses ±45° but the chart should be data-driven.
- **Forgetting `<extra></extra>` in hovertemplate** — produces a double-box tooltip. Easy to miss.
- **Computing `parks_cleared` as `int(...)` inline per HR in a list comp** — use the existing `VerdictMatrix.parks_cleared(i)` helper (already unit-tested in Phase 2).

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Polygon fill | SVG path string | `go.Scatter(fill='toself')` | Plotly closes the polygon and fills; testing is trivial (assert `x[0] == x[-1] == 0`). |
| Hover text per marker | Per-trace `text=` + custom JS | `customdata` + `hovertemplate` with `%{customdata[i]}` + d3-format specs | Native, vectorized, testable. |
| Aspect ratio lock | Manual figure size math | `yaxis.scaleanchor='x'` + `scaleratio=1` | One-line correct answer. |
| Axis hiding | Blank-string tick labels + hide grid | `xaxis.visible=False` | Hides labels, ticks, and grid in one flag. |
| Selected-park column lookup | Re-scan `view.parks` by `venue_id` | `view.verdict_matrix.venue_ids.tolist().index(view.venue_id)` — same pattern already used in `controller._clears_for_venue` | Matches existing project convention (D-08 alignment). |
| Parks-cleared count | `sum(1 for b in verdict_matrix.cleared[i] if b)` | `verdict_matrix.parks_cleared(i)` | Already unit-tested geometry helper. |
| Coord transform in chart | Re-implement atan2 + hypot | Import `CALIB_OX/OY/S` from `mlb_park.geometry.calibration` and do `(x, y) = (S*(coord_x - OX), S*(OY - coord_y))` | One source of truth for calibration. |

**Key insight:** every question the chart needs answered is already answered by a Phase 2 or Phase 4 module. The chart is a projection layer, not a computation layer. If you find yourself writing a loop that touches `verdict_matrix.cleared` or `spray_clamped_deg`, pause — there's probably a helper.

## Resolving `selected_park_idx`

CONTEXT.md flagged this as Claude's discretion. The options:

**Option A: Kwarg** — `build_figure(view, selected_park_idx=None)`. Caller (app.py) computes the index, passes in.
- **Against:** Duplicates `view.venue_id` — two ways to know the same thing, risk of drift. Caller in `app.py` would have to reach into `view.verdict_matrix.venue_ids` anyway; might as well do it inside `chart.py`.

**Option B: Derive internally from `view.venue_id`** — `build_figure(view)` calls `_resolve_selected_park_idx(view)`.
- **For:** Single-argument public API, matches the signature declared in D-09 exactly. View is self-contained.
- **For:** `view.clears_selected_park` is ALREADY pre-computed by the controller from `view.venue_id` — the chart doesn't actually need the column index to color markers (it consumes the per-HR bool tuple directly). The column index is only needed for the `parks_cleared_count` hover field, which can use `verdict_matrix.cleared[i, :].sum()` over the entire row — no selected-park index required.

**Recommendation: Option B, and in practice the chart never needs `selected_park_idx` at all.** Marker colors come from `view.clears_selected_park[i]`; parks-cleared-count comes from `verdict_matrix.cleared[i, :].sum()`. The `selected_park_idx` concept is a red herring — the controller already distilled everything the chart needs into view-level fields. The chart just needs to know **which Park to draw the outline for**, which is `view.parks_dict[view.venue_id]` — lookup by venue_id, not index.

Wait — `ViewModel` doesn't expose `parks`. Let me re-check.

**[VERIFIED: src/mlb_park/controller.py ViewModel dataclass]** — `ViewModel` has `venue_id`, `venue_name`, and the verdict matrix exposes `parks: tuple[Park, ...]` and `venue_ids: np.ndarray`. So: `selected_park = view.verdict_matrix.parks[view.verdict_matrix.venue_ids.tolist().index(view.venue_id)]`.

**Empty-state caveat:** when `plottable_events` is empty, `view.verdict_matrix is None`. In that case we still need to draw the stadium outline, so the chart needs access to the `Park` object another way. Two options:

1. **Load parks dict inside chart.py** — forbidden, it calls `load_all_parks()` which is `@st.cache_data`-decorated in services. Violates purity (chart would transitively import streamlit).
2. **Extend ViewModel with a `selected_park: Park | None` field** — requires a Phase 4 amendment but is 3 lines in `controller.build_view`. Clean.
3. **Accept `Park` as a second kwarg** — breaks single-arg D-09.

**Recommendation:** amend the ViewModel to carry `selected_park: Park` (always populated — `load_parks()` is called in `build_view` regardless of whether any HR is plottable). This is the cleanest path and keeps `chart.py` pure. **Flag for planner:** Phase 5 Wave 0 should extend `ViewModel` and `build_view` to populate `selected_park` before `chart.build_figure` can consume it.

**Alternative recommendation:** keep `ViewModel` untouched and have `build_figure` take `(view, park)` as two positional args — still pure, still single-origin (app.py already has `parks_map` from `load_all_parks`). **This is the smaller-blast-radius option** and I recommend it unless the planner is comfortable editing the ViewModel. D-09 says `build_figure(view: ViewModel)` — the planner should either relax that to `(view, park)` or add `selected_park` to the view. Both are valid; pick one during discuss/planning.

## Common Pitfalls

### Pitfall 1: `scaleanchor` + `range` fights the container and "auto-expands"
**What goes wrong:** With `scaleanchor='x'` + `scaleratio=1` + explicit `range=[0, 500]` on Y and `range=[-450, 450]` on X, Plotly's default behavior is to *extend* one axis's range to preserve the aspect ratio inside the Streamlit container's width. The visible chart ends up with X much wider than [-450, 450] when the container is wide.
**Why it happens:** `scaleanchor` guarantees pixel-per-unit equality, but the displayed range is whichever is larger — the requested range OR the range implied by the container size.
**How to avoid:** Add `constrain='domain'` on both axes. This tells Plotly to shrink the *plot domain* (padding) instead of expanding the range. [CITED: plotly community "Setting range overrides aspect ratio"]
**Warning signs:** Chart looks zoomed-out on wide screens; fence line appears far from the viewport edge.

### Pitfall 2: `layout.shapes` default layer is "above" — buries HRs
**What goes wrong:** Add a circle shape for the mound → the mound renders over HR markers, even if the HR scatter trace was added last.
**Why it happens:** Plotly shapes default to `layer="above"` (above all traces). Trace z-order only compares traces to traces. [CITED: plotly.com/python/reference/layout/shapes]
**How to avoid:** Set `layer="below"` on every shape, OR (preferred) use `go.Scatter` traces for every visual element so trace-order alone determines z-order. The recommended pattern here uses all traces, zero shapes.
**Warning signs:** Mound/infield appear to mask HRs near the plate.

### Pitfall 3: `customdata` dtype mismatch with `%{customdata[i]:.0f}`
**What goes wrong:** A string in a column (e.g., `opponent_abbr`) promotes the entire `np.column_stack` result to `dtype=object`. Then `%{customdata[2]:.0f}` silently renders "nan" or the raw Python repr when the float column is wrapped in an object array.
**Why it happens:** Plotly's d3-format for object dtypes can be brittle. Most of the time it works — distances render as floats — but edge cases (None, integer-typed ndarray) fail quietly.
**How to avoid:** Coerce all fields to `str` before stacking and drop the `:.0f` / `:.1f` specifiers in the template — do Python-side formatting (`f"{dist:.0f}"`) during customdata construction. More verbose but bulletproof.
**Warning signs:** Tooltip shows "nan" or "None" for some HRs.
**Pre-emptive test:** assert that `hovertemplate.count("%{customdata[")` equals 6 (once per field) AND that `customdata.shape == (n_plottable, 6)`.

### Pitfall 4: `Park.angles_deg` is 5 or 7 points — polygon must not assume 7
**What goes wrong:** Developer writes `xs = fence_ft * sin(angles)` hard-coded to 7 elements; the 5 venues using the 5-point curve produce a pentagon instead of a fan.
**Why it happens:** `Park.from_field_info` falls back to the 5-point curve when either `left` or `right` is missing [VERIFIED: src/mlb_park/geometry/park.py lines 50-64].
**How to avoid:** Let `len(angles_deg)` drive the loop. The recommended implementation uses `park.fence_ft * np.sin(...)` on the ndarray directly — correct for both lengths.
**Warning signs:** Some parks look angular; the "gap" between CF and LF/RF disappears.
**Test:** run structural tests against both a 5-point fixture park AND a 7-point fixture park.

### Pitfall 5: `use_container_width` deprecated after 2025-12-31
**What goes wrong:** Streamlit 2026 release notes mark `use_container_width=True` for removal after 2025-12-31 in favor of `width="stretch"` [CITED: discuss.streamlit.io/t/cursorrules-for-deprecated-use-container-width]. The current (1.56.0) version still accepts it with a DeprecationWarning.
**Why it happens:** Streamlit 1.55+ migrated chart sizing to a unified `width` API.
**How to avoid:** Use `st.plotly_chart(fig, use_container_width=True)` for now (it works through at least Streamlit 1.x); file a v2 backlog item to switch to `width="stretch"` when Streamlit 2.x lands. For Phase 5, either is acceptable — CONTEXT.md's D-09 quotes `use_container_width=True` so keep that as the written decision; planner may choose to use `width="stretch"` and note the equivalence.
**Warning signs:** DeprecationWarning in the Streamlit console on first render.

### Pitfall 6: Hovertemplate HTML escaping + d3-format confusion
**What goes wrong:** Developer writes `%{customdata[2]:.0f}ft` without a space → renders as "472ft"; writes `%{customdata[2]:,}` expecting thousands → gets literal `:,` because only certain d3 specs are recognized.
**Why it happens:** d3-format ≠ Python f-string.
**How to avoid:** Stick to `:.0f`, `:.1f`, `:.2f`. Put the unit label as literal text in the template: `Distance: %{customdata[2]:.0f} ft`.
**Warning signs:** Tooltip shows `:,` or `:f` literally.

### Pitfall 7: `st.plotly_chart` on_select triggers reruns
**What goes wrong:** If we ever add `on_select="rerun"` for click interactions, every HR click re-runs the whole script. In Phase 5 we don't use this, but it's worth a note for Phase 6 polish.
**Why it happens:** Streamlit's interaction model. Hover alone does NOT trigger a rerun (hover is client-side in Plotly). [CITED: docs.streamlit.io/develop/api-reference/charts/st.plotly_chart]
**How to avoid:** Do NOT set `on_select` in Phase 5. Default is no rerun; hover tooltips are free.
**Warning signs:** Page flickers on HR hover (would indicate on_select is set).

### Pitfall 8: Polygon not closed → `fill='toself'` fills the convex hull
**What goes wrong:** Forget to append `(0, 0)` as the final vertex; Plotly fills the implicit closure anyway, but a gap in the line stroke may show.
**Why it happens:** `fill='toself'` closes gaps within a single trace but the visual outline stroke only connects the points you provide.
**How to avoid:** Always append `(0, 0)` explicitly as the first AND last vertex.
**Test assertion:** `assert fair_trace.x[0] == fair_trace.x[-1] == 0 and fair_trace.y[0] == fair_trace.y[-1] == 0`.

## Runtime State Inventory

Not applicable — Phase 5 adds a new module (`chart.py`) plus a small edit to `app.py`. There is no rename, refactor, or migration. No stored data, live services, OS registrations, secrets, or build artifacts are affected.

## Code Examples

### build_figure skeleton (illustrative, not complete)
```python
# src/mlb_park/chart.py (illustrative structure)
from __future__ import annotations

import numpy as np
import plotly.graph_objects as go

from mlb_park.controller import ViewModel
from mlb_park.geometry.park import Park
from mlb_park.geometry.calibration import CALIB_OX, CALIB_OY, CALIB_S

# --- Constants (D-02, D-08) ---
MOUND_DISTANCE_FT = 60.5
BASE_DISTANCE_FT = 90.0
INFIELD_SKIN_RADIUS_FT = 95.0
HOME_PLATE_SIZE_FT = 1.5
BASE_MARKER_SIZE_FT = 1.25

CLEARS = "#2ca02c"
DOESNT_CLEAR = "#d62728"
FAIR_TERRITORY = "#e8f5e9"
INFIELD_DIRT = "#c1a17a"
MOUND_DIRT = "#c1a17a"
BASES_FG = "#ffffff"
HOME_PLATE_FG = "#ffffff"
BORDER = "#ffffff"

X_RANGE = [-450, 450]
Y_RANGE = [0, 500]


def build_figure(view: ViewModel, park: Park) -> go.Figure:
    """Build a Plotly spray chart for the given view + selected park.

    Pure: no Streamlit, no I/O. `park` is the Park object for view.venue_id;
    caller (app.py) resolves it from the parks_map already in scope.
    """
    fig = go.Figure()
    fig.add_trace(_fair_territory_trace(park))
    fig.add_trace(_infield_skin_trace())
    fig.add_trace(_baselines_trace())
    fig.add_trace(_mound_trace())
    fig.add_trace(_bases_trace())
    fig.add_trace(_hr_scatter_trace(view))   # LAST — must be on top
    _apply_layout(fig)
    return fig
```

### HR scatter trace
```python
def _hr_scatter_trace(view: ViewModel) -> go.Scatter:
    if not view.plottable_events:
        return go.Scatter(
            x=[], y=[], mode="markers", marker=dict(size=12),
            showlegend=False, name="hrs", hoverinfo="skip",
        )

    # Raw-coord transform (preserves true HR bearing, not clamped angle).
    xs = [CALIB_S * (ev.coord_x - CALIB_OX) for ev in view.plottable_events]
    ys = [CALIB_S * (CALIB_OY - ev.coord_y) for ev in view.plottable_events]

    colors = [CLEARS if cleared else DOESNT_CLEAR
              for cleared in view.clears_selected_park]

    # Pre-format every field to string → bulletproof d3-format (pitfall 3).
    n = len(view.plottable_events)
    customdata = np.empty((n, 6), dtype=object)
    for i, ev in enumerate(view.plottable_events):
        cleared_count = int(view.verdict_matrix.cleared[i, :].sum())
        customdata[i] = [
            ev.game_date.isoformat(),
            ev.opponent_abbr,
            f"{ev.distance_ft:.0f}",
            f"{ev.launch_speed:.1f}" if ev.launch_speed is not None else "—",
            f"{ev.launch_angle:.1f}" if ev.launch_angle is not None else "—",
            cleared_count,
        ]

    hovertemplate = (
        "%{customdata[0]} vs %{customdata[1]}<br>"
        "Distance: %{customdata[2]} ft<br>"
        "Exit Velocity: %{customdata[3]} mph<br>"
        "Launch Angle: %{customdata[4]}°<br>"
        "Clears %{customdata[5]}/30 parks"
        "<extra></extra>"
    )

    return go.Scatter(
        x=xs, y=ys, mode="markers",
        marker=dict(
            size=12, opacity=0.7, symbol="circle",
            color=colors, line=dict(color=BORDER, width=1),
        ),
        customdata=customdata, hovertemplate=hovertemplate,
        showlegend=False, name="hrs",
    )
```

### Layout
```python
def _apply_layout(fig: go.Figure) -> None:
    fig.update_layout(
        xaxis=dict(range=X_RANGE, visible=False, fixedrange=True, constrain="domain"),
        yaxis=dict(range=Y_RANGE, visible=False, fixedrange=True,
                   scaleanchor="x", scaleratio=1, constrain="domain"),
        plot_bgcolor="#ffffff",
        paper_bgcolor="#ffffff",
        margin=dict(l=10, r=10, t=10, b=10),
        showlegend=False,
        hovermode="closest",
    )
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `st.plotly_chart(fig, use_container_width=True)` | `st.plotly_chart(fig, width="stretch")` | Streamlit 1.55+ (2026-01); `use_container_width` removal after 2025-12-31 | Non-blocking; old form still works with a DeprecationWarning. Safe for Phase 5 as written in D-09. |
| `px.scatter` for everything | `go.Scatter` for hand-composed figures, `px` for DataFrame-driven charts | Stable since Plotly 5.x | We use `go` — matches our dataclass-first data shape. |
| Plotly 5.x Figure dict manipulation | Plotly 6.x same API; additional performance improvements | 6.0 (2024) | No code change required. |

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `np.column_stack` with mixed str/float produces `dtype=object` arrays that Plotly handles correctly for `customdata` | Pattern 3 + Pitfall 3 | Low — if d3-format misbehaves, fall back to pre-formatting strings (already recommended as the safe path). |
| A2 | `constrain="domain"` on both axes prevents range auto-expansion when combined with `scaleanchor` in Streamlit's flexbox container | Pitfall 1 | Medium — the plotly community thread confirms this pattern but was a couple of years old. Mitigation: Wave 3 manual smoke test (visual inspection) catches any remaining auto-expansion. |
| A3 | `view.verdict_matrix is None` only when `plottable_events` is empty | §Resolving selected_park_idx | Low — verified in controller.py lines 309-318; the invariant is documented in `ViewModel.verdict_matrix` doctring. |
| A4 | Hover does NOT trigger Streamlit reruns (only `on_select="rerun"` does) | Pitfall 7 | Low — this is documented Streamlit behavior and easy to confirm in manual smoke. |
| A5 | Plotly 6 `go.Scatter.marker.color` accepts a list of hex strings per-point (not a single color) | Pattern 4 | Very low — this is canonical Plotly usage since v1. |

## Open Questions

1. **Does D-09's `build_figure(view: ViewModel)` signature permit amendment to `build_figure(view, park)`?**
   - What we know: D-09 uses the single-arg form verbatim. CONTEXT.md lists "Whether to expose selected_park_idx as kwarg or derive from view.venue_id" as Claude's discretion.
   - What's unclear: whether "discretion" extends to adding a `park` positional arg.
   - Recommendation: either (a) plan a tiny ViewModel amendment to carry `selected_park: Park` (cleanest, one-line change in `build_view`), or (b) use `build_figure(view, park)` with a note that D-09's wording should be relaxed. **Prefer (a).** The planner should lock this in Wave 0.

2. **Infield skin as filled polygon vs layout.shape?**
   - What we know: both work; CONTEXT.md lists as Claude's discretion.
   - Recommendation: polygon trace (Pattern 2, second approach). Testable, self-clipping, z-order-safe.

3. **Base marker visual: `symbol="diamond"` vs a small square rotated 45°?**
   - What we know: no strong preference in CONTEXT.
   - Recommendation: `symbol="square"` with white fill; Plotly's "diamond" symbol is actually rotated-square and reads fine. 14 px size. Defer visual tuning to Wave 3 smoke.

## Validation Architecture

`workflow.nyquist_validation = true` per `.planning/config.json` → section REQUIRED.

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.x [VERIFIED: requirements.txt] |
| Config file | None yet (pytest auto-discovers `tests/` at repo root per project convention) — see existing `tests/conftest.py` |
| Quick run command | `pytest tests/test_chart.py -x -q` |
| Full suite command | `pytest -q` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| VIZ-01 | Selected stadium outline renders scaled in feet; both 5-point and 7-point fence curves produce closed polygons | unit (structural) | `pytest tests/test_chart.py::test_fair_territory_polygon_closed -x` | ❌ Wave 0 |
| VIZ-01 | Fixed viewport applied: `xaxis.range == [-450, 450]`, `yaxis.range == [0, 500]`, `yaxis.scaleanchor == "x"`, `scaleratio == 1.0` | unit (structural) | `pytest tests/test_chart.py::test_layout_ranges_and_aspect_ratio -x` | ❌ Wave 0 |
| VIZ-01 | Axes hidden (`xaxis.visible == False`, `yaxis.visible == False`) | unit (structural) | `pytest tests/test_chart.py::test_axes_hidden -x` | ❌ Wave 0 |
| VIZ-02 | HR scatter marker colors are all hex `#2ca02c` (CLEARS) or `#d62728` (DOESNT_CLEAR); colors map 1:1 to `view.clears_selected_park` | unit (structural) | `pytest tests/test_chart.py::test_hr_marker_colors_match_clears_tuple -x` | ❌ Wave 0 |
| VIZ-02 | HR trace is the LAST trace (z-order correctness) | unit (structural) | `pytest tests/test_chart.py::test_hr_scatter_is_last_trace -x` | ❌ Wave 0 |
| VIZ-03 | `hovertemplate` string contains tokens for all 6 fields (`%{customdata[0]}`..`%{customdata[5]}`) and the literal labels (`Distance`, `Exit Velocity`, `Launch Angle`, `Clears`, `ft`, `mph`, `°`, `/30`) | unit | `pytest tests/test_chart.py::test_hovertemplate_has_six_fields -x` | ❌ Wave 0 |
| VIZ-03 | `customdata` shape is `(n_plottable, 6)` with per-HR `parks_cleared_count` matching `verdict_matrix.cleared[i, :].sum()` | unit | `pytest tests/test_chart.py::test_customdata_shape_and_cleared_count -x` | ❌ Wave 0 |
| D-06 | Given fixture view with empty `plottable_events`, `build_figure` returns a valid Figure with empty HR trace (x=[], y=[]) and stadium outline present | unit | `pytest tests/test_chart.py::test_empty_plottable_events -x` | ❌ Wave 0 |
| D-09 | Purity: `chart.py` source contains no `import streamlit`, no `from streamlit`, no `st.session_state` | unit | `pytest tests/test_chart_purity.py::test_no_streamlit_in_chart_module -x` | ❌ Wave 0 |
| D-10 | Fair polygon iterates `len(park.angles_deg)` — works for both 5pt and 7pt parks | unit (parametrized) | `pytest tests/test_chart.py::test_fair_polygon_handles_five_and_seven_points -x` | ❌ Wave 0 |
| VIZ-01..03 | End-to-end: app.py renders the chart in the `else` branch without exceptions (manual smoke, existing Judge fixtures) | manual smoke | `streamlit run src/mlb_park/app.py` → select Yankees → Judge → any park → visual inspection | n/a |

### Sampling Rate
- **Per task commit:** `pytest tests/test_chart.py tests/test_chart_purity.py -x -q`
- **Per wave merge:** `pytest -q` (full suite)
- **Phase gate:** Full suite green + manual smoke confirmed (spray chart visible, hover works, color verdict matches selected park) before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] `tests/test_chart.py` — all VIZ-01/02/03 + D-06 + D-10 structural assertions
- [ ] `tests/test_chart_purity.py` — mirrors `tests/controller/test_purity.py`, points at `mlb_park.chart`
- [ ] Shared fixture: a minimal `ViewModel` factory in `tests/conftest.py` OR `tests/fixtures/` — provide both a non-empty (Judge 6-HR fixture) and empty-events variant. Can reuse existing Judge pipeline fixtures from Phase 3.
- [ ] Fixture park: at least one 5-point park (e.g., Fenway if its fieldInfo omits `left`/`right`) AND one 7-point park (e.g., Yankee Stadium) so `test_fair_polygon_handles_five_and_seven_points` can parametrize across both. Existing `tests/fixtures/` likely already has these — confirm during Wave 0.

### Structural test idioms (no headless browser)

```python
# tests/test_chart.py
import numpy as np
import plotly.graph_objects as go
from mlb_park import chart

def test_layout_ranges_and_aspect_ratio(sample_view, sample_park):
    fig = chart.build_figure(sample_view, sample_park)
    assert fig.layout.xaxis.range == (-450, 450)
    assert fig.layout.yaxis.range == (0, 500)
    assert fig.layout.yaxis.scaleanchor == "x"
    assert fig.layout.yaxis.scaleratio == 1.0
    assert fig.layout.xaxis.visible is False
    assert fig.layout.yaxis.visible is False

def test_fair_territory_polygon_closed(sample_view, sample_park):
    fig = chart.build_figure(sample_view, sample_park)
    fair = fig.data[0]  # first trace by convention
    assert fair.name == "fair"
    assert fair.x[0] == 0 and fair.x[-1] == 0
    assert fair.y[0] == 0 and fair.y[-1] == 0
    assert fair.fill == "toself"

def test_hr_scatter_is_last_trace(sample_view, sample_park):
    fig = chart.build_figure(sample_view, sample_park)
    assert fig.data[-1].name == "hrs"

def test_hr_marker_colors_match_clears_tuple(sample_view, sample_park):
    fig = chart.build_figure(sample_view, sample_park)
    hrs = fig.data[-1]
    expected = [chart.CLEARS if c else chart.DOESNT_CLEAR
                for c in sample_view.clears_selected_park]
    assert list(hrs.marker.color) == expected

def test_hovertemplate_has_six_fields(sample_view, sample_park):
    fig = chart.build_figure(sample_view, sample_park)
    hrs = fig.data[-1]
    tpl = hrs.hovertemplate
    for i in range(6):
        assert f"%{{customdata[{i}]}}" in tpl
    for literal in ("Distance", "Exit Velocity", "Launch Angle", "Clears", "ft", "mph", "/30"):
        assert literal in tpl
    assert "<extra></extra>" in tpl

def test_empty_plottable_events(empty_view, sample_park):
    fig = chart.build_figure(empty_view, sample_park)
    hrs = fig.data[-1]
    assert len(hrs.x) == 0 and len(hrs.y) == 0
    # Stadium outline still present
    assert fig.data[0].name == "fair"
```

```python
# tests/test_chart_purity.py (mirrors tests/controller/test_purity.py)
from pathlib import Path
from mlb_park import chart as chart_module

def test_no_streamlit_in_chart_module():
    src = Path(chart_module.__file__).read_text(encoding="utf-8")
    assert "import streamlit" not in src
    assert "from streamlit" not in src
    assert "st.session_state" not in src
```

**No headless browser / no image regression tests.** Rendering correctness is validated by Wave 3 manual smoke. Structural tests cover the data+layout contract; pixels are out of scope for this hobby app.

## Security Domain

Skipped — `security_enforcement` is not configured in `.planning/config.json`, and this phase touches no authn, authz, session, crypto, or user input. The only "input" is a structurally-validated `ViewModel` dataclass produced upstream.

## Sources

### Primary (HIGH confidence)
- `src/mlb_park/geometry/transform.py` — coordinate convention VERIFIED.
- `src/mlb_park/geometry/park.py` — `Park.angles_deg`/`fence_ft` shape (5 or 7) VERIFIED.
- `src/mlb_park/geometry/verdict.py` — `VerdictMatrix.cleared`, `parks_cleared()`, `venue_ids` VERIFIED.
- `src/mlb_park/controller.py` — `ViewModel` fields + `_clears_for_venue` VERIFIED.
- `src/mlb_park/pipeline/events.py` — `HREvent` field list VERIFIED.
- `tests/controller/test_purity.py` — purity-test pattern to replicate VERIFIED.
- [`st.plotly_chart` docs](https://docs.streamlit.io/develop/api-reference/charts/st.plotly_chart) — hover does not trigger reruns; `theme` and `use_container_width` behavior.
- [Plotly python API reference — Scatter](https://plotly.com/python-api-reference/generated/plotly.graph_objects.Scatter.html) — `fill='toself'`, `marker.color` per-point, `customdata`, `hovertemplate`, `zorder`.
- [Plotly layout.shapes reference](https://plotly.com/python/reference/layout/shapes/) — default `layer="above"` gotcha.

### Secondary (MEDIUM confidence)
- [Plotly hover-text-and-formatting docs](https://plotly.com/python/hover-text-and-formatting/) — d3-format specifiers, `%{customdata[i]}` syntax.
- [Plotly Axes docs — constrain='domain'](https://plotly.com/python/axes/) — interaction between `scaleanchor` and explicit `range`.
- [Plotly community — Setting range overrides aspect ratio](https://community.plotly.com/t/setting-range-overrides-aspect-ratio/77187) — confirms `constrain='domain'` fix.
- [Streamlit release notes 2025](https://docs.streamlit.io/develop/quick-reference/release-notes/2025) — `use_container_width` deprecation timeline.
- [Plotly figure introspection docs](https://plotly.com/python/figure-introspection/) — `fig.data`, `fig.layout` direct access for tests.

### Tertiary (LOW confidence — unused)
- None. All recommendations cross-verified against official docs or source code.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — Plotly 6.7 + numpy already pinned; no new deps.
- Architecture: HIGH — single pure module, pattern mirrors `controller.py`.
- Pitfalls: HIGH — all 8 confirmed via official docs or plotly community threads.
- Coordinate convention: HIGH — directly verified against `transform.py` source.
- `selected_park_idx` resolution: MEDIUM — final choice (ViewModel amendment vs. two-arg `build_figure`) flagged for planner decision.

**Research date:** 2026-04-15
**Valid until:** 2026-05-15 (30 days; stack is stable, only Streamlit `use_container_width` deprecation has a concrete 2025-12-31 cutoff already past — migrate to `width="stretch"` at planner's discretion).
