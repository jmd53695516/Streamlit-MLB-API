"""Tests for Phase 7 season-conditional caching in mlb_api.py.

Covers: SEASON-03 (rosterType), SEASON-04 (TTL dispatch), SEASON-05 (max_entries).
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from mlb_park.config import CURRENT_SEASON
from mlb_park.services import mlb_api


# ---------------------------------------------------------------------------
# SEASON-03: Conditional rosterType
# ---------------------------------------------------------------------------


def test_raw_team_hitting_stats_historical_uses_full_season(monkeypatch):
    """Past season (CURRENT_SEASON - 2) should use rosterType=fullSeason."""
    captured: dict = {}

    def fake_get(url: str, params: dict | None = None) -> dict:
        captured["url"] = url
        captured["params"] = params or {}
        return {"roster": []}

    monkeypatch.setattr(mlb_api, "_get", fake_get)

    past_season = CURRENT_SEASON - 2
    mlb_api._raw_team_hitting_stats(147, past_season)

    params = captured["params"]
    assert params.get("rosterType") == "fullSeason", (
        f"Expected rosterType=fullSeason for past season {past_season}, got {params.get('rosterType')!r}"
    )
    assert params.get("season") == past_season, (
        f"Expected season={past_season} in params, got {params.get('season')!r}"
    )


def test_raw_team_hitting_stats_current_uses_active(monkeypatch):
    """Current season should use rosterType=active."""
    captured: dict = {}

    def fake_get(url: str, params: dict | None = None) -> dict:
        captured["url"] = url
        captured["params"] = params or {}
        return {"roster": []}

    monkeypatch.setattr(mlb_api, "_get", fake_get)

    mlb_api._raw_team_hitting_stats(147, CURRENT_SEASON)

    params = captured["params"]
    assert params.get("rosterType") == "active", (
        f"Expected rosterType=active for current season {CURRENT_SEASON}, got {params.get('rosterType')!r}"
    )


# ---------------------------------------------------------------------------
# SEASON-04: TTL dispatch for get_game_log
# ---------------------------------------------------------------------------


def test_get_game_log_historical_dispatches_correctly(monkeypatch):
    """Past season should dispatch to get_game_log_historical."""
    called = []

    def fake_historical(person_id: int, season: int) -> list[dict]:
        called.append(("historical", person_id, season))
        return []

    def fake_current(person_id: int, season: int) -> list[dict]:
        called.append(("current", person_id, season))
        return []

    monkeypatch.setattr(mlb_api, "get_game_log_historical", fake_historical)
    monkeypatch.setattr(mlb_api, "get_game_log_current", fake_current)

    past_season = CURRENT_SEASON - 2
    mlb_api.get_game_log(123, past_season)

    assert len(called) == 1, f"Expected exactly 1 call, got {called}"
    assert called[0][0] == "historical", f"Expected historical dispatch, got {called[0][0]!r}"


def test_get_game_log_current_dispatches_correctly(monkeypatch):
    """Current season should dispatch to get_game_log_current."""
    called = []

    def fake_historical(person_id: int, season: int) -> list[dict]:
        called.append(("historical", person_id, season))
        return []

    def fake_current(person_id: int, season: int) -> list[dict]:
        called.append(("current", person_id, season))
        return []

    monkeypatch.setattr(mlb_api, "get_game_log_historical", fake_historical)
    monkeypatch.setattr(mlb_api, "get_game_log_current", fake_current)

    mlb_api.get_game_log(123, CURRENT_SEASON)

    assert len(called) == 1, f"Expected exactly 1 call, got {called}"
    assert called[0][0] == "current", f"Expected current dispatch, got {called[0][0]!r}"


# ---------------------------------------------------------------------------
# SEASON-04: TTL dispatch for get_team_hitting_stats
# ---------------------------------------------------------------------------


def test_get_team_hitting_stats_historical_dispatches_correctly(monkeypatch):
    """Past season should dispatch to get_team_hitting_stats_historical."""
    called = []

    def fake_historical(team_id: int, season: int) -> list[dict]:
        called.append(("historical", team_id, season))
        return []

    def fake_current(team_id: int, season: int) -> list[dict]:
        called.append(("current", team_id, season))
        return []

    monkeypatch.setattr(mlb_api, "get_team_hitting_stats_historical", fake_historical)
    monkeypatch.setattr(mlb_api, "get_team_hitting_stats_current", fake_current)

    past_season = CURRENT_SEASON - 2
    mlb_api.get_team_hitting_stats(147, past_season)

    assert len(called) == 1, f"Expected exactly 1 call, got {called}"
    assert called[0][0] == "historical", f"Expected historical dispatch, got {called[0][0]!r}"


def test_get_team_hitting_stats_current_dispatches_correctly(monkeypatch):
    """Current season should dispatch to get_team_hitting_stats_current."""
    called = []

    def fake_historical(team_id: int, season: int) -> list[dict]:
        called.append(("historical", team_id, season))
        return []

    def fake_current(team_id: int, season: int) -> list[dict]:
        called.append(("current", team_id, season))
        return []

    monkeypatch.setattr(mlb_api, "get_team_hitting_stats_historical", fake_historical)
    monkeypatch.setattr(mlb_api, "get_team_hitting_stats_current", fake_current)

    mlb_api.get_team_hitting_stats(147, CURRENT_SEASON)

    assert len(called) == 1, f"Expected exactly 1 call, got {called}"
    assert called[0][0] == "current", f"Expected current dispatch, got {called[0][0]!r}"


# ---------------------------------------------------------------------------
# SEASON-05: max_entries cap and TTL on get_game_feed
# ---------------------------------------------------------------------------


def test_game_feed_has_max_entries_200():
    """get_game_feed decorator must be configured with max_entries=200 (SEASON-05 OOM guard)."""
    source_text = Path(mlb_api.__file__).read_text(encoding="utf-8")
    assert "max_entries=200" in source_text, (
        "get_game_feed must have max_entries=200 in its @st.cache_data decorator"
    )


def test_game_feed_ttl_is_30d():
    """get_game_feed must use ttl='30d' (raised from 7d — completed feeds are immutable)."""
    lines = Path(mlb_api.__file__).read_text(encoding="utf-8").splitlines()
    # Narrow check: find the get_game_feed function and inspect its decorator
    found = False
    for i, line in enumerate(lines):
        if "def get_game_feed" in line:
            # Look backwards from the def line for the nearest @st.cache_data decorator
            for j in range(i - 1, max(i - 5, -1), -1):
                if "@st.cache_data" in lines[j]:
                    assert 'ttl="30d"' in lines[j], (
                        f"get_game_feed decorator must have ttl='30d', got: {lines[j].strip()}"
                    )
                    found = True
                    break
            break
    assert found, "Could not find @st.cache_data decorator for get_game_feed"
