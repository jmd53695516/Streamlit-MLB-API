"""Unit tests for get_team_hitting_stats / _raw_team_hitting_stats (Plan 04-01 Task 1).

Scope:
  - The public wrapper returns the `roster` list from the D-11-amended endpoint.
  - Empty roster → [].
  - The raw helper constructs the expected URL (teams/{id}/roster with
    rosterType=active + hydrate=person(stats(type=statsSingleSeason,season={s},group=hitting))).
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from mlb_park.services import mlb_api

REAL_FIXTURES = Path(__file__).parent.parent / "fixtures"


@pytest.fixture(scope="module")
def team_stats_147_payload() -> dict:
    """Full recorded response body for team 147 / season 2026 (roster + hydrated hitting stats)."""
    return json.loads(
        (REAL_FIXTURES / "team_stats_147_2026.json").read_text(encoding="utf-8")
    )


def test_returns_roster_list(monkeypatch, team_stats_147_payload):
    """Public wrapper returns response['roster'] — a non-empty list of dicts."""
    monkeypatch.setattr(
        mlb_api, "_raw_team_hitting_stats", lambda team_id, season: team_stats_147_payload["roster"]
    )
    # Phase 7: get_team_hitting_stats is now a plain dispatcher; clear the underlying cached wrappers.
    mlb_api.get_team_hitting_stats_current.clear()
    mlb_api.get_team_hitting_stats_historical.clear()

    result = mlb_api.get_team_hitting_stats(147, 2026)

    assert isinstance(result, list)
    assert len(result) > 0
    assert all(isinstance(entry, dict) for entry in result)
    assert "person" in result[0]


def test_empty_roster_returns_empty_list(monkeypatch):
    """D-15: empty roster → []."""
    monkeypatch.setattr(
        mlb_api, "_raw_team_hitting_stats", lambda team_id, season: []
    )
    # Phase 7: get_team_hitting_stats is now a plain dispatcher; clear the underlying cached wrappers.
    mlb_api.get_team_hitting_stats_current.clear()
    mlb_api.get_team_hitting_stats_historical.clear()

    result = mlb_api.get_team_hitting_stats(999, 2026)

    assert result == []


def test_raw_helper_builds_expected_url(monkeypatch, team_stats_147_payload):
    """Raw helper calls /teams/{id}/roster with rosterType=active + hydrate string."""
    from mlb_park.config import CURRENT_SEASON

    captured: dict = {}

    def fake_get(url: str, params: dict | None = None) -> dict:
        captured["url"] = url
        captured["params"] = params or {}
        return team_stats_147_payload

    monkeypatch.setattr(mlb_api, "_get", fake_get)

    mlb_api._raw_team_hitting_stats(147, CURRENT_SEASON)

    assert "teams/147/roster" in captured["url"]
    params = captured["params"]
    assert params.get("rosterType") == "active"
    hydrate = params.get("hydrate", "")
    assert "person(stats(" in hydrate
    assert "type=statsSingleSeason" in hydrate
    assert f"season={CURRENT_SEASON}" in hydrate
    assert "group=hitting" in hydrate


def test_raw_helper_rejects_non_int_args():
    """SSRF guard (T-4-01): team_id and season must be int."""
    with pytest.raises(AssertionError):
        mlb_api._raw_team_hitting_stats("147", 2026)  # type: ignore[arg-type]
    with pytest.raises(AssertionError):
        mlb_api._raw_team_hitting_stats(147, "2026")  # type: ignore[arg-type]


def test_historical_season_uses_full_season_roster_type(monkeypatch):
    """Phase 7 SEASON-03: past season must use rosterType=fullSeason with explicit season param."""
    from mlb_park.config import CURRENT_SEASON

    captured: dict = {}

    def fake_get(url: str, params: dict | None = None) -> dict:
        captured["url"] = url
        captured["params"] = params or {}
        return {"roster": []}

    monkeypatch.setattr(mlb_api, "_get", fake_get)

    past_season = CURRENT_SEASON - 2
    mlb_api._raw_team_hitting_stats(147, past_season)

    params = captured["params"]
    assert params["rosterType"] == "fullSeason", (
        f"Expected rosterType=fullSeason for past season {past_season}, got {params.get('rosterType')!r}"
    )
    assert params["season"] == past_season, (
        f"Expected season={past_season} in params, got {params.get('season')!r}"
    )
