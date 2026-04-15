"""Unit tests for controller.build_view (Plan 04-02 Task 2).

Covers D-29 + VALIDATION.md rows:
  1. happy_path             — Judge 2026: 6 events, 6 plottable, totals populated.
  2. zero_hr_player         — gameLog has no HR rows: empty events, matrix=None.
  3. all_missing_hitdata    — HR plays present but hitData absent: plottable=().
  4. one_feed_fails         — per-feed MLBAPIError isolated: errors non-empty, partial events.
  5. stadium_flip           — same player, two venues: clears_selected_park differs.
  6. totals_arithmetic      — synthetic matrix: no_doubters/cheap_hrs/avg math.
  7. selection_fields       — team_abbr/player_name/venue_name/player_home_venue_id.

All tests use ControllerStubAPI (no network). Fixtures live in tests/fixtures/.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import patch

import numpy as np
import pytest

from mlb_park.controller import ViewModel, build_view
from mlb_park.geometry.verdict import VerdictMatrix


FIXTURES = Path(__file__).parent.parent / "fixtures"
PIPELINE_FIXTURES = Path(__file__).parent.parent / "pipeline" / "fixtures"

JUDGE_PERSON_ID = 592450
NYY_TEAM_ID = 147
YANKEE_STADIUM = 3313
FENWAY_PARK = 3
# Citi Field — the one park in the 30-venue fixture set where at least one of
# Judge's 6 real 2026 HRs falls short (5 no-doubters, 1 cheap-at-19). Used by
# test_stadium_flip to guarantee the per-HR bool tuple differs across venues.
CITI_FIELD = 19


# ---------------------------------------------------------------------------
# Shared fixture loaders (module-scoped).
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def all_parks() -> dict[int, dict]:
    """All 30 venues from tests/fixtures/venue_*.json as a {venue_id: venue_dict} map."""
    out: dict[int, dict] = {}
    for path in sorted(FIXTURES.glob("venue_*.json")):
        v = json.loads(path.read_text(encoding="utf-8"))
        out[int(v["id"])] = v
    assert len(out) == 30
    return out


@pytest.fixture(scope="module")
def teams_list() -> list[dict]:
    """The canned 30-team roster list — Phase 1 teams.json."""
    return json.loads((FIXTURES / "teams.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def judge_feeds_map() -> dict[int, dict]:
    out: dict[int, dict] = {}
    for p in sorted(FIXTURES.glob("feed_*.json")):
        d = json.loads(p.read_text(encoding="utf-8"))
        out[int(d["gamePk"])] = d
    return out


@pytest.fixture(scope="module")
def judge_gamelog_list() -> list[dict]:
    raw = json.loads((FIXTURES / "gamelog_592450_2026.json").read_text(encoding="utf-8"))
    if isinstance(raw, list):
        return raw
    return raw.get("stats", [{}])[0].get("splits", [])


@pytest.fixture(scope="module")
def nyy_roster() -> list[dict]:
    return json.loads((FIXTURES / "team_stats_147_2026.json").read_text(encoding="utf-8"))["roster"]


def _happy_stub(
    make_controller_stub_api,
    *,
    teams_list,
    nyy_roster,
    judge_gamelog_list,
    judge_feeds_map,
    all_parks,
    feed_errors: dict[int, Exception] | None = None,
    override_gamelog: list[dict] | None = None,
    override_feeds: dict[int, dict] | None = None,
):
    """Build a ControllerStubAPI configured for the happy-path Judge-on-NYY scenario."""
    return make_controller_stub_api(
        teams=teams_list,
        team_hitting_stats={NYY_TEAM_ID: nyy_roster},
        game_log=override_gamelog if override_gamelog is not None else judge_gamelog_list,
        feeds=override_feeds if override_feeds is not None else judge_feeds_map,
        feed_errors=feed_errors,
        parks=all_parks,
    )


# ---------------------------------------------------------------------------
# 1. Happy path
# ---------------------------------------------------------------------------

def test_happy_path(
    make_controller_stub_api,
    teams_list,
    nyy_roster,
    judge_gamelog_list,
    judge_feeds_map,
    all_parks,
):
    stub = _happy_stub(
        make_controller_stub_api,
        teams_list=teams_list,
        nyy_roster=nyy_roster,
        judge_gamelog_list=judge_gamelog_list,
        judge_feeds_map=judge_feeds_map,
        all_parks=all_parks,
    )
    vm = build_view(
        team_id=NYY_TEAM_ID,
        player_id=JUDGE_PERSON_ID,
        venue_id=YANKEE_STADIUM,
        season=2026,
        api=stub,
    )
    assert isinstance(vm, ViewModel)
    assert len(vm.events) == 6
    assert len(vm.plottable_events) == 6
    assert vm.verdict_matrix is not None
    assert len(vm.clears_selected_park) == len(vm.plottable_events)
    assert vm.totals["total_hrs"] == 6
    assert vm.totals["plottable_hrs"] == 6
    assert vm.errors == ()


# ---------------------------------------------------------------------------
# 2. Zero-HR player (gameLog has no HR rows)
# ---------------------------------------------------------------------------

def test_zero_hr_player(
    make_controller_stub_api,
    teams_list,
    nyy_roster,
    all_parks,
):
    # Synthetic gameLog where stat.homeRuns == 0 for every row.
    zero_hr_log = [
        {
            "game": {"gamePk": 900001},
            "stat": {"homeRuns": 0},
            "team": {"id": NYY_TEAM_ID},
        },
        {
            "game": {"gamePk": 900002},
            "stat": {"homeRuns": 0},
            "team": {"id": NYY_TEAM_ID},
        },
    ]
    stub = _happy_stub(
        make_controller_stub_api,
        teams_list=teams_list,
        nyy_roster=nyy_roster,
        judge_gamelog_list=zero_hr_log,
        judge_feeds_map={},
        all_parks=all_parks,
        override_gamelog=zero_hr_log,
        override_feeds={},
    )
    vm = build_view(
        team_id=NYY_TEAM_ID,
        player_id=JUDGE_PERSON_ID,
        venue_id=YANKEE_STADIUM,
        season=2026,
        api=stub,
    )
    assert vm.events == ()
    assert vm.plottable_events == ()
    assert vm.verdict_matrix is None
    assert vm.totals["total_hrs"] == 0
    assert vm.totals["plottable_hrs"] == 0
    assert vm.totals["avg_parks_cleared"] == 0.0
    assert vm.totals["no_doubters"] == 0
    assert vm.totals["cheap_hrs"] == 0


# ---------------------------------------------------------------------------
# 3. All-missing-hitData scenario — events present but none plottable.
# ---------------------------------------------------------------------------

def test_all_missing_hitdata(
    make_controller_stub_api,
    teams_list,
    nyy_roster,
    all_parks,
):
    # Reuse the Phase 3 synthetic feed where HR plays lack hitData entirely.
    feed_path = PIPELINE_FIXTURES / "feed_missing_hitdata.json"
    feed = json.loads(feed_path.read_text(encoding="utf-8"))
    game_pk = int(feed["gamePk"])

    # Minimal gameLog referencing just this one HR game.
    log = [
        {
            "game": {"gamePk": game_pk},
            "stat": {"homeRuns": 1},
            "team": {"id": NYY_TEAM_ID},
        },
    ]

    stub = _happy_stub(
        make_controller_stub_api,
        teams_list=teams_list,
        nyy_roster=nyy_roster,
        judge_gamelog_list=log,
        judge_feeds_map={game_pk: feed},
        all_parks=all_parks,
        override_gamelog=log,
        override_feeds={game_pk: feed},
    )
    vm = build_view(
        team_id=NYY_TEAM_ID,
        player_id=JUDGE_PERSON_ID,
        venue_id=YANKEE_STADIUM,
        season=2026,
        api=stub,
    )
    assert len(vm.events) >= 1, "HR plays without hitData should still emit HREvents (DATA-05)"
    assert vm.plottable_events == ()
    assert vm.verdict_matrix is None
    assert vm.totals["plottable_hrs"] == 0


# ---------------------------------------------------------------------------
# 4. One-feed-fails: MLBAPIError on one gamePk, other HRs still extracted.
# ---------------------------------------------------------------------------

def test_one_feed_fails(
    make_controller_stub_api,
    teams_list,
    nyy_roster,
    judge_gamelog_list,
    judge_feeds_map,
    all_parks,
):
    # Pick one of the 5 Judge game-pks and make its feed raise.
    bad_game_pk = next(iter(judge_feeds_map.keys()))
    feeds_minus_one = {k: v for k, v in judge_feeds_map.items() if k != bad_game_pk}

    # Build a stub where the error is raised via the stub's MLBAPIError.
    from tests.controller.conftest import ControllerStubAPI
    stub = ControllerStubAPI(
        teams=teams_list,
        team_hitting_stats={NYY_TEAM_ID: nyy_roster},
        game_log=judge_gamelog_list,
        feeds=feeds_minus_one,
        feed_errors={bad_game_pk: ControllerStubAPI.MLBAPIError("boom")},
        parks=all_parks,
    )
    vm = build_view(
        team_id=NYY_TEAM_ID,
        player_id=JUDGE_PERSON_ID,
        venue_id=YANKEE_STADIUM,
        season=2026,
        api=stub,
    )
    assert len(vm.errors) >= 1
    assert any(e.game_pk == bad_game_pk for e in vm.errors)
    assert len(vm.events) >= 1, "Remaining HRs from other feeds should still be extracted"


# ---------------------------------------------------------------------------
# 5. Stadium flip — clears_selected_park differs across two venue_ids.
# ---------------------------------------------------------------------------

def test_stadium_flip(
    make_controller_stub_api,
    teams_list,
    nyy_roster,
    judge_gamelog_list,
    judge_feeds_map,
    all_parks,
):
    stub = _happy_stub(
        make_controller_stub_api,
        teams_list=teams_list,
        nyy_roster=nyy_roster,
        judge_gamelog_list=judge_gamelog_list,
        judge_feeds_map=judge_feeds_map,
        all_parks=all_parks,
    )
    vm_yankee = build_view(
        team_id=NYY_TEAM_ID,
        player_id=JUDGE_PERSON_ID,
        venue_id=YANKEE_STADIUM,
        season=2026,
        api=stub,
    )
    vm_citi = build_view(
        team_id=NYY_TEAM_ID,
        player_id=JUDGE_PERSON_ID,
        venue_id=CITI_FIELD,
        season=2026,
        api=stub,
    )
    # Judge hit 5 no-doubters + 1 "cheap at Citi only" in the 2026 fixture set,
    # so flipping Yankee Stadium ↔ Citi Field changes exactly one column of the
    # cleared matrix — the per-HR bool tuples must differ.
    assert vm_yankee.clears_selected_park != vm_citi.clears_selected_park, (
        "Selected-park flip must yield different per-HR bool tuples (different fences)."
    )
    # Underlying matrix is the same (same HRs + same parks); only the venue
    # selection differs. Compare via the JSON-safe to_dict summary.
    assert vm_yankee.to_dict()["verdict_matrix"] == vm_citi.to_dict()["verdict_matrix"]


# ---------------------------------------------------------------------------
# 6. Totals arithmetic — synthetic matrix with known per-HR park counts.
# ---------------------------------------------------------------------------

def test_totals_arithmetic():
    """Exercise _compute_totals directly with a synthetic VerdictMatrix.

    Scenario: 3 plottable HRs — parks-cleared-per-HR = [30, 4, 15].
    Expected totals:
      - no_doubters = 1  (the 30/30 HR)
      - cheap_hrs   = 1  (the 4/30 HR; <= 5)
      - avg_parks_cleared = (30 + 4 + 15) / 3 = 16.333...
    """
    from mlb_park.controller import _compute_totals

    # Build a dense cleared[:,:] of shape (3, 30) matching the targets.
    cleared = np.zeros((3, 30), dtype=bool)
    cleared[0, :] = True           # 30/30
    cleared[1, :4] = True          # 4/30
    cleared[2, :15] = True         # 15/30

    matrix = VerdictMatrix(
        hrs=(),           # unused by _compute_totals
        parks=(),         # unused by _compute_totals
        venue_ids=np.arange(30, dtype=int),
        spray_raw_deg=np.zeros(3),
        spray_clamped_deg=np.zeros(3),
        distance_ft=np.zeros(3),
        fence_ft=np.zeros((3, 30)),
        margin_ft=np.zeros((3, 30)),
        cleared=cleared,
    )
    # events / plottable tuples only contribute to the total_hrs / plottable_hrs counts.
    events = (object(), object(), object())
    plottable = (object(), object(), object())
    totals = _compute_totals(events, plottable, matrix)

    assert totals["total_hrs"] == 3
    assert totals["plottable_hrs"] == 3
    assert totals["no_doubters"] == 1
    assert totals["cheap_hrs"] == 1
    assert totals["avg_parks_cleared"] == pytest.approx((30 + 4 + 15) / 3)


# ---------------------------------------------------------------------------
# 7. Selection-context fields (team_abbr, player_name, venue_name, home_venue).
# ---------------------------------------------------------------------------

def test_view_model_selection_fields_populated(
    make_controller_stub_api,
    teams_list,
    nyy_roster,
    judge_gamelog_list,
    judge_feeds_map,
    all_parks,
):
    stub = _happy_stub(
        make_controller_stub_api,
        teams_list=teams_list,
        nyy_roster=nyy_roster,
        judge_gamelog_list=judge_gamelog_list,
        judge_feeds_map=judge_feeds_map,
        all_parks=all_parks,
    )
    vm = build_view(
        team_id=NYY_TEAM_ID,
        player_id=JUDGE_PERSON_ID,
        venue_id=YANKEE_STADIUM,
        season=2026,
        api=stub,
    )
    assert vm.team_abbr == "NYY"
    assert vm.player_name == "Aaron Judge"
    assert vm.venue_name == "Yankee Stadium"
    assert vm.player_home_venue_id == YANKEE_STADIUM
