"""Team Profile — full deep dive on one team across selected season(s)."""

from __future__ import annotations

import plotly.express as px
import streamlit as st

from lib.db import q
from lib.filters import season_picker, team_picker
from lib.kpis import fmt_float, fmt_int, fmt_pct

st.title("🏀 Team Profile")

with st.sidebar:
    st.header("Filters")
    team_id = team_picker(default_abbrev="LAL", key="team_profile_team")
    season = season_picker(key="team_profile_season")

if team_id is None or season is None:
    st.info("Pick a team and season in the sidebar.")
    st.stop()

# ─── Header
team = q("SELECT * FROM v_team_current WHERE team_id = ?", params=(team_id,))
if team.empty:
    st.warning("Team not found.")
    st.stop()
t = team.iloc[0]
st.subheader(f"{t.team_city} {t.team_name} ({t.team_abbrev}) — {season}")
c1, c2, c3 = st.columns(3)
c1.metric("League", t.league or "NBA")
c2.metric("Founded", fmt_int(t.season_founded))
c3.metric("Active until", fmt_int(t.season_active_till) if t.season_active_till else "current")

# ─── Season totals
totals = q(
    """
    SELECT
        COUNT(*) AS games,
        SUM(is_win::INT) AS wins,
        AVG(pts) AS ppg,
        AVG(off_rating) AS off_rtg,
        AVG(def_rating) AS def_rtg,
        AVG(net_rating) AS net_rtg,
        AVG(pace) AS pace,
        AVG(efg_pct) AS efg,
        AVG(tm_tov_pct) AS tov_pct,
        AVG(oreb_pct) AS oreb_pct,
        AVG(fta_rate) AS fta_rate
    FROM fact_team_game_stats tgs
    JOIN fact_game g USING (game_id)
    WHERE tgs.team_id = ? AND g.season_year = ?
    """,
    params=(team_id, season),
)
if totals.empty or totals.iloc[0].games == 0:
    st.warning("No games for this team-season combination.")
    st.stop()
r = totals.iloc[0]

st.divider()
st.subheader("Season totals (Four Factors highlighted)")
c = st.columns(6)
c[0].metric("Games", fmt_int(r.games))
c[1].metric("W–L", f"{int(r.wins or 0)}–{int(r.games - (r.wins or 0))}")
c[2].metric("PPG", fmt_float(r.ppg, 1))
c[3].metric("Off Rtg", fmt_float(r.off_rtg, 1))
c[4].metric("Def Rtg", fmt_float(r.def_rtg, 1))
c[5].metric("Net Rtg", fmt_float(r.net_rtg, 1))
c = st.columns(5)
c[0].metric("Pace", fmt_float(r.pace, 1))
c[1].metric("eFG%", fmt_pct(r.efg))
c[2].metric("TOV%", fmt_pct(r.tov_pct))
c[3].metric("OREB%", fmt_pct(r.oreb_pct))
c[4].metric("FTA Rate", fmt_float(r.fta_rate, 2))

st.divider()

# ─── Win/loss strip by game
left, right = st.columns(2)

with left:
    st.subheader("Win/loss timeline")
    df = q(
        """
        SELECT g.game_date, tgs.is_win, tgs.pts, tgs.plus_minus, g.game_id
        FROM fact_team_game_stats tgs
        JOIN fact_game g USING (game_id)
        WHERE tgs.team_id = ? AND g.season_year = ?
        ORDER BY g.game_date
        """,
        params=(team_id, season),
    )
    if not df.empty:
        df["result"] = df["is_win"].map({True: "W", False: "L"})
        fig = px.bar(
            df,
            x="game_date",
            y="plus_minus",
            color="result",
            color_discrete_map={"W": "#2E7D32", "L": "#C62828"},
            labels={"plus_minus": "+/-", "game_date": "Date"},
        )
        fig.update_layout(height=320, margin={"l": 20, "r": 20, "t": 20, "b": 20})
        st.plotly_chart(fig, use_container_width=True)

with right:
    st.subheader("Quarter scoring profile (avg pts/quarter)")
    df = q(
        """
        SELECT period, AVG(pts) AS avg_pts
        FROM fact_team_game_period p
        JOIN fact_game g USING (game_id)
        WHERE p.team_id = ? AND g.season_year = ?
              AND period BETWEEN 1 AND 4
        GROUP BY period ORDER BY period
        """,
        params=(team_id, season),
    )
    if not df.empty:
        fig = px.bar(
            df,
            x="period",
            y="avg_pts",
            labels={"period": "Quarter", "avg_pts": "Avg pts"},
            text_auto=".1f",
        )
        fig.update_traces(marker_color="#C9082A")
        fig.update_layout(height=320, margin={"l": 20, "r": 20, "t": 20, "b": 20})
        st.plotly_chart(fig, use_container_width=True)

st.divider()

# ─── Roster contributions (treemap)
st.subheader("Roster contributions (points)")
roster = q(
    """
    SELECT p.first_name || ' ' || p.last_name AS player,
           SUM(pgs.points) AS pts,
           SUM(pgs.num_minutes) AS min,
           COUNT(*) AS gp
    FROM fact_player_game_stats pgs
    JOIN dim_player p USING (person_id)
    JOIN fact_game g USING (game_id)
    WHERE pgs.team_id = ? AND g.season_year = ?
    GROUP BY player
    HAVING SUM(pgs.points) > 0
    ORDER BY pts DESC
    """,
    params=(team_id, season),
)
if not roster.empty:
    fig = px.treemap(
        roster,
        path=["player"],
        values="pts",
        hover_data=["min", "gp"],
        color="pts",
        color_continuous_scale="Reds",
    )
    fig.update_layout(height=420, margin={"l": 10, "r": 10, "t": 10, "b": 10})
    st.plotly_chart(fig, use_container_width=True)

st.divider()

# ─── Game log
st.subheader("Game log")
game_log = q(
    """
    SELECT g.game_date AS date, g.game_id,
           CASE WHEN tgs.is_home THEN 'vs' ELSE '@' END AS loc,
           CASE WHEN tgs.is_home THEN g.away_team_id ELSE g.home_team_id END AS opp_id,
           CASE WHEN tgs.is_win THEN 'W' ELSE 'L' END AS result,
           tgs.pts, tgs.plus_minus,
           tgs.fgm, tgs.fga, tgs.fg_pct,
           tgs.fg3m, tgs.fg3a, tgs.ast, tgs.reb, tgs.tov
    FROM fact_team_game_stats tgs
    JOIN fact_game g USING (game_id)
    WHERE tgs.team_id = ? AND g.season_year = ?
    ORDER BY g.game_date DESC
    """,
    params=(team_id, season),
)
st.dataframe(game_log, use_container_width=True, hide_index=True)
