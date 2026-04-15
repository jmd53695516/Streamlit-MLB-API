"""Phase 4 controller — ViewModel + (future) build_view.

This module is the ONLY place that composes pipeline output for the UI. It
must NOT import `streamlit` (D-23) — UI concerns live in app.py / views/.

Plan 04-01 scope: ViewModel dataclass + to_dict() JSON projection only.
The build_view entry point lands in Plan 04-02 (Wave 2).

Import discipline (D-02): every runtime dependency flows through
`mlb_park.pipeline`. VerdictMatrix is imported from geometry as a TYPE
reference only (annotations / isinstance); no runtime composition escapes
the pipeline package boundary.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Union

from mlb_park.pipeline import (  # noqa: F401 — re-exports primed for Plan 04-02
    CURRENT_SEASON,
    HREvent,
    HitData,
    MLBAPIError,
    PipelineError,
    compute_verdict_matrix,
    load_all_parks,
    load_parks,
)

# Type-only import; runtime calls go through mlb_park.pipeline (D-02 spirit).
from mlb_park.geometry.verdict import VerdictMatrix

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class ViewModel:
    """Immutable projection of a (team, player, venue) selection (D-06).

    Consumed by Phase 4/5 UI code. `to_dict()` produces a JSON-safe snapshot
    suitable for `st.json`, debugging dumps, and URL-state serialization.
    """

    season: int
    team_id: int
    team_abbr: str
    player_id: int
    player_name: str
    venue_id: int
    venue_name: str
    player_home_venue_id: int
    events: tuple[HREvent, ...]
    plottable_events: tuple[HREvent, ...]
    verdict_matrix: VerdictMatrix | None
    clears_selected_park: tuple[bool, ...]
    totals: dict[str, Union[int, float]]
    errors: tuple[PipelineError, ...]

    def to_dict(self) -> dict:
        """Return a JSON-safe snapshot of this view model.

        Layout:
          - Scalars pass through as-is.
          - events/plottable_events → list[dict] (HREvent fields; game_date → ISO string).
          - verdict_matrix → summary {shape, venue_ids, cleared_per_park} (D-24 scope;
            no to_dict() on the geometry dataclass). None when matrix is absent.
          - errors → list[{game_pk, endpoint, message}].
          - tuples → lists.
        """
        return {
            "season": int(self.season),
            "team_id": int(self.team_id),
            "team_abbr": str(self.team_abbr),
            "player_id": int(self.player_id),
            "player_name": str(self.player_name),
            "venue_id": int(self.venue_id),
            "venue_name": str(self.venue_name),
            "player_home_venue_id": int(self.player_home_venue_id),
            "events": [_hr_event_to_dict(ev) for ev in self.events],
            "plottable_events": [_hr_event_to_dict(ev) for ev in self.plottable_events],
            "verdict_matrix": _verdict_matrix_summary(self.verdict_matrix),
            "clears_selected_park": [bool(x) for x in self.clears_selected_park],
            "totals": dict(self.totals),
            "errors": [_pipeline_error_to_dict(e) for e in self.errors],
        }


def _hr_event_to_dict(ev: HREvent) -> dict:
    """Project an HREvent into a JSON-safe dict (date → ISO string)."""
    return {
        "game_pk": int(ev.game_pk),
        "game_date": ev.game_date.isoformat(),
        "opponent_abbr": str(ev.opponent_abbr),
        "inning": int(ev.inning),
        "half_inning": str(ev.half_inning),
        "play_idx": int(ev.play_idx),
        "distance_ft": ev.distance_ft,
        "coord_x": ev.coord_x,
        "coord_y": ev.coord_y,
        "launch_speed": ev.launch_speed,
        "launch_angle": ev.launch_angle,
        "has_distance": bool(ev.has_distance),
        "has_coords": bool(ev.has_coords),
        "has_launch_stats": bool(ev.has_launch_stats),
        "is_itp": bool(ev.is_itp),
    }


def _pipeline_error_to_dict(err: PipelineError) -> dict:
    return {
        "game_pk": None if err.game_pk is None else int(err.game_pk),
        "endpoint": str(err.endpoint),
        "message": str(err.message),
    }


def _verdict_matrix_summary(matrix: VerdictMatrix | None) -> dict | None:
    """Build the RESEARCH.md-prescribed summary shape (D-24 controller scope).

    Returns None when no matrix is present (UI can render "no HRs / no parks").
    """
    if matrix is None:
        return None
    venue_ids = [int(v) for v in matrix.venue_ids.tolist()]
    cleared_per_park = {
        int(vid): int(matrix.cleared[:, j].sum())
        for j, vid in enumerate(venue_ids)
    }
    return {
        "shape": list(matrix.cleared.shape),
        "venue_ids": venue_ids,
        "cleared_per_park": cleared_per_park,
    }


# ---------------------------------------------------------------------------
# Plan 04-02 helpers — _sorted_teams / _sorted_hitters (UX-01, UX-02, D-12/13).
# ---------------------------------------------------------------------------


def _sorted_teams(teams: list[dict]) -> list[dict]:
    """Return teams sorted by `name` ascending (UX-01).

    Pure: no mutation of the input list. Missing `name` sorts as empty string
    (shouldn't happen with the real StatsAPI response but keeps the function
    total for defensive callers).
    """
    return sorted(teams, key=lambda t: t.get("name", ""))


def _hr_of(entry: dict) -> int:
    """Extract `person.stats[0].splits[0].stat.homeRuns`, defaulting to 0 (D-13)."""
    stats = entry.get("person", {}).get("stats") or []
    if not stats:
        return 0
    splits = stats[0].get("splits") or []
    if not splits:
        return 0
    raw = splits[0].get("stat", {}).get("homeRuns", 0)
    try:
        return int(raw or 0)
    except (TypeError, ValueError):
        return 0


def _name_of(entry: dict) -> str:
    """Extract `person.fullName`, defaulting to empty string."""
    return entry.get("person", {}).get("fullName", "") or ""


def _sorted_hitters(roster: list[dict]) -> list[dict]:
    """Filter non-pitchers, then sort by (-homeRuns, fullName) (D-12, D-13).

    Missing `position` key ⇒ WARNING logged per-entry, entry treated as
    non-pitcher (defensive — the real StatsAPI always returns position, but
    a malformed fixture / roster row shouldn't crash the UI).
    Missing `homeRuns` ⇒ sorts as 0.
    """
    out: list[dict] = []
    for entry in roster:
        position = entry.get("position") or {}
        if not position:
            log.warning(
                "Roster entry missing position; treating as non-pitcher: %s",
                _name_of(entry) or "<unknown>",
            )
        if position.get("type") == "Pitcher":
            continue
        out.append(entry)
    return sorted(out, key=lambda e: (-_hr_of(e), _name_of(e)))


# `field` is re-exported for downstream helpers in Plan 04-02 (pre-empts an import churn commit).
__all__ = ["ViewModel", "field", "_sorted_teams", "_sorted_hitters"]
