# Feature Research

**Domain:** MLB sabermetrics hobby data-viz app (HR park-factor explorer)
**Researched:** 2026-04-14
**Confidence:** HIGH (domain is well-trodden; Baseball Savant and FanGraphs set the UX conventions this app will be compared against)

## Feature Landscape

### Table Stakes (Users Expect These)

Missing any of these makes the app feel broken or half-finished for the stated flow (Team -> Player -> Stadium -> "how cheap were the HRs").

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Cascading Team -> Player -> Stadium selectors with clear reset behavior | Core flow defined in PROJECT.md; users expect later selectors to invalidate/repopulate on earlier changes | LOW | `st.selectbox` x3 with `st.session_state` guards; sort players by HR count desc so the interesting ones are on top |
| Roster filter to hitters only (or non-zero HR hitters) | Picking a middle reliever and seeing "0 HRs" feels broken | LOW | Filter roster by position group != P, or secondary filter "only players with >=1 HR this season" |
| Summary card: Total HRs, avg parks cleared / 30, no-doubter count, cheap-HR count | Headline metric is the whole point of the app | LOW | Use `st.metric` row; define no-doubter as 30/30, cheap as <=5/30 (document thresholds) |
| Spray chart on selected stadium outline, HRs plotted with HR/not-HR color coding | Explicitly in Active requirements; the core visual | MEDIUM | Matplotlib or Plotly; fence interpolated from `fieldInfo` 6 points; legend must explain colors |
| Per-HR table: date, opponent, distance, EV, LA, parks cleared / 30 | Users want to drill down from summary to specifics | LOW | `st.dataframe` with column config; sortable; link date to game via gamePk optional |
| Clear units and axes on plot | "424" means nothing without "ft"; spray chart without orientation is confusing | LOW | Feet labels, home-plate-at-bottom convention, compass rose or LF/CF/RF labels |
| Loading indicator during game-feed fetches | Pulling 30-60 game feeds takes seconds; silent app feels frozen | LOW | `st.spinner("Fetching game feeds...")` wrapping the pipeline; `st.progress` if iterating |
| "No HRs this season" empty state | April rosters will have players with 0 HRs; picking one must not crash | LOW | Detect empty `hitData` set early; show friendly message + suggest top HR hitters |
| API error handling (404 player, 500 from MLB, timeout) | Unofficial API; failures happen | LOW | Try/except around each fetch, `st.error` with human message, don't leak tracebacks |
| Stadium name shown with team + location | "PNC Park" vs "Pirates" vs "Pittsburgh" — users switch context constantly | LOW | Label selectbox entries as "Team — Stadium (City)" |
| Caching indicator or "last refreshed" timestamp | Streamlit cache is invisible; users wonder if data is live | LOW | Sidebar note: "Data cached for 1 hour. Last fetched: HH:MM" |

### Differentiators (Competitive Advantage)

These elevate it above "a Streamlit demo" into "something I'd show a friend who likes baseball." All optional; prioritize by effort-to-wow ratio.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Hover tooltips on each HR dot (date, pitcher, distance, EV, LA, "cleared X/30") | Turns a static scatter into an interactive explorer; this is what Baseball Savant nails | LOW | Plotly `hover_data` — essentially free if you're using Plotly already. Huge UX lift |
| Click/select HR -> highlight which specific parks it did/didn't clear | Answers the natural follow-up question from the summary | MEDIUM | List the ~5 parks that made the difference; small table below plot |
| "HR distance vs. park fence at that angle" mini-bar for the selected stadium | Makes the cheap/no-doubter verdict visually intuitive (ball went 375, fence is 330 -> gone) | MEDIUM | Horizontal bar per HR: fence distance marker, ball distance marker, color by verdict |
| Toggle "show fences of all 30 parks" overlay on spray chart | Dramatic viz — you can see Coors/Fenway/PETCO differ at a glance | MEDIUM | Faint gray lines for other 29 parks, bold for selected; easy to get visually noisy, needs care |
| Player comp: put Player A's HRs on Player B's home park | "Would Judge's HRs play at Oracle?" — extends the premise | MEDIUM | Requires decoupling "player source" from "stadium target"; already the design |
| "Which park is this player most/least suited for?" ranking | Derives a player-specific park recommendation from their HR set | LOW | Sum parks-cleared across HRs, rank 30 parks; show top/bottom 3 |
| Cheap-HR / no-doubter threshold slider | Lets user define what counts as "cheap" (default <=5/30, configurable) | LOW | `st.slider` in sidebar; recomputes summary card live |
| Filter by opponent / home-vs-away / month | Standard sabermetric slice-and-dice | LOW | Checkboxes / date range; re-runs verdict computation on filtered set |
| Link out to MLB.com video of each HR | Users want to SEE the no-doubter; MLB Film Room URLs use playId | MEDIUM | `hitData` play has `playId` (UUID); build `https://www.mlb.com/video/search?q=playId=<uuid>` link in table |
| Dark mode / polished theme via `.streamlit/config.toml` | Default Streamlit looks generic; theming is low-cost polish | LOW | Set primary color to MLB blue or team color of selected team |
| Dynamic page title / favicon | "HR Park Explorer — Aaron Judge" in browser tab | LOW | `st.set_page_config` with dynamic title after player selected (second rerun) |
| "Compare to league average HR distance at this park" annotation | Cheap contextual stat the API gives you for free at the stadium level | MEDIUM | Aggregate park-average HR distance from all games feed fetched; one-line callout |

### Anti-Features (Commonly Requested, Often Problematic)

Things that sound cool but either violate PROJECT.md scope, bloat a hobby app, or duplicate what Baseball Savant already does better.

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| Leaderboard of "cheapest HRs in MLB this season" | Sounds fun, viral-ish | Requires fetching every HR hitter on every team -> hundreds of game feeds; hammers the unofficial API; violates "single player at a time" flow | Keep it single-player. If a user wants this, it's Baseball Savant's job |
| Career HR history / multi-season comparison | "But I want to see Judge's 2022 vs 2025" | Explicitly out of scope in PROJECT.md; multiplies data volume and cache pressure | Document "current season only" prominently; revisit post-validation |
| Wall height / Green Monster modeling | Obvious missing piece for Fenway verdicts | API doesn't return fence heights; would require hand-maintained JSON of 30 parks' wall heights — bit-rot risk for a hobby app | Document as a known v1 caveat in the UI ("Note: fence heights not modeled — Fenway's Green Monster undercounts HRs") |
| Official park factors (run / HR multipliers) | "Isn't that what a park factor IS?" | Not in the API; FanGraphs/Savant territory; computing real park factors needs multi-season regressions | Clarify in README that this app is about per-HR physical verdicts, not normalized park factors |
| User accounts, saved players, favorites | Standard web-app polish | Out of scope in PROJECT.md; Streamlit isn't the right tool; no backend | Use URL query params (`?playerId=...`) for shareable/bookmarkable state — gives 80% of the value |
| Social sharing / tweet-this-chart buttons | "Viral moment" thinking | Hobby app, no branding, no analytics — zero payoff | Skip. Users can screenshot if they want |
| Live in-game updates / auto-refresh mid-game | "Wouldn't it be cool if it updated as he hit one?" | API feed live is messy; Streamlit's rerun model fights this; scope-creep into live scoreboard territory | Out of scope per PROJECT.md. Manual refresh is fine for a hobby app |
| 3D stadium rendering / full stadium geometry | Baseball Savant's 3D HR Derby viz is gorgeous | Enormous effort, needs stadium meshes, WebGL — hobby project death | 2D top-down outline from `fieldInfo` is the right zoom level for this app |
| ML-predicted "would this have been HR" confidence score | Sounds sophisticated | Distance+angle is already deterministic given fence dims; adding a model adds complexity without insight | Stick with geometric verdict; be honest about the wall-height caveat |
| Pitcher-side analysis ("which pitchers give up cheap HRs") | Mirror of hitter flow | Doubles the surface area; scope creep; different user story | Document as v2+ idea; don't build in v1 |
| Download CSV / export buttons | Common data-app ask | Streamlit's `st.dataframe` already has a built-in CSV download on hover — you get this free | Rely on built-in; don't build custom export |
| Mobile-responsive redesign | "It should work on my phone" | Streamlit's mobile story is meh; spray charts don't work on tiny screens anyway | Document "best viewed on desktop"; don't fight the framework |

## Feature Dependencies

```
Team selector
    |
    v
Player selector (filtered to team's roster, HR count desc)
    |
    v
Player gameLog fetch ---> filter games with HRs ---> game feed fetch per game ---> HR play extraction
                                                                                          |
                                                                                          v
                                                                                    hitData[] per HR
                                                                                          |
                      +-------------------------------+---------------------------+
                      v                               v                           v
              Stadium selector           Summary card (totals)           Per-HR table
                      |                               |                           |
                      v                               v                           |
              Park fence interpolation         Recompute on threshold slider      |
                      |                                                           |
                      +---------------------+-------------------+                 |
                                            v                   v                 |
                                     Spray chart viz      Per-HR verdict <--------+
                                            |
                                            +--enhanced by--> Hover tooltips
                                            +--enhanced by--> "Which parks made the diff" drill-down
                                            +--enhanced by--> Video link out

Threshold slider ---enhances---> Summary card + table
Opponent/date filter ---enhances---> The hitData[] set (feeds everything downstream)
League HR-dist annotation ---requires---> All games feed already fetched (free if cached)
```

### Dependency Notes

- **Spray chart requires hitData + fieldInfo:** both must succeed before plotting; handle partial failure (player has HRs but venue lookup failed) with a fallback generic field
- **Hover tooltips require Plotly (not Matplotlib):** decision point — Matplotlib is simpler but static; Plotly unlocks most differentiators. Recommendation: Plotly for main chart, Matplotlib only if Plotly becomes painful
- **Threshold slider enhances summary + table:** rerun is cheap since hitData is cached; no new fetches needed
- **Video link requires `playId` from hitData:** confirm `playId` field is actually present in the play object (not just the play event); if missing, skip this differentiator
- **"Show all 30 fences overlay" conflicts with readability:** don't combine with hover-dense plots; offer as a toggle, off by default

## MVP Definition

### Launch With (v1)

All table stakes + a minimal subset of differentiators. This is the "doesn't feel broken" bar.

- [ ] Cascading Team -> Player -> Stadium selectors with session_state guards
- [ ] Roster filtered to non-pitcher hitters with at least 1 HR (fallback: all hitters)
- [ ] Data pipeline: gameLog -> games-with-HR -> game feeds -> hitData extraction, all cached
- [ ] Summary card (total HRs, avg parks cleared, no-doubters, cheap HRs) with documented thresholds
- [ ] Spray chart: selected stadium outline + all HRs colored by verdict, axes labeled in feet, LF/CF/RF orientation
- [ ] Per-HR table with date, distance, EV, LA, parks cleared / 30
- [ ] Loading spinner around fetch pipeline; "last refreshed" note
- [ ] Empty state for "player has 0 HRs this season"
- [ ] API error handling with friendly messages (no tracebacks to user)
- [ ] Page title + favicon set via `st.set_page_config`
- [ ] Documented wall-height caveat visible in UI (expander or footer)

### Add After Validation (v1.x)

Differentiators that are cheap relative to wow factor — add once v1 is stable.

- [ ] Plotly hover tooltips on HR dots (pitcher, date, EV/LA, cleared X/30) — highest leverage
- [ ] "Which park is this player most/least suited for?" ranking (sidebar or below plot)
- [ ] Cheap-HR threshold slider in sidebar
- [ ] Click/select HR -> list the parks that made the difference
- [ ] URL query params for shareable state (`?teamId=147&playerId=592450&venueId=3313`)
- [ ] Dark theme via `.streamlit/config.toml`
- [ ] Dynamic page title reflecting selected player

### Future Consideration (v2+)

Bigger investments; defer until the core app has been used enough to know they're worth it.

- [ ] HR-distance-vs-fence mini-bar per HR (requires layout work)
- [ ] All-30-parks fence overlay toggle
- [ ] Filter by opponent / home-vs-away / month
- [ ] MLB video link out per HR (depends on `playId` availability + URL stability)
- [ ] League-average HR-distance annotation at selected park
- [ ] Player comp mode (Player A's HRs on Player B's home park) — likely already falls out of the design

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| Cascading selectors | HIGH | LOW | P1 |
| Data pipeline + caching | HIGH | MEDIUM | P1 |
| Summary card | HIGH | LOW | P1 |
| Spray chart with verdict colors | HIGH | MEDIUM | P1 |
| Per-HR table | MEDIUM | LOW | P1 |
| Empty / error states | MEDIUM | LOW | P1 |
| Loading spinner | MEDIUM | LOW | P1 |
| Wall-height caveat disclosure | MEDIUM | LOW | P1 |
| Plotly hover tooltips | HIGH | LOW | P2 |
| Best/worst park ranking for player | HIGH | LOW | P2 |
| Cheap-HR threshold slider | MEDIUM | LOW | P2 |
| URL query param state | MEDIUM | LOW | P2 |
| Theme / dark mode | LOW | LOW | P2 |
| HR distance vs fence mini-bar | MEDIUM | MEDIUM | P3 |
| All-30-parks overlay toggle | MEDIUM | MEDIUM | P3 |
| Opponent/date filters | MEDIUM | LOW | P3 |
| Video link out | MEDIUM | MEDIUM | P3 |
| League-avg HR-distance annotation | LOW | MEDIUM | P3 |

**Priority key:**
- P1: Must have for launch — maps to v1
- P2: Should have, add when possible — maps to v1.x
- P3: Nice to have, future consideration — maps to v2+

## Competitor / Reference Feature Analysis

| Feature | Baseball Savant | FanGraphs | Our Approach |
|---------|-----------------|-----------|--------------|
| HR-in-X/30-parks verdict | Built-in on Statcast HR Tracking leaderboard (Standard + Adjusted views); applies wall heights | Not a feature; FG does park factors instead | Simpler: single player flow, geometric verdict only, document wall-height caveat |
| Spray chart | Savant Illustrator with filters (pitch type, EV, LA, result) | Interactive Spray Chart Tool | Single-player spray chart on any chosen stadium — Savant doesn't swap the background stadium |
| 3D stadium viz | 3D HR Derby + 3D pitch visualizations | None | Skip 3D — 2D outline is right for hobby scope |
| Park factors | Statcast Park Factors leaderboard (HR/run multipliers) | Full park factor tables | Explicitly NOT doing park factors — different kind of "park effect" |
| Hover-rich interactivity | Heavy Plotly/D3 everywhere | Interactive but heavier table-driven | Plotly hover on the HR scatter is the minimum-viable bar |
| Filtering UI | Extensive (pitch, count, EV, LA, opponent, date) | Season + split filters | Keep filters out of v1; add opponent/date post-validation |
| Mobile UX | Poor (desktop-first) | Poor (desktop-first) | Match the genre norm — desktop-first, don't fight Streamlit |
| Video integration | Deep — every play links to MLB video | None | Defer to v2; depends on `playId` in feed |

**UX patterns worth borrowing from Baseball Savant:**
- Dense hover tooltips on every dot (every piece of data you have, tooltip-able)
- Player dropdown shows seasonal context (HR total, team) next to name
- "Standard vs Adjusted" toggle pattern — clean way to disclose modeling assumptions (we'd call it "Fence distance only" vs "+ wall height" if we ever add the latter)
- Explicit in-UI explanations of what a metric means (expandable tooltip icons)

**Patterns to avoid:**
- Baseball Savant's filter bar is overwhelming — 20+ dropdowns. For a hobby app, 3 cascading selectors + 1 threshold slider is plenty
- FanGraphs' dense table-first layout — we want viz-first
- Savant's URL scheme is messy and opaque; if we do query params, keep them human-readable (`?team=NYY&player=aaron-judge` over raw IDs if possible)

## Quality Signals — Polished vs Hacky

Hobby apps live or die on these. None are features per se; they're hygiene.

| Signal | Polished | Hacky |
|--------|----------|-------|
| First load before any selection | Clear call-to-action ("Pick a team to start"), maybe a demo screenshot | Blank page, or immediate error from empty state |
| During fetch | `st.spinner` with descriptive text ("Fetching 47 game feeds..."), progress bar if iterable | Frozen UI, no feedback |
| After fetch, no HRs | Friendly "Aaron Rendon has 0 HRs this season — try these top hitters: ..." with quick links | "IndexError: list index out of range" |
| API error | `st.error("MLB API is unavailable — try again in a minute")` with retry button | Raw traceback, 500 page |
| Plot with one HR | Plot still renders cleanly, fence visible, single dot labeled | Plot renders but looks empty/broken |
| Plot with 60 HRs | Dots don't overlap illegibly (alpha or jitter), legend still readable | Giant unreadable blob |
| Units everywhere | "424 ft", "108.3 mph", "28° LA" | Raw numbers with no context |
| Stadium outline | Smooth curve (fence interpolated), foul lines drawn, home plate marked | Jagged polygon of 6 straight segments |
| Color scheme | Green=HR / red=not colorblind-friendly (use blue/orange or add shape differentiation) | Only red/green, no accessibility thought |
| Documentation in-app | Expander: "How the verdict is computed" with the wall-height caveat | No explanation; users wonder why Fenway results look weird |
| Caching behavior | Visible "last fetched at 3:42pm" note; manual "clear cache" button in sidebar for debugging | Silent cache; stale data with no way to force refresh |
| Session state resilience | Changing team resets player but keeps stadium; changing player keeps stadium; no cascading wipeouts | Every change blanks everything; user has to reselect from scratch |

## Sources

- [Baseball Savant Statcast Home Run Tracking](https://baseballsavant.mlb.com/leaderboard/home-runs) — the "HRs in X/30 parks" feature this app is riffing on (HIGH confidence, official)
- [Baseball Savant Visuals hub](https://baseballsavant.mlb.com/visuals) — catalog of Savant's viz tools; reference for polish baseline
- [Baseball Savant 3D Home Run Derby](https://baseballsavant.mlb.com/hr_derby) — reference for what we're NOT trying to build
- [Savant Illustrator](https://baseballsavant.mlb.com/illustrator) — spray chart UX reference (filters, hover, chart templates)
- [Statcast Park Factors leaderboard](https://baseballsavant.mlb.com/leaderboard/statcast-park-factors) — reference for "park factor" terminology we are deliberately NOT using
- [FanGraphs Interactive Spray Chart Tool announcement](https://blogs.fangraphs.com/introducing-the-interactive-spray-chart-tool/) — competitor spray-chart UX
- [RotoGraphs: Select HR Park Factors, Visualized](https://fantasy.fangraphs.com/select-home-run-park-factors-visualized/) — reference for visualizing park HR effects
- [Streamlit skeleton/loading patterns discussion](https://discuss.streamlit.io/t/non-trivial-application-skeleton-from-seasoned-software-data-engineer/86072) — hygiene patterns for polished Streamlit apps
- [Streamlit st.skeleton proposal issue](https://github.com/streamlit/streamlit/issues/8032) — state of loading-skeleton support in Streamlit
- PROJECT.md locked scope — single source of truth for anti-features

**Confidence notes:**
- HIGH on table stakes / anti-features: domain norms are well-established and the scope doc is explicit
- HIGH on Baseball Savant / FanGraphs feature claims: verified via web search this session
- MEDIUM on `playId`-to-video URL scheme: URL pattern is stable in practice but not formally documented; verify before implementing the video-link differentiator
- MEDIUM on "Plotly hover is free" assumption: true if we pick Plotly from the start; costlier if we build Matplotlib first and migrate

---
*Feature research for: MLB HR park-factor explorer (Streamlit hobby app)*
*Researched: 2026-04-14*
