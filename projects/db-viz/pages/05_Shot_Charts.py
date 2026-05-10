"""Shot Charts — slice the 17M PBP rows by shot location."""

from __future__ import annotations

import plotly.express as px
import streamlit as st

from lib.court import shot_chart_figure, to_court_ft
from lib.db import q
from lib.filters import _player_options, _team_options, season_picker
from lib.kpis import fmt_int, fmt_pct

st.title("🗺️ Shot Charts")
st.caption("Filter the 17M-row play-by-play table to a custom shot population.")

with st.sidebar:
    st.header("Filters")
    # Player & team multi-selects (None = league-wide)
    player_opts = _player_options()
    team_opts = _team_options()
    player_choice = st.multiselect(
        "Player(s)",
        [lbl for _, lbl in player_opts],
        default=[],
        help="Leave empty for league-wide",
    )
    team_choice = st.multiselect(
        "Team(s)",
        [lbl for _, lbl in team_opts],
        default=[],
        help="Leave empty for league-wide",
    )
    season_range = season_picker(multi=True, key="sc_season")
    period_choice = st.multiselect("Period", [1, 2, 3, 4, 5, 6], default=[])
    shot_value = st.radio("Shot value", ["All", "2pt only", "3pt only"], horizontal=True)
    mode = st.selectbox("Display mode", ["hexbin", "scatter", "heatmap_fg", "heatmap_pps"])

# ─── Build dynamic SQL
where = [
    "pbp.is_field_goal = TRUE",
    "pbp.x_legacy IS NOT NULL",
    "pbp.y_legacy IS NOT NULL",
    "ABS(pbp.x_legacy) < 300",
    "pbp.y_legacy BETWEEN -50 AND 470",
]
params: list = []

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

if season_range:
    where.append(f"g.season_year IN ({','.join(['?'] * len(season_range))})")
    params.extend(season_range)

if period_choice:
    where.append(f"pbp.period IN ({','.join(['?'] * len(period_choice))})")
    params.extend(period_choice)

if shot_value == "2pt only":
    where.append("pbp.shot_value = 2")
elif shot_value == "3pt only":
    where.append("pbp.shot_value = 3")

sql = f"""
    SELECT pbp.x_legacy, pbp.y_legacy, pbp.shot_result, pbp.shot_value,
           pbp.shot_distance
    FROM fact_play_by_play pbp
    LEFT JOIN fact_game g USING (game_id)
    WHERE {" AND ".join(where)}
    LIMIT 200000
"""

with st.spinner("Querying PBP..."):
    shots = q(sql, params=tuple(params))

if shots.empty:
    st.warning("No shots match these filters.")
    st.stop()

shots["is_made"] = shots["shot_result"] == "Made"
shots = to_court_ft(shots)

# ─── Render
left, right = st.columns([2, 1])
with left:
    fig = shot_chart_figure(shots, mode=mode, title=f"{len(shots):,} shots")
    st.pyplot(fig, clear_figure=True, use_container_width=False)

with right:
    st.subheader("Summary")
    n = len(shots)
    made = shots["is_made"].sum()
    pts = (shots["is_made"].astype(int) * shots["shot_value"].fillna(2).astype(int)).sum()
    st.metric("Total FGA", fmt_int(n))
    st.metric("FGM", fmt_int(made))
    st.metric("FG%", fmt_pct(made / n if n else 0))
    st.metric("Total points", fmt_int(pts))
    st.metric("PPS (points per shot)", f"{pts / n:.2f}" if n else "—")

st.divider()

# ─── Distance histogram
st.subheader("Shot distance distribution")
dist = shots[shots["shot_distance"].notna()]
if not dist.empty:
    fig = px.histogram(
        dist,
        x="shot_distance",
        nbins=40,
        color="shot_result",
        labels={"shot_distance": "Distance (ft)"},
    )
    fig.add_vline(x=22, line_dash="dot", line_color="orange", annotation_text="3pt corner")
    fig.add_vline(x=23.75, line_dash="dot", line_color="red", annotation_text="3pt arc")
    fig.update_layout(height=320, margin={"l": 20, "r": 20, "t": 20, "b": 20})
    st.plotly_chart(fig, use_container_width=True)

# ─── Zone breakdown
st.subheader("Zone breakdown")


def zone(row):
    d = row.shot_distance if row.shot_distance is not None else 0
    v = row.shot_value if row.shot_value else 2
    if v == 3:
        return "3pt"
    if d < 5:
        return "Restricted area"
    if d < 16:
        return "Mid-range (short)"
    return "Mid-range (long 2)"


shots["zone"] = shots.apply(zone, axis=1)
zsum = (
    shots.groupby("zone")
    .agg(
        fga=("is_made", "size"),
        fgm=("is_made", "sum"),
    )
    .reset_index()
)
zsum["fg_pct"] = (zsum["fgm"] / zsum["fga"]).round(3)
zsum["share_of_fga"] = (zsum["fga"] / zsum["fga"].sum()).round(3)
st.dataframe(zsum, use_container_width=True, hide_index=True)
