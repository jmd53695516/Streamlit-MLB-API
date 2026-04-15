"""Phase 1 smoke validation.

Invoke with:
    streamlit run scripts/smoke.py

Running as plain `python scripts/smoke.py` will *appear* to work but every call
will hit the network because @st.cache_data silently no-ops without a
ScriptRunContext (RESEARCH.md Pitfall 1). Always use `streamlit run`.

Renders 5 green sections — one per endpoint — plus a final section proving
load_all_parks() persists to data/venues_cache.json. Re-run after the first
success to verify ROADMAP criterion #3 (cold-2nd-run uses disk, no network).
"""
import streamlit as st

from mlb_park.config import YANKEES_TEAM_ID, JUDGE_PERSON_ID, VENUES_FILE
from mlb_park.services import mlb_api

st.set_page_config(page_title="Phase 1 Smoke", layout="wide")
st.title("Phase 1 Smoke Validation")
st.caption("Every section should render green on first and second run.")

# 1. Teams
st.header("1. Teams")
teams = mlb_api.get_teams()
st.success(f"Got {len(teams)} teams (expected 30). First team: {teams[0]['name']!r}")
assert len(teams) == 30, f"Expected 30 teams, got {len(teams)}"

# 2. Roster (Yankees)
st.header(f"2. Roster (team_id={YANKEES_TEAM_ID} — Yankees)")
roster = mlb_api.get_roster(YANKEES_TEAM_ID)
judge_present = any(p["person"]["id"] == JUDGE_PERSON_ID for p in roster)
st.success(f"Got {len(roster)} roster entries. Judge present: {judge_present}")
assert judge_present, "Aaron Judge (personId 592450) not found in Yankees active roster"

# 3. GameLog (Judge 2026)
st.header(f"3. GameLog (personId={JUDGE_PERSON_ID}, season=2026)")
log = mlb_api.get_game_log(JUDGE_PERSON_ID, 2026)
hr_games = [g for g in log if int(g["stat"]["homeRuns"]) >= 1]
st.success(f"Got {len(log)} games played, {len(hr_games)} with >=1 HR")

# 4. Game Feed (first HR game if any)
st.header("4. Game Feed (first Judge HR game)")
if hr_games:
    first_game_pk = hr_games[0]["game"]["gamePk"]
    feed = mlb_api.get_game_feed(first_game_pk)
    venue_name = feed["gameData"]["venue"]["name"]
    n_plays = len(feed["liveData"]["plays"]["allPlays"])
    st.success(
        f"Feed gamePk={feed['gamePk']} venue={venue_name!r} plays={n_plays}"
    )
else:
    st.info("No HR games yet this season — skipping game-feed check.")

# 5. All 30 Parks (disk-backed cache)
st.header("5. load_all_parks() — all 30 venues, disk cache")
parks = mlb_api.load_all_parks()
sample_park = next(iter(parks.values()))
st.success(
    f"Got {len(parks)} parks. Sample fieldInfo keys: "
    f"{sorted(sample_park.get('fieldInfo', {}).keys())}"
)
assert len(parks) == 30, f"Expected 30 venues, got {len(parks)}"

# Disk-cache evidence
st.divider()
st.subheader("Disk cache evidence (ROADMAP criterion #3)")
if VENUES_FILE.exists():
    import time
    age_s = time.time() - VENUES_FILE.stat().st_mtime
    st.write(f"**Path:** `{VENUES_FILE}`")
    st.write(f"**Size:** {VENUES_FILE.stat().st_size:,} bytes")
    st.write(f"**Age:** {age_s:,.1f} seconds since last write")
    st.info(
        "To verify criterion #3: note the mtime/age above, then re-run this page. "
        "The age should INCREASE (file not rewritten) — all 30 venues served from disk."
    )
else:
    st.error(f"Expected disk cache at {VENUES_FILE} but file is missing!")
