"""Phase 3 pipeline test fixtures: stub-api factory + synthetic/real fixture loaders.

Dependency injection only (D-17) — never imports mlb_park.services.mlb_api.
StubAPI mirrors the real module's four public attributes so production code
that writes `except api.MLBAPIError:` catches stub-raised exceptions identically.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

import pytest

PIPELINE_FIXTURES = Path(__file__).parent / "fixtures"
"""Synthetic fixtures authored for Phase 3 degradation tests (D-19)."""

REAL_FIXTURES = Path(__file__).parent.parent / "fixtures"
"""Phase 1 live-captured fixtures (Judge 2026 gameLog + 5 game feeds + 30 venues)."""

JUDGE_PERSON_ID = 592450


class StubAPI:
    """Stand-in for `mlb_park.services.mlb_api` used in dependency-injection tests.

    Exposes the exact four public attributes production code reaches for:
      - MLBAPIError (class attribute, subclass of RuntimeError)
      - get_game_log(person_id, season) -> list[dict]
      - get_game_feed(game_pk) -> dict (may raise MLBAPIError if game_pk in feed_errors)
      - load_all_parks() -> dict[int, dict]

    Pitfall 6 guard: MLBAPIError is a *class* attribute on StubAPI so
    `except api.MLBAPIError:` in production code catches errors raised by the stub,
    whether tests access it via instance or class.
    """

    MLBAPIError = type("StubMLBAPIError", (RuntimeError,), {})

    def __init__(
        self,
        *,
        game_log: list[dict] | None = None,
        feeds: dict[int, dict] | None = None,
        feed_errors: dict[int, Exception] | None = None,
        parks: dict[int, dict] | None = None,
    ) -> None:
        """Construct a stub with optional canned responses.

        Args:
            game_log: rows returned by get_game_log (regardless of person/season args).
            feeds: {gamePk: feed_dict} — get_game_feed looks up by gamePk.
            feed_errors: {gamePk: Exception} — get_game_feed raises the given exception
                for that gamePk instead of returning a feed.
            parks: {venue_id: venue_dict} returned by load_all_parks.
        """
        self._game_log: list[dict] = list(game_log) if game_log else []
        self._feeds: dict[int, dict] = dict(feeds) if feeds else {}
        self._feed_errors: dict[int, Exception] = dict(feed_errors) if feed_errors else {}
        self._parks: dict[int, dict] = dict(parks) if parks else {}

    def get_game_log(self, person_id: int, season: int) -> list[dict]:
        """Return the canned game-log rows (ignores person_id/season — fixture-driven)."""
        return list(self._game_log)

    def get_game_feed(self, game_pk: int) -> dict:
        """Return the canned feed for game_pk, or raise the canned error if set."""
        if game_pk in self._feed_errors:
            raise self._feed_errors[game_pk]
        return self._feeds[game_pk]

    def load_all_parks(self) -> dict[int, dict]:
        """Return a shallow copy of the canned parks dict."""
        return dict(self._parks)


@pytest.fixture
def make_stub_api() -> Callable[..., StubAPI]:
    """Factory fixture — tests call make_stub_api(game_log=..., feeds=...) to build a StubAPI.

    Function-scoped so each test gets an isolated stub with no shared mutable state.
    """

    def _factory(
        *,
        game_log: list[dict] | None = None,
        feeds: dict[int, dict] | None = None,
        feed_errors: dict[int, Exception] | None = None,
        parks: dict[int, dict] | None = None,
    ) -> StubAPI:
        return StubAPI(
            game_log=game_log,
            feeds=feeds,
            feed_errors=feed_errors,
            parks=parks,
        )

    return _factory


@pytest.fixture(scope="session")
def synthetic_feed() -> Callable[[str], dict]:
    """Loader for synthetic feed fixtures — `synthetic_feed('feed_itp.json')`.

    Path components are hard-constrained to PIPELINE_FIXTURES (T-3-05 mitigation):
    callers pass bare filenames; no `..` or absolute paths reach the filesystem.
    """

    def _load(name: str) -> dict:
        return json.loads((PIPELINE_FIXTURES / name).read_text(encoding="utf-8"))

    return _load


@pytest.fixture(scope="session")
def synthetic_gamelog() -> Callable[[str], list[dict]]:
    """Loader for synthetic gameLog fixtures — returns parsed list of row dicts."""

    def _load(name: str) -> list[dict]:
        return json.loads((PIPELINE_FIXTURES / name).read_text(encoding="utf-8"))

    return _load


@pytest.fixture(scope="session")
def judge_feeds() -> dict[int, dict]:
    """Load the 5 real Judge game-feed fixtures keyed by gamePk.

    Used by Plan 03's happy-path integration test (6 Judge HRs across 5 games).
    """
    out: dict[int, dict] = {}
    for path in sorted(REAL_FIXTURES.glob("feed_*.json")):
        feed = json.loads(path.read_text(encoding="utf-8"))
        game_pk = int(feed.get("gamePk") or path.stem.split("_")[1])
        out[game_pk] = feed
    return out


@pytest.fixture(scope="session")
def judge_gamelog() -> list[dict]:
    """Return the Judge 2026 gameLog `splits` list — matches `_raw_game_log` shape."""
    raw: Any = json.loads(
        (REAL_FIXTURES / "gamelog_592450_2026.json").read_text(encoding="utf-8")
    )
    # The recorded file is the full stats response; `_raw_game_log` returns `stats[0]["splits"]`.
    if isinstance(raw, list):
        return raw
    return raw.get("stats", [{}])[0].get("splits", [])
