# Roadmap — Streamlit MLB HR Park Factor Explorer

## Milestones

- **v1.0 MVP** — Phases 1-6 (shipped 2026-04-16)
- **v1.1 Multi-Season & Deploy** — Phases 7-8 (in progress)

## Phases

<details>
<summary>v1.0 MVP (Phases 1-6) — SHIPPED 2026-04-16</summary>

- [x] Phase 1: Foundation & API Layer (3/3 plans)
- [x] Phase 2: Models & Geometry (3/3 plans)
- [x] Phase 3: HR Pipeline (3/3 plans)
- [x] Phase 4: Controller & Selectors UI (3/3 plans)
- [x] Phase 5: Spray Chart Visualization (3/3 plans)
- [x] Phase 6: Summary, Rankings & Polish (2/2 plans)

**17 plans total** | Full archive: `.planning/milestones/v1.0-ROADMAP.md`

</details>

### v1.1 Multi-Season & Deploy

- [ ] **Phase 7: Multi-Season Selector** - Season selectbox, parameterized API calls and caching by year
- [ ] **Phase 8: Cloud Deployment** - Streamlit Community Cloud deploy with shareable URL

## Phase Details

### Phase 7: Multi-Season Selector
**Goal**: Users can explore any MLB season from 2022 onward, with the app correctly fetching and caching season-specific rosters and HR data
**Depends on**: Nothing (extends existing v1.0 features locally)
**Requirements**: SEASON-01, SEASON-02, SEASON-03, SEASON-04, SEASON-05
**Success Criteria** (what must be TRUE):
  1. User sees a season selectbox defaulting to the current year; selecting a past year reloads data for that season
  2. Changing the season resets the player and stadium selectors so stale selections cannot carry over
  3. A player who was traded or retired in a past season appears in the roster for that year
  4. Switching to a past season fetches cached responses with 30d TTL; switching back to the current season uses 1h TTL
  5. The game-feed cache is bounded and does not exhaust Streamlit Community Cloud memory on a cold load of a high-HR player
**Plans**: 2 plans
Plans:
- [x] 07-01-PLAN.md — Config + UI: dynamic season constants, selectbox, cascade callback, season threading
- [x] 07-02-PLAN.md — API caching: conditional rosterType, two-function TTL split, max_entries cap
**UI hint**: yes

### Phase 8: Cloud Deployment
**Goal**: The app is live on Streamlit Community Cloud with a shareable URL and zero manual cold-start steps required
**Depends on**: Phase 7
**Requirements**: DEPLOY-01, DEPLOY-02, DEPLOY-03, DEPLOY-04
**Success Criteria** (what must be TRUE):
  1. A friend can open a shared URL in their browser and use the full app without any local setup
  2. The deployed app loads venue data immediately on first open (no cold-start venue fetch delay)
  3. `requirements.txt` installs cleanly on the Cloud environment without dev or test dependencies
  4. `.streamlit/config.toml` is committed so app appearance and settings are consistent across environments
**Plans**: 2 plans
Plans:
- [x] 08-01-PLAN.md — Config, deps, and git: narrow .gitignore, create config.toml, add set_page_config, clean requirements.txt, track venues_cache.json
- [ ] 08-02-PLAN.md — Branch and deploy: create main branch, push to GitHub, deploy on Streamlit Community Cloud
**UI hint**: no

## Progress

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 1. Foundation & API Layer | v1.0 | 3/3 | Complete | 2026-04-14 |
| 2. Models & Geometry | v1.0 | 3/3 | Complete | 2026-04-15 |
| 3. HR Pipeline | v1.0 | 3/3 | Complete | 2026-04-15 |
| 4. Controller & Selectors UI | v1.0 | 3/3 | Complete | 2026-04-15 |
| 5. Spray Chart Visualization | v1.0 | 3/3 | Complete | 2026-04-16 |
| 6. Summary, Rankings & Polish | v1.0 | 2/2 | Complete | 2026-04-16 |
| 7. Multi-Season Selector | v1.1 | 2/2 | Complete | 2026-04-17 |
| 8. Cloud Deployment | v1.1 | 0/2 | Planned | - |

---
*Last updated: 2026-04-17 after Phase 8 planning*
