# Pitfalls Research

**Domain:** Streamlit + MLB StatsAPI HR spray/park-factor viz
**Researched:** 2026-04-14
**Confidence:** MEDIUM (StatsAPI is undocumented; specifics verified from reverse-engineering blogs, Seamheads, FanGraphs, and Streamlit docs)

## Critical Pitfalls

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

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Store raw JSON responses in `st.session_state` instead of a real cache | Zero setup | Memory blows up, lost on every reload, no TTL | Prototyping only — swap to `st.cache_data` before Phase 3 |
| Hardcode the 30 venue IDs and dimensions | No API call for venues | Camden-Yards-style mid-season changes go undetected | Fine for a frozen v1 demo; document the freeze date |
| Assume `hitData.coordinates` is always present | Simpler code | KeyError on ITP / rain-shortened games | Never — costs ~10 lines of `.get()` chains to fix |
| Name-based player dropdown (no IDs) | Shorter code | Same-name bugs, silent wrong-player results | Never |
| Skip wall-height modeling | PROJECT.md already accepts this | "Green Monster" HRs misclassified at Fenway vs. other parks | Accepted for v1 per PROJECT.md; revisit in v2 |
| Single giant `app.py` | Fastest to write | Testing spray math or API parsing in isolation becomes hard | Fine under ~300 lines; split once it grows |

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| `statsapi.mlb.com/api/v1` | No `hydrate` param → missing `fieldInfo` / `person.currentTeam` | Always `?hydrate=fieldInfo` for venues, `?hydrate=team(roster)` when needed |
| `game/{pk}/feed/live` | Parsing top-level `liveData.plays.allPlays`, missing that HR events are under `playEvents` within a play for hitData | Walk `allPlays[].result.eventType == "home_run"` → use the *play-level* `playEvents[-1].hitData` (the ball-in-play event) |
| `/people/{id}/stats?stats=gameLog` | Not setting `group=hitting` → pitcher stats returned for two-way players (Ohtani) | Always specify `group=hitting`; for Ohtani, explicitly filter to batting gameLog |
| Venue fieldInfo | Treating `leftField` as "LF line" (it's the LF power alley; `leftLine` is the foul line) | Map labels carefully; Left_Line = foul pole, Left = ~22.5°, Left_Center = ~67.5° from opposite foul |
| `requests` with no timeout | App hangs on MLB CDN hiccup | `requests.get(url, timeout=(5, 15))` always |
| `st.cache_data` with `requests.Session` as arg | `UnhashableParamError` | Prefix with `_session` or construct inside the function |

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| Fetching full game feed for every team game | 10+ second player load, 429s | Use gameLog HR-count to filter games first | Immediately — a 162-game player = 160 MB+ |
| No on-disk cache across Streamlit reruns | Re-fetching 60 games every code save | Add `.cache/games/{pk}.json` beside `st.cache_data` | During development (every save) |
| Recomputing park comparison on every rerender | Slider/widget changes trigger full recompute | Cache `compute_parks_cleared(coordX, coordY, distance)` keyed on floats | When >20 HRs shown |
| Plotly with one trace per HR | Slow pan/zoom in browser | One Scatter trace with `color` array, not 40 traces | >30 HRs on one chart |
| Fetching all 30 venues on startup | 3–5 seconds blank screen | Fetch venues lazily or prefetch once with a long TTL | Every cold start |

## Security Mistakes

| Mistake | Risk | Prevention |
|---------|------|------------|
| Committing a `User-Agent` with personal email into public git | Spam / unwanted contact | Load UA from env var or a local untracked file |
| Exposing the app publicly via Streamlit Cloud without caching | Your hobby app becomes a free MLB-API proxy, drawing throttling or MLB takedown | Keep it local, or put it behind auth, or add strict per-IP rate limiting |
| Trusting user-entered team/player IDs without validation | SSRF via malformed URL if you ever template raw input into URLs | Always validate IDs are integers before formatting into endpoints |

Note: this is a single-user local hobby app per PROJECT.md — security surface is small. Primary concern is API-terms-of-use, not classic web security.

## UX Pitfalls

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| Blank screen while fetching 60 game feeds | User thinks app is broken | `st.status()` / spinner with "Loading 14/60 games..." |
| Showing 0 HRs for a just-traded player without explanation | "Is this app broken?" | Detect empty results, show "Player moved to {team} on {date}; showing full-season HRs." |
| Silently dropping ITP HRs | User's total HR count doesn't match Baseball Reference | Show ITP count separately: "18 over-the-fence + 1 inside-the-park" |
| Spray chart with no orientation markers | User can't tell LF from RF | Always draw foul lines, label bases, show batter handedness indicator |
| Parks-cleared "out of 30" without context | User doesn't know which 4 parks the ball *didn't* clear | Hover tooltip listing the specific parks the HR would not clear |
| Fence polygon drawn as straight-line segments | Looks unprofessional, misleading near dogleg walls | Smooth curve (PCHIP) + note "approximate, 6 measured points" |

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

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| Coordinate orientation inverted | LOW | Fix transform in one place; visual verification on one known HR |
| Missing `hitData` crashes app | LOW | Wrap in `.get()` chains; add a "data unavailable" fallback path |
| Rate-limited (429) | LOW–MEDIUM | Back off 60s, add on-disk cache, reduce concurrency |
| Wrong player due to same-name | MEDIUM | Rekey all caches on personId; invalidate name-keyed caches |
| Fence interpolation wrong | MEDIUM | Rewrite as angle-based PCHIP; re-run park-comparison for all cached HRs |
| Camden Yards using stale 2022 dimensions | LOW | Force-refresh venue cache; verify `fieldInfo` values match current MLB.com ground-rules page |
| Streamlit version bump breaks cache | MEDIUM | Pin version, clear `.streamlit/` cache dir, re-test |

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| Missing `hitData` / ITP HRs | Phase 2 (data fetching) | Unit test on a game feed known to contain an ITP HR; null-safe extraction tests |
| Coordinate orientation / scale | Phase 3 (spray math) | Visual sanity: one known Judge HR lands in LF for RHH |
| Fence interpolation | Phase 3 (park compare) | PCHIP curve compared against published ballpark diagrams |
| Same-name players / trades | Phase 1 (selectors) + Phase 2 | Test case: a known mid-season trade from previous season |
| Streamlit caching | Phase 2 (API client) | No `UnhashableParamError` in logs; cold/warm load time delta > 5x |
| Season boundaries | Phase 1 (defaults) + Phase 2 | Manual test: set year to 2025 in January, confirm graceful empty state |
| Rate limiting | Phase 2 (API client) | Script: 30 rapid player-switches without 429 |
| Walk-off / distance gaps | Phase 3 (park compare) | Sanity-bound check against launch physics |
| Version skew | Phase 0 (scaffolding) | Pinned `requirements.txt`, one-command reproducible install |
| Venue dimension staleness (Camden) | Phase 2 (venue fetch) + README caveat | Compare `fieldInfo` to current MLB.com ground rules page |

## Sources

- [Reverse engineering MLB Gameday — Part 1](https://www.andschneider.dev/post/mlb-reverse-eng-part1/) — coordinate system origin (125, ~210), image-space pixel grid
- [indiemaps.com: visualizing MLB hit locations](https://indiemaps.com/blog/2009/07/visualizing-mlb-hit-locations-on-a-google-map/) — the 2.5 scale factor and `(125.42, 198.27)` home-plate origin in feet
- [TotalZone using MLB Gameday Hit Locations](https://www.baseballprojection.com/special/tz_hitlocation.htm) — scaling and orientation
- [Seamheads Ballparks Database](https://www.seamheads.com/ballparks/about.php) — standard angles for LF, LCF, CF, RCF, RF measurement points
- [FanGraphs: Camden Yards new dimensions (2022)](https://blogs.fangraphs.com/wall-over-but-the-shoutin-camden-yards-gets-new-dimensions/) — `fieldInfo` values change between seasons
- [MLB.com Orioles wall modification (2022)](https://www.mlb.com/news/orioles-camden-yards-left-field-wall-modifications) — 333/384/398 configuration
- [ESPN: Orioles moving wall again (2024→2025)](https://www.espn.com/mlb/story/_/id/42413260/orioles-set-again-move-left-field-wall-camden-yards) — 374/376 new configuration
- [Streamlit caching docs](https://docs.streamlit.io/develop/concepts/architecture/caching) — `cache_data` pickle semantics
- [streamlit/streamlit #11528](https://github.com/streamlit/streamlit/issues/11528) — v1.44 serialization regression
- [streamlit/streamlit #8308](https://github.com/streamlit/streamlit/issues/8308) — async still unsupported in cache decorators
- [toddrob99/MLB-StatsAPI](https://github.com/toddrob99/MLB-StatsAPI) — reference for endpoint/hydrate patterns (not used as a dep per PROJECT.md, but useful as a schema reference)
- [MLB StatsAPI endpoint (live venue fetch example)](https://statsapi.mlb.com/api/v1/venues/2681?hydrate=location,fieldInfo) — shape of `fieldInfo`

---
*Pitfalls research for: Streamlit + direct statsapi.mlb.com HR park-factor viz*
*Researched: 2026-04-14*
