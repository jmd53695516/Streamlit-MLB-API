---
phase: 4
slug: controller-selectors-ui
status: approved
shadcn_initialized: false
preset: none
created: 2026-04-15
reviewed_at: 2026-04-15
---

# Phase 4 — UI Design Contract

> Visual and interaction contract for the Streamlit shell that wires Team → Player → Stadium selectors to `controller.build_view` and renders a raw ViewModel dump. This is a **developer-grade raw-dump view**, not a polished end-user UI. Phase 5 adds the Plotly chart; Phase 6 adds spinners, friendly errors, and the summary card (UX-05, VIZ-04, VIZ-05).

---

## Design System

| Property | Value |
|----------|-------|
| Tool | none |
| Preset | not applicable (Streamlit app — no shadcn/React ecosystem) |
| Component library | Streamlit 1.55+ built-ins only (`st.selectbox`, `st.json`, `st.dataframe`, `st.info`, `st.warning`, `st.divider`, `st.columns`, `st.title`, `st.caption`) |
| Icon library | none (no icons in Phase 4; emoji only if Streamlit default renders them) |
| Font | Streamlit default theme font (Source Sans Pro) — no override |

**Intentionally unstyled:** No custom CSS, no `st.markdown(unsafe_allow_html=True)`, no theme overrides in `.streamlit/config.toml` for this phase. Phase 6 polish may introduce a theme; Phase 4 ships vanilla so visual regressions during polish are observable.

---

## Spacing Scale

Streamlit provides vertical rhythm automatically; this phase does not override it. Declared values are aspirational and apply only where `st.columns` or `st.container` gap choices arise.

| Token | Value | Usage |
|-------|-------|-------|
| xs | 4px | n/a in Phase 4 |
| sm | 8px | n/a in Phase 4 |
| md | 16px | Default Streamlit widget vertical gap (inherited) |
| lg | 24px | `st.divider()` visual break between selectors and raw dump |
| xl | 32px | n/a in Phase 4 |
| 2xl | 48px | n/a in Phase 4 |
| 3xl | 64px | n/a in Phase 4 |

Exceptions: Streamlit default spacing is accepted as-is. No custom spacing tokens are introduced in Phase 4.

---

## Typography

Streamlit defaults. Explicit roles listed to lock what each Streamlit primitive is used for.

| Role | Size | Weight | Line Height | Streamlit Primitive |
|------|------|--------|-------------|---------------------|
| Page title | 32px (Streamlit default for `st.title`) | 600 | 1.2 | `st.title("MLB HR Park Factor Explorer")` |
| Section caption | 14px (Streamlit default for `st.caption`) | 400 | 1.5 | `st.caption(...)` for the dev-mode subtitle under the title |
| Widget label | 14px (Streamlit default) | 600 | 1.5 | `st.selectbox` label arg |
| Body / info | 16px (Streamlit default) | 400 | 1.5 | `st.info`, `st.warning`, `st.json`, `st.dataframe` cells |

**No custom typography declared.** Phase 4 consumes Streamlit defaults unchanged.

---

## Color

Phase 4 uses Streamlit's default light theme (user can toggle system dark mode via Streamlit settings; no app-level override). The 60/30/10 split is **inherited** from Streamlit:

| Role | Value | Usage |
|------|-------|-------|
| Dominant (60%) | Streamlit default `#FFFFFF` (light) / `#0E1117` (dark) | Page background |
| Secondary (30%) | Streamlit default `#F0F2F6` (light) / `#262730` (dark) | Widget backgrounds, selectbox chrome, dataframe rows |
| Accent (10%) | Streamlit default `#FF4B4B` (theme `primaryColor`) | Selectbox focus ring, selected option highlight — **inherited only** |
| Destructive / warning | Streamlit default amber (`st.warning`) + red (`st.error`) | `st.warning` for pipeline errors (D-27); `st.error` reserved for Phase 6 |

Accent reserved for: Streamlit's own focus/selection states on the three selectboxes. Phase 4 does **not** introduce any custom color usage — no colored badges, no manual `:red[...]` markdown, no custom verdict colors in the dataframe (Phase 5 owns green/red verdict coloring on the chart).

**Dataframe `clears_selected` column:** rendered as a plain boolean (`True` / `False`). No conditional formatting in Phase 4. Phase 5 may add green/red styling when the chart ships.

---

## Copywriting Contract

Copywriting is the real contract for this phase. All strings below are **exact** and must match implementation.

### Page chrome

| Element | Exact Copy |
|---------|------------|
| Page title (`st.title`) | `MLB HR Park Factor Explorer` |
| Dev subtitle (`st.caption`) | `Phase 4 — raw ViewModel dump. Chart arrives in Phase 5.` |

### Selector labels and help text

| Widget | Label | Help (tooltip) | Placeholder (when `index=None`) |
|--------|-------|----------------|--------------------------------|
| Team selectbox | `Team` | `Choose an MLB team to load its hitters.` | `Select a team…` (Streamlit `placeholder` arg) |
| Player selectbox | `Player` | `Non-pitchers on this team, sorted by current-season HR count.` | `Select a player…` |
| Stadium selectbox | `Stadium` | `Defaults to the player's home park. Change to see how their HRs would play elsewhere.` | `Select a stadium…` |

**Option display formats** (locked from CONTEXT §specifics):

- Team option: `{team.name} ({team.abbreviation})` — e.g. `New York Yankees (NYY)`
- Player option: `{fullName} — {homeRuns} HR` — e.g. `Aaron Judge — 17 HR`. Zero-HR hitters render as `Juan Soto — 0 HR` (still selectable, per D-13).
- Stadium option: `{venue.name}` — e.g. `Yankee Stadium`

### State messages

| State | Streamlit primitive | Exact Copy |
|-------|---------------------|------------|
| Initial load (D-19): not all three selectors chosen | `st.info` | `Select a team, player, and stadium to begin.` |
| 0-HR player (D-25): `events` is empty | `st.info` | `{player_name} has no home runs in {season}.` — interpolate with the selected player's display name and season int, e.g. `Jose Iglesias has no home runs in 2026.` |
| All-missing-hitData (D-26): `events` non-empty, `plottable_events` empty | `st.info` | `No HRs have hitData for the verdict matrix — pipeline returned events but none are plottable.` |
| Pipeline error carrier non-empty (D-27) | `st.warning` | `{n} game feed(s) failed to fetch; see raw ViewModel below for details.` — use `game feed` singular when `n == 1`, `game feeds` otherwise. |

### Section headers in raw-dump area

| Section | Streamlit primitive | Exact Copy |
|---------|---------------------|------------|
| JSON block header | `st.subheader` | `ViewModel (raw)` |
| Dataframe block header | `st.subheader` | `Plottable HRs` |
| Divider between selectors and raw dump | `st.divider()` | (no copy — visual only) |

### Dataframe column headers (D-24)

Exact column names in order, rendered via `st.dataframe` on a pandas DataFrame built from `plottable_events`:

| Column | Source field | Format |
|--------|--------------|--------|
| `game_date` | `HREvent.game_date` | ISO date string `YYYY-MM-DD` |
| `opponent_abbr` | `HREvent.opponent_abbr` | 3-letter team code |
| `distance_ft` | `HREvent.total_distance` | integer feet, e.g. `421` |
| `launch_speed` | `HREvent.launch_speed` | float mph, 1 decimal, e.g. `108.3` |
| `launch_angle` | `HREvent.launch_angle` | float deg, 1 decimal, e.g. `27.4` |
| `clears_selected` | `ViewModel.clears_selected_park[i]` | boolean `True` / `False` |

**No destructive actions in Phase 4.** No delete, no reset button, no confirmations required. (The implicit "reset" cascade is silent via `on_change` callbacks per D-17 — no confirmation copy needed since the user's action itself signals intent.)

**No primary CTA** in the traditional sense — the three selectboxes are the input, and the view renders automatically once all three are populated. "Submit" / "Load" buttons are explicitly not present.

---

## Interaction Contract

This is the load-bearing section for Phase 4. It locks the widget wiring that REQUIREMENTS.md UX-01 through UX-04 demand.

### Widget hierarchy (top-to-bottom in `app.py`)

1. `st.title("MLB HR Park Factor Explorer")`
2. `st.caption("Phase 4 — raw ViewModel dump. Chart arrives in Phase 5.")`
3. **Selector row** — three `st.selectbox` widgets. Layout at planner's discretion (D-119 range): either stacked vertically OR in `st.columns(3)` side-by-side. **Order is locked: Team, Player, Stadium, left-to-right (or top-to-bottom).**
4. `st.divider()`
5. **Render region** — conditional content based on ViewModel state (see "Render tree" below).

### Selector behavior (locked from D-16 / D-17 / D-18 / D-19 / D-20)

| Selectbox | `key` | `index` default | `placeholder` | `on_change` | Populated from |
|-----------|-------|-----------------|---------------|-------------|----------------|
| Team | `"team_id"` | `None` | `"Select a team…"` | `_on_team_change` | `get_teams()` sorted by `team.name` asc |
| Player | `"player_id"` | `None` | `"Select a player…"` | `_on_player_change` | `get_team_hitting_stats(team_id, season)` filtered to non-pitchers, sorted by `(-homeRuns, fullName)`. **Disabled (or empty options list) when `team_id is None`.** |
| Stadium | `"venue_id"` | `None` (pre-callback) / player's home venue id (after `_on_player_change` fires) | `"Select a stadium…"` | none | `load_all_parks()` sorted by `venue.name` asc. **Disabled (or empty options list) when `player_id is None`.** |

### Callback semantics

- `_on_team_change`: sets `st.session_state["player_id"] = None` and `st.session_state["venue_id"] = None`. Does NOT fetch anything — Streamlit's next rerun will call `get_team_hitting_stats(new_team_id)` to repopulate the player selectbox.
- `_on_player_change`: sets `st.session_state["venue_id"] = _home_venue_id(st.session_state["team_id"])` where `_home_venue_id` reads from the cached `get_teams()` response (`team["venue"]["id"]`). Does NOT reset venue to `None` — it jumps directly to the home-park default per UX-03.
- Stadium selectbox has **no** callback — manual overrides stick until Team or Player changes.

### Render tree (below the divider)

```
if team_id is None or player_id is None or venue_id is None:
    st.info("Select a team, player, and stadium to begin.")
else:
    view = controller.build_view(team_id, player_id, venue_id)

    if view.errors:
        st.warning(f"{len(view.errors)} game feed(s) failed to fetch; see raw ViewModel below for details.")
        # singular/plural handled per copywriting contract

    if not view.events:
        st.info(f"{view.player_name} has no home runs in {view.season}.")
    elif not view.plottable_events:
        st.info("No HRs have hitData for the verdict matrix — pipeline returned events but none are plottable.")

    st.subheader("ViewModel (raw)")
    st.json(view.to_dict())

    if view.plottable_events:
        st.subheader("Plottable HRs")
        st.dataframe(_build_plottable_df(view), use_container_width=True)
```

**Render ordering note:** warning banners appear BEFORE the JSON dump so errors are not hidden below a large JSON block. Dataframe appears AFTER JSON so the scannable view is the last thing on the page (pleasant to scroll to).

### No-fetch-before-selection guarantee (D-18)

On cold start (all three `session_state` keys `None`):
- `get_teams()` IS called (needed to populate the Team selectbox).
- `get_team_hitting_stats(...)` is NOT called.
- `load_all_parks()` is NOT called.
- `build_view(...)` is NOT called.

This satisfies CLAUDE.md's "no hammering the API, aggressive caching" posture for the initial page load.

---

## Registry Safety

| Registry | Blocks Used | Safety Gate |
|----------|-------------|-------------|
| none (Streamlit built-ins only) | `st.title`, `st.caption`, `st.selectbox`, `st.divider`, `st.columns`, `st.subheader`, `st.info`, `st.warning`, `st.json`, `st.dataframe` | not applicable |

**No third-party Streamlit components** (`streamlit-extras`, `streamlit-aggrid`, `streamlit-option-menu`, etc.) are introduced in Phase 4. Any such addition is out of scope and requires a new CONTEXT entry.

---

## What Is Intentionally Unstyled (for Phase 6)

This list flags Phase 4's deliberate minimalism so Phase 6's polish planner doesn't mistake absence for oversight:

- No loading spinner (`st.spinner`) around `build_view` — Phase 6 / UX-05.
- No retry button on `st.warning` — Phase 6 / UX-05.
- No summary metrics card (`st.metric` for `totals.total_hrs`, etc.) — Phase 6 / VIZ-04. **Totals are already computed in the ViewModel (D-09) and visible in the JSON dump.**
- No best/worst parks ranking — Phase 6 / VIZ-05.
- No Plotly chart, no stadium outline, no HR scatter — Phase 5 / VIZ-01/02/03.
- No conditional row coloring in the plottable dataframe — Phase 5/6 polish.
- No sidebar layout, no `st.tabs`, no `st.expander` — single-page, single-column flow.
- No custom `.streamlit/config.toml` theme — Streamlit default theme only.
- No URL query-param state (`bind=`) — V2-05, deferred.
- No empty / disabled-state copy variants on the Player and Stadium selectboxes beyond the standard `placeholder` — the cascade visibly reveals one step at a time.

---

## Checker Sign-Off

- [x] Dimension 1 Copywriting: PASS
- [x] Dimension 2 Visuals: PASS
- [x] Dimension 3 Color: PASS
- [x] Dimension 4 Typography: PASS
- [x] Dimension 5 Spacing: PASS
- [x] Dimension 6 Registry Safety: PASS

**Approval:** approved 2026-04-15 by gsd-ui-checker
