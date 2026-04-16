# Feature Landscape

**Domain:** MLB sabermetrics hobby data-viz app (HR park-factor explorer)
**Researched:** 2026-04-16 (v1.1 section added) / 2026-04-14 (v1.0 original)

---

## v1.1 Milestone: Multi-Season Selector + Streamlit Cloud Deployment

This section covers only the NEW features for the v1.1 milestone. The existing v1.0 feature landscape follows below.

### Context: What Already Exists

The codebase already has season-parameterized internals — this is the key insight that makes the season selector cheap to add:

- `mlb_api.py` functions already accept `season: int` — `get_game_log(person_id, season)`, `get_team_hitting_stats(team_id, season)` both work with historical seasons
- `controller.py` accepts `season: int | None` and defaults to `CURRENT_SEASON` (hardcoded `2026` in `config.py`)
- `app.py` imports `CURRENT_SEASON` and passes it hard-coded — this is the single seam to break open for the selector
- `st.cache_data` automatically keys on function arguments, so historical season caching is free once the year is passed through
- Confirmed working API URL pattern: `statsapi.mlb.com/api/v1/people/{id}/stats?stats=gameLog&group=hitting&gameType=R&season=2022` — the `season` parameter is accepted and returns historical game logs

### Table Stakes (v1.1)

Features the milestone is explicitly about. Missing any = milestone incomplete.

| Feature | Why Required | Complexity | Notes |
|---------|--------------|------------|-------|
| Season selector widget | Core milestone goal | Low | `st.selectbox` with years `[2022, 2023, 2024, 2025, 2026]`; current year pre-selected; place above or beside Team selector |
| Pass selected season through to all API calls | Selector is cosmetic without this | Low | Seam already exists — `controller.build_view()` accepts `season`; `app.py` passes the hardcoded constant today; replace with widget value |
| Historical seasons cache with permanent TTL | Completed seasons are immutable; re-fetching 2022 data on every wake is wasteful | Low | `ttl = "30d" if season < CURRENT_SEASON else TTL_GAMELOG`. One conditional. `st.cache_data` keys by arg value so different season years get separate cache entries automatically |
| Public GitHub repository | Community Cloud requires it | Low | No secrets in the codebase — the MLB StatsAPI is unauthenticated, so flipping a private repo to public is safe |
| Deploy to Streamlit Community Cloud | The explicit second milestone goal | Low-Med | Requires: public repo, `requirements.txt` at root (already exists), entrypoint specified as `src/mlb_park/app.py` in deploy dialog |
| Forward-slash path audit | Community Cloud runs on Debian Linux; Windows backslash paths break | Low | Audit `config.py` `VENUES_FILE` constant and any `os.path` calls; `pathlib.Path` used throughout is safe |

### Differentiators (v1.1)

Add-ons that cost little given the foundation but materially improve the shared-link experience.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Season-aware messaging | "Aaron Judge has 0 HRs in 2019" (wrong year) vs "0 HRs in 2026" (correct year) — grounds the user | Low | `view.season` already on the ViewModel; use it in every info/empty-state message in `app.py` |
| Season label in chart title / section headers | Grounds the user when viewing historical data | Low | One f-string: `f"{player_name}, {team} — {season} Season"` |
| Roster fetched for selected season, not current | When viewing 2022, show the 2022 roster — players who retired or moved teams disappear correctly | Med | `get_team_hitting_stats(team_id, season)` already accepts season; ensure the selector re-fetches roster when season changes. Streamlit handles this via rerun when `season` selectbox changes |
| `.streamlit/config.toml` theming | Avoids jarring default Streamlit look when sharing the link publicly | Low | 5 lines — `primaryColor`, `backgroundColor`, `font`. Must live at repo root per Community Cloud docs |

### Anti-Features (v1.1)

Do not build these in this milestone.

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| Season-aware venue/park dimensions | Fence dimensions have not changed materially for any park in the past 5 seasons. Version-matching venue data by season adds complexity with near-zero payoff | Accept the existing v1 caveat: fence data is current-era regardless of selected season. Document it |
| Per-season team list (filtering out teams that didn't exist) | The A's moved Oakland→Sacramento→Las Vegas but the team ID is stable. The `teams` endpoint returns current identity. Filtering teams by season adds branching with no API support | Always show the current 30 teams. Historical roster calls with `season=2023` return the correct players for that year regardless |
| Career multi-season aggregation | Scope creep explicitly out of scope in PROJECT.md | Single-season view per selection. Users manually pick years |
| `secrets.toml` in the repo | Community Cloud docs are explicit: never commit secrets | No secrets are needed — the MLB API is unauthenticated. No `secrets.toml` needed at all for v1.1 |
| `packages.txt` | Only needed for APT Linux dependencies | This app has no C extensions, no system libs, no APT deps — do not create the file |
| `pytest` in production `requirements.txt` | Test dependency on the Cloud runtime is wasteful (adds to install time, contributes to cold-start latency) | Either remove pytest from `requirements.txt` or create a separate `requirements-dev.txt` for local use |

### StatsAPI Historical Season Behavior

**Verified (MEDIUM confidence — confirmed via live URL found in production):**

The `season` parameter works on the following endpoints used by this app:

| Endpoint | Season Param | Behavior |
|----------|-------------|---------|
| `/people/{id}/stats?stats=gameLog&group=hitting&gameType=R&season=YYYY` | Yes | Returns game-by-game hitting log for that season |
| `/teams/{id}/roster?rosterType=active&season=YYYY` | Yes (schema-confirmed) | Returns roster as it was that season |
| `/teams?sportId=1` | Optional | Omit; always use current 30 teams by identity |
| `/schedule?sportId=1&season=YYYY` | Yes | Returns schedule for that season |
| `/game/{gamePk}/feed/live` | N/A | gamePk is globally unique; no season param needed |
| `/venues/{id}?hydrate=fieldInfo` | N/A | Fence geometry does not vary by season in the API |

**Edge cases to handle:**

- **Player not on team in selected year:** The roster call with `season=2022` returns the correct roster for that year. If the currently-selected player (from current season) wasn't on the team that year, they won't appear. The UI should handle gracefully: player selector re-populates when season changes; no crash expected since the selector is rebuilt from the season-specific roster.
- **A's relocation:** Oakland (2022-2024) → Sacramento/Sutter Health Park (2025) → Las Vegas (2028+). Team ID is stable. Selecting "Athletics" for any season and passing `season=YEAR` to the roster call returns the correct roster. The venue returned by the team may reflect the current venue, not the historical one — acceptable for this app.
- **Retired players:** Won't appear in any team's season roster. Not a problem — the selector only shows what the API returns.

**TTL strategy:**

| Season Type | TTL | Rationale |
|-------------|-----|-----------|
| Historical (`year < CURRENT_SEASON`) | `"30d"` | Game feeds are finalized and immutable |
| Current season | `"1h"` (existing) | Games still in progress or recent |

### Streamlit Community Cloud Deployment Checklist

**Source: Official Streamlit docs (HIGH confidence)**

**Required:**
- [ ] Public GitHub repository (Community Cloud requirement — no workaround)
- [ ] `requirements.txt` at repo root (already exists — verify contents)
- [ ] Remove or separate `pytest` from production requirements
- [ ] Entrypoint: specify `src/mlb_park/app.py` in the deploy dialog (not at root, must be explicit)
- [ ] Python version: select 3.12 in Advanced Settings (matches local dev)
- [ ] Forward-slash path audit: verify `VENUES_FILE` in `config.py` uses `pathlib.Path` correctly

**Resource limits to be aware of:**

| Resource | Free Tier | Impact |
|----------|-----------|--------|
| Memory | 690MB–2.7GB (not guaranteed) | LOW RISK — app holds ~1,500 rows max in memory |
| CPU | 0.078–2 cores | LOW RISK — pure Python geometry, no ML |
| Sleep after inactivity | 12 hours | MEDIUM — `st.cache_data` is in-memory; cold-start on first wake means all API calls re-fire. Acceptable for hobby app |
| GitHub deploy rate limit | 5 pushes/min | Irrelevant |
| Geography | US only | Irrelevant |

**Not required:**
- `packages.txt` — no APT dependencies
- `secrets.toml` — API is unauthenticated
- `st.secrets` usage — nothing to secret

**Deployment steps (distilled):**
1. Push to public GitHub
2. Go to share.streamlit.io → "Create app"
3. Specify repo, branch (`main`), entrypoint file (`src/mlb_park/app.py`)
4. Select Python 3.12 in Advanced Settings
5. No secrets to configure
6. Deploy

**Sleep/wake behavior note:** When the app sleeps (12h inactivity), `st.cache_data` is cleared entirely since it is in-memory. The first visitor after sleep pays the cold-start cost — all API calls re-execute. For a hobby app with friends as the audience this is acceptable but worth noting in a README.

### Feature Dependencies (v1.1)

```
Season selector widget (st.selectbox)
  |
  +-> controller.build_view(season=selected_season)      [seam exists, pass-through]
       |
       +-> get_team_hitting_stats(team_id, season)        [already parameterized]
       |    -> TTL conditional: 30d if historical, 1h if current
       |
       +-> get_game_log(person_id, season)                [already parameterized]
            -> TTL conditional: 30d if historical, 1h if current

Season change in selectbox
  -> Streamlit rerun -> player selector re-builds from season-specific roster
  -> No explicit session_state management needed (Streamlit handles)

Community Cloud deployment
  -> Public GitHub repo (prerequisite)
  -> requirements.txt at root (exists)
  -> No secrets (MLB API is unauthenticated)
  -> Path audit (one-time)
  -> Deploy dialog: specify src/mlb_park/app.py as entrypoint
```

### MVP for v1.1

**Must ship:**
1. Season `st.selectbox` in `app.py` with years 2022–current, current pre-selected — ~5 lines
2. Pass selected season to `controller.build_view()` instead of hardcoded constant — ~3 lines
3. Historical TTL conditional in `mlb_api.py` — ~5 lines
4. Path audit (`VENUES_FILE`, any string paths) — 30 min review
5. Push to public GitHub + deploy via share.streamlit.io — 15 min

**Add if time allows:**
6. Season-aware messaging in empty states and chart titles — trivial
7. `.streamlit/config.toml` with minimal theming — 5 lines

**Explicitly defer:**
- Season-aware venue dimensions — not needed, accepted caveat
- Historical team list filtering — not needed, team IDs are stable
- Any backend architecture changes — none needed

---

## v1.0 Feature Landscape (Original Research, 2026-04-14)

*(Preserved for reference — features below are already built)*

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

### Differentiators (Competitive Advantage, v1.0)

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

### Anti-Features (v1.0)

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| Leaderboard of "cheapest HRs in MLB this season" | Sounds fun, viral-ish | Requires fetching every HR hitter on every team -> hundreds of game feeds; hammers the unofficial API; violates "single player at a time" flow | Keep it single-player |
| Career HR history / multi-season comparison | "But I want to see Judge's 2022 vs 2025" | Explicitly out of scope in PROJECT.md; multiplies data volume and cache pressure | Document "pick a season from the selector"; revisit post-validation |
| Wall height / Green Monster modeling | Obvious missing piece for Fenway verdicts | API doesn't return fence heights; would require hand-maintained JSON — bit-rot risk for a hobby app | Document as known v1 caveat in the UI |
| Official park factors (run / HR multipliers) | "Isn't that what a park factor IS?" | Not in the API; FanGraphs/Savant territory | Clarify in README |
| User accounts, saved players, favorites | Standard web-app polish | Out of scope in PROJECT.md; Streamlit isn't the right tool; no backend | Use URL query params for shareable state |
| Social sharing / tweet-this-chart buttons | "Viral moment" thinking | Hobby app, no branding, no analytics — zero payoff | Skip |
| Live in-game updates / auto-refresh mid-game | "Wouldn't it be cool if it updated as he hit one?" | API feed live is messy; Streamlit's rerun model fights this | Out of scope per PROJECT.md |
| 3D stadium rendering / full stadium geometry | Baseball Savant's 3D HR Derby viz is gorgeous | Enormous effort, needs stadium meshes, WebGL | 2D top-down outline from `fieldInfo` is right for this app |
| ML-predicted "would this have been HR" confidence score | Sounds sophisticated | Distance+angle is already deterministic given fence dims | Stick with geometric verdict |
| Pitcher-side analysis | Mirror of hitter flow | Doubles the surface area; scope creep | v2+ idea |
| Download CSV / export buttons | Common data-app ask | `st.dataframe` already has built-in CSV download on hover | Rely on built-in |
| Mobile-responsive redesign | "It should work on my phone" | Streamlit's mobile story is meh; spray charts don't work on tiny screens anyway | Document "best viewed on desktop" |

## Sources

### v1.1 Sources
- statsapi.mlb.com live URL (production, found in wild): `https://statsapi.mlb.com/api/v1/people/630105/stats?stats=gameLog,statSplits,statsSingleSeason&group=hitting&gameType=R&season=2022` — HIGH confidence, direct endpoint evidence
- [MLB-StatsAPI endpoints.py — toddrob99/MLB-StatsAPI](https://github.com/toddrob99/MLB-StatsAPI/blob/master/statsapi/endpoints.py) — MEDIUM; documents `season` param for roster, schedule, teams endpoints
- [Streamlit Community Cloud: App Dependencies](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/app-dependencies) — HIGH; official docs on requirements.txt, packages.txt, priority order
- [Streamlit Community Cloud: File Organization](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/file-organization) — HIGH; entrypoint path, config.toml must be at repo root
- [Streamlit Community Cloud: Deploy](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/deploy) — HIGH; deployment steps and dialog options
- [Streamlit Community Cloud: Secrets Management](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/secrets-management) — HIGH; secrets.toml format and st.secrets
- [Streamlit Community Cloud: Manage your app (resource limits)](https://docs.streamlit.io/deploy/streamlit-community-cloud/manage-your-app) — HIGH; CPU 0.078–2 cores, Memory 690MB–2.7GB, 12h sleep policy
- [Public MLB API: schedule.md](https://github.com/pseudo-r/Public-MLB-API/blob/main/docs/schedule.md) — MEDIUM; schedule endpoint season parameter documented
- [Oakland Athletics relocation — Wikipedia](https://en.wikipedia.org/wiki/Oakland_Athletics_relocation_to_Las_Vegas) — HIGH; A's in Sacramento 2025, Vegas 2028

### v1.0 Sources
- [Baseball Savant Statcast Home Run Tracking](https://baseballsavant.mlb.com/leaderboard/home-runs) — HIGH confidence, official
- [Baseball Savant Visuals hub](https://baseballsavant.mlb.com/visuals) — catalog of Savant's viz tools
- [Savant Illustrator](https://baseballsavant.mlb.com/illustrator) — spray chart UX reference
- PROJECT.md locked scope — single source of truth for anti-features

---
*Feature research for: MLB HR park-factor explorer (Streamlit hobby app)*
*v1.0 researched: 2026-04-14 | v1.1 researched: 2026-04-16*
