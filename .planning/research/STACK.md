# Stack Research

**Domain:** Lightweight Streamlit data-visualization hobby app (MLB home-run park-factor explorer)
**Researched:** 2026-04-14
**Confidence:** HIGH (core stack verified against 2026 PyPI releases and official docs); MEDIUM on geometry choice (informed judgment for the specific workload).

## Context & Locked Decisions (do not re-open)

- UI framework: **Streamlit** (locked)
- MLB data source: **Direct HTTP to `statsapi.mlb.com/api/v1`** via a plain HTTP client — **no** third-party wrappers (e.g., `MLB-StatsAPI`) (locked)
- Scope: current season, single-user local app

Everything below is the supporting stack around those two pillars.

---

## Recommended Stack

### Core Technologies

| Technology | Version | Purpose | Why Recommended |
|---|---|---|---|
| Python | **3.12** (3.11 minimum) | Runtime | 3.12 is the current mainstream target for Streamlit 1.56 and the broader data-viz ecosystem; 3.13 still has sporadic wheel gaps for niche C-ext libs. 3.12 is the safe-and-fast default in April 2026. |
| Streamlit | **1.56.0** (released 2026-03-31) | UI framework | Locked. Pin to `>=1.55,<2.0` — 1.55 added `on_change` on `st.tabs`/`st.popover`/`st.expander` and `bind=` URL-state for widgets, both genuinely useful for cascading Team -> Player -> Stadium selectors. |
| requests | **2.32.x** | HTTP client to `statsapi.mlb.com` | Streamlit reruns top-to-bottom on every interaction — the app is **sync-first**. `requests` is the standard sync client, battle-tested, and the MLB StatsAPI is a handful of cached GETs per rerun (no concurrency win to justify `httpx`). Keep it boring. |
| plotly | **6.7.0** (released 2026-04-09) | Spray chart + stadium outline overlay | See "Plotting Decision" below. Plotly wins for interactive scatter-over-polygon with hover tooltips, which is exactly the spray-chart interaction pattern. |
| pandas | **2.2.x** | Tabular data wrangling (HR event table, per-park verdict matrix) | Mature, Streamlit-native (`st.dataframe`, `st.data_editor` both assume pandas), and performance is a non-issue at this data volume (~50 HRs x 30 parks = 1,500 rows max). Polars would be overkill and creates integration friction with `st.data_editor`. |

### Supporting Libraries

| Library | Version | Purpose | When to Use |
|---|---|---|---|
| numpy | **2.x** (whatever pandas 2.2 pulls in) | Vector math for the 30-park fence-distance interpolation | Pulled in transitively by pandas/plotly; use directly for the vectorized "is distance >= interpolated_fence_at(angle)" check across all 30 parks at once. |
| python-dateutil | latest | Parsing MLB StatsAPI date strings | Pulled in by pandas; handy for game-date parsing. No need to add explicitly. |

**Deliberately NOT adding:**
- `shapely` — see "Geometry Decision" below. Not worth the GEOS C dependency for this workload.
- `httpx` — sync-only app, no concurrency needs, `requests` suffices.
- `polars` — overkill at this data volume and worse Streamlit widget integration than pandas.
- `requests-cache` — `st.cache_data` already solves the caching problem at the right layer (the Streamlit function boundary). Adding `requests-cache` on top creates two overlapping caches with different invalidation models. See "Caching Decision" below.
- `matplotlib` — static-first, clumsy hover/click in Streamlit. Only reach for it if Plotly's polygon rendering surprises you.
- `altair` — fast and pretty, but the 5,000-row default limit and the Vega-Lite abstraction layer make custom polygon overlays (stadium outlines) awkward compared to Plotly's imperative `Scatter`/`Scatterpolar` traces.

### Development Tools

| Tool | Purpose | Notes |
|---|---|---|
| **uv** (Astral) | Package + venv manager | Use `uv` as a drop-in replacement for `pip`/`venv`. `uv pip install -r requirements.txt` works without any migration. 10-100x faster installs matter less than its automatic venv handling for a hobby project. |
| requirements.txt | Dependency pinning | Keep it as a flat `requirements.txt` (not `pyproject.toml` + lock). This is a single-file hobby app — `pyproject.toml` is ceremony. `uv` reads `requirements.txt` natively. |
| ruff | Linter/formatter (optional) | If you want any linting, ruff is the 2026 default. Skip if you don't care. |

---

## Installation

```bash
# Install uv once (Windows PowerShell or bash)
pip install uv  # or: winget install --id=astral-sh.uv

# Create venv and install deps
uv venv
uv pip install -r requirements.txt
```

**`requirements.txt`:**
```
streamlit>=1.55,<2.0
requests>=2.32,<3.0
plotly>=6.0,<7.0
pandas>=2.2,<3.0
```

That's it. Four direct dependencies. `numpy` comes in via pandas/plotly.

---

## Key Stack Decisions (the "why")

### Plotting Decision: Plotly over Matplotlib / Altair

The core viz is: **a closed polygon (stadium outline) + a scatter layer of HR landing points, color-coded by a per-HR verdict, with hover tooltips showing distance/EV/launch angle**.

| Library | Verdict | Reasoning |
|---|---|---|
| **Plotly** | **Chosen** | Native interactivity (hover, zoom, pan) with zero extra server load via `st.plotly_chart`. Polygon overlays are trivial: add a `Scatter` trace with `fill='toself'` for the stadium outline, then a second `Scatter` trace for HRs with `marker.color` mapped to verdict. Hover tooltips via `customdata`/`hovertemplate` are made for per-HR metadata. |
| Matplotlib | Rejected | Static by default; hover requires `mpld3`/extra plumbing. Interactive spray charts feel sluggish in Streamlit. Only use if you hit a Plotly rendering weirdness. |
| Altair | Rejected | Hits a 5,000-row default limit (not our problem at 50-60 HRs, but a papercut waiting to happen), and the Vega-Lite grammar makes custom polygon overlays more awkward than Plotly's imperative traces. Great for native statistical charts, less great for "draw this specific shape." |

**Confidence: HIGH.** Plotly 6.7 is the current release (2026-04-09), and Streamlit 1.56 ships a theme token (`theme.chartDivergingColors`) that applies to Plotly charts — clear indication Plotly is a first-class integration.

### HTTP Decision: requests over httpx

Streamlit executes top-to-bottom on every user interaction. There's no event loop, no concurrency win from async. The app fires a handful of cached GETs per rerun (teams, roster, gameLog, game feeds, venues) and then renders. `requests` is:

- Synchronous (matches Streamlit's execution model)
- Zero learning curve
- The default for ~95% of Streamlit API-wrapping examples in the wild

`httpx` would be defensible if you wanted HTTP/2 or to parallelize the game-feed fetches (N games with HRs -> N game-feed calls). If that becomes a real bottleneck, the upgrade path is: wrap the per-game fetch in `concurrent.futures.ThreadPoolExecutor` with `requests`. Only reach for `httpx` (or async) if thread-pool caching proves insufficient.

**Confidence: HIGH.**

### Caching Decision: st.cache_data only, no requests-cache

Two caches > one cache only if they solve different problems. They don't here.

- `@st.cache_data(ttl=...)` caches the **parsed Python return value** (dicts, DataFrames) at the function boundary. TTL per function is trivial: `ttl="24h"` for `/venues`, `ttl="1h"` for `/schedule` and game feeds, `ttl="6h"` for team/roster.
- `requests-cache` would cache the **raw HTTP response** on disk. It duplicates what `st.cache_data` already does, and adds a second invalidation knob to get wrong.

**Recommended pattern:**
```python
@st.cache_data(ttl="24h", show_spinner=False)
def get_venue(venue_id: int) -> dict:
    r = requests.get(f"https://statsapi.mlb.com/api/v1/venues/{venue_id}",
                     params={"hydrate": "fieldInfo"}, timeout=10)
    r.raise_for_status()
    return r.json()

@st.cache_data(ttl="1h", show_spinner=False)
def get_game_feed(game_pk: int) -> dict: ...
```

**TTL guide for this app:**
| Endpoint | TTL | Rationale |
|---|---|---|
| `/teams?sportId=1` | `"7d"` | 30 teams; changes at season boundaries |
| `/teams/{id}/roster` | `"6h"` | Roster moves happen but aren't urgent |
| `/venues/{id}?hydrate=fieldInfo` | `"30d"` | Fence dimensions effectively static |
| `/people/{id}/stats?stats=gameLog` | `"1h"` | Updates after each game |
| `/game/{gamePk}/feed/live` | `"1h"` | Finalized feeds are immutable; live ones benefit from short TTL |

**Confidence: HIGH** (Streamlit official docs confirm `ttl` accepts `"1h"`/`"30d"` string notation and it's the canonical API-caching pattern).

### Data Wrangling Decision: pandas over polars

Data volume is tiny (hundreds of rows at peak). The decisive factor is **Streamlit integration**: `st.dataframe` and `st.data_editor` both expect pandas natively; polars requires conversion and `st.data_editor` explicitly does not support polars as of the latest Streamlit releases. Pandas 2.2's PyArrow-backed dtypes are fast enough that the raw-perf argument for polars disappears below ~100K rows.

**Confidence: HIGH.**

### Geometry Decision: roll your own with `math.atan2` + numpy, skip shapely

The geometry problem here is narrow:
1. **Spray angle** from `(coordX, coordY)` relative to home plate — one `math.atan2(dx, dy)` call per HR.
2. **Fence distance at that angle** for each of 30 parks — 1-D linear interpolation between the 6 known fence measurements (LF line / LF / LCF / CF / RCF / RF line), which is `numpy.interp` on a sorted angle->distance array per park.
3. **Stadium outline as a polygon** for *drawing*, not for point-in-polygon testing — you're not asking "is this HR inside the park's polygon?", you're asking "is this HR's distance >= the fence distance at its spray angle?" That's a 1-D comparison, not a 2-D geometric containment check.

Shapely would give you `Polygon.contains(Point)`, which is the wrong operation — a ball landing *past* the fence is outside the polygon, not inside, and the wall-height problem that's already deferred to v1 would still be unaddressed. For ~30 parks x ~50 HRs, a vectorized numpy `interp` is both faster and clearer than building 30 shapely polygons.

**Shapely is justified later if:** you ever want to draw realistic ground-rule zones, model wall segments as distinct line strings with per-segment heights, or do spatial joins. None of that is in v1 scope.

**Confidence: MEDIUM** — this is a judgment call, but the 1-D interpolation framing is genuinely the right shape for the problem. If you find yourself writing a ray-casting helper, stop and install shapely.

### Dependency Pinning Decision: requirements.txt + uv

`uv` with a flat `requirements.txt` gives you:
- Fast installs (10-100x pip)
- Automatic venv handling
- Zero migration cost (it reads `requirements.txt` natively)
- No `pyproject.toml` / lockfile ceremony that a single-file hobby app doesn't need

Poetry/PDM/Hatch are all defensible for shipping libraries. For a local-only Streamlit app, they're over-structured.

**Confidence: HIGH.**

---

## Alternatives Considered

| Recommended | Alternative | When to Use Alternative |
|---|---|---|
| plotly | matplotlib | Rendering a static PNG for a blog post / report export. |
| plotly | altair | If you were building purely statistical charts (histograms, aggregations) and didn't need a custom polygon overlay. |
| requests | httpx | If you parallelize game-feed fetches with async and ThreadPool-over-requests isn't fast enough. |
| requests | aiohttp | Never, for this app. (Async-only, no sync client, no Streamlit advantage.) |
| pandas | polars | If data volume crossed ~100K rows per rerun — not a concern here. |
| pandas | duckdb (in-memory) | If you wanted SQL-over-DataFrames for ad-hoc filtering. Overkill. |
| uv | pip + venv | If you refuse to install anything from Astral. Works identically, just slower. |
| uv | poetry | If this project grows into a published library with a `pyproject.toml`. |
| math+numpy geometry | shapely | If you add wall-segment modeling, ground-rule zones, or any 2-D containment queries. |

## What NOT to Use

| Avoid | Why | Use Instead |
|---|---|---|
| `MLB-StatsAPI` (toddrob99) | Explicitly out of scope — user wants raw JSON | Direct `requests` to `statsapi.mlb.com/api/v1` |
| `requests-cache` | Duplicates `st.cache_data`, two invalidation models | `@st.cache_data(ttl=...)` at the function boundary |
| `pybaseball` | Scrapes Baseball Savant / FanGraphs — different data source, heavy dep tree | Not needed; StatsAPI has everything the v1 spec asks for |
| `matplotlib` as primary | Static rendering, awkward hover in Streamlit | `plotly` |
| `asyncio` / `aiohttp` | No event loop in Streamlit's sync rerun model | `requests` (+ optional ThreadPoolExecutor if needed) |
| `shapely` in v1 | Adds GEOS C dep for a 1-D interpolation problem | `math.atan2` + `numpy.interp` |
| `poetry` / `pyproject.toml` | Ceremony for a single-file hobby app | `uv` + `requirements.txt` |
| `st.cache_resource` for API data | That decorator is for connection/model singletons | `st.cache_data` for JSON/DataFrame returns |

---

## Version Compatibility

| Package | Pin | Notes |
|---|---|---|
| streamlit>=1.55,<2.0 | 1.55 adds `on_change`/`bind=` improvements; <2.0 hedge against a future major |
| plotly>=6.0,<7.0 | 6.x is current (6.7.0 shipped 2026-04-09); pin major |
| pandas>=2.2,<3.0 | 2.2 is the stable PyArrow-dtype-capable line |
| requests>=2.32,<3.0 | 2.32.x is the long-stable line; requests has never shipped a 3.x |
| Python 3.12 | Plotly 6, Streamlit 1.56, pandas 2.2 all fully supported |

No known conflicts in this set as of April 2026.

---

## Sources

- [Streamlit 2026 release notes (docs.streamlit.io)](https://docs.streamlit.io/develop/quick-reference/release-notes/2026) — HIGH confidence; verified 1.55/1.56 features and release dates.
- [streamlit on PyPI](https://pypi.org/project/streamlit/) — HIGH; confirms 1.56.0 latest.
- [plotly on PyPI](https://pypi.org/project/plotly/) — HIGH; confirms 6.7.0 (2026-04-09).
- [st.cache_data - Streamlit Docs](https://docs.streamlit.io/develop/api-reference/caching-and-state/st.cache_data) — HIGH; TTL string notation and function-boundary caching semantics.
- [Caching overview - Streamlit Docs](https://docs.streamlit.io/develop/concepts/architecture/caching) — HIGH; cache_data vs cache_resource guidance.
- [Streamlit Chart Libraries Comparison (DEV Community, 2026)](https://dev.to/squadbase/streamlit-chart-libraries-comparison-a-frontend-developers-guide-54il) — MEDIUM; corroborates plotly-for-interactive pattern.
- [Plot Library Speed Trial (Streamlit forum)](https://discuss.streamlit.io/t/plot-library-speed-trial/4688) — MEDIUM; Altair fast but row-limited, Plotly balanced, Matplotlib slowest.
- [HTTPX vs Requests vs AIOHTTP (decodo.com, 2026)](https://decodo.com/blog/httpx-vs-requests-vs-aiohttp) — MEDIUM; sync-vs-async framing; requests remains the sync-first default.
- [Best Python Package Managers in 2026: uv vs pip vs Poetry (scopir.com)](https://scopir.com/posts/best-python-package-managers-2026/) — MEDIUM; uv as drop-in replacement consensus.
- [uv docs: From pip to a uv project](https://docs.astral.sh/uv/guides/migration/pip-to-project/) — HIGH; official Astral docs confirm `requirements.txt` compatibility.
- [pandas vs Polars with Streamlit (discuss.streamlit.io)](https://discuss.streamlit.io/t/using-streamlit-cache-with-polars/38000) and [issue #8273](https://github.com/streamlit/streamlit/issues/8273) — MEDIUM; confirms `st.data_editor` does not natively accept polars.
- [shapely.Polygon docs](https://shapely.readthedocs.io/en/stable/reference/shapely.Polygon.html) — HIGH; confirms shapely's core ops are 2-D containment, not 1-D distance-at-angle which is our actual need.

---
*Stack research for: Streamlit MLB HR Park Factor Explorer*
*Researched: 2026-04-14*
