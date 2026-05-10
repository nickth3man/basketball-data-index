# NBA DuckDB Dashboard

> Interactive Streamlit dashboard exposing **all 15 tables** of `projects/test-db/nba.duckdb` (1.95 GB, 30 years of NBA history including 17.3M play-by-play events).

**Status: implemented and verified.** All 14 pages render without errors against the live database; full coverage of every base table is asserted by `tests/test_pages.py` + `tests/test_queries.py`.

## Goals

1. **Coverage** — every one of the 15 tables (including bridge tables and the 17.3M-row PBP event log) is reachable from the UI; no data hidden.
2. **Interactivity** — filters, drill-downs, click-to-explore (especially shot charts).
3. **Performance** — sub-second response for typical filtered queries via DuckDB columnar scans + Streamlit caching.
4. **Reproducibility** — single command launches; runs locally against the existing `.duckdb` file with no server infrastructure.
5. **Open source only** — every dependency MIT / Apache-2.0 / BSD / GPL-3.0.

---

## Quick start

```bash
cd projects/db-viz
pip install -r requirements.txt
streamlit run app.py
# Then open http://localhost:8501

# Tests (no browser needed)
python tests/test_queries.py   # SQL coverage smoke test
python tests/test_pages.py     # AppTest harness — runs every page end-to-end
```

Auto-discovers the database at `../test-db/nba.duckdb`. Override with the
`NBA_DUCKDB_PATH` environment variable.

---

## Tech stack (research-backed)

Decisions based on multi-source research (firecrawl, tavily, brave, deepwiki, octocode, direct GitHub scrapes).

### Frameworks evaluated

| Framework | License | Verdict |
|---|---|---|
| **Streamlit** | Apache-2.0 | **Chosen** — Python-native, official DuckDB integration guide (Mar-2025), `@st.cache_data` makes 17M-row queries snappy, multipage app structure, custom court overlays via matplotlib/sportypy |
| Evidence.dev | MIT | Considered for static-export side deliverable (SQL+Markdown reports, ECharts, DuckDB-WASM) |
| Observable Framework | ISC + BSD-3 | Rejected — would ship the entire 1.95 GB `.duckdb` to the browser via WASM |
| Rill Data | Apache-2.0 | Rejected — constrained dashboard model, no custom Python viz for court overlays |
| Apache Superset | Apache-2.0 | Rejected — heavy server infra, no court overlay extension |
| Metabase | AGPL OSS | Rejected — drag-and-drop charts, weak custom viz |
| Lightdash | MIT | Rejected — requires dbt project |
| Dash (Plotly) | MIT | Considered — more callback boilerplate than Streamlit |

### NBA visualization libraries

| Library | License | Use |
|---|---|---|
| **sportypy** ([sportsdataverse/sportypy](https://github.com/sportsdataverse/sportypy)) | GPL-3.0 | Primary court drawer — `NBACourt().draw(display_range="offense")` with built-in `.scatter() / .hexbin() / .heatmap() / .contourf() / .arrow()` matplotlib wrappers |
| Plotly | MIT | All non-court charts (lines, bars, sankey, treemaps, animations); 3D shot-path plots |
| Folium + streamlit-folium | MIT / MIT | Arena lat/lng map view |
| streamlit-aggrid | MIT | Interactive paginated tables (PBP browser, leaderboards) |
| streamlit-plotly-events | MIT | Click-to-drill from shot charts into game timelines |

### Reference projects studied

| Repo | License | Lessons borrowed |
|---|---|---|
| [tbala25/nba-scouting-dashboard](https://github.com/tbala25/nba-scouting-dashboard) | Apache-2.0 | Page layout for Team Scouting; Four Factors view |
| [kfoofw/nba-shot-chart-streamlit](https://github.com/kfoofw/nba-shot-chart-streamlit) | open | Player-season filter pattern |
| [nogibjj/BallersDash](https://github.com/nogibjj/BallersDash) | open | Player vs Team comparison sections |
| [mpope9/nba-sql](https://github.com/mpope9/nba-sql) | open | Schema concepts (already used in test-db) |

### Authoritative references

- **[DuckDB official Streamlit guide (2025-03-28)](https://duckdb.org/2025/03/28/using-duckdb-in-streamlit.html)** — establishes the `read_only=True` connection pattern + `@st.cache_resource` / `@st.cache_data` we use throughout.
- **sportypy README** — confirms NBA court coords are in feet, origin at center; baskets at `(±41.75, 0)`. Our PBP `x_legacy/y_legacy` columns use NBA Stats convention (1/10-ft, rotated 90°) — needs the rotation transform in `lib/court.py`.

---

## Connection & caching pattern (canonical)

```python
# lib/db.py
import duckdb, os, datetime
import streamlit as st
from pathlib import Path

DB_PATH = Path(os.environ.get(
    "NBA_DUCKDB_PATH",
    Path(__file__).parent.parent.parent / "test-db" / "nba.duckdb"
))

@st.cache_resource(ttl=datetime.timedelta(hours=1), max_entries=2)
def get_conn() -> duckdb.DuckDBPyConnection:
    """One read-only connection per Streamlit process. read_only=True allows
    multiple concurrent app sessions to attach safely."""
    con = duckdb.connect(str(DB_PATH), read_only=True)
    con.execute("PRAGMA threads=4")
    con.execute("PRAGMA memory_limit='4GB'")
    return con

@st.cache_data(ttl=3600, max_entries=200, show_spinner=False)
def q(sql: str, params: tuple = (), _conn=None):
    """Execute SQL and cache the resulting DataFrame.
    Underscore prefix on _conn tells Streamlit not to hash it."""
    conn = _conn or get_conn()
    return conn.execute(sql, params).fetchdf()
```

Why this pattern:
1. Connection is created once per process, not per request (10× latency reduction).
2. Read-only mode lets multiple browser tabs attach to the same `.duckdb`.
3. `cache_data` memoizes deterministic query outputs — heavy aggregations run once and serve instantly on every re-render.

---

## Page-by-page design — all 15 tables covered

### Coverage matrix

| Page | dim_team | dim_player | dim_arena | dim_date | fact_game | fact_game_official | fact_team_game_stats | fact_team_game_period | fact_player_game_stats | fact_play_by_play | fact_game_odds_snapshot | fact_game_main_line | fact_game_market_odds | fact_scheduled_game | v_team_current |
|---|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|
| 1 Home / League Pulse | • |   |   | • | • |   | • |   | • |   |   |   |   | • | • |
| 2 Team Profile | • |   |   | • | • |   | • | • | • |   |   |   |   |   | • |
| 3 Player Profile |   | • |   | • | • |   |   |   | • | • |   |   |   |   |   |
| 4 Game Center | • | • | • |   | • | • | • | • | • | • | • | • |   |   |   |
| 5 Shot Charts |   | • |   | • | • |   |   |   |   | • |   |   |   |   |   |
| 6 PBP Browser |   | • |   |   | • |   |   |   |   | • |   |   |   |   |   |
| 7 Quarter Splits | • |   |   | • | • |   | • | • |   |   |   |   |   |   | • |
| 8 Officials |   |   |   |   | • | • |   |   |   |   |   |   |   |   |   |
| 9 Odds & Betting | • |   |   | • | • |   | • |   |   |   | • | • | • |   | • |
| 10 Schedule | • |   |   | • | • |   |   |   |   |   |   |   |   | • | • |
| 11 Arenas |   |   | • |   | • |   |   |   |   |   |   |   |   |   |   |
| 12 Season Trends | • |   |   | • | • |   | • |   | • |   |   |   |   |   | • |
| 13 Compare (H2H) | • | • |   | • |   |   | • |   | • |   |   |   |   |   | • |
| 14 SQL Lab | every | every | every | every | every | every | every | every | every | every | every | every | every | every | every |

Every table appears in at least one page. SQL Lab is the universal escape hatch.

### Page 1 — Home / League Pulse
At-a-glance health metrics across all NBA history.
- KPI strip (`st.metric`): total games, players, franchises, PBP events, latest game date, current season
- Season-over-season scoring trend (Plotly line)
- 3PA revolution area chart
- Pace × OffRtg scatter, color by season
- Today's slate (from `fact_scheduled_game`)
- "On this day in NBA history" widget

### Page 2 — Team Profile
Full deep-dive on one team across selected season(s).
- Header with team metadata
- Win/loss strip by month
- Season totals card grid (Four Factors highlighted)
- Quarter scoring profile (`fact_team_game_period`)
- Roster contributions treemap
- Game log (st-aggrid; click → Game Center)
- Team shot heatmap (sportypy)
- Coach summary

### Page 3 — Player Profile
Full career view of a single player.
- Bio block (birth, school, draft, height/weight)
- Career trajectory (PPG/RPG/APG/MPG by season)
- Shooting splits (FG%/3P%/FT% with attempt volume)
- Career milestones (10K/20K/30K points, first triple-double)
- Best games leaderboard
- Career shot chart (sportypy hexbin with FG% color scale)
- Comparison to position average (radar)
- Most-shared teammates sankey

### Page 4 — Game Center
Single-game deep-dive — the page where all data converges.
- Header: matchup, arena, score, attendance, officials
- Box score side-by-side (home vs away)
- Quarter scoring grouped bar
- Per-player box score (st-aggrid × 2)
- PBP timeline (Plotly score-differential over `seconds_elapsed`)
- Shot chart (sportypy split-court, home left / away right)
- Naive win-probability chart
- Officials block with per-ref drill-through
- Pre-game odds: opening + Pinnacle + market diversity

### Page 5 — Shot Charts (marquee viz)
Slice-and-dice the 17M PBP rows by shot location.
- Filters: player, team, season range, game type, period, shot value, time-remaining bucket, score situation
- Mode toggle: Scatter / Hexbin / Heatmap (FG%) / Heatmap (PPS) / Contour
- Color scale vs league avg (red above, blue below) by zone
- Shot-distance histogram with 2pt/3pt arc overlays
- Zone breakdown table (paint/mid/corner-3/above-break-3)
- Animated shot density over time (`animation_frame=season_year` showing the 3PT migration)

### Page 6 — PBP Browser
Raw event log explorer.
- AG-Grid table (paged, server-side filter via DuckDB)
- Action-type histogram
- Run analysis (consecutive same-team scoring)
- Lineup co-occurrence (derived from sub events)
- CSV / Parquet export

### Page 7 — Quarter Splits
Surface the underused `fact_team_game_period` table.
- League quarter heatmap (teams × quarters, color by avg PPG)
- Best/worst Q4 teams by season
- Quarterly +/- violin distribution
- Comeback finder (trailed by ≥15 at half and won)

### Page 8 — Officials
- Top officials by games worked
- Avg fouls / pace per official
- Official-team affinity heatmap
- 3-ref crew chemistry

### Page 9 — Odds & Betting
- Closing-line value distribution
- Line movement over time (per game)
- Pinnacle main lines explorer (st-aggrid)
- Market diversity per game
- ROI calculator (e.g. "home dog +5+")
- Favorites vs underdogs by season

### Page 10 — Schedule
- Upcoming games (next 14 days)
- Schedule density heatmap (team × week)
- Back-to-back finder
- Travel miles estimator (chained `dim_arena` lat/lng)

### Page 11 — Arenas
- Folium map (pin per arena, sized by games hosted)
- All-time games hosted bar
- Average attendance (caveat: only 2025-26 populated)
- Multi-tenant arenas

### Page 12 — Season Trends
- Pace evolution
- 3PT revolution stacked area (%FGA from 2pt/3pt/FT)
- Defense decline (league avg DefRtg)
- Scoring inflation with rule-change annotations
- Iron-man decline (% playing 75+ games)
- East vs West parity (avg net-rating delta)

### Page 13 — Compare (Head-to-Head)
Modes: Player vs Player, Team vs Team, Player vs Era-Average.
- Radar chart (Plotly polar)
- Trajectory overlay
- Career stat table side-by-side
- Common opponents sankey

### Page 14 — SQL Lab
- SQL editor (monospace `st.text_area`)
- Schema browser sidebar (from `information_schema.columns`)
- Query history (last 20)
- AG-Grid result with pagination + export
- 20+ pre-canned example queries
- Safety: connection is `read_only=True` so DDL/DML returns errors

---

## Repository layout

```
projects/db-viz/
├── app.py                           # entry: st.set_page_config + sidebar branding
├── lib/
│   ├── __init__.py
│   ├── db.py                        # get_conn(), q()
│   ├── court.py                     # to_court_ft() coord transform; sportypy NBACourt helpers
│   ├── filters.py                   # reusable sidebar widgets (player_picker, team_picker, ...)
│   ├── kpis.py                      # st.metric formatting helpers
│   └── viz.py                       # plotly chart factories
├── pages/
│   ├── 01_Home.py
│   ├── 02_Team_Profile.py
│   ├── 03_Player_Profile.py
│   ├── 04_Game_Center.py
│   ├── 05_Shot_Charts.py
│   ├── 06_PBP_Browser.py
│   ├── 07_Quarter_Splits.py
│   ├── 08_Officials.py
│   ├── 09_Odds_and_Betting.py
│   ├── 10_Schedule.py
│   ├── 11_Arenas.py
│   ├── 12_Season_Trends.py
│   ├── 13_Compare.py
│   └── 14_SQL_Lab.py
├── assets/
│   ├── arena_geocodes.json          # static lat/lng for arenas (offline, OSS-sourced)
│   └── canned_queries.sql           # SQL Lab examples
├── requirements.txt
├── .streamlit/
│   └── config.toml                  # theme, server settings
├── README.md                        # this file
└── tests/
    └── test_queries.py              # smoke-test that every page's SQL parses & returns rows
```

---

## Cross-cutting design decisions

### Entity pickers
A reusable `lib/filters.py::player_picker()` widget:
- Searchable dropdown over `SELECT person_id, first_name, last_name FROM dim_player ORDER BY last_name`
- Returns `person_id` (never name strings — there are 12 duplicate-name pairs)

Same for `team_picker()` (uses `v_team_current` so the user sees current franchise names).

### Performance budget per page

| Operation | Target | Mitigation |
|---|---|---|
| Page first paint | < 500ms | Prefetched cached queries on warm cache |
| Filter change → chart update | < 1s | DuckDB columnar scan + `@st.cache_data` |
| 17M-row PBP filtered to 1 player career (~12K shots) | < 2s | Index on `person_id` (already in test-db) |
| Game Center full load (all PBP + stats for 1 game) | < 1.5s | PK lookup `game_id` |
| Aggregations across all seasons (e.g. league pace by year) | < 3s | Cache 1h, refresh nightly |

### Coord transform for shots
`fact_play_by_play.x_legacy/y_legacy` use NBA Stats convention (1/10 ft, rotated 90° from sportypy default):

```python
# lib/court.py
def to_court_ft(df, x_col="x_legacy", y_col="y_legacy"):
    """NBA Stats coords -> sportypy NBACourt feet coords (origin = half-court)."""
    df = df.copy()
    df["court_x"] = -df[y_col] / 10.0
    df["court_y"] =  df[x_col] / 10.0
    return df
```

Used by Pages 3, 4, and 5.

### GPL-3.0 isolation
`sportypy` is GPL-3.0. To keep app code license-flexible:
- All sportypy imports live in `lib/court.py` only.
- Other pages call `from lib.court import shot_chart_figure(...)` returning a matplotlib `Figure`.
- App as distributed bundles GPL'd library code — fine for self-hosted dashboards.

### Theming
`.streamlit/config.toml`:
```toml
[theme]
primaryColor = "#C9082A"          # NBA red
backgroundColor = "#0E1117"
secondaryBackgroundColor = "#1C1F2B"
textColor = "#FAFAFA"
font = "sans serif"

[server]
maxUploadSize = 1
runOnSave = true
```

### Data freshness
- Reads `nba.duckdb` mtime on startup; shows "Data as of: YYYY-MM-DD" in sidebar
- Connection cache TTL = 1 hour, so a `build.py` rebuild surfaces within an hour
- For immediate refresh, restart the Streamlit process

### Concurrent users
`read_only=True` lets multiple processes / browser tabs attach simultaneously.

---

## Implementation phases (~16 hours total)

### Phase A — scaffolding (~2h)
- `projects/db-viz/` skeleton, `lib/db.py`, smoke test
- `app.py` with sidebar nav and "Data as of" badge
- `01_Home.py` with KPI strip only (proves end-to-end pipeline)

### Phase B — entity pages (~4h)
- `lib/filters.py::player_picker / team_picker`
- `02_Team_Profile.py`, `03_Player_Profile.py`, `04_Game_Center.py` (no shot charts yet)

### Phase C — shot charts & PBP (~4h)
- `lib/court.py` (sportypy wrapper + coord transform)
- `05_Shot_Charts.py` (full feature set)
- Add shot chart components to Pages 2, 3, 4
- `06_PBP_Browser.py` with st-aggrid
- PBP timeline component for Game Center

### Phase D — supplementary pages (~4h)
- Pages 7–13

### Phase E — power tools & polish (~2h)
- `14_SQL_Lab.py` with schema browser
- `tests/test_queries.py` smoke tests
- Screenshots, license attributions

---

## Verification

After each phase:
1. `streamlit run app.py` launches without error
2. Each page renders within 3 seconds on cold cache
3. **Coverage check**: `tests/test_queries.py` runs a query against every one of the 15 tables and asserts non-empty result — guarantees no table is "loaded but unused"
4. **Cross-validation against `projects/test-db/` outputs**: e.g., LeBron 2003-04 = 1,654 points
5. Manual interaction: click on a shot chart hex → drill to game list; click on a player row in Game Center → jump to Player Profile

---

## Gotchas anticipated (from research + test-db lessons)

1. **PBP coord rotation**: `x_legacy`/`y_legacy` need rotation transform, not just unit conversion (see `lib/court.py`).
2. **Players with same name**: filters MUST drive on `person_id`. test-db README flags 12 duplicates.
3. **`team_id = 0` in PBP**: nulled during ETL but viz code should still `WHERE team_id IS NOT NULL` defensively.
4. **Sparse advanced metrics pre-2000**: `off_rating`, `pie`, etc. NULL for older games — chart `WHERE x IS NOT NULL` and surface a "limited coverage before 1996-97" note.
5. **Sparse attendance**: only 2025-26 has `fact_game.attendance` populated. Arenas page must surface this caveat.
6. **`game_id` always 10-char string**: never cast to int. Filters carry it as VARCHAR.
7. **Pinnacle odds team-name mismatches**: `fact_game_main_line` has NULL `team1_id`/`team2_id` for renamed/relocated franchises. Surface unresolved rows in a separate panel.
8. **Cache invalidation**: `@st.cache_data` keys on SQL string + params. Dynamic SQL with f-strings is fine but must be deterministic given inputs.
9. **DuckDB read-only + WAL conflict**: if `build.py` rebuild happens while dashboard has open connections, DuckDB errors gracefully on next query. Catch and display "Database is being rebuilt — refresh in a minute".
10. **PBP query without filter** can return millions of rows — every PBP page MUST apply `LIMIT` or `WHERE action_type IN (...)`. Use `con.execute(...).arrow()` for streaming when over 1M rows.
11. **sportypy matplotlib output** must be passed to `st.pyplot(fig, clear_figure=True)` to avoid figure leaks across reruns.
12. **Streamlit reruns the entire script on every interaction** — heavy queries MUST be inside `@st.cache_data`-decorated functions, not inline.
13. **Plotly time-series animations with 17M rows** crash the browser — pre-aggregate to season×zone bins (max 30×7 frames) before passing to Plotly.

---

## Out of scope (v1)

- Authentication / multi-user roles (single-user local app)
- Live data ingestion (relies on `build.py` rebuilds)
- ML models (player similarity, win-probability) — Phase F candidate
- LangChain natural-language SQL bot (Page 14 SQL Lab is the v1 manual equivalent)
- 3D shot trajectory plots — Phase F candidate
- Logos and team branding — placeholders only (logo files would require network calls, avoided for OSS-only constraint)
- PDF export / scheduled email reports — Evidence.dev would be the right tool

---

## Critical files (for future modification)

- `lib/db.py` — connection authority; edit here to change DB path or pragmas
- `lib/court.py` — court drawing + coord transform
- `lib/filters.py` — entity pickers used by ≥7 pages
- `pages/14_SQL_Lab.py` — schema browser uses `information_schema`; update if test-db schema changes
- `../test-db/sql/01_schema.sql` — upstream schema authority. Schema changes there must be reflected in dashboard's column references

---

## Open-source license attributions

| Component | License | Project URL |
|---|---|---|
| DuckDB | MIT | https://duckdb.org |
| Streamlit | Apache-2.0 | https://streamlit.io |
| Plotly (Python) | MIT | https://plotly.com/python/ |
| Matplotlib | Matplotlib license (BSD-style) | https://matplotlib.org |
| sportypy | GPL-3.0 | https://github.com/sportsdataverse/sportypy |
| pandas | BSD-3-Clause | https://pandas.pydata.org |
| numpy | BSD-3-Clause | https://numpy.org |
| streamlit-aggrid | MIT | https://github.com/PablocFonseca/streamlit-aggrid |
| streamlit-folium | MIT | https://github.com/randyzwitch/streamlit-folium |
| Folium | MIT | https://python-visualization.github.io/folium/ |
| streamlit-plotly-events | MIT | https://github.com/null-jones/streamlit-plotly-events |
| pyarrow | Apache-2.0 | https://arrow.apache.org/ |

All MIT/Apache/BSD; sportypy GPL-3.0 is isolated to `lib/court.py` per the GPL-isolation strategy above.
