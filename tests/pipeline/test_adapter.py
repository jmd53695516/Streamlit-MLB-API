"""D-06 adapter contract: HREvent -> HitData | None.

Also covers the Plan 03-03 public re-export surface at `mlb_park.pipeline`.
"""
from __future__ import annotations

import datetime

import pytest


def _make_event(
    *,
    has_distance: bool,
    has_coords: bool,
    distance_ft: float | None = 415.0,
    coord_x: float | None = 110.0,
    coord_y: float | None = 95.0,
    game_pk: int = 700001,
    play_idx: int = 7,
):
    """Build an HREvent with controllable degradation flags."""
    from mlb_park.pipeline import HREvent

    return HREvent(
        game_pk=game_pk,
        game_date=datetime.date(2026, 4, 13),
        opponent_abbr="LAA",
        inning=4,
        half_inning="top",
        play_idx=play_idx,
        distance_ft=distance_ft if has_distance else None,
        coord_x=coord_x if has_coords else None,
        coord_y=coord_y if has_coords else None,
        launch_speed=108.0,
        launch_angle=27.0,
        has_distance=has_distance,
        has_coords=has_coords,
        has_launch_stats=True,
        is_itp=False,
    )


# ---- Adapter contract -----------------------------------------------------


def test_adapter_returns_none_when_distance_missing():
    """B1: has_distance=False -> None even if coords exist."""
    from mlb_park.pipeline import hr_event_to_hit_data

    ev = _make_event(has_distance=False, has_coords=True, distance_ft=None)
    assert hr_event_to_hit_data(ev) is None


def test_adapter_returns_none_when_coords_missing():
    """B2: has_coords=False -> None even if distance exists."""
    from mlb_park.pipeline import hr_event_to_hit_data

    ev = _make_event(has_distance=True, has_coords=False, coord_x=None, coord_y=None)
    assert hr_event_to_hit_data(ev) is None


def test_adapter_returns_hitdata_when_both_present():
    """B3+B4+B5: full hitData -> HitData with mirrored fields and tuple identifier."""
    from mlb_park.pipeline import hr_event_to_hit_data
    from mlb_park.geometry.verdict import HitData

    ev = _make_event(has_distance=True, has_coords=True, game_pk=823568, play_idx=12)
    hd = hr_event_to_hit_data(ev)
    assert isinstance(hd, HitData)
    assert hd.distance_ft == 415.0
    assert hd.coord_x == 110.0
    assert hd.coord_y == 95.0
    assert hd.identifier == (823568, 12)


# ---- Re-export surface ----------------------------------------------------


def test_pipeline_public_api_re_exports():
    """B6: the documented surface imports without error from mlb_park.pipeline."""
    from mlb_park.pipeline import (  # noqa: F401
        extract_hrs,
        hr_event_to_hit_data,
        HREvent,
        PipelineResult,
        PipelineError,
        load_all_parks,
    )


def test_load_all_parks_is_identity_re_export():
    """B7: pipeline.load_all_parks IS services.mlb_api.load_all_parks (no wrapper)."""
    from mlb_park.pipeline import load_all_parks as via_pipeline
    from mlb_park.services.mlb_api import load_all_parks as via_services

    assert via_pipeline is via_services
