"""PBP Browser — raw event log explorer with filters + AG-Grid."""

from __future__ import annotations

import plotly.express as px
import streamlit as st
from st_aggrid import AgGrid, GridOptionsBuilder

from lib.db import q
from lib.filters import _player_options, _team_options, season_picker

st.title("📜 Play-by-Play Browser")
st.caption("Raw event-log explorer over `fact_play_by_play` (17.3M rows).")

with st.sidebar:
    st.header("Filters")
    season_range = season_picker(multi=True, key="pbp_season")
    player_opts = _player_options()
    team_opts = _team_options()
    player_choice = st.multiselect("Player(s)", [lbl for _, lbl in player_opts], default=[])
    team_choice = st.multiselect("Team(s)", [lbl for _, lbl in team_opts], default=[])
    period_choice = st.multiselect("Period", [1, 2, 3, 4, 5, 6], default=[])
    action_types = q(
        "SELECT DISTINCT action_type FROM fact_play_by_play "
        "WHERE action_type IS NOT NULL ORDER BY action_type"
    )
    action_choice = st.multiselect("Action type", action_types["action_type"].tolist(), default=[])
    desc_filter = st.text_input("Description contains")
    row_limit = st.slider("Max rows", 1000, 100000, 5000, step=1000)

# Build SQL
where = ["1=1"]
params: list = []

if season_range:
    where.append(f"g.season_year IN ({','.join(['?'] * len(season_range))})")
    params.extend(season_range)
if player_choice:
    pid_map = {lbl: pid for pid, lbl in player_opts}
    pids = [pid_map[lbl] for lbl in player_choice]
    where.append(f"pbp.person_id IN ({','.join(['?'] * len(pids))})")
    params.extend(pids)
if team_choice:
    tid_map = {lbl: tid for tid, lbl in team_opts}
    tids = [tid_map[lbl] for lbl in team_choice]
    where.append(f"pbp.team_id IN ({','.join(['?'] * len(tids))})")
    params.extend(tids)
if period_choice:
    where.append(f"pbp.period IN ({','.join(['?'] * len(period_choice))})")
    params.extend(period_choice)
if action_choice:
    where.append(f"pbp.action_type IN ({','.join(['?'] * len(action_choice))})")
    params.extend(action_choice)
if desc_filter:
    where.append("pbp.description ILIKE ?")
    params.append(f"%{desc_filter}%")

sql = f"""
    SELECT pbp.game_id, pbp.action_number, pbp.period, pbp.clock,
           pbp.team_tri_code, pbp.player_name, pbp.action_type, pbp.subtype,
           pbp.description, pbp.score_home, pbp.score_away, pbp.shot_result,
           pbp.shot_distance, pbp.game_date
    FROM fact_play_by_play pbp
    LEFT JOIN fact_game g USING (game_id)
    WHERE {" AND ".join(where)}
    ORDER BY pbp.game_date DESC, pbp.game_id, pbp.action_number
    LIMIT {row_limit}
"""

with st.spinner("Querying..."):
    df = q(sql, params=tuple(params))

st.caption(f"Showing **{len(df):,}** rows (limit {row_limit:,}).")

if df.empty:
    st.info("No events match these filters.")
    st.stop()

# Action-type histogram
left, right = st.columns([1, 2])
with left:
    st.subheader("Action distribution")
    counts = df["action_type"].value_counts().reset_index()
    counts.columns = ["action_type", "n"]
    fig = px.bar(counts.head(15), x="n", y="action_type", orientation="h", labels={"n": "Count"})
    fig.update_layout(height=400, margin={"l": 20, "r": 20, "t": 20, "b": 20})
    st.plotly_chart(fig, use_container_width=True)

with right:
    st.subheader("Events")
    gb = GridOptionsBuilder.from_dataframe(df)
    gb.configure_default_column(filter=True, sortable=True, resizable=True)
    gb.configure_pagination(paginationPageSize=50)
    AgGrid(df, gridOptions=gb.build(), height=400, fit_columns_on_grid_load=False)

# Export
st.download_button(
    "Download as CSV",
    df.to_csv(index=False).encode("utf-8"),
    file_name="pbp_filtered.csv",
    mime="text/csv",
)
