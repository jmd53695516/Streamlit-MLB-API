"""Tests for Park dataclass, fence interpolation, and load_parks."""
from __future__ import annotations

import dataclasses

import numpy as np
import pytest

from mlb_park.geometry.park import (
    FENCE_ANGLES_5PT,
    FENCE_ANGLES_7PT,
    GAP_ANGLE_DEG,
    Park,
    load_parks,
)


@pytest.fixture
def five_point_field_info():
    return {
        "leftLine": 318, "leftCenter": 399, "center": 408,
        "rightCenter": 385, "rightLine": 314,
        "capacity": 47309, "turfType": "Grass", "roofType": "Open",
    }


@pytest.fixture
def seven_point_field_info(five_point_field_info):
    return {**five_point_field_info, "left": 375, "right": 370}


def test_five_point_construction(five_point_field_info):
    park = Park.from_field_info(five_point_field_info, venue_id=3313, name="Yankee Stadium")
    assert park.venue_id == 3313
    assert park.name == "Yankee Stadium"
    np.testing.assert_array_equal(park.angles_deg, np.array(FENCE_ANGLES_5PT))
    np.testing.assert_array_equal(park.fence_ft, np.array([318., 399., 408., 385., 314.]))


def test_seven_point_construction(seven_point_field_info):
    park = Park.from_field_info(seven_point_field_info, venue_id=9999, name="Fake Park")
    np.testing.assert_array_equal(park.angles_deg, np.array(FENCE_ANGLES_7PT))
    # Order: leftLine, left, leftCenter, center, rightCenter, right, rightLine
    np.testing.assert_array_equal(
        park.fence_ft,
        np.array([318., 375., 399., 408., 385., 370., 314.]),
    )


def test_left_only_falls_back_to_five_point(five_point_field_info):
    """D-10 v1 simplification: venues with `left` but no `right` use 5-pt curve."""
    fi = {**five_point_field_info, "left": 375}
    park = Park.from_field_info(fi, venue_id=42, name="Left-only park")
    assert park.angles_deg.shape == (5,)


def test_missing_canonical_key_raises(five_point_field_info):
    bad = {k: v for k, v in five_point_field_info.items() if k != "center"}
    with pytest.raises(KeyError):
        Park.from_field_info(bad, venue_id=1, name="bad")


def test_exact_angles_return_exact_fences(five_point_field_info):
    park = Park.from_field_info(five_point_field_info, 3313, "Yankee Stadium")
    assert park.fence_distance_at(-45.0) == pytest.approx(318.0)
    assert park.fence_distance_at(-22.5) == pytest.approx(399.0)
    assert park.fence_distance_at(0.0) == pytest.approx(408.0)
    assert park.fence_distance_at(+22.5) == pytest.approx(385.0)
    assert park.fence_distance_at(+45.0) == pytest.approx(314.0)


def test_midpoint_linear_interp(five_point_field_info):
    park = Park.from_field_info(five_point_field_info, 3313, "Yankee Stadium")
    # Halfway between -45 and -22.5 is -33.75; fence ≈ mean(leftLine, leftCenter)
    mid = park.fence_distance_at(-33.75)
    assert mid == pytest.approx((318.0 + 399.0) / 2.0)


def test_interp_clamps_beyond_bounds(five_point_field_info):
    park = Park.from_field_info(five_point_field_info, 3313, "Yankee Stadium")
    assert park.fence_distance_at(+60.0) == pytest.approx(314.0)   # RF line
    assert park.fence_distance_at(-60.0) == pytest.approx(318.0)   # LF line


def test_vectorized_interp(five_point_field_info):
    park = Park.from_field_info(five_point_field_info, 3313, "Yankee Stadium")
    angles = np.array([-45.0, -22.5, 0.0, +22.5, +45.0])
    out = park.fence_distance_at(angles)
    np.testing.assert_array_almost_equal(out, np.array([318., 399., 408., 385., 314.]))


def test_park_is_frozen(five_point_field_info):
    park = Park.from_field_info(five_point_field_info, 3313, "Yankee Stadium")
    with pytest.raises(dataclasses.FrozenInstanceError):
        park.name = "Hacked Stadium"  # type: ignore[misc]


def test_load_parks_over_30_fixtures(venues):
    """Build all 30 Parks from captured venue fixtures."""
    parks = load_parks(venues)
    assert len(parks) == 30
    for vid, park in parks.items():
        assert isinstance(park, Park)
        assert park.angles_deg.shape in {(5,), (7,)}
        assert park.fence_ft.shape == park.angles_deg.shape
        # Monotonic angles
        assert np.all(np.diff(park.angles_deg) > 0)
        # Reasonable fence distances (no bad parse)
        assert np.all(park.fence_ft > 250.0)
        assert np.all(park.fence_ft < 500.0)


def test_seven_point_park_count_matches_fixtures(venues):
    """Per 01-03-SUMMARY.md + RESEARCH.md: 7 venues expose BOTH `left` AND `right`."""
    parks = load_parks(venues)
    seven_count = sum(1 for p in parks.values() if p.angles_deg.shape == (7,))
    # 7 venues have both gaps; 5 have left-only (treated as 5pt); 18 have neither.
    assert seven_count == 7, f"unexpected 7-pt park count: {seven_count}"


def test_gap_angle_is_30_degrees():
    """D-11 + RESEARCH.md: gap points sit at ±30°, not ±33.75°."""
    assert GAP_ANGLE_DEG == 30.0
    assert FENCE_ANGLES_7PT[1] == -30.0
    assert FENCE_ANGLES_7PT[-2] == +30.0
