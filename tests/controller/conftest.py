"""Phase 4 controller test fixtures — ControllerStubAPI + team-stats fixture loaders.

Extends the Phase 3 StubAPI surface with:
  - get_teams()              — canned list of team dicts
  - get_team_hitting_stats() — canned {team_id: roster} lookup

Fixture loaders are hard-constrained to tests/fixtures/ (T-3-05 / T-4-04
mitigation — bare filenames only, no `..` traversal).
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

import pytest

from tests.pipeline.conftest import StubAPI

REAL_FIXTURES = Path(__file__).parent.parent / "fixtures"


class ControllerStubAPI(StubAPI):
    """Phase 3 StubAPI + Phase 4's two new public methods.

    MLBAPIError is inherited as a class attribute so production code that
    writes `except api.MLBAPIError:` catches stub-raised errors identically.
    """

    def __init__(
        self,
        *,
        game_log: list[dict] | None = None,
        feeds: dict[int, dict] | None = None,
        feed_errors: dict[int, Exception] | None = None,
        parks: dict[int, dict] | None = None,
        teams: list[dict] | None = None,
        team_hitting_stats: dict[int, list[dict]] | None = None,
    ) -> None:
        super().__init__(
            game_log=game_log,
            feeds=feeds,
            feed_errors=feed_errors,
            parks=parks,
        )
        self._teams: list[dict] = list(teams) if teams else []
        self._team_hitting_stats: dict[int, list[dict]] = (
            dict(team_hitting_stats) if team_hitting_stats else {}
        )

    def get_teams(self) -> list[dict]:
        """Return the canned teams list (a shallow copy)."""
        return list(self._teams)

    def get_team_hitting_stats(self, team_id: int, season: int) -> list[dict]:
        """Return the canned roster for team_id, or [] if not registered.

        The season argument is accepted for API parity with the real wrapper
        but ignored — fixture-driven tests pin a single season per stub.
        """
        return list(self._team_hitting_stats.get(team_id, []))


@pytest.fixture
def make_controller_stub_api() -> Callable[..., ControllerStubAPI]:
    """Factory fixture — tests call make_controller_stub_api(...) for isolated stubs."""

    def _factory(
        *,
        game_log: list[dict] | None = None,
        feeds: dict[int, dict] | None = None,
        feed_errors: dict[int, Exception] | None = None,
        parks: dict[int, dict] | None = None,
        teams: list[dict] | None = None,
        team_hitting_stats: dict[int, list[dict]] | None = None,
    ) -> ControllerStubAPI:
        return ControllerStubAPI(
            game_log=game_log,
            feeds=feeds,
            feed_errors=feed_errors,
            parks=parks,
            teams=teams,
            team_hitting_stats=team_hitting_stats,
        )

    return _factory


def _load_roster(filename: str) -> list[dict]:
    """Load a tests/fixtures/<filename> JSON and return its `roster` list.

    T-4-04 mitigation: callers pass bare filenames; the path is pinned to
    REAL_FIXTURES/<name> with no `..` traversal.
    """
    path = REAL_FIXTURES / filename
    payload: Any = json.loads(path.read_text(encoding="utf-8"))
    return list(payload.get("roster", []))


@pytest.fixture(scope="session")
def team_stats_nyy_2026() -> list[dict]:
    """Real Yankees 2026 roster with hydrated hitting stats (37+ entries)."""
    return _load_roster("team_stats_147_2026.json")


@pytest.fixture(scope="session")
def team_stats_empty() -> list[dict]:
    """Synthetic empty-roster fixture — covers D-15."""
    return _load_roster("team_stats_empty.json")


@pytest.fixture(scope="session")
def team_stats_all_pitchers() -> list[dict]:
    """Pitcher-only subset of the NYY 2026 roster — all entries have position.type=='Pitcher'."""
    return _load_roster("team_stats_all_pitchers.json")


@pytest.fixture(scope="session")
def team_stats_zero_hr_player() -> list[dict]:
    """Single outfielder with homeRuns=0 — covers 'no HRs yet' edge case."""
    return _load_roster("team_stats_zero_hr_player.json")
