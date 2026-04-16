---
gsd_state_version: 1.0
milestone: v1.1
milestone_name: Multi-Season & Deploy
status: Defining requirements
last_updated: "2026-04-16T12:00:00.000Z"
progress:
  total_phases: 0
  completed_phases: 0
  total_plans: 0
  completed_plans: 0
  percent: 0
---

# Project State — Streamlit MLB HR Park Factor Explorer

## Project Reference

See: .planning/PROJECT.md (updated 2026-04-16)

**Core value**: Given any MLB hitter, quickly answer "how cheap or no-doubt were their home runs this season?" by comparing each HR's distance and spray angle against every MLB park's fence dimensions.
**Current focus**: v1.1 — Multi-season selector + Streamlit Cloud deployment.

## Current Position

- **Milestone**: v1.1 Multi-Season & Deploy
- **Status**: Defining requirements
- **Progress**: Not started

## Performance Metrics

| Metric | Value |
|--------|-------|
| Phases total | 6 |
| Phases complete | 6 |
| Requirements total (v1) | 18 |
| Requirements delivered | 18 |
| Coverage validated | 18/18 |
| Python LOC | 5,151 (2,143 src + 3,008 test) |
| Tests passing | 110 |

## Accumulated Context

### Decisions Made

- Direct HTTP to `statsapi.mlb.com/api/v1` — no third-party wrapper libraries ✓
- Ignore wall height in v1 HR verdict (API doesn't expose fence height) ✓
- Current season only — keeps per-player game-feed fan-out bounded ✓
- Streamlit (not Flask/FastAPI+frontend) — fastest path for hobby data app ✓
- Plotly over matplotlib — unlocks hover tooltips for minimal extra cost ✓
- Piecewise-linear fence interpolation in angle space (not cubic spline) ✓
- Only `services/mlb_api.py` touches `requests` and `@st.cache_data` ✓

### Blockers

None.

## Session Continuity

**Last session ended**: 2026-04-16 — v1.1 milestone started.

**Next session should**:

1. Define requirements and create roadmap for v1.1.

---
*Last updated: 2026-04-16 after v1.1 milestone start*
