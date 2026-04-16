"""Unit tests for controller helper functions (Plan 04-02 Task 1).

Covers:
  - sorted_teams: alphabetical by `name` (UX-01).
  - sorted_hitters: non-pitcher filter (D-12) + (-homeRuns, fullName) sort (UX-02/D-13).

All fixture loads route through the Plan 04-01 session fixtures; ad-hoc tests
build minimal synthetic roster dicts inline to pin specific edge cases.
"""
from __future__ import annotations

import logging

import pytest

from mlb_park.controller import sorted_hitters, sorted_teams


# ---------------------------------------------------------------------------
# sorted_teams
# ---------------------------------------------------------------------------

def test_sorted_teams_orders_by_name_asc():
    teams = [
        {"id": 1, "name": "Yankees"},
        {"id": 2, "name": "Athletics"},
        {"id": 3, "name": "Mets"},
    ]
    out = sorted_teams(teams)
    assert [t["name"] for t in out] == ["Athletics", "Mets", "Yankees"]


def test_sorted_teams_handles_empty():
    assert list(sorted_teams([])) == []


# ---------------------------------------------------------------------------
# sorted_hitters helpers
# ---------------------------------------------------------------------------

def _make_entry(
    *,
    person_id: int,
    full_name: str,
    position_type: str | None,
    home_runs: int | None,
    include_stats: bool = True,
) -> dict:
    """Build a minimal roster entry that mirrors the StatsAPI hydrated shape."""
    entry: dict = {
        "person": {"id": person_id, "fullName": full_name},
    }
    if include_stats:
        stat: dict = {}
        if home_runs is not None:
            stat["homeRuns"] = home_runs
        entry["person"]["stats"] = [
            {"splits": [{"stat": stat}]},
        ]
    if position_type is not None:
        entry["position"] = {"type": position_type}
    return entry


def test_sorted_hitters_excludes_pitchers(team_stats_nyy_2026):
    out = sorted_hitters(team_stats_nyy_2026)
    for e in out:
        assert e["position"]["type"] != "Pitcher"


def test_sorted_hitters_sort_order():
    roster = [
        _make_entry(person_id=1, full_name="Cole",  position_type="Outfielder", home_runs=5),
        _make_entry(person_id=2, full_name="Judge", position_type="Outfielder", home_runs=17),
        _make_entry(person_id=3, full_name="Aaron", position_type="Outfielder", home_runs=0),
    ]
    out = sorted_hitters(roster)
    assert [e["person"]["fullName"] for e in out] == ["Judge", "Cole", "Aaron"]


def test_sorted_hitters_tiebreak_by_name():
    roster = [
        _make_entry(person_id=1, full_name="Zed",   position_type="Outfielder", home_runs=10),
        _make_entry(person_id=2, full_name="Alice", position_type="Outfielder", home_runs=10),
    ]
    out = sorted_hitters(roster)
    assert [e["person"]["fullName"] for e in out] == ["Alice", "Zed"]


def test_sorted_hitters_zero_hr_player_included(team_stats_zero_hr_player):
    out = sorted_hitters(team_stats_zero_hr_player)
    ids = [e["person"]["id"] for e in out]
    assert 900001 in ids, "0-HR hitter must remain in the output (D-13)"


def test_sorted_hitters_missing_position_defaults_non_pitcher(caplog):
    """Entries without a `position` key are treated as non-pitchers (D-12 fallback).

    Invariant: the warning log fires once per entry whose `position` is falsy.
    This test has exactly one such entry, so exactly one WARNING record appears.
    """
    roster = [
        {
            "person": {
                "id": 999,
                "fullName": "Gloveless Gary",
                "stats": [],
            },
        },
    ]
    with caplog.at_level(logging.WARNING, logger="mlb_park.controller"):
        out = sorted_hitters(roster)
    ids = [e["person"]["id"] for e in out]
    assert 999 in ids, "missing-position entry must be treated as non-pitcher"
    warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert len(warnings) == 1


def test_sorted_hitters_missing_homeruns_defaults_zero():
    """Entry lacking `person.stats` sorts as homeRuns=0 (below any entry with HRs)."""
    roster = [
        _make_entry(person_id=1, full_name="HasHRs", position_type="Outfielder", home_runs=3),
        {
            "person": {"id": 2, "fullName": "NoStats"},
            "position": {"type": "Outfielder"},
        },
    ]
    out = sorted_hitters(roster)
    assert [e["person"]["fullName"] for e in out] == ["HasHRs", "NoStats"]


def test_sorted_hitters_empty_roster():
    assert list(sorted_hitters([])) == []
