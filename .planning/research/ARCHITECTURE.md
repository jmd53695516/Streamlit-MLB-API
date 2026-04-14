# Architecture Research

**Domain:** Streamlit single-user data-viz app over MLB StatsAPI (read-only HTTP)
**Researched:** 2026-04-14
**Confidence:** HIGH for Streamlit/caching patterns and coordinate math; MEDIUM for exact Gameday coordinate constants (home-plate origin, scale) — these should be validated empirically with one known HR in Phase 1.

## Standard Architecture

### System Overview

```
┌──────────────────────────────────────────────────────────────┐
│                     Streamlit app.py (UI)                    │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐   │
│  │ Team select │→ │Player select│→ │ Stadium select      │   │
│  └─────────────┘  └─────────────┘  └─────────────────────┘   │
│             │             │                   │              │
│             ▼             ▼                   ▼              │
│  ┌──────────────────────────────────────────────────────┐    │
│  │          controller.build_view(team, player, venue)  │    │
│  └──────────────────────────────────────────────────────┘    │
├──────────────────────────────────────────────────────────────┤
│                      Service layer                           │
│  ┌────────────────┐  ┌──────────────┐  ┌───────────────┐     │
│  │ hr_pipeline.py │  │ park_model.py│  │ plotting.py   │     │
│  │ (orchestrate)  │  │ (geometry)   │  │ (mpl/plotly)  │     │
│  └───────┬────────┘  └──────┬───────┘  └───────┬───────┘     │
├──────────┼──────────────────┼──────────────────┼─────────────┤
│          ▼                  ▼                  ▼             │
│  ┌─────────────────────────────────────────────────────┐     │
│  │             mlb_api.py  (HTTP + st.cache_data)      │     │
│  │   teams | roster | gameLog | game_feed | venue      │     │
│  └─────────────────────────────────────────────────────┘     │
├──────────────────────────────────────────────────────────────┤
│                 statsapi.mlb.com/api/v1                      │
└──────────────────────────────────────────────────────────────┘
```

### Component Responsibilities

| Component | Owns | Does NOT own |
|-----------|------|--------------|
| `app.py` | Streamlit layout, selectors, session state, calling controller | Any HTTP, any math |
| `controller.py` | Orchestrates: given (team, player, venue) return a `ViewModel` for rendering | HTTP details, plotting primitives |
| `mlb_api.py` | All HTTP. One function per endpoint. All `@st.cache_data` decorators live here. Returns raw dicts or thin typed models | Business logic, filtering, math |
| `hr_pipeline.py` | Player → list of `HREvent` objects (one per HR with hitData) | HTTP, plotting |
| `park_model.py` | Venue geometry: `Park` dataclass, `fence_distance_at_angle(angle)`, `clears_fence(distance, angle, park)` | Fetching, plotting |
| `plotting.py` | Draws stadium outline + HR dots on a figure from `Park` + `List[HREvent]` | Fetching, verdict computation |
| `models.py` | Dataclasses: `Team`, `Player`, `Park`, `HREvent`, `ClearVerdict`, `ViewModel` | Behavior |
| `config.py` | Base URL, timeouts, cache TTLs, coordinate constants | — |

**Rule:** Imports flow downward only. `plotting` does not import `mlb_api`. `park_model` has no I/O. `mlb_api` knows nothing about HRs.

## Recommended Project Structure

```
streamlit_mlb_hr/
├── app.py                    # Streamlit entrypoint, selectors, layout
├── controller.py             # build_view(team_id, player_id, venue_id) -> ViewModel
├── services/
│   ├── __init__.py
│   ├── mlb_api.py            # HTTP + caching (only module that touches requests)
│   ├── hr_pipeline.py        # gameLog -> HR games -> feed -> HREvent[]
│   ├── park_model.py         # Park geometry, fence interpolation, verdict
│   └── plotting.py           # Matplotlib/Plotly rendering
├── models.py                 # Dataclasses
├── config.py                 # Constants (base URL, TTLs, coord origin)
├── data/
│   └── venues_cache.json     # Optional on-disk seed of 30 venues (see below)
├── tests/
│   ├── test_park_model.py    # Pure-function geometry tests (no network)
│   ├── test_hr_pipeline.py   # With mocked mlb_api
│   └── fixtures/             # Saved JSON from real API calls
├── requirements.txt
└── README.md
```

### Structure Rationale

- **Flat-ish over deeply nested.** 8–10 files total; a hobby app doesn't need `src/domain/entities/`.
- **`services/` folder** isolates the three pure-logic modules (pipeline, geometry, plotting) from UI and I/O.
- **Single HTTP module** is the only place `requests` is imported and the only place `@st.cache_data` appears — makes cache behavior auditable in one file.
- **`models.py` at root** because every layer uses them; avoiding an import cycle via a neutral location.
- **`tests/fixtures/`** with real recorded JSON is worth the disk space — the StatsAPI is unofficial and undocumented, so schema regressions are the main risk.

## Architectural Patterns

### Pattern 1: Cached HTTP Wrappers (one per endpoint)

**What:** Each StatsAPI endpoint gets one top-level function in `mlb_api.py` decorated with `@st.cache_data(ttl=...)`. Never call `requests.get` outside this module.

**Why:** `st.cache_data` keys on function args and pickles the return value. Keeping one function per endpoint makes the cache key obvious and the TTL explicit.

**Example:**

```python
# services/mlb_api.py
import requests, streamlit as st
from config import BASE_URL, TTL_VENUE, TTL_ROSTER, TTL_GAMELOG, TTL_FEED

@st.cache_data(ttl=TTL_VENUE, show_spinner=False)   # 24h — venues rarely change
def get_venue(venue_id: int) -> dict:
    r = requests.get(f"{BASE_URL}/venues/{venue_id}",
                     params={"hydrate": "fieldInfo"}, timeout=10)
    r.raise_for_status()
    return r.json()["venues"][0]

@st.cache_data(ttl=TTL_TEAMS)       # 24h
def get_teams() -> list[dict]: ...

@st.cache_data(ttl=TTL_ROSTER)      # 6h
def get_roster(team_id: int) -> list[dict]: ...

@st.cache_data(ttl=TTL_GAMELOG)     # 1h — updates as season progresses
def get_game_log(player_id: int, season: int) -> list[dict]: ...

@st.cache_data(ttl=TTL_FEED)        # 7d — a completed game's feed is immutable
def get_game_feed(game_pk: int) -> dict: ...
```

**Trade-off:** `st.cache_data` is per-Streamlit-session-process; if the app restarts, cache is cold. For venues we add a thin on-disk fallback (see Pattern 3).

### Pattern 2: Pipeline as a Pure Function with Injected Client

**What:** `hr_pipeline.extract_hrs(player_id, season, api=mlb_api)` takes the api module as a dependency. Testable by passing a stub module in tests.

**Example:**

```python
# services/hr_pipeline.py
def extract_hrs(player_id: int, season: int, api=mlb_api) -> list[HREvent]:
    log = api.get_game_log(player_id, season)
    # Filter to games with homeRuns >= 1 from the gameLog stat line
    hr_games = [g for g in log if g["stat"]["homeRuns"] >= 1]
    events = []
    for g in hr_games:
        feed = api.get_game_feed(g["game"]["gamePk"])
        events.extend(_hrs_for_batter(feed, player_id))
    return events

def _hrs_for_batter(feed: dict, batter_id: int) -> list[HREvent]:
    plays = feed["liveData"]["plays"]["allPlays"]
    out = []
    for p in plays:
        if p["result"]["eventType"] != "home_run": continue
        if p["matchup"]["batter"]["id"] != batter_id: continue
        hd = p.get("hitData") or {}
        coords = hd.get("coordinates") or {}
        if "coordX" not in coords or "totalDistance" not in hd:
            continue  # skip; see error boundaries
        out.append(HREvent(
            game_pk=feed["gamePk"], play_id=p["about"]["atBatIndex"],
            date=p["about"]["startTime"][:10],
            distance=float(hd["totalDistance"]),
            launch_speed=hd.get("launchSpeed"),
            launch_angle=hd.get("launchAngle"),
            coord_x=float(coords["coordX"]),
            coord_y=float(coords["coordY"]),
            venue_id=feed["gameData"]["venue"]["id"],
        ))
    return out
```

**Trade-off:** Passing the module as a param is slightly un-Pythonic but beats monkey-patching in tests.

### Pattern 3: Eager-Once Venue Load with Disk Fallback

**What:** On first run of the app, fetch all 30 venues and persist to `data/venues_cache.json`. On subsequent cold starts, read from disk and only re-fetch if file missing or stale (>30 days).

**Why:** Venues rarely change (dimension changes happen a few times per decade). `st.cache_data` alone re-fetches on every app process restart; disk cache eliminates that. 30 venues × one call each is cheap but pointless to repeat.

```python
# services/mlb_api.py
VENUES_FILE = Path("data/venues_cache.json")
VENUES_STALE_DAYS = 30

def load_all_parks() -> dict[int, Park]:
    if VENUES_FILE.exists() and _age_days(VENUES_FILE) < VENUES_STALE_DAYS:
        raw = json.loads(VENUES_FILE.read_text())
    else:
        team_venues = {t["venue"]["id"] for t in get_teams()}
        raw = {vid: get_venue(vid) for vid in team_venues}
        VENUES_FILE.parent.mkdir(exist_ok=True)
        VENUES_FILE.write_text(json.dumps(raw))
    return {int(vid): Park.from_api(v) for vid, v in raw.items()}
```

Call `load_all_parks()` once at app start and stash in `st.session_state["parks"]`.

### Pattern 4: Geometry as Pure Functions on a `Park` Dataclass

**What:** Park dimensions are parsed once into a `Park` with six (angle, distance) fence samples plus foul-line angles. A pure function `fence_distance_at(park, angle_deg) -> feet` does the interpolation.

**See "Geometry Approach" section below for full detail.**

### Pattern 5: ViewModel Between Controller and UI

**What:** `controller.build_view()` returns one `ViewModel` dataclass containing everything the UI needs: list of HRs with per-park verdicts, summary stats, and the `Park` for plotting. UI does no computation.

```python
@dataclass
class ViewModel:
    player_name: str
    stadium: Park
    hrs: list[HRWithVerdicts]  # each has list of 30 bool verdicts + selected-stadium bool
    summary: Summary           # total, avg_parks_cleared, no_doubters, cheapies
```

**Why:** Keeps `app.py` declarative — just layout and bindings.

## Data Flow

### Selector-Driven Flow

```
User picks Team
    ↓
app.py reads team_id from selectbox
    ↓
mlb_api.get_roster(team_id)              [cached 6h]
    ↓
Player selectbox populates
    ↓
User picks Player
    ↓
User picks Stadium  (from already-loaded parks dict)
    ↓
controller.build_view(team_id, player_id, venue_id)
    │
    ├─ parks = st.session_state["parks"]                   (loaded once at startup)
    ├─ hrs   = hr_pipeline.extract_hrs(player_id, season)
    │            ├─ api.get_game_log(player_id)            [cached 1h]
    │            └─ for each HR game:
    │                  api.get_game_feed(game_pk)          [cached 7d — game done]
    ├─ verdicts = [park_model.clears_all_parks(hr, parks) for hr in hrs]
    └─ return ViewModel(...)
    ↓
app.py renders:
    - plotting.draw_field(selected_park, hrs_with_verdicts)
    - summary card, HR table
```

### Cache Hierarchy (what lives where, TTL)

| Layer | Key | TTL | Rationale |
|-------|-----|-----|-----------|
| Disk (`venues_cache.json`) | all 30 venues | 30 days | Dimensions rarely change; survives app restarts |
| `@st.cache_data` on `get_teams` | — | 24h | Teams stable within a season |
| `@st.cache_data` on `get_roster` | team_id | 6h | Roster moves happen daily-ish |
| `@st.cache_data` on `get_game_log` | player_id, season | 1h | Updates nightly during season |
| `@st.cache_data` on `get_game_feed` | game_pk | 7d | A completed game's feed is immutable |
| `@st.cache_data` on `get_venue` | venue_id | 24h | Fallback when disk miss |
| `st.session_state["parks"]` | — | session | Parsed `Park` objects (avoid re-parsing) |

### Call Budget for One Player View

Assume a 30-HR hitter spread across ~28 games:

- 1 `get_teams` (cold) or 0 (warm)
- 1 `get_roster(team)` per team selection
- 1 `get_game_log(player, season)`
- ~28 `get_game_feed(game_pk)` on first view of this player
- 0 venue calls (loaded at startup)

Total: ~30 calls first time for a given player, **0 calls on any re-render** while caches are warm. Subsequent player re-selects are cheap because game feeds are cached by `game_pk` — overlap between players on same team is common.

## Geometry Approach

This is the core technical risk. Specification below is detailed enough to implement.

### Coordinate System (Gameday `hitData.coordinates`)

Based on widely-reported community findings (MLB doesn't document this):

- Origin approx `(x0, y0) = (125.0, 199.0)` pixels — home plate
- Y axis points **down the image** (i.e., a ball hit to center field has `coordY < 199`)
- Units: scaled pixels. The community constant is `2.29` feet per unit (sometimes reported as `2.495`); **calibrate in Phase 1** by finding a known 400 ft center-field HR and back-solving.

Given `(coordX, coordY)`:

```python
dx = coord_x - X0            # east-west (+ = toward RF)
dy = Y0 - coord_y            # north-south (+ = toward outfield); note the flip
distance_units = sqrt(dx*dx + dy*dy)
distance_ft    = distance_units * FT_PER_UNIT   # sanity-check vs hitData.totalDistance
spray_deg      = degrees(atan2(dx, dy))         # 0 = straight CF, -45 = LF line, +45 = RF line
```

**Convention used throughout the app:** spray angle in degrees, `-45` = LF line, `0` = dead center, `+45` = RF line. We use this angle — not `hitData.coordinates` directly — for fence lookups, so the angle is park-agnostic.

We prefer `hitData.totalDistance` (authoritative, the ball's actual projected distance) over distance derived from `coordX/Y`. Coords are used only for the angle.

### Park Fence Model

`fieldInfo` provides six dimensions (feet): `leftLine, left, leftCenter, center, rightCenter, right, rightLine`. Map to fixed angles:

| Field point | Angle (deg) |
|-------------|-------------|
| Left-field line | -45 |
| Left-field power alley | -30 |
| Left-center | -22.5 |
| Center | 0 |
| Right-center | +22.5 |
| Right-field power alley | +30 |
| Right-field line | +45 |

(Some venues expose 6 points, some 7 — handle both by building from whatever keys are present. Missing keys: fall back by linear interp between neighbors.)

### Interpolation: Linear in (angle, distance)

**Recommendation: piecewise linear interpolation.** Reasons:

1. Only 6–7 samples spanning 90°. Cubic spline over sparse samples tends to overshoot (oscillation near the line/alley), producing false "clears" near foul poles.
2. Real outfield walls are piecewise-straight segments (quirks like the Crawford Boxes aside), so linear is actually more physically faithful than a smooth curve.
3. Trivial to implement; no scipy dependency.

```python
# services/park_model.py
from bisect import bisect_left

@dataclass(frozen=True)
class Park:
    venue_id: int
    name: str
    angles: tuple[float, ...]     # sorted ascending, e.g. (-45, -30, -22.5, 0, 22.5, 30, 45)
    fences: tuple[float, ...]     # feet, parallel to angles
    # optional: elevation, roof

def fence_distance_at(park: Park, angle_deg: float) -> float:
    a = park.angles; d = park.fences
    if angle_deg <= a[0]:  return d[0]
    if angle_deg >= a[-1]: return d[-1]
    i = bisect_left(a, angle_deg)
    t = (angle_deg - a[i-1]) / (a[i] - a[i-1])
    return d[i-1] * (1 - t) + d[i] * t

def clears_fence(hr_distance_ft: float, spray_deg: float, park: Park) -> bool:
    return hr_distance_ft >= fence_distance_at(park, spray_deg)
```

**Foul filter:** before scoring, clamp/reject `|spray_deg| > 45` (foul territory — shouldn't happen for a HR but defensive).

### Stadium Outline Rendering

The six fence points plus home plate form a closed polygon — good enough for v1 and matches what fans recognize as a "ballpark outline."

```python
# services/plotting.py
def field_polygon(park: Park, n_per_segment: int = 1) -> np.ndarray:
    """Return (N, 2) array of (x_ft, y_ft) points: home -> LF line -> ... -> RF line -> home."""
    pts = [(0.0, 0.0)]  # home plate
    for ang, dist in zip(park.angles, park.fences):
        rad = math.radians(ang)
        pts.append((dist * math.sin(rad), dist * math.cos(rad)))  # +y = CF, +x = RF
    pts.append((0.0, 0.0))
    return np.array(pts)

def draw_field(park: Park, hrs: list[HRWithVerdict]) -> Figure:
    fig, ax = plt.subplots(figsize=(7, 7))
    poly = field_polygon(park)
    ax.fill(poly[:,0], poly[:,1], alpha=0.08)
    ax.plot(poly[:,0], poly[:,1], linewidth=2)               # outfield wall
    # foul lines: home to LF-line and RF-line fence points
    ax.plot([0, poly[1,0]], [0, poly[1,1]], '--', alpha=0.5)
    ax.plot([0, poly[-2,0]], [0, poly[-2,1]], '--', alpha=0.5)
    for hr in hrs:
        rad = math.radians(hr.spray_deg)
        x = hr.distance * math.sin(rad)
        y = hr.distance * math.cos(rad)
        ax.scatter(x, y, c='green' if hr.clears_here else 'red', s=40, edgecolors='black')
    ax.set_aspect('equal'); ax.set_xlim(-400, 400); ax.set_ylim(-50, 500)
    ax.set_title(park.name)
    return fig
```

**Matplotlib vs Plotly:** Matplotlib is the right default — static, simple, cheap, and the hover interactivity Plotly adds isn't essential for 30–40 dots. Start matplotlib; swap to Plotly later only if hover tooltips (e.g., date + exit velo on hover) become a must-have.

## Error Boundaries

Explicit behavior for each failure mode:

| Scenario | Handling |
|----------|----------|
| API slow / timeout | `requests` with `timeout=10`; wrap each cached function and on `requests.exceptions.RequestException` re-raise as `MLBAPIError`. Controller catches and returns `ViewModel.error("…")`. UI shows `st.error()` with a retry button that calls `st.cache_data.clear()` on the offending function. |
| Player has 0 HRs | `hr_pipeline.extract_hrs` returns `[]`. UI shows an informational card ("No HRs yet this season") and skips the plot. |
| `hitData` missing on a play | Skip the play with a `logging.warning(play_id)`. Add to an "excluded" counter surfaced in a small debug expander ("2 HRs excluded: missing hitData"). Don't crash. |
| `fieldInfo` absent on a venue | Park is "incomplete." `load_all_parks` logs a warning and excludes that park from the "parks cleared" denominator (show "cleared 17 of 28 parks with known dims"). Selecting that park for the outline shows an `st.warning` and a fallback generic diamond. |
| Coord calibration sanity fail | At app startup, pick the most recent HR with `totalDistance` in the cache and check that distance-from-coords is within 10% of `totalDistance`. If not, log a calibration warning. Don't crash — `totalDistance` is the authoritative input anyway. |
| HTTPS 5xx from MLB | Retry once after 1s with jitter (inside `mlb_api`), then raise. |
| Non-current season in `get_game_log` | Not supported in v1 per PROJECT scope; controller enforces `season = current_year`. |

## Build Order

Phases match the expected roadmap phases; each is testable in isolation.

1. **Phase 1 — API + fixtures.** `mlb_api.py` with the 5 endpoint functions + cache decorators. Write `tests/fixtures/` by saving real JSON for one team, one player, a few games, a few venues. No UI yet; verify via a scratch script.
2. **Phase 2 — Geometry.** `models.py` + `park_model.py`. Pure-function, 100% unit-tested. No network. Calibrate coord-to-feet against a recorded HR's `totalDistance`.
3. **Phase 3 — HR pipeline.** `hr_pipeline.py` over cached fixtures. End-to-end "player_id → HREvent[]" green before touching Streamlit.
4. **Phase 4 — Controller + minimal UI.** `controller.build_view` + `app.py` with the three selectors and a JSON dump of the ViewModel. Confirm the pipeline drives the UI.
5. **Phase 5 — Plotting.** `plotting.draw_field`. Single stadium, one player.
6. **Phase 6 — Summary + per-HR table + polish.** Add summary card, HR detail table, error-boundary UX, disk venue cache.
7. **Phase 7 — (optional) Plotly swap**, wall-height TODO, caching knobs.

## Anti-Patterns

### Anti-Pattern 1: Plotting module calls the API

**What people do:** Convenience function `plot_player_hrs(player_id, venue_id)` that fetches inside.
**Why wrong:** Ties rendering to network latency; defeats `st.session_state` caching; untestable without mocks.
**Instead:** Plotting takes fully-resolved `Park` + `HREvent[]`. Fetching is the controller's job.

### Anti-Pattern 2: Fetching all 162 games per team

**What people do:** Iterate the team schedule and pull every game feed.
**Why wrong:** ~162 calls per player when ~28 will do; pointless load on an unofficial API.
**Instead:** gameLog is a per-player stat with `homeRuns` per game — filter to `homeRuns > 0` first, *then* fetch feeds only for those games.

### Anti-Pattern 3: Cubic spline for fence interpolation

**What people do:** `scipy.interpolate.CubicSpline(angles, fences)` because it looks smooth.
**Why wrong:** Oscillation/overshoot near LF/RF lines produces phantom "cleared the fence" verdicts at -44°. Real walls are piecewise-linear anyway.
**Instead:** Piecewise linear (see geometry section).

### Anti-Pattern 4: Global `requests.Session` without timeout

**What people do:** `requests.get(url)` with no timeout.
**Why wrong:** A single stalled request hangs the whole Streamlit rerun.
**Instead:** `timeout=(3, 10)` (connect, read) on every call, centralized in `mlb_api._get()`.

### Anti-Pattern 5: Caching the whole ViewModel

**What people do:** `@st.cache_data` on `controller.build_view`.
**Why wrong:** Its inputs are cheap IDs but the cache entry is fat (30 HRs × 30 parks of verdicts); cache invalidation becomes coarse — change one thing and you rebuild everything.
**Instead:** Cache at the HTTP layer only. The controller is fast when HTTP is warm.

### Anti-Pattern 6: Storing raw JSON in session_state

**What people do:** `st.session_state["feed"] = feed_json` for every game.
**Why wrong:** Memory bloat; duplicates the cache; re-serialized per session.
**Instead:** Keep only parsed `Park` dict and the current `ViewModel` in session state. Let `@st.cache_data` own the raw JSON.

## Scaling Considerations

This is a single-user local app; scaling is not a concern. Two dimensions worth noting:

| Dimension | At hobby scale | If ever shared |
|-----------|---------------|----------------|
| API calls | ~30 cold per player, 0 warm | Add a disk-backed HTTP cache (e.g., `requests-cache`) so feeds persist across restarts |
| Compute | Trivial; 30 HRs × 30 parks = 900 verdicts | Still trivial |

## Integration Points

### External Services

| Service | Integration | Gotchas |
|---------|-------------|---------|
| statsapi.mlb.com | REST, no auth, no published rate limit | Unofficial — schema can change silently. Record fixtures. |

### Internal Boundaries

| Boundary | Communication | Notes |
|----------|---------------|-------|
| `app.py` → `controller.py` | Direct function call with IDs | Only place UI touches logic |
| `controller.py` → `services/*` | Direct call | Controller composes pipeline + park_model + plotting |
| `services/*` → `mlb_api.py` | Only `hr_pipeline` calls it | `park_model` and `plotting` must be I/O-free |
| Any → `models.py` | Shared dataclasses | No behavior; avoid cycles |

## Sources

- Streamlit docs on `st.cache_data` and `st.session_state` (HIGH — official, stable since 1.18)
- MLB StatsAPI endpoint shapes as already verified in PROJECT.md (HIGH — user-verified)
- Gameday coordinate constants (`X0≈125`, `Y0≈199`, `~2.29 ft/unit`): community-reported, not official (MEDIUM — **requires Phase 1 calibration against `totalDistance`**)
- Piecewise-linear vs cubic for sparse outfield samples: reasoning from geometry, not a citation (MEDIUM — defensible; validate visually by overplotting fences for 2–3 parks)

---
*Architecture research for: Streamlit MLB HR park-factor viz*
*Researched: 2026-04-14*
