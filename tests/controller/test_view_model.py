"""Unit tests for controller.ViewModel dataclass (Plan 04-01 Task 2).

Coverage:
  - JSON round-trip (to_dict → json.dumps does not raise).
  - All D-06 field names present in to_dict() output.
  - Frozen semantics enforced.
  - verdict_matrix summary has RESEARCH.md-prescribed shape
    {"shape", "venue_ids", "cleared_per_park"}.
"""
from __future__ import annotations

import json
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from mlb_park.controller import ViewModel
from mlb_park.pipeline import HitData, compute_verdict_matrix, load_parks

FIXTURES = Path(__file__).parent.parent / "fixtures"

D06_FIELDS = {
    "season",
    "team_id",
    "team_abbr",
    "player_id",
    "player_name",
    "venue_id",
    "venue_name",
    "player_home_venue_id",
    "events",
    "plottable_events",
    "verdict_matrix",
    "clears_selected_park",
    "totals",
    "errors",
}


def _minimal_vm() -> ViewModel:
    return ViewModel(
        season=2026,
        team_id=147,
        team_abbr="NYY",
        player_id=592450,
        player_name="Aaron Judge",
        venue_id=3313,
        venue_name="Yankee Stadium",
        player_home_venue_id=3313,
        events=(),
        plottable_events=(),
        verdict_matrix=None,
        clears_selected_park=(),
        totals={"hr_count": 0, "avg_parks_cleared": 0.0},
        errors=(),
    )


def test_to_dict_json_safe():
    vm = _minimal_vm()
    # Must not raise.
    payload = json.dumps(vm.to_dict())
    assert isinstance(payload, str)


def test_to_dict_includes_all_fields():
    vm = _minimal_vm()
    d = vm.to_dict()
    assert set(d.keys()) == D06_FIELDS


def test_frozen():
    vm = _minimal_vm()
    with pytest.raises(FrozenInstanceError):
        vm.season = 9999  # type: ignore[misc]


def test_to_dict_verdict_matrix_summary_shape():
    # Build real VerdictMatrix from a Phase 3 parks fixture.
    venues: dict[int, dict] = {}
    for path in sorted(FIXTURES.glob("venue_*.json")):
        venue = json.loads(path.read_text(encoding="utf-8"))
        venues[int(venue["id"])] = venue
    parks = load_parks(venues)
    assert len(parks) == 30

    hrs = (
        HitData(distance_ft=450.0, coord_x=90.0, coord_y=90.0, identifier="hr0"),
        HitData(distance_ft=360.0, coord_x=130.0, coord_y=110.0, identifier="hr1"),
    )
    matrix = compute_verdict_matrix(hrs, parks)

    vm = ViewModel(
        season=2026,
        team_id=147,
        team_abbr="NYY",
        player_id=592450,
        player_name="Aaron Judge",
        venue_id=next(iter(parks.keys())),
        venue_name="Test",
        player_home_venue_id=next(iter(parks.keys())),
        events=(),
        plottable_events=(),
        verdict_matrix=matrix,
        clears_selected_park=(True, False),
        totals={"hr_count": 2, "avg_parks_cleared": 15.0},
        errors=(),
    )

    d = vm.to_dict()
    # Full JSON round-trip safety.
    json.dumps(d)

    summary = d["verdict_matrix"]
    assert isinstance(summary, dict)
    assert set(summary.keys()) == {"shape", "venue_ids", "cleared_per_park"}
    assert summary["shape"] == [2, 30]
    assert len(summary["venue_ids"]) == 30
    assert all(isinstance(v, int) for v in summary["venue_ids"])
    cpp = summary["cleared_per_park"]
    assert isinstance(cpp, dict)
    assert len(cpp) == 30
    for vid, count in cpp.items():
        assert isinstance(vid, int) or (isinstance(vid, str) and vid.lstrip("-").isdigit())
        assert isinstance(count, int)


def test_load_parks_reexported_from_pipeline():
    """D-02: load_parks must be importable from mlb_park.pipeline."""
    from mlb_park import pipeline

    assert hasattr(pipeline, "load_parks")
    assert "load_parks" in pipeline.__all__
