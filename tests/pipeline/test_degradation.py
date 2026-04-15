"""DATA-05 degradation flag tests for extract_hrs.

Each test pairs one synthetic feed fixture with a minimal gameLog row and
asserts the exact has_distance / has_coords / has_launch_stats / is_itp
combination specified by D-10, D-11, D-12.
"""
from __future__ import annotations

from mlb_park.pipeline.extract import extract_hrs


def _gamelog_row(
    *, game_pk: int, hrs: int = 1, team_id: int = 147, date: str = "2026-04-13",
) -> dict:
    return {
        "date": date,
        "game": {"gamePk": game_pk},
        "team": {"id": team_id, "name": "New York Yankees"},
        "opponent": {"id": 117, "name": "Houston Astros"},
        "stat": {"homeRuns": hrs},
    }


# ---------------------------------------------------------------------------
# B6 — no hitData anywhere in playEvents (D-10 bottom-out + D-12 flags False)
# ---------------------------------------------------------------------------

def test_missing_hitdata_all_flags_false(make_stub_api, synthetic_feed) -> None:
    feed = synthetic_feed("feed_missing_hitdata.json")
    game_log = [_gamelog_row(game_pk=900001, hrs=1, date="2026-04-13")]
    stub = make_stub_api(game_log=game_log, feeds={900001: feed})

    result = extract_hrs(592450, 2026, api=stub)

    assert len(result.events) == 1
    ev = result.events[0]
    assert ev.has_distance is False
    assert ev.has_coords is False
    assert ev.has_launch_stats is False
    assert ev.is_itp is False
    assert ev.distance_ft is None
    assert ev.coord_x is None
    assert ev.coord_y is None
    assert ev.launch_speed is None
    assert ev.launch_angle is None


# ---------------------------------------------------------------------------
# B4 — ITP detection (D-11)
# ---------------------------------------------------------------------------

def test_itp_flag(make_stub_api, synthetic_feed) -> None:
    feed = synthetic_feed("feed_itp.json")
    game_log = [_gamelog_row(game_pk=900002, hrs=1, date="2026-04-20")]
    stub = make_stub_api(game_log=game_log, feeds={900002: feed})

    result = extract_hrs(592450, 2026, api=stub)

    assert len(result.events) == 1
    ev = result.events[0]
    assert ev.is_itp is True
    assert ev.has_distance is True
    assert ev.has_coords is True
    assert ev.has_launch_stats is True


# ---------------------------------------------------------------------------
# B5 — partial hitData: distance present, coords null (D-12 independent flags)
# ---------------------------------------------------------------------------

def test_partial_hitdata_independent_flags(make_stub_api, synthetic_feed) -> None:
    feed = synthetic_feed("feed_partial_hitdata.json")
    game_log = [_gamelog_row(game_pk=900003, hrs=1, date="2026-04-22")]
    stub = make_stub_api(game_log=game_log, feeds={900003: feed})

    result = extract_hrs(592450, 2026, api=stub)

    assert len(result.events) == 1
    ev = result.events[0]
    assert ev.has_distance is True
    assert ev.has_coords is False
    assert ev.has_launch_stats is True
    assert ev.is_itp is False
    assert ev.distance_ft == 410.0
    assert ev.coord_x is None
    assert ev.coord_y is None
    assert ev.launch_speed == 108.4
    assert ev.launch_angle == 27.0


# ---------------------------------------------------------------------------
# B3 — terminal playEvent lacks hitData; fallback to earlier event (D-10)
# ---------------------------------------------------------------------------

def test_terminal_lacks_hitdata_fallback(make_stub_api, synthetic_feed) -> None:
    feed = synthetic_feed("feed_terminal_lacks_hitdata.json")
    game_log = [_gamelog_row(game_pk=900005, hrs=1, date="2026-04-28")]
    stub = make_stub_api(game_log=game_log, feeds={900005: feed})

    result = extract_hrs(592450, 2026, api=stub)

    assert len(result.events) == 1
    ev = result.events[0]
    assert ev.has_distance is True
    assert ev.has_coords is True
    assert ev.has_launch_stats is True
    assert ev.distance_ft == 415.5
