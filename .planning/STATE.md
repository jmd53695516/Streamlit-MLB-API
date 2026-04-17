---
gsd_state_version: 1.0
milestone: v1.1
milestone_name: Multi-Season & Deploy
status: Executing Phase 07
last_updated: "2026-04-17T00:07:24.302Z"
progress:
  total_phases: 2
  completed_phases: 0
  total_plans: 2
  completed_plans: 0
  percent: 0
---

# Project State — Streamlit MLB HR Park Factor Explorer

## Project Reference

See: .planning/PROJECT.md (updated 2026-04-16)

**Core value**: Given any MLB hitter, quickly answer "how cheap or no-doubt were their home runs this season?" by comparing each HR's distance and spray angle against every MLB park's fence dimensions.
**Current focus**: v1.1 — Multi-season selector + Streamlit Cloud deployment.

## Current Position

Phase: 07 (Multi-Season Selector) — EXECUTING
Plan: 1 of 2

- **Milestone**: v1.1 Multi-Season & Deploy
- **Phase**: 7 — Multi-Season Selector (not started)
- **Status**: Roadmap created, ready to plan Phase 7
- **Progress**: 0/2 phases complete

```
v1.1 progress: [                    ] 0%
Phase 7: Not started
Phase 8: Not started
```

## Performance Metrics

| Metric | Value |
|--------|-------|
| v1.0 phases complete | 6/6 |
| v1.1 phases total | 2 |
| v1.1 phases complete | 0 |
| v1.1 requirements total | 9 |
| v1.1 requirements delivered | 0 |
| Coverage validated | 9/9 mapped |
| Python LOC (v1.0 baseline) | 5,151 (2,143 src + 3,008 test) |
| Tests passing (v1.0 baseline) | 110 |

## Accumulated Context

### Decisions Made

- Direct HTTP to `statsapi.mlb.com/api/v1` — no third-party wrapper libraries ✓
- Ignore wall height in v1 HR verdict (API doesn't expose fence height) ✓
- Streamlit (not Flask/FastAPI+frontend) — fastest path for hobby data app ✓
- Plotly over matplotlib — unlocks hover tooltips for minimal extra cost ✓
- Piecewise-linear fence interpolation in angle space (not cubic spline) ✓
- Only `services/mlb_api.py` touches `requests` and `@st.cache_data` ✓
- Past-season API responses cached at 30d TTL; current season at 1h TTL ✓
- Game-feed cache capped at max_entries to bound Cloud memory usage ✓
- `venues_cache.json` committed to repo to eliminate cold-start venue fetches ✓

### Blockers

None.

## Session Continuity

**Last session ended**: 2026-04-16 — v1.1 roadmap created.

**Next session should**:

1. Run `/gsd-plan-phase 7` to plan Phase 7: Multi-Season Selector.

---
*Last updated: 2026-04-16 after v1.1 roadmap creation*
