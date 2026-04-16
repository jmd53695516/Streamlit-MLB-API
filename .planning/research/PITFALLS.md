# Pitfalls Research

**Domain:** Streamlit + MLB StatsAPI HR spray/park-factor viz
**Researched:** 2026-04-14 (v1.0) / updated 2026-04-16 (v1.1 multi-season + cloud deploy)
**Confidence:** MEDIUM (StatsAPI is undocumented; specifics verified from reverse-engineering blogs, Seamheads, FanGraphs, and Streamlit docs)

---

## Part A — v1.0 Pitfalls (original)

### Pitfall 1: `hitData` missing or partial on certain HR plays

**What goes wrong:**
Code assumes every HR play has a populated `hitData` dict with `coordinates.coordX/coordY`, `totalDistance`, `launchSpeed`, `launchAngle`. In reality:
- **Inside-the-park HRs** often have coordinates of the *fielded* location (where the ball landed in play), not a "projected landing". `totalDistance` may be short (e.g., 340 ft) or missing.
- **Pre-Statcast / minor-league rehab games / spring training feeds** may omit launch metrics entirely.
- **Review-reversed plays** (ground-rule double reviewed into a HR, or HR reversed on review): the HR event may reference a play whose `hitData` was computed for the original ruling.
- Some early-season / weather-abbreviated games have been observed with `hitData: {}` or no `coordinates` subkey.

**Why it happens:**
Statcast/Hawk-Eye tracking is opt-in by broadcast infrastructure and can go dark. The API surfaces whatever the `game/{pk}/feed/live` GUMBO feed has, with no guarantee of field presence.

**How to avoid:**
- Treat every `hitData` field as `Optional`. Use `.get()` chains or a small `safe_get(d, "a.b.c")` helper.
- Build a small classifier: `has_landing_coords`, `has_distance`, `has_launch_metrics` — and degrade the UI per-HR (e.g., show "distance unavailable — excluded from park comparison") instead of crashing or silently dropping.
- Explicitly flag inside-the-park HRs (`result.eventType == "home_run"` + `totalDistance < ~330` or a dedicated check against the play description) and either exclude them from park comparison or mark them "ITP — not fence-dependent".

**Warning signs:**
KeyError/TypeError on a specific player's game. Charts where a HR lands 280 ft from home plate. Silent NaN in the parks-cleared count.

**Phase to address:** Phase 2 (data fetching / HR extraction).

---

### Pitfall 2: Gameday coordinate system — Y-axis is inverted and origin is per-image, not absolute

**What goes wrong:**
Naively using `coordX, coordY` as Cartesian (x right, y up) puts every HR in the infield or behind home plate. The Gameday coordinate system treats the **top-left** of a 250x250 image as origin, so:
- `coordX ≈ 125` is the centerfield line (not zero)
- `coordY ≈ 200` is home plate (larger Y = closer to home plate)
- Moving toward CF means Y *decreases*
- Spray angle computed without flipping Y will be mirrored across the x-axis

The recommended transform is roughly `x_ft = 2.5 * (coordX - 125.42)` and `y_ft = 2.5 * (198.27 - coordY)`. Scale and origin vary slightly per venue.

**Why it happens:**
The coordinates originated from pixel positions on a scorer's 250x250 field diagram, not a physics coordinate system. This is not documented in any official MLB spec — only in reverse-engineering writeups.

**How to avoid:**
- Pin the transform in a single `coords_to_feet(coordX, coordY)` function with constants documented. Unit-test it with 3–4 known HRs (e.g., a pulled LF HR should land at positive x for RHH, negative for LHH mirror).
- Compute spray angle as `atan2(x_ft, y_ft)` where angle 0 = dead center, negative = LF, positive = RF (or choose a convention and stick to it). Verify by eyeballing one Aaron Judge HR vs. one Shohei Ohtani HR.
- Treat the ~125/~198 origin as approximate; for HR plotting, small offsets (<2 ft) don't matter, but don't bake in sub-foot precision claims.

**Warning signs:**
All HRs clustering in one quadrant. Spray chart showing balls behind home plate. Left-handed and right-handed batters looking identical. "Pulled" HRs landing to opposite field.

**Phase to address:** Phase 3 (coordinate math + spray angle), with a visual sanity-check test.

---

### Pitfall 3: Fence distance interpolation with only 6 labeled points

**What goes wrong:**
`fieldInfo` gives `leftLine`, `left`, `leftCenter`, `center`, `rightCenter`, `right`, `rightLine` (7 values, some venues 5–6). These are **not** evenly spaced in angle — the foul lines are 0° and 90° from home plate, LF/RF are roughly 22.5°, LCF/RCF are roughly 67.5° from the opposite line, and CF is 45°. Naive "lerp by index" produces a fence that kinks weirdly near the foul poles.

Additionally:
- **Camden Yards** (BAL) changed dimensions twice recently (2022 "Walltimore" push-out, 2025 partial pull-in). The `fieldInfo` endpoint returns *current* dimensions; mid-season changes are rare but have happened.
- Foul territory / shape of dogleg walls (Fenway's Green Monster wraparound, Houston's old Tal's Hill era, Camden's 2022 sharp dogleg) can't be captured by 6 numbers. A ball hit to a "corner" angle in real life may be well inside the interpolated curve.

**Why it happens:**
The fieldInfo schema predates modern analytics' need for full fence polygons. Six markers was "good enough" for TV graphics.

**How to avoid:**
- Map each label to its *angle from home plate* explicitly (e.g., leftLine=−45°, left=−22.5°, leftCenter=−11.25°, center=0°, rightCenter=+11.25°, right=+22.5°, rightLine=+45°). Interpolate in angle space, not index space. Verify against a published diagram.
- Use monotone cubic or PCHIP interpolation (not linear) to avoid fence "bumps" between markers. Angle values above are approximate — cite a source (Seamheads, FanGraphs, a published ballpark diagram) in a constants file.
- Call out the Camden Yards caveat explicitly in the UI or README: fence dimensions are current-as-of API fetch, not historical for HRs earlier in the season.
- Document the wall-height limitation already in PROJECT.md — add that interpolated distance is also an approximation of wall *shape*.

**Warning signs:**
A HR that cleared the fence at a real park is marked "not out" for that same park. Fence polyline looks like a hexagon instead of a smooth curve. Balls hit ~5° from the foul line appear to need 380 ft when the foul pole is listed at 330 ft.

**Phase to address:** Phase 3 (park-comparison logic) and Phase 4 (visualization).

---

### Pitfall 4: Same-name players, mid-season trades, and roster staleness

**What goes wrong:**
- `/teams/{id}/roster` returns the *current* roster. A player traded to another team mid-season won't appear under their original team, but their season HRs under the original uniform are still tied to their `personId`.
- Free agents / DFAs drop off rosters; the UI will show zero HRs for players who were productive earlier in the year.
- Duplicate names exist (Will Smith catcher LAD vs. Will Smith pitcher, multiple Luis Garcías, Francisco Álvarez vs. other Alvarezes). Picking by display name without ID is a bug factory.
- 40-man vs. 26-man vs. 60-day IL roster — hydration matters.

**Why it happens:**
Rosters are a snapshot; stats and play events are keyed to immutable `personId`. Hobby apps conflate the two.

**How to avoid:**
- Always key by `personId`; use name only for display. Store `(personId, currentTeamId, displayName)` in the selector.
- Hydrate the roster with `?rosterType=active` and decide whether to include IL: `?rosterType=fullSeason` (if supported) or union of active + 7/10/60-day IL.
- For "player traded away" cases: after the initial roster selection, fetch gameLog with `season=YYYY` regardless of current team — their full-season HRs will come through.
- In the UI, disambiguate: show jersey number or position next to same-name players.

**Warning signs:**
"Player X has 0 HRs" when the user knows they had 15. Dropdown missing a player who was traded. Selecting "Luis García" returns the wrong person's games.

**Phase to address:** Phase 1 (selectors) + Phase 2 (data fetching).

---

### Pitfall 5: Streamlit `st.cache_data` — parametrizing on large/unhashable args

**What goes wrong:**
- Passing a DataFrame, dict, or `requests.Session` as a function arg makes Streamlit attempt to hash it for the cache key. Large DataFrames slow every call; unhashable types raise `UnhashableParamError`.
- Using module-level mutable state (e.g., a dict of cached venues) *outside* the cache decorator defeats the TTL mechanism.
- Mutating a returned cached object (e.g., `df = get_hrs(...); df["new_col"] = ...`) — `st.cache_data` pickles on store and unpickles a fresh copy on read, so this is safe but *slow* for big objects (pickle roundtrip every hit).
- Cache-key explosion: caching by `(player_id, game_pk, date)` when `date` is derivable from `game_pk` doubles the cache footprint.
- A single Streamlit server serves all users from one cache; `st.cache_data` is keyed on arg hash only, not user — fine for public data like MLB HRs, but worth noting.

**Why it happens:**
`st.cache_data` is pickle-based and shared across sessions by default. Hobbyists often miss the hashing model.

**How to avoid:**
- Only pass primitive/hashable args: `int` IDs, `str` dates (ISO format), `tuple` of IDs. For a `requests.Session`, create it inside the function or wrap with `@st.cache_resource`.
- Prefix args you don't want to be part of the key with a leading underscore (`_session`) — Streamlit skips those in hashing.
- TTL: venues = 24h, rosters = 1h, gameLog = 15–30 min during season, individual `game/feed/live` for *completed* games = effectively immutable (1 week+), for in-progress games = 60s.
- Return immutable-friendly shapes (DataFrames, dataclasses). Never mutate a returned cached object — copy first.

**Warning signs:**
`UnhashableParamError` or `CachedObjectMutationWarning`. Slow first-paint after every code edit. Memory creeping up on long-running sessions. Stale data that won't refresh until the app restarts.

**Phase to address:** Phase 2 (API client + caching layer).

---

### Pitfall 6: `season=YYYY` edge cases and year-boundary weirdness

**What goes wrong:**
- In March (spring training) the API accepts `season=2026` for `gameType=S` (spring) but `gameLog` with default filters returns nothing — regular-season games haven't happened.
- Early April: gameLog exists but HRs ≈ 0 for many players — app looks broken.
- Late October / World Series: `gameType=R` ends in late Sept; WS HRs are `gameType=W`. A filter of `gameType=R` silently drops them.
- New Year / offseason: `season=2026` in January returns an empty set; user sees a blank dropdown.
- Doubleheaders: two `gamePk` values on the same date, both with HRs — don't dedupe on date alone.

**Why it happens:**
Season boundary logic is implicit in MLB's calendar, not in the client.

**How to avoid:**
- Compute the "current season" as: if month ≥ 3, current year; else previous year (with a manual override).
- Include regular-season AND postseason game types when relevant: `gameType=R,F,D,L,W` (regular, wildcard, division, LCS, WS). Document the choice.
- Surface an empty-state message: "No HRs yet for {player} in {season}. Season opens {date}." instead of a blank chart.
- Key game-level caches on `gamePk`, never on `(playerId, date)`.

**Warning signs:**
Blank dropdowns in January. "Why are Freddie Freeman's postseason HRs missing?" Two HRs on the same date getting counted once.

**Phase to address:** Phase 2 (data fetching) + Phase 1 (default selectors).

---

### Pitfall 7: Rate-limiting yourself — the fan-out problem

**What goes wrong:**
A naive implementation for "Aaron Judge this season":
1. Fetch gameLog (1 request) → 60 games with HRs
2. For each game, fetch `game/{pk}/feed/live` (60 requests, each ~1–5 MB of JSON)

That's ~200 MB of JSON per player selection, cold. Do that 30 times while developing and MLB's CDN starts throttling (403 / 429 / slow responses). The API is unofficial; there's no documented rate limit, but community reports suggest >~20 req/s sustained triggers throttling.

**Why it happens:**
`feed/live` is the only endpoint with per-play `hitData`; there's no "all HRs for a player" endpoint. You have to walk games.

**How to avoid:**
- Aggressive on-disk caching of completed games (they never change). Store raw JSON in `.cache/games/{gamePk}.json` in addition to `st.cache_data` in-memory.
- Use `/schedule?gamePk={pk}` or gameLog HR-count to skip fetching game feeds for games where the player didn't HR.
- Add a `requests.Session` with a polite `User-Agent: streamlit-hr-explorer/0.1 (joe.dollinger@gmail.com)` — no auth required but identifies you if MLB complains.
- Add a small `time.sleep(0.1)` between consecutive game-feed fetches, or use a token-bucket limiter.
- Don't prefetch all teams × players on startup. Lazy-fetch on selection.

**Warning signs:**
Sporadic 403 / 429 / connection resets. Responses suddenly gzipped or truncated. The Streamlit app taking 30+ seconds on first player load.

**Phase to address:** Phase 2 (API client with persistence + throttling).

---

### Pitfall 8: Walk-off HRs and trajectory/distance estimation gaps

**What goes wrong:**
On a walk-off HR, the ball may leave the park but tracking can stop at fence height — `totalDistance` is projected by Statcast's model, but in rare cases (ball into upper deck, obscured trajectory) the projection is missing or capped. Similarly, HRs that hit a facade or scoreboard may have a `totalDistance` that reflects the collision point, not the would-have-landed distance.

**Why it happens:**
`totalDistance` is a model output from Hawk-Eye trajectory fitting. When the tracker loses the ball (obstruction, crowd, lights), the model falls back to partial data.

**How to avoid:**
- Don't blindly trust `totalDistance` for the parks-cleared comparison. Cross-check against `launchSpeed` + `launchAngle` + a simple projectile model as a sanity bound (a 95 mph LA 30° ball can't travel 500 ft regardless of what the field says).
- For HRs with implausibly low `totalDistance` (< 330 ft for a non-ITP HR), flag them for review and either exclude or use a model-estimated distance.

**Warning signs:**
A HR listed at 290 ft that wasn't inside-the-park. Parks-cleared count of 30/30 on a clearly middling HR.

**Phase to address:** Phase 3 (park-comparison logic).

---

### Pitfall 9: Python / Streamlit version skew in 2026

**What goes wrong:**
- Streamlit 1.40+ (late 2024) deprecated `st.experimental_rerun` → `st.rerun`; `st.cache` (legacy) is fully removed as of 1.45 — copy-pasting older tutorials breaks.
- Streamlit 1.44 introduced a pickle-serialization change that broke caching of some custom classes (GitHub issue #11528). Returning plain dicts / DataFrames avoids this.
- Python 3.13 (released Oct 2024) changed some `datetime` deprecations (`datetime.utcnow()` → `datetime.now(timezone.utc)`); lint warnings in new Python.
- `requests` vs. `httpx`: both fine, but if using `asyncio` inside Streamlit callbacks you'll hit the event-loop conflicts Streamlit has documented.

**Why it happens:**
Rapid Streamlit release cadence + tutorial-driven hobby development = stale snippets.

**How to avoid:**
- Pin versions in `requirements.txt`: `streamlit>=1.45,<2.0`, `python>=3.11`.
- Use `st.rerun()` (not `experimental_rerun`). Use `st.cache_data` / `st.cache_resource` (not `st.cache`).
- Avoid async in cached functions — `st.cache_data` still doesn't support coroutines (issue #8308, still open).

**Warning signs:**
`AttributeError: module 'streamlit' has no attribute 'cache'`. Deprecation warnings in the terminal. Pickle errors after a Streamlit version bump.

**Phase to address:** Phase 0 (project scaffolding / pinning deps).

---

## Part B — v1.1 NEW Pitfalls: Multi-Season Support

### Pitfall 10: Season parameter not threaded through every call site

**What goes wrong:**
The v1.0 codebase has `CURRENT_SEASON = 2026` in `config.py`, imported as a module-level constant and used in `app.py` line 79 (`get_team_hitting_stats(team_id, CURRENT_SEASON)`), in `extract_hrs(player_id, season=None)` which falls back to `config.CURRENT_SEASON`, and implicitly in several other call paths. Adding a season selector widget and wiring it to `st.session_state["season"]` is easy. The pitfall is forgetting to pass `season` through every downstream call:

- `get_team_hitting_stats(team_id, season)` — needs season to show HR totals for that year's roster
- `extract_hrs(player_id, season)` — needs season for gameLog
- `controller.build_view(team_id, player_id, venue_id)` — currently uses its own `season` field; must receive season from caller
- Any place that does `from mlb_park.pipeline import CURRENT_SEASON` as a hardcoded default

If even one call site keeps the hardcoded constant, you get a silent split-brain: the selector shows "2023 season" but the player HR list is from 2026.

**Why it happens:**
Module-level constants feel safe for single-season apps. When season becomes a UI-driven variable, every consumer must receive it as an argument — but static imports don't remind you to update call sites.

**Prevention:**
- Add `season: int` as an explicit required parameter to `controller.build_view()`, `get_team_hitting_stats()`, and `extract_hrs()`. Remove the `season=None` fallback from `extract_hrs` once the selector exists — forced arguments catch every missing call site at import time.
- Grep for `CURRENT_SEASON` before shipping; every remaining reference is a bug.
- The `ViewModel.season` field already exists (confirmed in `controller.py`) — make sure it's populated from the caller's `season` argument, not from `config.CURRENT_SEASON`.

**Detection:**
Select 2022 season, pick a player who had 40 HR in 2022 but only 5 in 2026 — if the app shows 5, a call site is still using the hardcoded constant.

**Phase to address:** Phase 1 of v1.1 (season selector wiring).

---

### Pitfall 11: `st.cache_data` cache bloat across 5 seasons × all players

**What goes wrong:**
The v1.0 cache was bounded: one season, one player at a time, completed game feeds cached for 7d. With 5 selectable seasons, each player-season combination is a separate cache entry. A heavy user exploring multiple players × multiple seasons can accumulate:
- 5 seasons × 30 teams × ~15 hitters/team × gameLog = 2,250 gameLog cache entries
- Each `get_game_feed(gamePk)` for historical seasons is permanently valid (game is final), so TTL=7d means they accumulate for a week before eviction

On Community Cloud with ~1 GB memory limit, a single large historical season's game feeds for one prolific HR hitter (60 games × ~2 MB JSON = 120 MB unpickled) can eat a significant fraction of the total budget.

**Prevention:**
- For historical seasons (any season < current year), set `TTL_FEED` much longer or use `persist="disk"` on `get_game_feed` — disk-cached completed feeds survive app sleeps and consume cloud storage rather than RAM.
- Use `st.cache_data(ttl="30d", persist="disk")` for completed game feeds. Community Cloud provides ephemeral disk storage (not documented precisely but confirmed in forum posts).
- For TTL strategy: current-season gameLog stays at `1h`; historical-season gameLog can be `"30d"` (rosters are final, games won't change).
- Consider a `max_entries` cap: `@st.cache_data(ttl=..., max_entries=500)` to prevent unbounded growth.

**Detection:**
App crashes with a memory error after the user selects multiple seasons in sequence. Log the cache size (via `st.cache_data.clear()` and memory profiler) during development.

**Phase to address:** Phase 1 of v1.1 (multi-season API parameterization).

---

### Pitfall 12: Historical roster vs. historical HRs — showing the wrong roster for past seasons

**What goes wrong:**
`/teams/{id}/roster?rosterType=active` returns the **current** active roster, regardless of what season you request. If you select "NYY 2022" and call `get_team_hitting_stats(team_id=147, season=2022)`, the roster hydration `?hydrate=person(stats(type=statsSingleSeason,season=2022,group=hitting))` will correctly return 2022 stats — BUT the player list itself is the **2026 active roster**. Players who retired, were traded, or are newly signed appear incorrectly:

- Aaron Judge is on both (fine)
- A 2022 player who retired won't appear (their 2022 HRs are invisible)
- A 2026 player who wasn't on the 2022 team will appear with 0 HR (confusing)

**Prevention:**
- For the player selector in historical seasons, use `?rosterType=fullSeason&season=YYYY` if the API supports it (not verified — requires testing). The endpoint `/teams/{id}/roster?rosterType=active&season=YYYY` may return the historical season's active roster.
- Fallback approach: filter the current roster response to only show players with `stat.homeRuns >= 1` for the selected season — players with 0 HR in that season simply don't appear, which is correct UX behavior (you can't view their HRs anyway).
- Test with a retired player (e.g., Nelson Cruz, who retired after 2022) — they should NOT appear in the 2026 roster dropdown but SHOULD be discoverable via another path if the app ever supports player search.

**Detection:**
Select a past season. Verify the player list matches what rosters looked like that year (cross-reference Baseball Reference team pages).

**Phase to address:** Phase 1 of v1.1 (season selector + roster parameterization).

---

### Pitfall 13: Athletics / Oakland venue ID inconsistency across seasons

**What goes wrong:**
The Oakland Athletics played their last game at the Oakland Coliseum (venue ID: 10) on September 26, 2024. In 2025, they moved to Sutter Health Park in West Sacramento (a minor-league park). For 2026, the team is still the "Athletics" but at a temporary venue.

If your app builds the 30-park dropdown from `get_teams()` → `team["venue"]["id"]` for the **current** season, then:
- The 2024 or earlier Oakland HRs are associated with venue 10 (Oakland Coliseum fieldInfo)
- The 2025 venue may have different fieldInfo dimensions (Sutter Health Park is smaller — ~AAA dimensions)
- The current `load_all_parks()` disk cache at `data/venues_cache.json` has the **current** 30 venues — which may not include Oakland Coliseum for 2025+ seasons

When a user selects a 2022 player from the old A's, the app computes park comparisons against the current 30 venues. The stadium the player actually hit in (Oakland Coliseum) might not be in the dropdown.

**Prevention:**
- The 30-park comparison list is the current 30 venues (for "would this HR clear the fence?"). This is intentional and correct — the question is always "how does this HR compare against today's parks."
- However, the spray chart is drawn against the **selected** stadium's fieldInfo. If a user selects a 2022 Athletics player and wants to overlay on "their home park," Oakland Coliseum (venue 10) must still be fetchable via `/venues/10?hydrate=fieldInfo`.
- Add Oakland Coliseum (venue ID 10) as a supplemental fetchable venue even if it's no longer in the 30-team current set. Alternatively, acknowledge in the UI that the stadium list is current-season-only.
- For the park-comparison matrix, the 30-park set should be consistent (current season's active venues) and documented as such.

**Detection:**
Select the Athletics, pick season 2022, select a player who hit in Oakland — the stadium dropdown should either include Oakland Coliseum or show an explanatory message.

**Phase to address:** Phase 1 of v1.1 (venue set definition + historical stadium policy).

---

### Pitfall 14: Statcast data quality degrades sharply before 2015 — and is imperfect in 2015-2016

**What goes wrong:**
The v1.1 milestone targets "past 5 years," which as of 2026 means 2022–2026. Statcast was installed in all 30 parks starting with the **2015** season, so 2022+ seasons have mature, high-quality tracking. However:

- **2015**: 13.4% of all batted balls had missing Statcast data. By 2016 this dropped to ~1.5%. Both seasons are outside the v1.1 "past 5" window, but if the range ever expands, 2015 data will have significant null `hitData` rates.
- **2022-2026**: The tracking is high quality but not 100%. Rain-shortened games, outage events, and atypical trajectories (popups, choppers) still produce null `coordinates` or `totalDistance`. The existing v1.0 `has_*` flags in `HREvent` already handle this — they just need to be exercised with historical data that may trigger them more often.
- **The `hitData` null rate is higher for pre-2020 historical data** than for current-season data. The app will encounter more degraded HRs when users explore 2022-2023 vs. 2025-2026.

**Prevention:**
- The v1.0 extraction pipeline (`extract.py`, `HREvent`) already uses `has_landing_coords`, `has_distance`, `has_launch_metrics` flags per DATA-05. This is the right design — multi-season support inherits it automatically.
- Add a UI indicator for the degraded-HR rate in the selected season. E.g., "12 of 47 HRs missing distance data" in the summary card.
- When testing historical seasons during development, pick a 2022 player with known HRs and verify the plottable/non-plottable split is surfaced, not hidden.

**Detection:**
Select a 2022 player. Compare the app's total HR count against Baseball Reference. The difference = HRs the app has but can't plot. Verify the warning banner shows the correct count.

**Phase to address:** Phase 1 of v1.1 (testing with historical seasons).

---

### Pitfall 15: `venues_cache.json` on disk reflects today's venue set, not each season's

**What goes wrong:**
`load_all_parks()` writes `data/venues_cache.json` containing the 30 current venues keyed by venue ID. This file is:
1. Gitignored (correct for local dev)
2. NOT present on Streamlit Community Cloud at deploy time (the repo doesn't contain it)
3. Rebuilt from the API on first run

For a multi-season app, the 30-park comparison matrix should ideally reflect the venues active in the selected season. But rebuilding the venue cache per season would require 30 × 5 = 150 venue API calls on cold start, and the fence dimensions don't change year-to-year except for the rare mid-season modification (Camden Yards 2022, etc.).

**Prevention:**
- Keep the current behavior: 30 current venues, 30-day disk TTL. This is the right call for a hobby app — it's the "would this HR clear the fence TODAY?" framing.
- Document this explicitly in the UI: "Park dimensions reflect current season configuration."
- On Community Cloud, the disk cache is ephemeral (cleared on each deploy and potentially on app wake). The first cold-start after a deploy will fetch all 30 venues. With aggressive `st.cache_data` TTL and the disk-backed JSON, subsequent users in the same app session won't re-fetch.
- Do NOT try to version the venue cache by season — the complexity is not worth the accuracy gain for a hobby app.

**Detection:**
Deploy to Community Cloud. After a fresh deploy, verify the park dropdown populates correctly (triggering the 30-venue fetch). Time the first cold-start user experience.

**Phase to address:** Phase 2 of v1.1 (cloud deployment prep).

---

### Pitfall 16: `CURRENT_SEASON` hard-coded in `config.py` must be updated annually

**What goes wrong:**
`config.py` has `CURRENT_SEASON = 2026`. When the v1.1 season selector is added, `CURRENT_SEASON` becomes the **default** selected season (the one pre-selected when the app loads). If this constant is never updated, the app's default will silently become stale year after year.

**Prevention:**
- Replace `CURRENT_SEASON = 2026` with dynamic computation: if `datetime.now().month >= 3` use current year, else use current year - 1.
- Or keep it as a constant but gate it: the season selector's default is computed dynamically; `CURRENT_SEASON` is only used as a fallback in tests.
- Add a comment: `# MAINTENANCE: update each spring when new season opens`.

**Detection:**
Run the app in January 2027. The default season selector should show 2026, not 2027 (season hasn't started). Run it in April 2027 — it should default to 2027.

**Phase to address:** Phase 1 of v1.1 (season selector implementation).

---

## Part C — v1.1 NEW Pitfalls: Streamlit Community Cloud Deployment

### Pitfall 17: App hibernates after 12 hours of no traffic — cache is lost on wake

**What goes wrong:**
Streamlit Community Cloud hibernates apps that have no traffic for **12 hours** (reduced from 24h in March 2025). When the app wakes on the next visitor, it:
1. Cold-starts the Python process — all `st.cache_data` in-memory cache is gone
2. The disk-backed `venues_cache.json` may also be gone (ephemeral filesystem)
3. The first visitor after a cold start triggers all API calls: 30-venue fetch + team list + any player selections

For a hobby app shared with friends who visit occasionally, almost every visit will be a cold start. The 30-venue fetch (30 HTTP calls) takes 5-15 seconds on a cold start.

**Prevention:**
- Use `@st.cache_data(persist="disk")` on `load_all_parks()` or its constituent calls. Disk-persisted cache survives the sleep-and-wake cycle within the same deployment (not across new deploys).
- Add a clear loading indicator: `st.spinner("Loading park dimensions (first visit may take ~10 seconds)...")` — sets expectations for the cold-start user.
- The existing `venues_cache.json` disk write in `load_all_parks()` serves this purpose partially, but it's written to `data/` which may be ephemeral. Verify the write path works on Community Cloud (ephemeral writable filesystem is confirmed to exist but size is unspecified).
- Consider pre-populating `data/venues_cache.json` in the git repo (commit it) so the first visitor after a deploy doesn't pay the 30-venue fetch cost. Venue data changes at most once a season; committing it is safe. Add a manual refresh button for the maintainer.

**Detection:**
Deploy to Community Cloud. Visit the app. Wait 12+ hours (or simulate by stopping the app). Visit again. Measure the time to first interactive state.

**Phase to address:** Phase 2 of v1.1 (deployment prep).

---

### Pitfall 18: `st.cache_data` in-memory cache is NOT shared across simultaneous users on Community Cloud

**What goes wrong:**
On Streamlit Community Cloud, each app runs as a **single process** but with multiple WebSocket connections (one per browser tab/user). `st.cache_data` IS shared across users in that single process — which is correct and desirable for public MLB data. However:
- If the app is redeployed (new git push), the process restarts and all in-memory cache is cleared. Every new deploy = cold start for all users.
- The `_session = requests.Session()` module-level object (in `mlb_api.py`) is shared across all users in the process. This is correct behavior but means TCP connection pooling is shared — good for performance.
- The `data/venues_cache.json` disk write uses `tempfile.mkstemp` with atomic rename — this is correct and safe, but the temp directory used must be writable on Community Cloud. Use `dir=str(path.parent)` (already done in the code) to write temps to `data/`, not to the system temp dir.

**Prevention:**
- No action needed for the session sharing (it's correct). Document it in a code comment.
- For the deploy-invalidates-cache problem: commit `data/venues_cache.json` as a static artifact updated periodically. This means deploy does NOT trigger a 30-venue refetch.
- Test that `os.replace()` (atomic rename) works on the Community Cloud Linux filesystem (it does — Linux supports atomic rename within the same partition, and Community Cloud is Linux/Debian).

**Detection:**
Redeploy while a user is in the app. Verify the user sees a graceful reload (not an error). Verify the 30-venue fetch does or does not happen depending on whether `venues_cache.json` is in the repo.

**Phase to address:** Phase 2 of v1.1 (deployment prep).

---

### Pitfall 19: Community Cloud memory limit (~1 GB) — the multi-season game feed accumulation problem

**What goes wrong:**
Community Cloud apps are constrained to approximately **1 GB RAM** (community reports; not officially documented as of 2026). With multi-season support, a user who explores several players across several seasons can accumulate large amounts of in-memory cached game feeds:

- Each `game/feed/live` response is 1-5 MB of raw JSON, pickled by `st.cache_data`
- A player with 60 HR games × 3 MB/feed = 180 MB for one player in one season
- 3 players × 5 seasons = potentially 2.7 GB of game feed cache entries before TTL eviction

The app will be killed by the OOM reaper, showing users a "This app has gone over its resource limit" error.

**Prevention:**
- **Most important:** Use `@st.cache_data(ttl="7d", max_entries=200)` on `get_game_feed`. `max_entries` evicts the oldest entries (LRU) before memory grows unbounded.
- For historical seasons, the game feed JSON is immutable (finalized games don't change). Use `persist="disk"` and a long TTL. Disk storage on Community Cloud is more generous than RAM (not precisely documented, but likely several GB of ephemeral SSD).
- Do not load the full game feed JSON into a pandas DataFrame in memory. Keep game feed parsing lazy: extract only the HR plays from each feed immediately, then discard the raw dict. The `extract_hrs` pipeline already does this correctly via `_walk_feed_for_hrs` — don't cache intermediate DataFrames of the full feed.
- Consider caching only the extracted `HREvent` list per game (small), not the raw feed dict (large). This requires a restructuring of the cache boundary but pays off in multi-season deployments.

**Detection:**
On Community Cloud, explore 3+ players across 3+ seasons rapidly. Watch for the Streamlit memory limit error page. Check the app logs for OOM signals.

**Phase to address:** Phase 1-2 of v1.1 (multi-season cache design + deployment validation).

---

### Pitfall 20: Secrets management — no secrets needed for this app, but `secrets.toml` anti-patterns still apply

**What goes wrong:**
This app makes unauthenticated requests to `statsapi.mlb.com` — no API key is required. However, the `USER_AGENT` string in `config.py` currently contains `joe.dollinger@gmail.com`. Committing a personal email address to a public GitHub repo (required for Community Cloud free tier deployment) means:
- The email is publicly visible in the git history
- Spam and scraping risk

Additionally, if the app is ever extended to use a paid data source (Baseball Savant auth, a Cloudflare-protected endpoint, etc.), developers often make the mistake of putting credentials directly in `config.py` and committing them.

**Prevention:**
- Remove the email from `USER_AGENT` in `config.py` before making the repo public. Replace with a generic identifier: `mlb-park-explorer/1.1`.
- If any credential is ever added, use `st.secrets` with `.streamlit/secrets.toml` locally and the Community Cloud secrets UI for deployment. Never commit `secrets.toml`.
- Add `.streamlit/secrets.toml` to `.gitignore` now (even if empty), to establish the pattern before it's needed.
- The Community Cloud secrets management UI encrypts secrets at rest and in transit (Streamlit 1.35+ uses zero-knowledge encryption per official docs). It is safe for API keys.

**Detection:**
Before making the repo public, run `git log -p | grep -i "email\|key\|password\|secret\|token"` to verify no credentials are in history.

**Phase to address:** Phase 2 of v1.1 (deployment prep / repo publicization).

---

### Pitfall 21: Shared IP address — statsapi.mlb.com may rate-limit or block Community Cloud's egress IPs

**What goes wrong:**
All apps on Streamlit Community Cloud share a pool of outbound IP addresses (confirmed by forum discussions; the IPs are not published and "may change at any time without notice" per Streamlit docs). When multiple deployed apps simultaneously hit the same external API from the same IP pool:

- The external API (statsapi.mlb.com) sees many requests from the same IP ranges
- MLB's CDN (Akamai/Fastly) may apply rate limiting or temporary blocks to those IP ranges
- The app would start receiving 403, 429, or connection-reset errors that it would NOT receive locally

This is the same problem that causes Yahoo Finance and other APIs to rate-limit Community Cloud apps (documented in Streamlit forums). MLB's StatsAPI is unofficial with no documented rate limits, but it is known to throttle heavy use.

**Prevention:**
- The aggressive `st.cache_data` caching is the primary defense: most requests are served from cache after the first user loads a given player. A cold-start user may trigger 30-60 HTTP requests; subsequent users for the same player get cached responses.
- The existing retry logic in `_get()` (one retry after 1 second) handles transient throttling. Consider extending to exponential backoff: 1s, 2s, 4s.
- Add a polite delay between consecutive game-feed fetches: the existing code does not throttle the `for row in hr_rows: feed = api.get_game_feed(game_pk)` loop. Add `time.sleep(0.1)` between fetches when not in test mode.
- If MLB starts blocking Community Cloud IPs, the fallback is self-hosting (Railway, Fly.io, Render) where you control the egress IP. Document this in the README.
- Do NOT add a `Retry-After` header spammer or aggressive retry loop — that makes the throttling worse.

**Detection:**
Deploy and have 3-4 friends simultaneously load different players. Watch the Streamlit logs for 403/429/connection-reset errors. Compare response times to local development.

**Phase to address:** Phase 2 of v1.1 (deployment + post-deploy validation).

---

### Pitfall 22: GitHub repo must be public for Community Cloud free tier — code is exposed

**What goes wrong:**
Streamlit Community Cloud's free tier requires the GitHub repository to be public by default (private repos require additional OAuth permissions granted during setup, and are reportedly less stable on the free tier). Making the repo public means:
- All code, commit history, and any committed data files are world-readable
- If `data/venues_cache.json` is committed, it's public (that's fine — it's public MLB data)
- Any personal information in comments, config, or git history is exposed
- The `USER_AGENT` email issue (Pitfall 20) becomes a real privacy concern

**Prevention:**
- Before making the repo public, audit all files: `git log --all --name-only` and `git grep -i "email\|personal\|private"`.
- The repo CAN be private with Community Cloud (Streamlit grants additional GitHub OAuth scope for private repo access). This is the recommended approach for a personal hobby app. See the Streamlit docs on connecting a GitHub account.
- If keeping it public: ensure `data/` is gitignored, `USER_AGENT` is sanitized, and no personal information appears in any committed file.

**Detection:**
Before enabling the public deploy, do a `git log -p` review looking for PII or credentials.

**Phase to address:** Phase 2 of v1.1 (deployment prep).

---

### Pitfall 23: `pyproject.toml` vs `requirements.txt` — Community Cloud will find both and may behave unexpectedly

**What goes wrong:**
The project currently has BOTH `pyproject.toml` AND `requirements.txt` (confirmed in repo root). Community Cloud's documentation states it uses the "first environment configuration file it finds" and that you "cannot mix and match Python package managers." With both files present:
- Community Cloud may prefer `pyproject.toml` and ignore `requirements.txt`
- The `pyproject.toml` may have different (or missing) pinned versions compared to `requirements.txt`
- The deploy may succeed locally-equivalent but install slightly different package versions than expected

**Prevention:**
- Review what's in `pyproject.toml`. If it's only build-system config (not a dep list), Community Cloud should ignore it for package installation purposes and use `requirements.txt`.
- If `pyproject.toml` has `[project.dependencies]`, those will conflict with `requirements.txt`. Consolidate to one source of truth.
- Explicitly test: deploy to Community Cloud with the current file layout and verify the installed package versions in the deployment logs match the expected pins.
- The CLAUDE.md stack guidance recommends `requirements.txt` as the single source. If `pyproject.toml` was added only for dev tooling (e.g., ruff config, build metadata), it's safe to keep it — just ensure it has no `[project.dependencies]` that conflict.

**Detection:**
In the Community Cloud deployment logs, look for which package manager was detected and what versions were installed. Cross-reference against `requirements.txt`.

**Phase to address:** Phase 2 of v1.1 (deployment prep / dependency audit).

---

### Pitfall 24: Python version on Community Cloud — `runtime.txt` may be ignored

**What goes wrong:**
As of early 2026, multiple Community Cloud users report that placing `python-3.12` in a `runtime.txt` file is being **ignored**, with the deployment defaulting to Python 3.13 (the current default). Python 3.13 has some compatibility issues with certain C-extension packages. For this app's stack (streamlit, plotly, pandas, requests, numpy), Python 3.13 is generally fine — but it's worth verifying.

**Prevention:**
- Test a trial deploy and check the deployment logs for the Python version actually used.
- The CLAUDE.md stack doc recommends Python 3.12 as the target. If Community Cloud forces 3.13, verify all packages install without errors and the app runs correctly.
- If 3.13 causes issues, the alternative is to move to a self-hosted platform (Railway, Fly.io) where Python version is fully controlled.
- Do not rely on `runtime.txt` working reliably on Community Cloud as of 2026 — treat the Python version as whatever Community Cloud defaults to, and verify compatibility.

**Detection:**
Check the first few lines of the Community Cloud deploy logs for `Python 3.x.x`. Verify it matches expectations. If not, test the app thoroughly on the actual version.

**Phase to address:** Phase 2 of v1.1 (deployment setup).

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Store raw JSON responses in `st.session_state` instead of a real cache | Zero setup | Memory blows up, lost on every reload, no TTL | Prototyping only — swap to `st.cache_data` before Phase 3 |
| Hardcode the 30 venue IDs and dimensions | No API call for venues | Camden-Yards-style mid-season changes go undetected | Fine for a frozen v1 demo; document the freeze date |
| Assume `hitData.coordinates` is always present | Simpler code | KeyError on ITP / rain-shortened games | Never — costs ~10 lines of `.get()` chains to fix |
| Name-based player dropdown (no IDs) | Shorter code | Same-name bugs, silent wrong-player results | Never |
| Skip wall-height modeling | PROJECT.md already accepts this | "Green Monster" HRs misclassified at Fenway vs. other parks | Accepted for v1 per PROJECT.md; revisit in v2 |
| Single giant `app.py` | Fastest to write | Testing spray math or API parsing in isolation becomes hard | Fine under ~300 lines; split once it grows |
| Use `CURRENT_SEASON` constant when season is now a selector | Zero refactor cost | Silent stale season on year boundary | Never — creates split-brain data |
| Commit `venues_cache.json` to git | Eliminates 30-venue cold-start fetch | Requires annual manual update | Acceptable for a hobby app; document the update procedure |

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| `statsapi.mlb.com/api/v1` | No `hydrate` param → missing `fieldInfo` / `person.currentTeam` | Always `?hydrate=fieldInfo` for venues, `?hydrate=team(roster)` when needed |
| `game/{pk}/feed/live` | Parsing top-level `liveData.plays.allPlays`, missing that HR events are under `playEvents` within a play for hitData | Walk `allPlays[].result.eventType == "home_run"` → use the *play-level* `playEvents[-1].hitData` (the ball-in-play event) |
| `/people/{id}/stats?stats=gameLog` | Not setting `group=hitting` → pitcher stats returned for two-way players (Ohtani) | Always specify `group=hitting`; for Ohtani, explicitly filter to batting gameLog |
| Venue fieldInfo | Treating `leftField` as "LF line" (it's the LF power alley; `leftLine` is the foul line) | Map labels carefully; Left_Line = foul pole, Left = ~22.5°, Left_Center = ~67.5° from opposite foul |
| `requests` with no timeout | App hangs on MLB CDN hiccup | `requests.get(url, timeout=(5, 15))` always |
| `st.cache_data` with `requests.Session` as arg | `UnhashableParamError` | Prefix with `_session` or construct inside the function |
| Community Cloud deploy with `pyproject.toml` + `requirements.txt` | Ambiguous package manager detection | Ensure `pyproject.toml` has no `[project.dependencies]`; use `requirements.txt` as sole dep source |
| Multi-season season param | Hardcoded `CURRENT_SEASON` constant leaks through after adding selector | Pass `season: int` explicitly at every call boundary; grep for `CURRENT_SEASON` before ship |

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| Fetching full game feed for every team game | 10+ second player load, 429s | Use gameLog HR-count to filter games first | Immediately — a 162-game player = 160 MB+ |
| No on-disk cache across Streamlit reruns | Re-fetching 60 games every code save | Add `.cache/games/{pk}.json` beside `st.cache_data` | During development (every save) |
| Recomputing park comparison on every rerender | Slider/widget changes trigger full recompute | Cache `compute_parks_cleared(coordX, coordY, distance)` keyed on floats | When >20 HRs shown |
| Plotly with one trace per HR | Slow pan/zoom in browser | One Scatter trace with `color` array, not 40 traces | >30 HRs on one chart |
| Fetching all 30 venues on startup | 3–5 seconds blank screen | Fetch venues lazily or prefetch once with a long TTL | Every cold start |
| Community Cloud cold start (post-sleep) | All cache cleared, 30-venue re-fetch, slow first visitor | Commit `venues_cache.json` to repo; use `persist="disk"` on game feeds | After 12h idle on Community Cloud |
| Unbounded `st.cache_data` with multi-season | OOM after 3+ users explore different players × seasons | Add `max_entries=200` to `get_game_feed`; use `persist="disk"` for historical games | On Community Cloud with ~1 GB limit |

## Security Mistakes

| Mistake | Risk | Prevention |
|---------|------|------------|
| Committing a `User-Agent` with personal email into public git | Spam / unwanted contact | Load UA from env var or use a generic identifier |
| Exposing the app publicly via Streamlit Cloud without caching | Your hobby app becomes a free MLB-API proxy, drawing throttling or MLB takedown | Keep caching aggressive; add per-session rate limiting if needed |
| Trusting user-entered team/player IDs without validation | SSRF via malformed URL if you ever template raw input into URLs | Always validate IDs are integers before formatting into endpoints |
| Putting credentials in `config.py` for future paid API | Exposed in public git history | Use `st.secrets` + Community Cloud secrets UI; never commit creds |

Note: this is a hobby app — security surface is small. Primary concern is API-terms-of-use and personal-info hygiene before making the repo public.

## UX Pitfalls

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| Blank screen while fetching 60 game feeds | User thinks app is broken | `st.status()` / spinner with "Loading 14/60 games..." |
| Showing 0 HRs for a just-traded player without explanation | "Is this app broken?" | Detect empty results, show "Player moved to {team} on {date}; showing full-season HRs." |
| Silently dropping ITP HRs | User's total HR count doesn't match Baseball Reference | Show ITP count separately: "18 over-the-fence + 1 inside-the-park" |
| Spray chart with no orientation markers | User can't tell LF from RF | Always draw foul lines, label bases, show batter handedness indicator |
| Parks-cleared "out of 30" without context | User doesn't know which 4 parks the ball *didn't* clear | Hover tooltip listing the specific parks the HR would not clear |
| Fence polygon drawn as straight-line segments | Looks unprofessional, misleading near dogleg walls | Smooth curve (PCHIP) + note "approximate, 6 measured points" |
| Season selector with no default | User must manually pick a year before seeing any data | Default to current season (dynamic calculation, not hardcoded constant) |
| Cold-start delay with no explanation | First visitor after sleep thinks app is broken | Show spinner with "Waking up — loading park data (first visit may take ~15 seconds)" |
| App sleeping with no wake message | Visitor sees Streamlit's generic "wake" page | Community Cloud handles this automatically; no action needed, but set expectations in README |

## "Looks Done But Isn't" Checklist

- [ ] **Player selector:** Often missing traded/DFA'd/IL players — verify a mid-season trade case (e.g., last year's deadline deal) still shows full-season HRs
- [ ] **HR list:** Often missing inside-the-park HRs — verify total matches Baseball Reference / FanGraphs
- [ ] **Spray chart:** Often has wrong Y-axis orientation — verify a known pulled HR from a RHH lands where expected (LF side)
- [ ] **Park comparison:** Often uses linear interpolation by index — verify a ball near the foul line (~3° off) uses the `leftLine`/`rightLine` value, not `left`/`right`
- [ ] **Venue dimensions:** Often stale — verify Camden Yards shows 2025 (pulled-in) dimensions, not 2022 "Walltimore"
- [ ] **Caching:** Often no TTL on gameLog — verify a HR hit today shows up within the configured TTL (not stuck on yesterday's cache)
- [ ] **Coordinate transform:** Often off by scale factor — verify one known HR's computed (x_ft, y_ft) matches its `totalDistance` via `sqrt(x² + y²)` to within ~10%
- [ ] **Postseason:** Often missing — verify a World Series HR from last year shows up when selecting that player and last season
- [ ] **Error handling:** Often crashes on missing hitData — verify the app handles a game with `hitData: {}` gracefully
- [ ] **Rate limiting:** Often missing — verify 10 rapid player selections don't trigger 429 or noticeable slowdown
- [ ] **Season threading:** `CURRENT_SEASON` constant not replaced at all call sites — grep confirms zero remaining references after refactor
- [ ] **Historical roster:** Selecting 2022 season shows 2022-era players, not 2026 active roster
- [ ] **Multi-season cache:** After selecting 3 players × 3 seasons, app does not OOM on Community Cloud
- [ ] **Cold start:** After 12h idle, first Community Cloud visitor sees a helpful loading message, not a blank/crashed app
- [ ] **Repo hygiene:** No personal email, passwords, or API keys in git history before making repo public
- [ ] **Package manager:** Community Cloud deploy logs show `requirements.txt` was used (not `pyproject.toml` deps)

## Pitfall-to-Phase Mapping (complete, v1.0 + v1.1)

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| Missing `hitData` / ITP HRs | Phase 2 (data fetching) | Unit test on a game feed known to contain an ITP HR; null-safe extraction tests |
| Coordinate orientation / scale | Phase 3 (spray math) | Visual sanity: one known Judge HR lands in LF for RHH |
| Fence interpolation | Phase 3 (park compare) | PCHIP curve compared against published ballpark diagrams |
| Same-name players / trades | Phase 1 (selectors) + Phase 2 | Test case: a known mid-season trade from previous season |
| Streamlit caching basics | Phase 2 (API client) | No `UnhashableParamError` in logs; cold/warm load time delta > 5x |
| Season boundaries | Phase 1 (defaults) + Phase 2 | Manual test: set year to 2025 in January, confirm graceful empty state |
| Rate limiting | Phase 2 (API client) | Script: 30 rapid player-switches without 429 |
| Walk-off / distance gaps | Phase 3 (park compare) | Sanity-bound check against launch physics |
| Version skew | Phase 0 (scaffolding) | Pinned `requirements.txt`, one-command reproducible install |
| Venue dimension staleness (Camden) | Phase 2 (venue fetch) + README caveat | Compare `fieldInfo` to current MLB.com ground rules page |
| Season param not threaded (v1.1) | v1.1 Phase 1 | Grep: zero `CURRENT_SEASON` in non-config call sites; 2022 test player shows correct HR count |
| Cache bloat multi-season (v1.1) | v1.1 Phase 1 | `max_entries` set on `get_game_feed`; no OOM on Community Cloud after 3-player exploration |
| Historical roster mismatch (v1.1) | v1.1 Phase 1 | 2022 season player list cross-referenced against Baseball Reference team page |
| Athletics venue ID inconsistency (v1.1) | v1.1 Phase 1 | 2022 A's player can see Oakland Coliseum in stadium dropdown or sees explanatory note |
| Statcast quality degrades in older seasons (v1.1) | v1.1 Phase 1 | 2022 player: plottable/non-plottable split surfaced in UI, not hidden |
| `venues_cache.json` policy on cloud (v1.1) | v1.1 Phase 2 | Post-deploy cold start: park dropdown populates within 15s; document behavior |
| `CURRENT_SEASON` annual staleness (v1.1) | v1.1 Phase 1 | Dynamic computation in place; no hardcoded year after refactor |
| App hibernation / cold start (v1.1) | v1.1 Phase 2 | Post-sleep visit: loading spinner shown; app recovers without error |
| Shared Community Cloud cache behavior (v1.1) | v1.1 Phase 2 | Two simultaneous users see consistent data; redeploy clears cache gracefully |
| Community Cloud memory limit (v1.1) | v1.1 Phase 1-2 | `max_entries=200` + `persist="disk"` verified; no OOM after multi-season exploration |
| Secrets / email hygiene (v1.1) | v1.1 Phase 2 | `git log -p` shows no PII; `USER_AGENT` is generic |
| Shared IP rate limiting (v1.1) | v1.1 Phase 2 | 3 friends simultaneously load players; no 429 in logs |
| Public repo exposure (v1.1) | v1.1 Phase 2 | Repo audit: no PII, no creds, `data/` gitignored |
| `pyproject.toml` + `requirements.txt` conflict (v1.1) | v1.1 Phase 2 | Deploy logs confirm `requirements.txt` package manager; installed versions match pins |
| Python version on Community Cloud (v1.1) | v1.1 Phase 2 | Deploy logs confirm Python version; all packages install cleanly |

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| Coordinate orientation inverted | LOW | Fix transform in one place; visual verification on one known HR |
| Missing `hitData` crashes app | LOW | Wrap in `.get()` chains; add a "data unavailable" fallback path |
| Rate-limited (429) on Community Cloud | MEDIUM | Extend retry backoff; add `time.sleep(0.1)` in game-feed loop; consider self-hosting |
| Wrong player due to same-name | MEDIUM | Rekey all caches on personId; invalidate name-keyed caches |
| Fence interpolation wrong | MEDIUM | Rewrite as angle-based PCHIP; re-run park-comparison for all cached HRs |
| Camden Yards using stale 2022 dimensions | LOW | Force-refresh venue cache; verify `fieldInfo` values match current MLB.com ground-rules page |
| Streamlit version bump breaks cache | MEDIUM | Pin version, clear `.streamlit/` cache dir, re-test |
| Season constant not threaded | LOW-MEDIUM | Grep `CURRENT_SEASON`, update each call site, test with 2022 player |
| Community Cloud OOM | MEDIUM | Add `max_entries`, switch game feeds to `persist="disk"`, test under multi-user load |
| Community Cloud cold-start too slow | LOW | Commit `venues_cache.json`; add loading spinner with expected duration |
| PII found in git history | HIGH | Rewrite git history (`git filter-repo`); force push; notify anyone who cloned |

## Sources

- [Reverse engineering MLB Gameday — Part 1](https://www.andschneider.dev/post/mlb-reverse-eng-part1/) — coordinate system origin (125, ~210), image-space pixel grid
- [indiemaps.com: visualizing MLB hit locations](https://indiemaps.com/blog/2009/07/visualizing-mlb-hit-locations-on-a-google-map/) — the 2.5 scale factor and `(125.42, 198.27)` home-plate origin in feet
- [TotalZone using MLB Gameday Hit Locations](https://www.baseballprojection.com/special/tz_hitlocation.htm) — scaling and orientation
- [Seamheads Ballparks Database](https://www.seamheads.com/ballparks/about.php) — standard angles for LF, LCF, CF, RCF, RF measurement points
- [FanGraphs: Camden Yards new dimensions (2022)](https://blogs.fangraphs.com/wall-over-but-the-shoutin-camden-yards-gets-new-dimensions/) — `fieldInfo` values change between seasons
- [MLB.com Orioles wall modification (2022)](https://www.mlb.com/news/orioles-camden-yards-left-field-wall-modifications) — 333/384/398 configuration
- [ESPN: Orioles moving wall again (2024→2025)](https://www.espn.com/mlb/story/_/id/42413260/orioles-set-again-move-left-field-wall-camden-yards) — 374/376 new configuration
- [Streamlit caching docs](https://docs.streamlit.io/develop/concepts/architecture/caching) — `cache_data` pickle semantics, persist="disk", max_entries
- [streamlit/streamlit #11528](https://github.com/streamlit/streamlit/issues/11528) — v1.44 serialization regression
- [streamlit/streamlit #8308](https://github.com/streamlit/streamlit/issues/8308) — async still unsupported in cache decorators
- [Streamlit Community Cloud status and limitations](https://docs.streamlit.io/deploy/streamlit-community-cloud/status) — Linux/Debian, US-only hosting, rate limits
- [Streamlit Community Cloud app sleeping (forum)](https://discuss.streamlit.io/t/web-apps-keeps-on-sleeping-after-30-minutes-or-a-day-of-inactivity/97350) — 12h sleep threshold (March 2025 change)
- [Streamlit Community Cloud memory limit (forum)](https://discuss.streamlit.io/t/is-there-a-runtime-limit-other-than-memory-limit-on-streamlit-cloud-apps/61358) — ~1 GB RAM limit (community reported)
- [Streamlit Community Cloud secrets management](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/secrets-management) — st.secrets, secrets.toml, zero-knowledge encryption
- [Streamlit Community Cloud IP addresses (forum)](https://discuss.streamlit.io/t/ip-addresses-for-streamlit-community-cloud/75304) — shared IPs, external API rate limiting risk
- [Streamlit Community Cloud app dependencies](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/app-dependencies) — requirements.txt placement, package manager detection
- [Streamlit Cloud Python version ignored (forum)](https://discuss.streamlit.io/t/streamlit-cloud-using-python-3-13-despite-runtime-txt-specifying-3-11/113759) — runtime.txt unreliable in 2026
- [Oakland Athletics relocation timeline (Wikipedia)](https://en.wikipedia.org/wiki/Oakland_Athletics_relocation_to_Las_Vegas) — 2024 final Oakland game, 2025 Sacramento, 2028 Las Vegas target
- [FiveThirtyEight: MLB Hit Tracking Misses A Lot](https://fivethirtyeight.com/features/mlbs-hit-tracking-tool-misses-a-lot-of-hits/) — Statcast coverage gaps 2015 (13.4% missing), improving through 2016
- [Statcast Wikipedia](https://en.wikipedia.org/wiki/Statcast) — installed all 30 parks in 2015; no pre-2015 data
- [toddrob99/MLB-StatsAPI](https://github.com/toddrob99/MLB-StatsAPI) — reference for endpoint/hydrate patterns (not used as a dep per PROJECT.md, but useful as a schema reference)
- [MLB StatsAPI endpoint (live venue fetch example)](https://statsapi.mlb.com/api/v1/venues/2681?hydrate=location,fieldInfo) — shape of `fieldInfo`

---
*Pitfalls research for: Streamlit + direct statsapi.mlb.com HR park-factor viz*
*Originally researched: 2026-04-14 (v1.0)*
*Updated: 2026-04-16 (v1.1 multi-season + Community Cloud deployment)*
