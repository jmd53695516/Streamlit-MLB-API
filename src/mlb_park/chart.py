"""Phase 5 spray chart -- pure Plotly figure construction.

D-09 purity rule: this module must stay free of any Streamlit dependency.
The module is imported by app.py (which does the Streamlit wiring) and by
tests/charts/*.

Public API (locked per research Q1 option b):
    build_figure(view: ViewModel, park: Park) -> go.Figure

`park` is the Park object for view.venue_id -- caller (app.py) resolves it
from parks_map (load_all_parks()) already in scope. This keeps the Phase 4
ViewModel dataclass untouched.
"""
from __future__ import annotations

import numpy as np
import plotly.graph_objects as go

from mlb_park.controller import ViewModel
from mlb_park.geometry.park import Park

# --- Color palette (D-08) ---
CLEARS = "#2ca02c"
DOESNT_CLEAR = "#d62728"
FAIR_TERRITORY = "#e8f5e9"
INFIELD_DIRT = "#c1a17a"
MOUND_DIRT = "#c1a17a"
BASES_FG = "#ffffff"
HOME_PLATE_FG = "#ffffff"
BORDER = "#ffffff"

# --- Infield dimensions (D-02 -- MLB regulation, same every park) ---
MOUND_DISTANCE_FT = 60.5
BASE_DISTANCE_FT = 90.0
INFIELD_SKIN_RADIUS_FT = 95.0
HOME_PLATE_SIZE_FT = 1.5
BASE_MARKER_SIZE_FT = 1.25

# --- Viewport (D-04 -- fixed across all 30 parks) ---
X_RANGE = [-450, 450]
Y_RANGE = [0, 500]


def build_figure(view: ViewModel, park: Park) -> go.Figure:
    """Build the spray chart Figure for `view` + selected `park`.

    Trace z-order (D-01): fair territory -> infield skin -> baselines ->
    mound -> bases -> HR scatter (LAST, always on top).
    """
    fig = go.Figure()
    fig.add_trace(_fair_territory_trace(park))
    fig.add_trace(_infield_skin_trace())
    fig.add_trace(_baselines_trace())
    fig.add_trace(_mound_trace())
    fig.add_trace(_bases_trace())
    fig.add_trace(_hr_scatter_trace(view))  # MUST remain last (D-01, Pitfall 2)
    _apply_layout(fig)
    return fig


def _fair_territory_trace(park: Park) -> go.Scatter:
    """Fair-territory polygon from Park fence curve (D-01, D-10).

    Vertices: home -> LF-line fence pt -> ... -> RF-line fence pt -> home.
    Transparently handles both 5-point (5 fence vertices) and 7-point (7 fence
    vertices) parks by iterating whatever length `park.angles_deg` supplies.

    Sign convention (D-11, verified vs transform.py):
        x = fence_ft * sin(angle_rad)    # + = RF, - = LF
        y = fence_ft * cos(angle_rad)    # always >= 0 in fair territory
    """
    angles_rad = np.deg2rad(park.angles_deg)
    xs = park.fence_ft * np.sin(angles_rad)
    ys = park.fence_ft * np.cos(angles_rad)
    x_closed = np.concatenate(([0.0], xs, [0.0]))
    y_closed = np.concatenate(([0.0], ys, [0.0]))
    return go.Scatter(
        x=x_closed, y=y_closed,
        mode="lines", fill="toself",
        fillcolor=FAIR_TERRITORY,
        line=dict(color=FAIR_TERRITORY, width=1),
        hoverinfo="skip", showlegend=False, name="fair",
    )


def _infield_skin_trace() -> go.Scatter:
    """Dirt infield as a quarter-annulus polygon (research Pattern 2).

    Radius INFIELD_SKIN_RADIUS_FT (95 ft) from home, spanning -45 deg to +45 deg in
    spray-angle space. Same every park -- MLB regulation (D-02).
    """
    arc_deg = np.linspace(-45.0, 45.0, 33)
    arc_rad = np.deg2rad(arc_deg)
    xs = np.concatenate(([0.0], INFIELD_SKIN_RADIUS_FT * np.sin(arc_rad), [0.0]))
    ys = np.concatenate(([0.0], INFIELD_SKIN_RADIUS_FT * np.cos(arc_rad), [0.0]))
    return go.Scatter(
        x=xs, y=ys, mode="lines", fill="toself",
        fillcolor=INFIELD_DIRT, line=dict(color=INFIELD_DIRT, width=0),
        hoverinfo="skip", showlegend=False, name="infield",
    )


# Base positions in chart coords -- 90-ft basepaths rotated +/-45 deg from CF axis.
_SQRT2_OVER_2 = float(np.sqrt(2.0) / 2.0)
_FIRST_BASE = (+BASE_DISTANCE_FT * _SQRT2_OVER_2, +BASE_DISTANCE_FT * _SQRT2_OVER_2)
_SECOND_BASE = (0.0, BASE_DISTANCE_FT * float(np.sqrt(2.0)))
_THIRD_BASE = (-BASE_DISTANCE_FT * _SQRT2_OVER_2, +BASE_DISTANCE_FT * _SQRT2_OVER_2)
_HOME_PLATE = (0.0, 0.0)


def _baselines_trace() -> go.Scatter:
    """Thin white lines connecting home -> 1B -> 2B -> 3B -> home (D-01)."""
    xs = [_HOME_PLATE[0], _FIRST_BASE[0], _SECOND_BASE[0], _THIRD_BASE[0], _HOME_PLATE[0]]
    ys = [_HOME_PLATE[1], _FIRST_BASE[1], _SECOND_BASE[1], _THIRD_BASE[1], _HOME_PLATE[1]]
    return go.Scatter(
        x=xs, y=ys, mode="lines",
        line=dict(color=BASES_FG, width=1.5),
        hoverinfo="skip", showlegend=False, name="baselines",
    )


def _mound_trace() -> go.Scatter:
    """Pitcher's mound -- small filled circle at (0, MOUND_DISTANCE_FT).

    Radius ~5 ft; rendered as a 25-vertex parametric circle closed into a
    fill='toself' polygon so z-order follows trace-add order (Pitfall 2).
    """
    theta = np.linspace(0.0, 2.0 * np.pi, 25)
    radius = 5.0
    xs = radius * np.cos(theta)
    ys = MOUND_DISTANCE_FT + radius * np.sin(theta)
    return go.Scatter(
        x=xs, y=ys, mode="lines", fill="toself",
        fillcolor=MOUND_DIRT, line=dict(color=MOUND_DIRT, width=0),
        hoverinfo="skip", showlegend=False, name="mound",
    )


def _bases_trace() -> go.Scatter:
    """Four base markers: home (pentagon) + 1B/2B/3B (diamonds).

    Single trace with per-point marker.symbol list. Home uses pentagon;
    the three bags use diamond (Plotly diamond is a rotated square).
    """
    xs = [_HOME_PLATE[0], _FIRST_BASE[0], _SECOND_BASE[0], _THIRD_BASE[0]]
    ys = [_HOME_PLATE[1], _FIRST_BASE[1], _SECOND_BASE[1], _THIRD_BASE[1]]
    symbols = ["pentagon", "diamond", "diamond", "diamond"]
    return go.Scatter(
        x=xs, y=ys, mode="markers",
        marker=dict(
            symbol=symbols, size=10,
            color=BASES_FG, line=dict(color="#888888", width=1),
        ),
        hoverinfo="skip", showlegend=False, name="bases",
    )


def _hr_scatter_trace(view: ViewModel) -> go.Scatter:
    """Wave 1 stub -- empty trace named 'hrs'. Wave 3 replaces the body."""
    return go.Scatter(
        x=[],
        y=[],
        mode="markers",
        marker=dict(
            size=12,
            opacity=0.7,
            symbol="circle",
            color=[],
            line=dict(color=BORDER, width=1),
        ),
        showlegend=False,
        name="hrs",
        hoverinfo="skip",
    )


def _apply_layout(fig: go.Figure) -> None:
    """Apply the locked D-04 viewport + aspect lock. Research pitfall 1: constrain='domain'."""
    fig.update_layout(
        xaxis=dict(
            range=X_RANGE,
            visible=False,
            fixedrange=True,
            constrain="domain",
        ),
        yaxis=dict(
            range=Y_RANGE,
            visible=False,
            fixedrange=True,
            scaleanchor="x",
            scaleratio=1,
            constrain="domain",
        ),
        plot_bgcolor="#ffffff",
        paper_bgcolor="#ffffff",
        margin=dict(l=10, r=10, t=10, b=10),
        showlegend=False,
        hovermode="closest",
    )


__all__ = ["build_figure"]
