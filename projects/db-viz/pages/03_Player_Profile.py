"""Player Profile — full career view including bio, trajectory, shot chart."""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from lib.court import shot_chart_figure, to_court_ft
from lib.db import q
from lib.filters import player_picker
from lib.kpis import fmt_float, fmt_int, fmt_pct


def _na(v, default="—"):
    """NA-safe display."""
    return default if v is None or pd.isna(v) else v


st.title("👤 Player Profile")

with st.sidebar:
    st.header("Filter")
    person_id = player_picker(default_name="LeBron James", key="player_profile")

if person_id is None:
    st.stop()

# ─── Bio
bio = q("SELECT * FROM dim_player WHERE person_id = ?", params=(person_id,))
if bio.empty:
    st.error("Player not found.")
    st.stop()
b = bio.iloc[0]
first = "" if pd.isna(b.first_name) else str(b.first_name)
last = "" if pd.isna(b.last_name) else str(b.last_name)
name = f"{first} {last}".strip() or "(unknown)"
st.subheader(name)

c = st.columns(6)
c[0].metric("Born", str(b.birth_date) if not pd.isna(b.birth_date) else "—")
c[1].metric("Country", _na(b.country))
c[2].metric("Height (in)", fmt_int(b.height_inches) if not pd.isna(b.height_inches) else "—")
c[3].metric("Weight (lbs)", fmt_int(b.body_weight_lbs) if not pd.isna(b.body_weight_lbs) else "—")
draft_str = "Undrafted"
if not pd.isna(b.draft_year):
    rd = int(b.draft_round) if not pd.isna(b.draft_round) else "?"
    pk = int(b.draft_number) if not pd.isna(b.draft_number) else "?"
    draft_str = f"{int(b.draft_year)} R{rd} #{pk}"
c[4].metric("Draft", draft_str)
years_str = "—"
if not pd.isna(b.from_year) and not pd.isna(b.to_year):
    years_str = f"{int(b.from_year)}-{int(b.to_year)}"
c[5].metric("Years", years_str)

pos = ""
if not pd.isna(b.is_guard) and b.is_guard:
    pos += "G"
if not pd.isna(b.is_forward) and b.is_forward:
    pos += "F"
if not pd.isna(b.is_center) and b.is_center:
    pos += "C"
st.caption(f"School: {_na(b.school)}  |  Jersey: {_na(b.jersey)}  |  Pos: {pos or '—'}")

st.divider()

# ─── Career trajectory
left, right = st.columns(2)
career = q(
    """
    SELECT g.season_year,
           COUNT(*) AS gp,
           SUM(pgs.points) AS pts,
           AVG(pgs.points) AS ppg,
           AVG(pgs.reb) AS rpg,
           AVG(pgs.assists) AS apg,
           AVG(pgs.num_minutes) AS mpg,
           AVG(pgs.fg_pct) AS fg_pct,
           AVG(pgs.fg3_pct) AS fg3_pct,
           AVG(pgs.ft_pct) AS ft_pct
    FROM fact_player_game_stats pgs
    JOIN fact_game g USING (game_id)
    WHERE pgs.person_id = ? AND g.season_year IS NOT NULL
    GROUP BY g.season_year
    HAVING COUNT(*) > 0
    ORDER BY g.season_year
    """,
    params=(person_id,),
)

with left:
    st.subheader("Career trajectory (per game)")
    if not career.empty:
        df_long = career.melt(
            id_vars=["season_year"],
            value_vars=["ppg", "rpg", "apg", "mpg"],
            var_name="stat",
            value_name="value",
        )
        fig = px.line(
            df_long,
            x="season_year",
            y="value",
            color="stat",
            markers=True,
            labels={"season_year": "Season", "value": "Per-game"},
        )
        fig.update_layout(height=380, margin={"l": 20, "r": 20, "t": 20, "b": 20})
        st.plotly_chart(fig, use_container_width=True)

with right:
    st.subheader("Shooting splits (%)")
    if not career.empty:
        df_long = career.melt(
            id_vars=["season_year"],
            value_vars=["fg_pct", "fg3_pct", "ft_pct"],
            var_name="stat",
            value_name="pct",
        )
        fig = px.line(
            df_long,
            x="season_year",
            y="pct",
            color="stat",
            markers=True,
            labels={"season_year": "Season", "pct": "%"},
        )
        fig.update_layout(
            height=380, margin={"l": 20, "r": 20, "t": 20, "b": 20}, yaxis_tickformat=".0%"
        )
        st.plotly_chart(fig, use_container_width=True)

st.divider()

# ─── Career totals card
totals = q(
    """
    SELECT COUNT(*) AS gp, SUM(points) AS pts, SUM(reb) AS reb, SUM(assists) AS ast,
           SUM(steals) AS stl, SUM(blocks) AS blk
    FROM fact_player_game_stats WHERE person_id = ?
    """,
    params=(person_id,),
)
t = totals.iloc[0]
c = st.columns(6)
c[0].metric("Career GP", fmt_int(t.gp))
c[1].metric("Career PTS", fmt_int(t.pts))
c[2].metric("Career REB", fmt_int(t.reb))
c[3].metric("Career AST", fmt_int(t.ast))
c[4].metric("Career STL", fmt_int(t.stl))
c[5].metric("Career BLK", fmt_int(t.blk))

st.divider()

# ─── Best games leaderboard
st.subheader("Top 10 games by points")
top = q(
    """
    SELECT g.game_date, g.game_id, pgs.points AS pts,
           pgs.reb, pgs.assists AS ast, pgs.fgm, pgs.fga,
           pgs.fg3m, pgs.fg3a, pgs.plus_minus
    FROM fact_player_game_stats pgs
    JOIN fact_game g USING (game_id)
    WHERE pgs.person_id = ?
    ORDER BY pgs.points DESC NULLS LAST LIMIT 10
    """,
    params=(person_id,),
)
st.dataframe(top, use_container_width=True, hide_index=True)

st.divider()

# ─── Career shot chart
st.subheader("Career shot chart")
mode = st.radio("Mode", ["scatter", "hexbin", "heatmap_fg"], horizontal=True, key="shot_mode")

shots = q(
    """
    SELECT x_legacy, y_legacy, shot_result, shot_value
    FROM fact_play_by_play
    WHERE person_id = ? AND is_field_goal = TRUE
          AND x_legacy IS NOT NULL AND y_legacy IS NOT NULL
          AND ABS(x_legacy) < 300 AND y_legacy BETWEEN -50 AND 470
    """,
    params=(person_id,),
)
if shots.empty:
    st.info("No shot-coordinate data for this player.")
else:
    shots["is_made"] = shots["shot_result"] == "Made"
    shots = to_court_ft(shots)
    fig = shot_chart_figure(shots, mode=mode, title=f"{name}: {len(shots):,} FGAs")
    st.pyplot(fig, clear_figure=True, use_container_width=False)

    pct_made = shots["is_made"].mean()
    c = st.columns(4)
    c[0].metric("Total FGA", fmt_int(len(shots)))
    c[1].metric("Total FGM", fmt_int(shots["is_made"].sum()))
    c[2].metric("FG%", fmt_pct(pct_made))
    c[3].metric(
        "Avg distance", fmt_float(shots["court_x"].apply(lambda x: 41.75 - x).mean(), 1) + " ft"
    )
