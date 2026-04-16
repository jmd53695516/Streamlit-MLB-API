# Requirements: Streamlit MLB HR Park Factor Explorer

**Defined:** 2026-04-16
**Core Value:** Given any MLB hitter, quickly answer "how cheap or no-doubt were their home runs this season?" by comparing each HR's distance and spray angle against every MLB park's fence dimensions.

## v1.1 Requirements

Requirements for multi-season support and Streamlit Community Cloud deployment.

### Multi-Season

- [ ] **SEASON-01**: User can select any MLB season from the past 5 years (2022-2026) via a selectbox
- [ ] **SEASON-02**: Changing the season resets the player and stadium selectors
- [ ] **SEASON-03**: Historical seasons use fullSeason roster so traded/retired players appear for the year they played
- [ ] **SEASON-04**: Past-season API responses are cached with 30d TTL; current season retains 1h TTL
- [ ] **SEASON-05**: Game feed cache is capped at max_entries to prevent OOM on Community Cloud

### Deployment

- [ ] **DEPLOY-01**: App is deployed to Streamlit Community Cloud with a shareable URL
- [ ] **DEPLOY-02**: `requirements.txt` is cleaned up for Cloud (remove pytest, add editable install)
- [ ] **DEPLOY-03**: `.streamlit/config.toml` is committed with app config; `.gitignore` narrowed to exclude only `secrets.toml`
- [ ] **DEPLOY-04**: `venues_cache.json` is committed to the repo to eliminate cold-start venue fetches on Cloud

## Future Requirements

Deferred to future milestone.

### Data Enrichment

- **DATA-01**: Wall height modeling for more accurate HR verdicts (blocked on API data availability)
- **DATA-02**: Career HR history across multiple seasons

### Sharing

- **SHARE-01**: Shareable deep links to specific player/season/stadium combinations

## Out of Scope

| Feature | Reason |
|---------|--------|
| Wall height modeling | API doesn't return fence heights |
| Career HR aggregation | Scope creep; per-season is the unit of analysis |
| User accounts / persistence | Single-user app, no backend |
| USER_AGENT sanitization | User chose not to include; can address before going public if needed |
| Live/in-progress game updates | Hobby app, not a live scoreboard |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| SEASON-01 | Phase 7 | Pending |
| SEASON-02 | Phase 7 | Pending |
| SEASON-03 | Phase 7 | Pending |
| SEASON-04 | Phase 7 | Pending |
| SEASON-05 | Phase 7 | Pending |
| DEPLOY-01 | Phase 8 | Pending |
| DEPLOY-02 | Phase 8 | Pending |
| DEPLOY-03 | Phase 8 | Pending |
| DEPLOY-04 | Phase 8 | Pending |

**Coverage:**
- v1.1 requirements: 9 total
- Mapped to phases: 9
- Unmapped: 0

---
*Requirements defined: 2026-04-16*
*Last updated: 2026-04-16 after v1.1 roadmap creation*
