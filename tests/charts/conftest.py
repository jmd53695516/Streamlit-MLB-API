"""Phase 5 chart test fixtures -- ViewModel + Park factories for spray chart tests.

Reuses ControllerStubAPI from tests/controller/conftest.py (Phase 4) to build
a real ViewModel via controller.build_view with fixture-backed data.

Session-scoped: expensive build_view call runs once per test session.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from mlb_park.controller import ViewModel, build_view
from mlb_park.geometry.park import Park
from tests.controller.conftest import ControllerStubAPI

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"

JUDGE_PERSON_ID = 592450
NYY_TEAM_ID = 147
YANKEE_STADIUM = 3313


# ---------------------------------------------------------------------------
# Raw data loaders (session-scoped, reusable)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def _venues_dict() -> dict[int, dict]:
    """All 30 venues from tests/fixtures/venue_*.json."""
    out: dict[int, dict] = {}
    for path in sorted(FIXTURES_DIR.glob("venue_*.json")):
        v = json.loads(path.read_text(encoding="utf-8"))
        out[int(v["id"])] = v
    return out


@pytest.fixture(scope="session")
def _teams_list() -> list[dict]:
    return json.loads((FIXTURES_DIR / "teams.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="session")
def _nyy_roster() -> list[dict]:
    return json.loads(
        (FIXTURES_DIR / "team_stats_147_2026.json").read_text(encoding="utf-8")
    )["roster"]


@pytest.fixture(scope="session")
def _judge_gamelog() -> list[dict]:
    raw = json.loads(
        (FIXTURES_DIR / "gamelog_592450_2026.json").read_text(encoding="utf-8")
    )
    if isinstance(raw, list):
        return raw
    return raw.get("stats", [{}])[0].get("splits", [])


@pytest.fixture(scope="session")
def _judge_feeds() -> dict[int, dict]:
    out: dict[int, dict] = {}
    for p in sorted(FIXTURES_DIR.glob("feed_*.json")):
        d = json.loads(p.read_text(encoding="utf-8"))
        out[int(d["gamePk"])] = d
    return out


# ---------------------------------------------------------------------------
# Park fixtures -- 5-point and 7-point fence curves
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def sample_park(_venues_dict: dict[int, dict]) -> Park:
    """A 7-point Park (both `left` and `right` in fieldInfo)."""
    for vid, v in _venues_dict.items():
        fi = v.get("fieldInfo") or {}
        if "left" in fi and "right" in fi:
            park = Park.from_field_info(fi, venue_id=vid, name=v.get("name", ""))
            assert park.angles_deg.shape == (7,), (
                f"Expected 7-point park, got {park.angles_deg.shape}"
            )
            return park
    pytest.skip("No 7-point fixture venue available for sample_park")


@pytest.fixture(scope="session")
def fenway_park_5pt(_venues_dict: dict[int, dict]) -> Park:
    """A 5-point Park (missing `left` or `right` in fieldInfo)."""
    for vid, v in _venues_dict.items():
        fi = v.get("fieldInfo") or {}
        if fi and ("left" not in fi or "right" not in fi):
            # Verify the 5 canonical keys exist
            if all(k in fi for k in ("leftLine", "leftCenter", "center", "rightCenter", "rightLine")):
                park = Park.from_field_info(fi, venue_id=vid, name=v.get("name", ""))
                assert park.angles_deg.shape == (5,), (
                    f"Expected 5-point park, got {park.angles_deg.shape}"
                )
                return park
    # Synthetic fallback
    return Park.from_field_info(
        {"leftLine": 310.0, "leftCenter": 379.0, "center": 390.0,
         "rightCenter": 383.0, "rightLine": 302.0},
        venue_id=3, name="Fenway Park (synthetic 5pt)",
    )


@pytest.fixture(scope="session")
def yankee_park_7pt(sample_park: Park) -> Park:
    """A 7-point Park -- alias for sample_park (both guaranteed 7-point)."""
    assert sample_park.angles_deg.shape == (7,)
    return sample_park


# ---------------------------------------------------------------------------
# ViewModel fixtures -- non-empty (Judge HRs) and empty
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def sample_view(
    _venues_dict: dict[int, dict],
    _teams_list: list[dict],
    _nyy_roster: list[dict],
    _judge_gamelog: list[dict],
    _judge_feeds: dict[int, dict],
) -> ViewModel:
    """ViewModel with Judge's 6 HRs -- plottable_events non-empty, verdict_matrix populated."""
    stub = ControllerStubAPI(
        teams=_teams_list,
        team_hitting_stats={NYY_TEAM_ID: _nyy_roster},
        game_log=_judge_gamelog,
        feeds=_judge_feeds,
        parks=_venues_dict,
    )
    view = build_view(
        team_id=NYY_TEAM_ID,
        player_id=JUDGE_PERSON_ID,
        venue_id=YANKEE_STADIUM,
        season=2026,
        api=stub,
    )
    assert len(view.plottable_events) >= 3, (
        f"sample_view needs >= 3 plottable HRs, got {len(view.plottable_events)}"
    )
    assert view.verdict_matrix is not None, "sample_view must have a verdict_matrix"
    return view


@pytest.fixture(scope="session")
def empty_view() -> ViewModel:
    """ViewModel with zero plottable events -- empty state for D-06 testing."""
    return ViewModel(
        season=2026,
        team_id=NYY_TEAM_ID,
        team_abbr="NYY",
        player_id=JUDGE_PERSON_ID,
        player_name="Aaron Judge",
        venue_id=YANKEE_STADIUM,
        venue_name="Yankee Stadium",
        player_home_venue_id=YANKEE_STADIUM,
        events=(),
        plottable_events=(),
        verdict_matrix=None,
        clears_selected_park=(),
        totals={
            "total_hrs": 0,
            "plottable_hrs": 0,
            "avg_parks_cleared": 0.0,
            "no_doubters": 0,
            "cheap_hrs": 0,
        },
        errors=(),
    )
