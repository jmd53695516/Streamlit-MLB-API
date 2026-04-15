"""Contract tests for mlb_park.pipeline dataclasses (D-05, D-13, D-16, D-18).

Proves:
  1. CURRENT_SEASON constant exists and equals 2026.
  2. Package re-exports HREvent, PipelineResult, PipelineError.
  3. HREvent constructs with all 15 D-05 fields.
  4. HREvent is frozen (mutation raises FrozenInstanceError).
  5. PipelineResult stores events as a tuple.
  6. PipelineError accepts Optional[int] game_pk.
"""
from __future__ import annotations

import datetime
from dataclasses import FrozenInstanceError

import pytest


def test_current_season_constant() -> None:
    """D-16: CURRENT_SEASON importable from mlb_park.config and equals 2026."""
    from mlb_park.config import CURRENT_SEASON

    assert CURRENT_SEASON == 2026


def test_pipeline_package_reexports() -> None:
    """D-18: mlb_park.pipeline re-exports the three public dataclasses."""
    from mlb_park.pipeline import HREvent, PipelineError, PipelineResult

    assert HREvent is not None
    assert PipelineError is not None
    assert PipelineResult is not None


def test_hrevent_constructs_with_all_15_fields() -> None:
    """D-05: HREvent accepts all 15 fields with correct types."""
    from mlb_park.pipeline import HREvent

    event = HREvent(
        game_pk=900001,
        game_date=datetime.date(2026, 4, 13),
        opponent_abbr="HOU",
        inning=1,
        half_inning="bottom",
        play_idx=0,
        distance_ft=420.5,
        coord_x=121.0,
        coord_y=92.0,
        launch_speed=107.5,
        launch_angle=26.0,
        has_distance=True,
        has_coords=True,
        has_launch_stats=True,
        is_itp=False,
    )

    assert event.game_pk == 900001
    assert event.game_date == datetime.date(2026, 4, 13)
    assert event.opponent_abbr == "HOU"
    assert event.inning == 1
    assert event.half_inning == "bottom"
    assert event.play_idx == 0
    assert event.distance_ft == 420.5
    assert event.coord_x == 121.0
    assert event.coord_y == 92.0
    assert event.launch_speed == 107.5
    assert event.launch_angle == 26.0
    assert event.has_distance is True
    assert event.has_coords is True
    assert event.has_launch_stats is True
    assert event.is_itp is False


def test_hrevent_is_frozen() -> None:
    """D-05: HREvent is a frozen dataclass — mutation raises FrozenInstanceError."""
    from mlb_park.pipeline import HREvent

    event = HREvent(
        game_pk=900001,
        game_date=datetime.date(2026, 4, 13),
        opponent_abbr="HOU",
        inning=1,
        half_inning="bottom",
        play_idx=0,
        distance_ft=None,
        coord_x=None,
        coord_y=None,
        launch_speed=None,
        launch_angle=None,
        has_distance=False,
        has_coords=False,
        has_launch_stats=False,
        is_itp=False,
    )
    with pytest.raises(FrozenInstanceError):
        event.game_pk = 900002  # type: ignore[misc]


def test_pipeline_result_stores_events_as_tuple() -> None:
    """D-13: PipelineResult.events is a tuple (not list)."""
    from mlb_park.pipeline import PipelineResult

    result = PipelineResult(events=(), errors=(), season=2026, player_id=592450)
    assert isinstance(result.events, tuple)
    assert isinstance(result.errors, tuple)
    assert result.season == 2026
    assert result.player_id == 592450


def test_pipeline_error_accepts_optional_game_pk() -> None:
    """D-13: PipelineError.game_pk may be None (gameLog-level failure)."""
    from mlb_park.pipeline import PipelineError

    err = PipelineError(game_pk=None, endpoint="game_log", message="x")
    assert err.game_pk is None
    assert err.endpoint == "game_log"
    assert err.message == "x"
