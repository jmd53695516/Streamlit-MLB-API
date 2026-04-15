"""D-09 / D-13 / D-14 error-handling tests for extract_hrs.

- Per-feed MLBAPIError is caught + recorded as PipelineError; other games still process.
- gameLog MLBAPIError propagates (not caught).
- gameLog/feed HR count mismatch logs WARNING but does NOT raise.
"""
from __future__ import annotations

import logging

import pytest

from mlb_park.pipeline.extract import extract_hrs

from tests.pipeline.conftest import StubAPI


def _gamelog_row(
    *, game_pk: int, hrs: int = 1, team_id: int = 147, date: str = "2026-05-01",
) -> dict:
    return {
        "date": date,
        "game": {"gamePk": game_pk},
        "team": {"id": team_id, "name": "New York Yankees"},
        "opponent": {"id": 117, "name": "Houston Astros"},
        "stat": {"homeRuns": hrs},
    }


def _judge_minimal_feed(*, game_pk: int, date: str) -> dict:
    return {
        "gamePk": game_pk,
        "gameData": {
            "datetime": {"officialDate": date},
            "teams": {
                "home": {"id": 147, "abbreviation": "NYY"},
                "away": {"id": 117, "abbreviation": "HOU"},
            },
        },
        "liveData": {
            "plays": {
                "allPlays": [
                    {
                        "result": {
                            "eventType": "home_run",
                            "description": "Aaron Judge homers (1).",
                        },
                        "matchup": {"batter": {"id": 592450}},
                        "about": {"inning": 2, "halfInning": "top"},
                        "playEvents": [
                            {
                                "type": "hit_into_play",
                                "hitData": {
                                    "totalDistance": 405.0,
                                    "launchSpeed": 106.0,
                                    "launchAngle": 26.0,
                                    "coordinates": {"coordX": 120.0, "coordY": 88.0},
                                },
                            }
                        ],
                    }
                ]
            }
        },
    }


# ---------------------------------------------------------------------------
# B9 — D-14: per-feed MLBAPIError caught, OTHER games still processed
# ---------------------------------------------------------------------------

def test_per_feed_mlbapierror_collected(make_stub_api) -> None:
    """One game's feed raises; the other game's HR is still extracted."""
    game_log = [
        _gamelog_row(game_pk=900006, hrs=1, date="2026-05-01"),
        _gamelog_row(game_pk=900008, hrs=1, date="2026-05-03"),
    ]
    feeds = {900008: _judge_minimal_feed(game_pk=900008, date="2026-05-03")}
    feed_errors = {900006: StubAPI.MLBAPIError("503 Service Unavailable")}
    stub = make_stub_api(game_log=game_log, feeds=feeds, feed_errors=feed_errors)

    result = extract_hrs(592450, 2026, api=stub)

    assert len(result.events) == 1
    assert result.events[0].game_pk == 900008

    assert len(result.errors) == 1
    err = result.errors[0]
    assert err.game_pk == 900006
    assert err.endpoint == "game_feed"
    assert "503" in err.message


# ---------------------------------------------------------------------------
# B10 — D-14: gameLog MLBAPIError propagates
# ---------------------------------------------------------------------------

class _GameLogRaisingStub(StubAPI):
    def get_game_log(self, person_id: int, season: int) -> list[dict]:
        raise self.MLBAPIError("500 boom")


def test_gamelog_mlbapierror_propagates() -> None:
    """If get_game_log fails, extract_hrs raises (D-14)."""
    stub = _GameLogRaisingStub()
    with pytest.raises(stub.MLBAPIError):
        extract_hrs(1, 2026, api=stub)


# ---------------------------------------------------------------------------
# B8 — D-09: count mismatch warns but does NOT raise; matched plays kept
# ---------------------------------------------------------------------------

def test_count_mismatch_warning_not_error(
    make_stub_api, synthetic_feed, synthetic_gamelog, caplog,
) -> None:
    """gameLog says HR=2 for 900006; feed has 1 Judge HR -> warning + 1 event."""
    game_log = synthetic_gamelog("gamelog_count_mismatch.json")
    feeds = {900006: synthetic_feed("feed_count_mismatch.json")}
    stub = make_stub_api(game_log=game_log, feeds=feeds)

    with caplog.at_level(logging.WARNING, logger="mlb_park.pipeline.extract"):
        result = extract_hrs(592450, 2026, api=stub)

    # No exception raised, exactly 1 event emitted.
    assert len(result.events) == 1
    assert result.events[0].game_pk == 900006
    assert len(result.errors) == 0

    # Exact warning format from CONTEXT.md §"Specific Ideas".
    assert any(
        "gameLog/feed HR count mismatch for gamePk=900006: expected 2, matched 1"
        in rec.getMessage()
        for rec in caplog.records
    ), f"expected mismatch warning, got: {[r.getMessage() for r in caplog.records]}"
