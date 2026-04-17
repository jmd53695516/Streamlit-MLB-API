"""Phase 4 Plan 03 — unit tests for app.py on_change callbacks.

D-30 / VALIDATION.md test strategy: the two callbacks
(_on_team_change, _on_player_change) read/write st.session_state but do no
Streamlit-runtime work. We test by monkeypatching st.session_state to a
plain dict (faithful shim — Streamlit's SessionState is dict-like).

CRITICAL patching detail: the callbacks resolve `get_teams` by the local
name bound inside `mlb_park.app`'s namespace at import time. Patching
`mlb_park.services.mlb_api.get_teams` would NOT intercept the call —
we must patch `mlb_park.app.get_teams`. Replacing the whole callable also
fully bypasses the @st.cache_data wrapper.
"""
from __future__ import annotations

import pytest


def test_on_team_change_nulls_children(monkeypatch: pytest.MonkeyPatch) -> None:
    """UX-04 + D-17: changing team nulls player_id and venue_id."""
    import mlb_park.app as app

    fake_state = {"team_id": 147, "player_id": 592450, "venue_id": 3313}
    monkeypatch.setattr("mlb_park.app.st.session_state", fake_state)

    app._on_team_change()

    assert fake_state["player_id"] is None
    assert fake_state["venue_id"] is None
    # team_id is owned by Streamlit's widget machinery; callback does not touch it.
    assert fake_state["team_id"] == 147


def test_on_player_change_sets_home_venue(monkeypatch: pytest.MonkeyPatch) -> None:
    """UX-03 + D-17 + D-20: picking a player sets venue_id to team's home park."""
    import mlb_park.app as app

    fake_state = {"team_id": 147, "player_id": 592450, "venue_id": None}
    monkeypatch.setattr("mlb_park.app.st.session_state", fake_state)

    # Replace the bound callable entirely — bypasses @st.cache_data wrapper.
    monkeypatch.setattr(
        "mlb_park.app.get_teams",
        lambda: [
            {
                "id": 147,
                "name": "Yankees",
                "abbreviation": "NYY",
                "venue": {"id": 3313, "name": "Yankee Stadium"},
            }
        ],
    )

    app._on_player_change()

    assert fake_state["venue_id"] == 3313


def test_on_season_change_nulls_all_three_children(monkeypatch: pytest.MonkeyPatch) -> None:
    """D-02: changing season nulls team_id, player_id, and venue_id."""
    import mlb_park.app as app
    fake_state = {"season": 2024, "team_id": 147, "player_id": 592450, "venue_id": 3313}
    monkeypatch.setattr("mlb_park.app.st.session_state", fake_state)
    app._on_season_change()
    assert fake_state["team_id"] is None
    assert fake_state["player_id"] is None
    assert fake_state["venue_id"] is None


def test_on_player_change_no_team_selected_is_noop(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Defensive: callback must not raise when team_id is None.

    Shouldn't happen in normal cascading flow (player can't be picked before
    team), but guard against an out-of-order session_state mutation.
    """
    import mlb_park.app as app

    fake_state = {"team_id": None, "player_id": 592450, "venue_id": None}
    monkeypatch.setattr("mlb_park.app.st.session_state", fake_state)

    # If get_teams is called we want a clear failure rather than a real HTTP hit.
    def _explode() -> list[dict]:
        raise AssertionError("get_teams must not be called when team_id is None")

    monkeypatch.setattr("mlb_park.app.get_teams", _explode)

    # Must not raise.
    app._on_player_change()

    assert fake_state["venue_id"] is None
