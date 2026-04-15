"""DATA-01 / DATA-02 happy-path + ordering tests for extract_hrs.

All tests inject a StubAPI via `api=` kwarg — zero network, zero real mlb_api import.
"""
from __future__ import annotations

import logging

import pytest

from mlb_park.config import CURRENT_SEASON
from mlb_park.pipeline.extract import extract_hrs

from tests.pipeline.conftest import StubAPI


# ---------------------------------------------------------------------------
# Helpers — inline minimal feed/gamelog builders (no new committed fixtures).
# ---------------------------------------------------------------------------

def _gamelog_row(
    *, game_pk: int, hrs: int = 1, team_id: int = 147, date: str = "2026-04-10",
) -> dict:
    return {
        "date": date,
        "game": {"gamePk": game_pk},
        "team": {"id": team_id, "name": "New York Yankees"},
        "opponent": {"id": 117, "name": "Houston Astros"},
        "stat": {"homeRuns": hrs},
    }


def _judge_hr_feed(
    *,
    game_pk: int,
    date: str,
    home_id: int,
    home_abbr: str,
    away_id: int,
    away_abbr: str,
) -> dict:
    """Minimal feed with 1 Judge HR (full hitData) — flex home/away teams."""
    return {
        "gamePk": game_pk,
        "gameData": {
            "datetime": {"officialDate": date},
            "teams": {
                "home": {"id": home_id, "abbreviation": home_abbr},
                "away": {"id": away_id, "abbreviation": away_abbr},
            },
        },
        "liveData": {
            "plays": {
                "allPlays": [
                    {
                        "result": {
                            "eventType": "home_run",
                            "description": "Aaron Judge homers on a fly ball.",
                        },
                        "matchup": {"batter": {"id": 592450}},
                        "about": {"inning": 1, "halfInning": "top"},
                        "playEvents": [
                            {
                                "type": "hit_into_play",
                                "hitData": {
                                    "totalDistance": 410.0,
                                    "launchSpeed": 108.0,
                                    "launchAngle": 27.0,
                                    "coordinates": {"coordX": 121.0, "coordY": 90.0},
                                },
                            }
                        ],
                    }
                ]
            }
        },
    }


# ---------------------------------------------------------------------------
# B1 — DATA-01: filter-before-fetch
# ---------------------------------------------------------------------------

class _CountingStub(StubAPI):
    """Tracks every gamePk passed to get_game_feed."""

    def __init__(self, **kw):
        super().__init__(**kw)
        self.feed_calls: list[int] = []

    def get_game_feed(self, game_pk: int) -> dict:
        self.feed_calls.append(game_pk)
        return super().get_game_feed(game_pk)


def test_filter_before_fetch() -> None:
    """B1: gameLog rows with homeRuns=0 must not trigger a feed fetch (D-07)."""
    game_log = [
        _gamelog_row(game_pk=700001, hrs=0, date="2026-04-01"),  # must NOT be fetched
        _gamelog_row(game_pk=700002, hrs=1, date="2026-04-02"),
        _gamelog_row(game_pk=700003, hrs=2, date="2026-04-03"),
    ]
    feeds = {
        700002: _judge_hr_feed(
            game_pk=700002, date="2026-04-02",
            home_id=147, home_abbr="NYY", away_id=117, away_abbr="HOU",
        ),
        700003: _judge_hr_feed(
            game_pk=700003, date="2026-04-03",
            home_id=147, home_abbr="NYY", away_id=117, away_abbr="HOU",
        ),
    }
    stub = _CountingStub(game_log=game_log, feeds=feeds)

    extract_hrs(592450, 2026, api=stub)

    assert len(stub.feed_calls) == 2, f"expected 2 feed fetches, got {stub.feed_calls}"
    assert 700001 not in stub.feed_calls, "0-HR gamePk must not be fetched"
    assert set(stub.feed_calls) == {700002, 700003}


# ---------------------------------------------------------------------------
# B2/B7 — DATA-02 batter filter
# ---------------------------------------------------------------------------

def test_batter_filter(
    make_stub_api, synthetic_feed, caplog,
) -> None:
    """B2/B7: HR by non-target batter is excluded; count mismatch warns but doesn't raise."""
    feed = synthetic_feed("feed_non_batter_hr.json")
    # gameLog says homeRuns=1 but the feed has no Judge HR — tests D-08 filter AND D-09 mismatch.
    game_log = [_gamelog_row(game_pk=900004, hrs=1, date="2026-04-25")]
    stub = make_stub_api(game_log=game_log, feeds={900004: feed})

    with caplog.at_level(logging.WARNING, logger="mlb_park.pipeline.extract"):
        result = extract_hrs(592450, 2026, api=stub)

    assert result.events == ()
    assert result.errors == ()
    # D-09: expected=1, matched=0 → warning logged.
    assert any(
        "gameLog/feed HR count mismatch for gamePk=900004" in rec.getMessage()
        for rec in caplog.records
    ), f"expected count-mismatch warning, got records: {[r.getMessage() for r in caplog.records]}"


# ---------------------------------------------------------------------------
# B11 — D-16: season defaults to CURRENT_SEASON
# ---------------------------------------------------------------------------

class _ArgsRecordingStub(StubAPI):
    """Records (person_id, season) pairs passed to get_game_log."""

    def __init__(self, **kw):
        super().__init__(**kw)
        self.calls: list[tuple[int, int]] = []

    def get_game_log(self, person_id: int, season: int) -> list[dict]:
        self.calls.append((person_id, season))
        return super().get_game_log(person_id, season)


def test_season_defaults_to_current() -> None:
    """B11: extract_hrs(player_id, season=None) resolves to config.CURRENT_SEASON."""
    stub = _ArgsRecordingStub(game_log=[])
    result = extract_hrs(42, api=stub)
    assert stub.calls == [(42, CURRENT_SEASON)]
    assert result.season == CURRENT_SEASON
    assert result.player_id == 42


# ---------------------------------------------------------------------------
# B12 — D-13: chronological order (game_date asc, play_idx asc)
# ---------------------------------------------------------------------------

def test_chronological_order(make_stub_api) -> None:
    """B12: events sort by (game_date asc, play_idx asc)."""
    # Feed for later date (April) placed FIRST in gameLog to prove sort, not input order.
    feed_april = _judge_hr_feed(
        game_pk=700010, date="2026-04-03",
        home_id=147, home_abbr="NYY", away_id=117, away_abbr="HOU",
    )
    feed_march = _judge_hr_feed(
        game_pk=700011, date="2026-03-27",
        home_id=147, home_abbr="NYY", away_id=117, away_abbr="HOU",
    )
    game_log = [
        _gamelog_row(game_pk=700010, hrs=1, date="2026-04-03"),
        _gamelog_row(game_pk=700011, hrs=1, date="2026-03-27"),
    ]
    stub = make_stub_api(
        game_log=game_log, feeds={700010: feed_april, 700011: feed_march}
    )

    result = extract_hrs(592450, 2026, api=stub)

    assert len(result.events) == 2
    assert result.events[0].game_date < result.events[1].game_date
    assert result.events[0].game_pk == 700011  # March first


# ---------------------------------------------------------------------------
# B13 — Pitfall 3: opponent_abbr relative to batter's team id
# ---------------------------------------------------------------------------

def test_opponent_abbr_home_and_away(make_stub_api) -> None:
    """B13: Judge home vs LAA -> 'LAA'; Judge away at SF -> 'SF'."""
    # Judge home: NYY is home (id=147), LAA away (id=108) -> opponent is LAA.
    feed_home = _judge_hr_feed(
        game_pk=700020, date="2026-04-05",
        home_id=147, home_abbr="NYY", away_id=108, away_abbr="LAA",
    )
    # Judge away: SF is home (id=137), NYY away (id=147) -> opponent is SF.
    feed_away = _judge_hr_feed(
        game_pk=700021, date="2026-04-06",
        home_id=137, home_abbr="SF", away_id=147, away_abbr="NYY",
    )
    game_log = [
        _gamelog_row(game_pk=700020, hrs=1, date="2026-04-05"),
        _gamelog_row(game_pk=700021, hrs=1, date="2026-04-06"),
    ]
    stub = make_stub_api(
        game_log=game_log, feeds={700020: feed_home, 700021: feed_away}
    )

    result = extract_hrs(592450, 2026, api=stub)

    assert len(result.events) == 2
    by_pk = {ev.game_pk: ev for ev in result.events}
    assert by_pk[700020].opponent_abbr == "LAA"
    assert by_pk[700021].opponent_abbr == "SF"


# ---------------------------------------------------------------------------
# Happy-path integration test against real Judge fixtures (6 HRs in 5 games)
# ---------------------------------------------------------------------------

def test_happy_path_judge_fixtures(make_stub_api, judge_feeds, judge_gamelog) -> None:
    """DATA-02 end-to-end: 6 Judge HRs, all hitData present, is_itp=False for all."""
    stub = make_stub_api(game_log=judge_gamelog, feeds=judge_feeds)
    result = extract_hrs(592450, 2026, api=stub)

    assert len(result.events) == 6, f"expected 6 HRs, got {len(result.events)}"
    assert len(result.errors) == 0
    for ev in result.events:
        assert ev.has_distance, f"event {ev.game_pk}/{ev.play_idx} missing distance"
        assert ev.has_coords, f"event {ev.game_pk}/{ev.play_idx} missing coords"
        assert ev.has_launch_stats, f"event {ev.game_pk}/{ev.play_idx} missing launch stats"
        assert ev.is_itp is False
    game_pks = sorted(ev.game_pk for ev in result.events)
    assert game_pks == sorted([823243, 823241, 823568, 822998, 823563, 823563])
