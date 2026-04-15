"""Fixture capture for Phase 1 — writes raw JSON to tests/fixtures/.

Invoke with:
    python scripts/record_fixtures.py

Uses the PRIVATE `_raw_*` helpers in mlb_park.services.mlb_api so captures
bypass @st.cache_data (which silently no-ops outside `streamlit run` anyway,
but we want guaranteed fresh fetches regardless of where the script runs).

Per RESEARCH.md Open Question #1 (A6): **additive on re-run**. Existing
`feed_*.json` files are preserved even if Judge's HR set shifts across
captures (e.g., a game reclassification drops an old HR). To force a clean
re-capture, manually delete the fixture files first.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from mlb_park.config import YANKEES_TEAM_ID, JUDGE_PERSON_ID
from mlb_park.services.mlb_api import (
    _raw_teams,
    _raw_roster,
    _raw_game_log,
    _raw_game_feed,
    _raw_venue,
)

SEASON = 2026
FIXTURES = Path(__file__).resolve().parents[1] / "tests" / "fixtures"


def _write(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    print(f"  wrote {path.relative_to(FIXTURES.parents[1])} "
          f"({path.stat().st_size:,} bytes)")


def main() -> int:
    FIXTURES.mkdir(parents=True, exist_ok=True)
    print(f"Capturing fixtures to {FIXTURES}/")

    # 1. Teams
    print("1. /teams?sportId=1")
    teams = _raw_teams()
    _write(FIXTURES / "teams.json", teams)
    assert len(teams) == 30, f"Expected 30 teams, got {len(teams)}"

    # 2. Yankees roster — verify Judge personId still resolves
    print(f"2. /teams/{YANKEES_TEAM_ID}/roster (Yankees)")
    roster = _raw_roster(YANKEES_TEAM_ID)
    _write(FIXTURES / f"roster_{YANKEES_TEAM_ID}.json", roster)
    judge = next(
        (p for p in roster if p["person"]["id"] == JUDGE_PERSON_ID), None
    )
    assert judge is not None and "Judge" in judge["person"]["fullName"], (
        f"personId {JUDGE_PERSON_ID} no longer maps to Aaron Judge — "
        f"re-verify via /teams/{YANKEES_TEAM_ID}/roster and update config.py"
    )

    # 3. Judge gameLog
    print(f"3. /people/{JUDGE_PERSON_ID}/stats gameLog season={SEASON}")
    log = _raw_game_log(JUDGE_PERSON_ID, SEASON)
    _write(FIXTURES / f"gamelog_{JUDGE_PERSON_ID}_{SEASON}.json", log)

    # 4. Per-game feeds for Judge HR games — ADDITIVE
    hr_games = [g for g in log if int(g["stat"]["homeRuns"]) >= 1]
    print(f"4. /game/{{pk}}/feed/live for {len(hr_games)} Judge HR game(s)")
    if not hr_games:
        # Criterion #4 still satisfied if prior runs captured HR game feeds.
        note = FIXTURES / "feeds_empty.note.txt"
        note.write_text(
            f"On this capture date, Judge had 0 HR games in {SEASON}. "
            f"Older feed_*.json fixtures from prior runs remain valid.\n",
            encoding="utf-8",
        )
        print(f"  (no HR games today — note at {note.name})")
    for g in hr_games:
        game_pk = int(g["game"]["gamePk"])
        target = FIXTURES / f"feed_{game_pk}.json"
        if target.exists():
            print(f"  skip feed_{game_pk}.json (exists, additive policy)")
            continue
        feed = _raw_game_feed(game_pk)
        _write(target, feed)

    # 5. All 30 unique home venues
    venue_ids = sorted({t["venue"]["id"] for t in teams})
    print(f"5. /venues/{{id}}?hydrate=location,fieldInfo for {len(venue_ids)} venues")
    for vid in venue_ids:
        target = FIXTURES / f"venue_{vid}.json"
        if target.exists():
            # Venues rarely change; skip unless user wants refresh.
            print(f"  skip venue_{vid}.json (exists, additive policy)")
            continue
        _write(target, _raw_venue(vid))

    print(f"\nDone. Fixtures in {FIXTURES}/")
    existing = sorted(FIXTURES.glob("*.json"))
    print(f"Total JSON fixtures on disk: {len(existing)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
