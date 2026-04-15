"""Integration test: full Phase 2 pipeline over Judge fixtures × 30 venues.

Consumes only tests/fixtures/ JSON (no network). Exercises:
  1. load_parks builds 30 Parks from captured venue JSON
  2. HitData objects built from the 6 Judge HR records
  3. compute_verdict_matrix produces a (6, 30) matrix with no NaNs
  4. Margin sign invariant and hand-computed reference cells agree
"""
from __future__ import annotations

import numpy as np
import pytest

from mlb_park.geometry import (
    HitData,
    Park,
    compute_verdict_matrix,
    gameday_to_spray_and_distance,
    load_parks,
)


@pytest.fixture
def judge_hit_datas(judge_hrs):
    return [
        HitData(
            distance_ft=hr["totalDistance"],
            coord_x=hr["coordX"],
            coord_y=hr["coordY"],
            identifier={"gamePk": hr["gamePk"]},
        )
        for hr in judge_hrs
    ]


def test_full_matrix_shape_and_finiteness(judge_hit_datas, venues):
    parks = load_parks(venues)
    assert len(parks) == 30
    vm = compute_verdict_matrix(judge_hit_datas, parks)
    assert vm.cleared.shape == (6, 30)
    assert vm.fence_ft.shape == (6, 30)
    assert vm.margin_ft.shape == (6, 30)
    assert np.all(np.isfinite(vm.fence_ft))
    assert np.all(np.isfinite(vm.margin_ft))
    # Sanity: fences are physically reasonable.
    assert vm.fence_ft.min() > 250.0
    assert vm.fence_ft.max() < 500.0


def test_margin_sign_invariant_full_matrix(judge_hit_datas, venues):
    parks = load_parks(venues)
    vm = compute_verdict_matrix(judge_hit_datas, parks)
    np.testing.assert_array_equal(vm.cleared, vm.margin_ft > 0)


def test_hand_computed_cell_yankee_stadium(judge_hit_datas, venues):
    """Verify one cell manually: HR N vs Yankee Stadium's interpolated fence at its clamped angle."""
    parks = load_parks(venues)
    vm = compute_verdict_matrix(judge_hit_datas, parks)
    # Find Yankee Stadium index (venue_id 3313).
    j = int(np.where(vm.venue_ids == 3313)[0][0])
    yankee = parks[3313]
    for i, hit in enumerate(judge_hit_datas):
        _, clamped, _ = gameday_to_spray_and_distance(hit.coord_x, hit.coord_y)
        expected_fence = float(np.interp(clamped, yankee.angles_deg, yankee.fence_ft))
        expected_margin = hit.distance_ft - expected_fence
        assert vm.fence_ft[i, j] == pytest.approx(expected_fence, abs=1e-6)
        assert vm.margin_ft[i, j] == pytest.approx(expected_margin, abs=1e-6)
        assert bool(vm.cleared[i, j]) == (expected_margin > 0)


def test_iter_records_count(judge_hit_datas, venues):
    parks = load_parks(venues)
    vm = compute_verdict_matrix(judge_hit_datas, parks)
    records = list(vm.iter_records())
    assert len(records) == 6 * 30
    # Identifiers round-trip from HitData.
    assert all(r.identifier is not None for r in records)
    game_pks_seen = {r.identifier["gamePk"] for r in records}
    assert game_pks_seen == {822998, 823241, 823243, 823563, 823568}


def test_package_level_reexports():
    """Phase 3 should be able to import everything from the subpackage root."""
    from mlb_park.geometry import (  # noqa: F401
        HitData,
        Park,
        VerdictMatrix,
        VerdictRecord,
        clamp_spray_angle,
        compute_verdict_matrix,
        gameday_to_spray_and_distance,
        load_parks,
    )


def test_every_judge_hr_clears_at_least_one_park(judge_hit_datas, venues):
    """Sanity: Judge HRs are real HRs; every one should clear at least one MLB park."""
    parks = load_parks(venues)
    vm = compute_verdict_matrix(judge_hit_datas, parks)
    per_hr_parks_cleared = vm.cleared.sum(axis=1)
    assert np.all(per_hr_parks_cleared >= 1), f"Judge HR(s) cleared zero parks: {per_hr_parks_cleared}"
