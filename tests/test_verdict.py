"""Unit tests for HitData / VerdictMatrix / compute_verdict_matrix."""
from __future__ import annotations

import dataclasses
import time

import numpy as np
import pytest

from mlb_park.geometry.park import Park
from mlb_park.geometry.verdict import (
    HitData,
    VerdictMatrix,
    VerdictRecord,
    compute_verdict_matrix,
)


@pytest.fixture
def yankee_park():
    fi = {
        "leftLine": 318, "leftCenter": 399, "center": 408,
        "rightCenter": 385, "rightLine": 314,
    }
    return Park.from_field_info(fi, venue_id=3313, name="Yankee Stadium")


def test_hitdata_is_frozen():
    hit = HitData(distance_ft=420.0, coord_x=120.0, coord_y=100.0)
    assert hit.identifier is None
    with pytest.raises(dataclasses.FrozenInstanceError):
        hit.distance_ft = 500.0  # type: ignore[misc]


def test_cf_shot_clears_yankee_stadium(yankee_park):
    # CF straight shot: coordX == Ox, coordY < Oy → angle 0°, distance = s * (Oy - y)
    # Use reported distance 420 > center fence 408 → clears with +12 ft margin.
    hit = HitData(distance_ft=420.0, coord_x=125.608, coord_y=105.162)
    vm = compute_verdict_matrix([hit], {3313: yankee_park})
    assert vm.cleared.shape == (1, 1)
    assert vm.margin_ft[0, 0] == pytest.approx(420.0 - 408.0, abs=0.01)
    assert vm.cleared[0, 0]


def test_short_shot_does_not_clear(yankee_park):
    hit = HitData(distance_ft=300.0, coord_x=125.608, coord_y=105.162)
    vm = compute_verdict_matrix([hit], {3313: yankee_park})
    assert vm.margin_ft[0, 0] == pytest.approx(300.0 - 408.0, abs=0.01)
    assert not vm.cleared[0, 0]


def test_margin_sign_invariant_holds_everywhere(yankee_park):
    hits = [
        HitData(distance_ft=350.0, coord_x=80.0, coord_y=80.0),
        HitData(distance_ft=450.0, coord_x=125.0, coord_y=60.0),
        HitData(distance_ft=408.0, coord_x=125.608, coord_y=105.162),  # right at fence
    ]
    vm = compute_verdict_matrix(hits, {3313: yankee_park})
    np.testing.assert_array_equal(vm.cleared, vm.margin_ft > 0)


def test_iter_records_yields_frozen_records(yankee_park):
    hit = HitData(distance_ft=420.0, coord_x=125.608, coord_y=105.162, identifier=("game", 1))
    vm = compute_verdict_matrix([hit], {3313: yankee_park})
    records = list(vm.iter_records())
    assert len(records) == 1
    r = records[0]
    assert isinstance(r, VerdictRecord)
    assert r.hr_index == 0
    assert r.venue_id == 3313
    assert r.park_name == "Yankee Stadium"
    assert r.cleared is True
    assert r.identifier == ("game", 1)
    with pytest.raises(dataclasses.FrozenInstanceError):
        r.cleared = False  # type: ignore[misc]


def test_parks_cleared_matches_row_sum(yankee_park):
    fi2 = {"leftLine": 330, "leftCenter": 420, "center": 435, "rightCenter": 410, "rightLine": 335}
    far_park = Park.from_field_info(fi2, venue_id=9999, name="Far Park")
    hit = HitData(distance_ft=420.0, coord_x=125.608, coord_y=105.162)  # 0° CF
    vm = compute_verdict_matrix([hit], [yankee_park, far_park])
    # Yankee CF=408: cleared. Far Park CF=435: not cleared. → 1/2.
    assert vm.parks_cleared(0) == 1
    assert vm.parks_cleared(0) == int(vm.cleared[0].sum())


def test_empty_inputs_produce_shaped_empty_matrix(yankee_park):
    vm_no_hrs = compute_verdict_matrix([], [yankee_park])
    assert vm_no_hrs.cleared.shape == (0, 1)
    vm_no_parks = compute_verdict_matrix([HitData(400.0, 125.6, 105.0)], [])
    assert vm_no_parks.cleared.shape == (1, 0)


def test_timing_guard_for_vectorization(yankee_park):
    """6 HRs × 30 parks must complete in well under 100ms — nested Python loops would be 10-100× slower.

    Bound chosen with headroom for Windows timer resolution + cold numpy import
    on first test in a session. A nested-Python-loop regression would push this
    into the hundreds of ms easily.
    """
    # 30 identical copies of yankee_park to simulate scale.
    parks = [yankee_park for _ in range(30)]
    hits = [HitData(400.0 + i, 125.0 + i, 100.0 - i) for i in range(6)]
    # Warm-up call so numpy dispatch and any lazy imports don't skew timing.
    compute_verdict_matrix(hits, parks)
    t0 = time.perf_counter()
    vm = compute_verdict_matrix(hits, parks)
    elapsed = time.perf_counter() - t0
    assert vm.cleared.shape == (6, 30)
    assert elapsed < 0.1, f"compute_verdict_matrix too slow: {elapsed*1000:.2f}ms"
