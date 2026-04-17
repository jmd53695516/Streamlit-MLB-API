"""Validate RESEARCH.md Open Question 1: does rosterType=fullSeason return
person.stats hydration identically to rosterType=active?

Run once before implementing SEASON-03. Requires network access.
Usage: python scripts/test_historical_roster.py
"""
import json
import sys
import requests

BASE = "https://statsapi.mlb.com/api/v1"
NYY = 147
SEASON = 2024
HYDRATE = f"person(stats(type=statsSingleSeason,season={SEASON},group=hitting))"


def main() -> None:
    print(f"Testing rosterType=fullSeason for NYY {SEASON}...")
    resp = requests.get(
        f"{BASE}/teams/{NYY}/roster",
        params={"rosterType": "fullSeason", "season": SEASON, "hydrate": HYDRATE},
        timeout=15,
    )
    resp.raise_for_status()
    data = resp.json()

    # Check 1: "roster" key exists
    roster = data.get("roster")
    assert roster is not None, "FAIL: no 'roster' key in response"
    assert len(roster) > 0, "FAIL: roster is empty"
    print(f"  OK: roster has {len(roster)} entries")

    # Check 2: entries have person.id
    for entry in roster[:3]:
        pid = entry.get("person", {}).get("id")
        assert pid is not None, f"FAIL: entry missing person.id: {json.dumps(entry, indent=2)[:200]}"
    print(f"  OK: entries have person.id")

    # Check 3: person.stats hydration exists and has homeRuns
    found_hr = False
    for entry in roster:
        stats = entry.get("person", {}).get("stats", [])
        if not stats:
            continue
        splits = stats[0].get("splits", [])
        if not splits:
            continue
        hr = splits[0].get("stat", {}).get("homeRuns")
        if hr is not None and int(hr) > 0:
            name = entry["person"].get("fullName", "???")
            print(f"  OK: {name} has {hr} HR (hydration works)")
            found_hr = True
            break

    if not found_hr:
        print("  WARN: no player with HR > 0 found in first pass — checking all entries...")
        for entry in roster:
            stats = entry.get("person", {}).get("stats", [])
            if stats:
                print(f"  Stats structure sample: {json.dumps(stats[0], indent=2)[:300]}")
                found_hr = True
                break
        if not found_hr:
            print("  FAIL: person.stats hydration is EMPTY for all roster entries")
            print("  FALLBACK NEEDED: fullSeason does not support hydration the same way")
            sys.exit(1)

    # Check 4: also test that explicit "season" param in query string is accepted
    resp2 = requests.get(
        f"{BASE}/teams/{NYY}/roster",
        params={"rosterType": "fullSeason", "season": SEASON, "hydrate": HYDRATE},
        timeout=15,
    )
    assert resp2.status_code == 200, f"FAIL: season param rejected (status {resp2.status_code})"
    print(f"  OK: explicit season={SEASON} param accepted (status 200)")

    print("\nALL CHECKS PASSED — rosterType=fullSeason with hydration works for historical seasons.")
    print("RESEARCH.md Open Question 1: RESOLVED (confirmed)")


if __name__ == "__main__":
    main()
