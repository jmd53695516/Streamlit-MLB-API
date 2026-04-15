# Phase 1 Fixtures

Raw JSON recorded from `statsapi.mlb.com` by `scripts/record_fixtures.py`.
These fixtures let Phase 2+ tests run offline — no network required.

## Layout

- `teams.json` — response of `/api/v1/teams?sportId=1` (30 teams)
- `roster_147.json` — Yankees active roster (personId 592450 = Aaron Judge)
- `gamelog_592450_2026.json` — Judge 2026 regular-season game log (gameType=R)
- `feed_{gamePk}.json` — full `/api/v1.1/game/{gamePk}/feed/live` response
  for each 2026 game in which Judge hit >=1 HR
- `venue_{venue_id}.json` — `fieldInfo`+`location` hydrate for each of
  30 team home venues

## Re-running the recorder

```
python scripts/record_fixtures.py
```

**Additive policy:** existing `feed_*.json` and `venue_*.json` are preserved
on re-run. To force a clean re-capture, delete fixture files manually first.

**Calibration target (Phase 2):** any Judge HR with complete `hitData`
(non-ITP, distance + coordinates present) can back-solve the Gameday
coord-to-feet transform. See the `hitData` field inside `feed_*.json`
under `liveData.plays.allPlays[i].playEvents[-1].hitData` for HR plays
(where `result.eventType == "home_run"`).
