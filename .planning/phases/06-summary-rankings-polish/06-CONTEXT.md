---
phase: 06-summary-rankings-polish
requirements: [VIZ-04, VIZ-05, UX-05]
depends_on: [Phase 5 (chart.py + app.py), Phase 4 (controller + ViewModel)]
captured: 2026-04-15
status: discussed
---

# Phase 06: Summary, Rankings & Polish — Context

## Phase Boundary

**Goal:** Ship v1 — summary metrics card (VIZ-04), best/worst parks ranking (VIZ-05), loading spinners + friendly error handling (UX-05), plus cleanup of code review findings from Phases 4 and 5.

**In scope:**
- Summary metrics card with 4 `st.metric` widgets above the chart
- Full 30-park ranking table in a collapsible `st.expander`, sorted by clears descending, with top 3 / bottom 3 highlighted
- `st.spinner` wrapping `build_view` for loading feedback
- `st.error` with descriptive message + retry button on API failures
- Code review cleanup: stale caption, private-function promotion, dead constant, magic number, verdict_matrix guard
- **This is the final phase** — after this, the app ships as v1

**Out of scope (V2 backlog):**
- V2-01: empty-state UI beyond current D-12 banner
- V2-02: per-HR details table (already partially exists as the plottable-HR dataframe)
- V2-03: wall-height caveat (MLB StatsAPI `fieldInfo` has fence distances only, no heights; Baseball Savant may have height data at `baseballsavant.mlb.com/leaderboard/statcast-park-factors?fenceStatType=height` but it's JS-rendered and not accessible via the locked direct-HTTP constraint)
- V2-04: cheap-HR threshold slider
- V2-05: URL query-param state for bookmarkable views

## Implementation Decisions

### Locked from prior phases / roadmap / CLAUDE.md
- **Plotly 6.7.0** for any visualization (locked)
- **`st.cache_data(ttl=...)`** as the only caching layer (CLAUDE.md)
- **`controller.build_view`** returns the ViewModel with `verdict_matrix.cleared[i,j]` — all metrics derived from this
- **chart.py is pure** (no streamlit imports) — any new pure computation follows the same pattern
- **Existing empty-state banner** (D-12): `st.info("{player} has no plottable HRs this season.")`
- **ViewModel.totals** dict already contains `total_hrs` and `plottable_count` — may need extension for VIZ-04 metrics (or compute in app.py from verdict_matrix directly)

### D-01 Summary metrics card layout (VIZ-04)
**Decision:** 4 `st.metric` widgets in a single `st.columns(4)` row, positioned **above the chart**.

| Column | Label | Value | Source |
|--------|-------|-------|--------|
| 1 | Total HRs | `len(view.plottable_events)` | ViewModel.plottable_events |
| 2 | Avg Parks Cleared | `mean(cleared_per_hr)` rounded to 1 decimal | verdict_matrix.cleared row sums / n_hrs |
| 3 | No-Doubters (30/30) | count of HRs where `cleared[i, :].all()` | verdict_matrix.cleared |
| 4 | Cheap HRs (≤5/30) | count of HRs where `cleared[i, :].sum() <= 5` | verdict_matrix.cleared |

No `delta` parameter on `st.metric` — just label + value. Keep it clean.

### D-02 Best/worst parks ranking (VIZ-05)
**Decision:** Full 30-park ranked table in a collapsible `st.expander("Park Rankings")`, sorted by clears descending.

**Columns:**
| Column | Label | Value | Source |
|--------|-------|-------|--------|
| 1 | Park | Park name | `view.parks[j].name` |
| 2 | Clears | Count of this player's HRs that clear park j | `verdict_matrix.cleared[:, j].sum()` |
| 3 | Clear % | `clears / n_plottable * 100`, formatted as `XX%` | derived |
| 4 | Avg Margin (ft) | Mean of `verdict_matrix.margin_ft[:, j]`, formatted as `+X.X` or `-X.X` ft | verdict_matrix.margin_ft |

**Highlighting:** Top 3 rows highlighted green, bottom 3 highlighted red. Since native `st.dataframe` doesn't easily support row-level coloring, use **pandas Styler** with `st.dataframe(df.style.apply(...))` to color the background of the top 3 and bottom 3 rows.

**Tie handling:** If multiple parks are tied at rank 3 or rank 28, include all tied parks in the highlighted group (may result in 4+ highlighted rows).

### D-03 Loading spinner (UX-05 — loading)
**Decision:** Single `st.spinner("Loading player data...")` wrapping the `controller.build_view(...)` call.

```python
with st.spinner("Loading player data..."):
    view = controller.build_view(team_id, player_id, venue_id, ...)
```

One spinner covers all API fetches (gameLog, feeds, parks). No per-section spinners — fetches are fast enough that multiple spinners would just flash.

### D-04 Error handling (UX-05 — errors)
**Decision:** `st.error` with descriptive message + retry button that clears all caches.

```python
try:
    view = controller.build_view(...)
except Exception as e:
    st.error(f"Could not load data. The MLB API may be temporarily unavailable. ({type(e).__name__})")
    if st.button("Retry"):
        st.cache_data.clear()
        st.rerun()
```

- Wraps the `build_view` call in a try/except
- `st.cache_data.clear()` clears ALL cached data (simple; individual key clearing is complex and error-prone)
- `st.rerun()` restarts the page flow after clearing cache
- Error message is user-friendly, not a raw traceback; exception type is included for debugging

### D-05 Stale caption removal (polish)
**Decision:** Remove the `st.caption("Phase 4 — raw ViewModel dump...")` line from `app.py` (approximately line 57). It's obsolete now that the chart renders.

### D-06 Promote private functions to public API (polish)
**Decision:** Rename `_sorted_teams` → `sorted_teams`, `_sorted_hitters` → `sorted_hitters`, `_hr_of` → `hr_of` in `controller.py`, and add them to `__all__`. Update all call sites in `app.py`.

**Why:** These are called from `app.py` and are part of the controller's public contract. The underscore prefix was a Phase 4 implementation artifact; now that the API is stable, promote them.

### D-07 Code review fixes (polish)
**Decision:** Fix the following from Phase 4 + 5 code reviews:

| Finding | File | Fix |
|---------|------|-----|
| WR-01 (Phase 5): mound radius magic number | `chart.py:142` | Extract `MOUND_RADIUS_FT = 5.0` as a named constant next to existing infield constants |
| IN-03 (Phase 5): dead constant `BASE_MARKER_SIZE_FT` | `chart.py:38` | Remove the unused constant (or use it in `_bases_trace` if appropriate) |
| WR-01 (Phase 4): unguarded `next()` in `build_view` | `controller.py:289,294` | Wrap in a try/except or use `next(..., None)` with a guard check |
| IN-01 (Phase 5): stale Phase 4 caption | `app.py:57` | Covered by D-05 above |

### D-08 Wall-height caveat
**Decision:** NOT included in Phase 6 (user did not select V2-03). Documented as backlog item. Reference URL for future work: `baseballsavant.mlb.com/leaderboard/statcast-park-factors?fenceStatType=height` (JS-rendered, not accessible via direct HTTP).

### Claude's Discretion
- Exact `st.metric` formatting (e.g., whether to show "18.3 / 30" or just "18.3" for avg parks cleared)
- Whether the ranking computation lives in `controller.py` (extending `build_view` or a separate function) or computed inline in `app.py` — researcher/planner should decide based on testability
- pandas Styler exact color values for top 3 / bottom 3 highlighting — use the existing `CLEARS` / `DOESNT_CLEAR` hex from `chart.py` for consistency
- Whether to add a `st.divider()` between the metrics row and the chart
- Order of page sections if the plottable-HR dataframe (from Phase 4) remains: metrics → chart → ranking expander → dataframe (or remove the Phase 4 raw JSON dump entirely since the chart replaces it)

## Canonical References

### Project instructions
- `CLAUDE.md` — Plotly 6.7, `@st.cache_data`, hobby-app ethos

### Planning artifacts
- `.planning/ROADMAP.md` — Phase 6 goal and success criteria
- `.planning/REQUIREMENTS.md` — VIZ-04, VIZ-05, UX-05

### Phase 4 artifacts (controller being modified)
- `src/mlb_park/controller.py` — ViewModel, `build_view`, `_sorted_teams`, `_sorted_hitters`, `_hr_of`
- `.planning/phases/04-controller-selectors-ui/04-REVIEW.md` — code review findings being fixed

### Phase 5 artifacts (chart being extended)
- `src/mlb_park/chart.py` — color constants (reuse `CLEARS`/`DOESNT_CLEAR` for ranking highlighting)
- `.planning/phases/05-spray-chart-visualization/05-REVIEW.md` — code review findings being fixed
- `.planning/phases/05-spray-chart-visualization/05-CONTEXT.md` — D-08 color palette

### Phase 5 app integration
- `src/mlb_park/app.py` — existing page structure (selectors → chart → dataframe)

### External references
- [`st.metric` docs](https://docs.streamlit.io/develop/api-reference/data/st.metric)
- [`st.expander` docs](https://docs.streamlit.io/develop/api-reference/layout/st.expander)
- [`st.spinner` docs](https://docs.streamlit.io/develop/api-reference/status/st.spinner)
- [`pandas.DataFrame.style`](https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.style.html)
- `baseballsavant.mlb.com/leaderboard/statcast-park-factors?fenceStatType=height` — wall height data source for future V2-03 work (JS-rendered, not accessible via direct HTTP)

## Specific Ideas

- **Reuse chart.py color constants** for the ranking table highlighting (`CLEARS = #2ca02c` for top 3 rows, `DOESNT_CLEAR = #d62728` for bottom 3 rows). Keeps the color language consistent across the entire app.
- **Remove the Phase 4 raw JSON dump** (`st.json(view.to_dict())`) since the chart now serves that purpose. Keep only the plottable-HR dataframe if it adds value.
- **Page section order after Phase 6:** selectors → metrics row → chart → ranking expander → plottable-HR dataframe (if kept).

## Deferred Ideas

- **V2-03 wall-height caveat** — user-provided Savant URL has data but requires JS scraping. Not feasible under the direct-HTTP constraint. Future phase could hardcode known wall heights from public sources.
- **V2-04 cheap-HR threshold slider** — currently hardcoded at ≤5/30. Future enhancement.
- **V2-05 URL state** — `st.query_params` for bookmarkable views.
- **Per-section loading** — if API latency grows, could add per-fetch spinners. Not needed at current performance.
- **Dark mode theming** — `theme=None` on `st.plotly_chart` for Streamlit dark mode support.
