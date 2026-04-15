"""Golden tests for the gameday → (angle, distance) transform."""
from __future__ import annotations

import math

import numpy as np
import pytest

from mlb_park.geometry.calibration import CALIB_OX, CALIB_OY, CALIB_S
from mlb_park.geometry.transform import (
    SPRAY_MIN_DEG,
    SPRAY_MAX_DEG,
    clamp_spray_angle,
    gameday_to_spray_and_distance,
)


def test_cf_straight_away_is_zero_angle():
    raw, clamped, dist = gameday_to_spray_and_distance(CALIB_OX, CALIB_OY - 100.0)
    assert abs(raw) < 1e-9
    assert abs(clamped) < 1e-9
    assert abs(dist - 100.0 * CALIB_S) < 1e-6


def test_pulled_to_lf_is_negative_angle():
    # coordX < Ox → dx < 0 → atan2 negative
    raw, _, _ = gameday_to_spray_and_distance(CALIB_OX - 50.0, CALIB_OY - 50.0)
    assert raw < 0
    assert raw > -90.0  # 45° pull


def test_pushed_to_rf_is_positive_angle():
    raw, _, _ = gameday_to_spray_and_distance(CALIB_OX + 50.0, CALIB_OY - 50.0)
    assert raw > 0
    assert raw < 90.0


def test_clamp_boundaries():
    assert clamp_spray_angle(50.0) == SPRAY_MAX_DEG
    assert clamp_spray_angle(-60.0) == SPRAY_MIN_DEG
    assert clamp_spray_angle(0.0) == 0.0
    assert clamp_spray_angle(44.9) == pytest.approx(44.9)


def test_clamp_vectorized():
    arr = np.array([-60.0, -30.0, 0.0, 30.0, 60.0])
    out = clamp_spray_angle(arr)
    np.testing.assert_array_equal(out, np.array([-45.0, -30.0, 0.0, 30.0, 45.0]))


def test_all_judge_hrs_distance_within_1ft(judge_hrs):
    """Per RESEARCH.md fitted residuals, every HR is < 0.2 ft from totalDistance."""
    assert len(judge_hrs) == 6
    for hr in judge_hrs:
        _, _, dist = gameday_to_spray_and_distance(hr["coordX"], hr["coordY"])
        assert abs(dist - hr["totalDistance"]) < 1.0, (
            f"HR {hr['gamePk']} distance {dist:.2f} vs reported {hr['totalDistance']:.2f}"
        )


def test_judge_hrs_angle_band(judge_hrs):
    """All Judge HRs land in [-47°, +14°] raw; exactly one (823563 HR2) clamps to -45°."""
    clamp_events = 0
    for hr in judge_hrs:
        raw, clamped, _ = gameday_to_spray_and_distance(hr["coordX"], hr["coordY"])
        assert -47.0 < raw < 14.0, f"HR {hr['gamePk']} raw angle {raw:.2f} outside expected band"
        if raw != clamped:
            clamp_events += 1
    # RESEARCH.md §Key empirical findings #2: exactly one clamp event
    # (gamePk 823563 HR2 at -45.95°).
    assert clamp_events == 1, f"Expected exactly 1 clamp event per RESEARCH.md, got {clamp_events}"
