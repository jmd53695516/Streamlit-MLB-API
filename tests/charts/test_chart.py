"""Phase 5 chart structural tests (VIZ-01, VIZ-02, VIZ-03, D-06, D-10).

No headless browser, no image diff -- asserts over fig.data and fig.layout directly.

Wave 0 state: 4 tests PASS (layout + axes + hr-last + empty), 5 tests FAIL
(fair polygon + colors + hover + customdata -- gates for Waves 2 and 3).
"""
from __future__ import annotations

import numpy as np
import plotly.graph_objects as go
import pytest

from mlb_park import chart


# --- VIZ-01: Fair-territory polygon ---

def test_fair_territory_polygon_closed(sample_view, sample_park):
    fig = chart.build_figure(sample_view, sample_park)
    fair = next((t for t in fig.data if t.name == "fair"), None)
    assert fair is not None, "fair-territory trace named 'fair' not found"
    assert fair.x[0] == 0 and fair.x[-1] == 0
    assert fair.y[0] == 0 and fair.y[-1] == 0
    assert fair.fill == "toself"


def test_fair_polygon_handles_five_and_seven_points(sample_view, fenway_park_5pt, yankee_park_7pt):
    for park, expected_edge in [(fenway_park_5pt, 5), (yankee_park_7pt, 7)]:
        fig = chart.build_figure(sample_view, park)
        fair = next(t for t in fig.data if t.name == "fair")
        # home + N fence pts + home = N+2 vertices
        assert len(fair.x) == expected_edge + 2, (
            f"park with {expected_edge}-point fence produced {len(fair.x)}-vertex polygon"
        )


# --- VIZ-01: Layout ---

def test_layout_ranges_and_aspect_ratio(sample_view, sample_park):
    fig = chart.build_figure(sample_view, sample_park)
    assert tuple(fig.layout.xaxis.range) == (-450, 450)
    assert tuple(fig.layout.yaxis.range) == (0, 500)
    assert fig.layout.yaxis.scaleanchor == "x"
    assert fig.layout.yaxis.scaleratio == 1.0


def test_axes_hidden(sample_view, sample_park):
    fig = chart.build_figure(sample_view, sample_park)
    assert fig.layout.xaxis.visible is False
    assert fig.layout.yaxis.visible is False


# --- VIZ-02: HR scatter trace ---

def test_hr_scatter_is_last_trace(sample_view, sample_park):
    fig = chart.build_figure(sample_view, sample_park)
    assert fig.data[-1].name == "hrs", (
        f"HR trace must be last; got order: {[t.name for t in fig.data]}"
    )


def test_hr_marker_colors_match_clears_tuple(sample_view, sample_park):
    fig = chart.build_figure(sample_view, sample_park)
    hrs = next(t for t in fig.data if t.name == "hrs")
    expected = [chart.CLEARS if c else chart.DOESNT_CLEAR
                for c in sample_view.clears_selected_park]
    assert list(hrs.marker.color) == expected


# --- VIZ-03: Hover ---

def test_hovertemplate_has_six_fields(sample_view, sample_park):
    fig = chart.build_figure(sample_view, sample_park)
    hrs = next(t for t in fig.data if t.name == "hrs")
    tpl = hrs.hovertemplate or ""
    for i in range(6):
        assert f"%{{customdata[{i}]}}" in tpl, f"missing customdata[{i}] in hovertemplate"
    for literal in ("Distance", "Exit Velocity", "Launch Angle", "Clears",
                    "ft", "mph", "/30"):
        assert literal in tpl, f"missing literal {literal!r} in hovertemplate"
    assert "<extra></extra>" in tpl


def test_customdata_shape_and_cleared_count(sample_view, sample_park):
    fig = chart.build_figure(sample_view, sample_park)
    hrs = next(t for t in fig.data if t.name == "hrs")
    n = len(sample_view.plottable_events)
    cd = np.asarray(hrs.customdata)
    assert cd.shape == (n, 6), f"customdata shape {cd.shape} != ({n}, 6)"
    # parks_cleared count in column 5 matches verdict_matrix.cleared[i, :].sum()
    for i in range(n):
        expected = int(sample_view.verdict_matrix.cleared[i, :].sum())
        assert int(cd[i, 5]) == expected


# --- D-06: Empty state ---

def test_empty_plottable_events(empty_view, sample_park):
    fig = chart.build_figure(empty_view, sample_park)
    hrs = next(t for t in fig.data if t.name == "hrs")
    assert len(hrs.x) == 0 and len(hrs.y) == 0
