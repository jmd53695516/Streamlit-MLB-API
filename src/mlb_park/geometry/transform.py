"""Gameday (coordX, coordY) → (spray_angle_deg, distance_ft) transform.

Pure-function layer over the fitted calibration constants (D-09 convention):
  * 0° points to CF, negative toward LF, positive toward RF.
  * dx = coordX - Ox,  dy = Oy - coordY  (Y-inverted so +dy → CF).
  * distance_ft   = s * sqrt(dx^2 + dy^2)
  * angle_raw_deg = degrees(atan2(dx, dy))

D-14: expose BOTH raw and clamped angle. The raw value is useful for debug /
logging (counting clamp events); the clamped value is what the verdict matrix
uses for fence interpolation.
"""
from __future__ import annotations

import math
from typing import overload

import numpy as np

from mlb_park.geometry.calibration import CALIB_OX, CALIB_OY, CALIB_S

SPRAY_MIN_DEG: float = -45.0
SPRAY_MAX_DEG: float = +45.0


@overload
def clamp_spray_angle(angle_deg: float) -> float: ...
@overload
def clamp_spray_angle(angle_deg: np.ndarray) -> np.ndarray: ...
def clamp_spray_angle(angle_deg):
    """Clamp spray angle into [SPRAY_MIN_DEG, SPRAY_MAX_DEG]. Accepts scalar or ndarray."""
    if isinstance(angle_deg, np.ndarray):
        return np.clip(angle_deg, SPRAY_MIN_DEG, SPRAY_MAX_DEG)
    return max(SPRAY_MIN_DEG, min(SPRAY_MAX_DEG, float(angle_deg)))


def gameday_to_spray_and_distance(coord_x: float, coord_y: float) -> tuple[float, float, float]:
    """Transform a single (coordX, coordY) pair to (raw_angle_deg, clamped_angle_deg, distance_ft).

    Distance is always non-negative. Raw angle is in (-180°, +180°] — for in-play batted balls
    it will typically land in [-47°, +14°] against the Judge fixtures; D-14 clamp keeps
    downstream interpolation well-defined.
    """
    dx = float(coord_x) - CALIB_OX
    dy = CALIB_OY - float(coord_y)
    distance_ft = CALIB_S * math.hypot(dx, dy)
    raw_angle_deg = math.degrees(math.atan2(dx, dy))
    clamped = clamp_spray_angle(raw_angle_deg)
    return raw_angle_deg, clamped, distance_ft
