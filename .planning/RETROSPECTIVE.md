# Project Retrospective

*A living document updated after each milestone. Lessons feed forward into future planning.*

## Milestone: v1.0 — MVP

**Shipped:** 2026-04-16
**Phases:** 6 | **Plans:** 17

### What Was Built
- Five cached MLB StatsAPI wrappers with disk-backed venue cache and per-endpoint TTLs
- Pure-function geometry layer: calibrated coordinate transform, fence interpolation, per-park verdicts across all 30 parks
- HR extraction pipeline with graceful degradation (ITP detection, missing hitData flags, per-feed error isolation)
- Streamlit app with cascading Team -> Player -> Stadium selectors via session_state
- Interactive Plotly spray chart with stadium outline, color-coded HR scatter, and hover tooltips
- Summary metrics card (4 widgets), 30-park rankings table with top/bottom highlighting, loading spinner, error handling with retry

### What Worked
- Wave-based plan execution with worktree isolation kept phases moving fast
- Pure-function geometry layer (no I/O) made unit testing trivial — 110 tests, all fast
- Strict "only mlb_api.py touches requests" boundary prevented API coupling from leaking into business logic
- Code review between phases caught naming issues and dead code before they compounded
- Aggressive st.cache_data TTLs meant the app rarely hits the API during development

### What Was Inefficient
- REQUIREMENTS.md traceability table stayed "Pending" throughout all 6 phases — never updated until milestone completion
- STATE.md body text drifted from frontmatter (manually written sections got stale while CLI updated frontmatter)
- Some SUMMARY.md files lacked one_liner field, making automated extraction fail silently

### Patterns Established
- Controller assembles ViewModel; chart.py renders it; app.py wires Streamlit widgets — clean separation
- Geometry code lives in its own package with zero framework imports
- Test fixtures recorded from real API responses, committed to repo for offline testing
- Code review runs automatically after phase execution, before verification

### Key Lessons
1. Pin the coordinate calibration early — the Gameday coordinate system was the biggest unknown and blocking it would have cascaded
2. Plotly's fill='toself' polygon traces are the right abstraction for stadium outlines — simpler than expected
3. For hobby apps, st.cache_data with function-level TTLs is sufficient — no need for requests-cache or Redis

---

## Cross-Milestone Trends

### Process Evolution

| Milestone | Phases | Plans | Key Change |
|-----------|--------|-------|------------|
| v1.0 | 6 | 17 | Initial project — established wave execution, code review gates, verification flow |

### Cumulative Quality

| Milestone | Tests | LOC (src) | LOC (test) |
|-----------|-------|-----------|------------|
| v1.0 | 110 | 2,143 | 3,008 |

### Top Lessons (Verified Across Milestones)

1. Pure-function layers with no framework imports are dramatically easier to test and reason about
2. Record real API fixtures early — they unlock offline development for every subsequent phase
