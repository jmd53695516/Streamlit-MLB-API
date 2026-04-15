"""Phase 3 pipeline data contracts (D-05, D-13).

Pure data only — no parsing, no network, no logging. Parsing logic lives in
pipeline/extract.py (Plan 03-02). Keeping this module dependency-light means
downstream agents and callers can import the types without pulling the full
extraction surface area.

Shapes:
  - HREvent: rich per-HR record (15 fields) consumed by Phase 4+ controllers.
  - PipelineResult: events+errors envelope returned by extract_hrs.
  - PipelineError: per-failure record captured during extraction.
"""
from __future__ import annotations

import datetime
from dataclasses import dataclass


@dataclass(frozen=True)
class HREvent:
    """One home run (D-05).

    Fields are split into three groups:
      - Core identity: game_pk, game_date, opponent_abbr, inning, half_inning, play_idx
      - Measurements (Optional — None when has_* flags are False):
          distance_ft, coord_x, coord_y, launch_speed, launch_angle
      - Degradation flags: has_distance, has_coords, has_launch_stats, is_itp
    """

    # Core identity
    game_pk: int
    game_date: datetime.date
    opponent_abbr: str
    inning: int
    half_inning: str
    play_idx: int

    # Measurements (may be None when has_* flags are False)
    distance_ft: float | None
    coord_x: float | None
    coord_y: float | None
    launch_speed: float | None
    launch_angle: float | None

    # Degradation flags (D-11, D-12)
    has_distance: bool
    has_coords: bool
    has_launch_stats: bool
    is_itp: bool


@dataclass(frozen=True)
class PipelineError:
    """Per-failure record (D-13, D-14).

    `game_pk=None` signals a gameLog-level failure (no per-game context).
    """

    game_pk: int | None
    endpoint: str
    message: str


@dataclass(frozen=True)
class PipelineResult:
    """Events + errors envelope returned by extract_hrs (D-13).

    events are chronological by (game_date asc, play_idx asc).
    """

    events: tuple[HREvent, ...]
    errors: tuple[PipelineError, ...]
    season: int
    player_id: int
