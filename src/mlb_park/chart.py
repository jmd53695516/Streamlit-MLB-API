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

    Wave 1 scaffold: returns a Figure with only an empty HR-trace placeholder
    and the locked layout applied. Fair-territory + infield + bases traces
    land in Plan 05-02 (Wave 2); HR scatter + hover + customdata land in
    Plan 05-03 (Wave 3).
    """
    fig = go.Figure()
    # Wave 2 will insert: _fair_territory_trace(park), _infield_skin_trace(),
    # _baselines_trace(), _mound_trace(), _bases_trace() BEFORE the HR trace.
    fig.add_trace(_hr_scatter_trace(view))  # ALWAYS LAST (D-01 z-order)
    _apply_layout(fig)
    return fig


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
