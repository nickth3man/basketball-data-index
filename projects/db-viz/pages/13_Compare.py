"""Compare — head-to-head player or team."""

from __future__ import annotations

import streamlit as st

from lib.db import q
from lib.filters import player_picker, season_picker, team_picker
from lib.viz import radar

st.title("⚖️ Compare")

mode = st.radio("Mode", ["Player vs Player", "Team vs Team"], horizontal=True)

if mode == "Player vs Player":
    c1, c2 = st.columns(2)
    with c1:
        p1 = player_picker(label="Player A", default_name="LeBron James", key="cmp_p1")
    with c2:
        p2 = player_picker(label="Player B", default_name="Stephen Curry", key="cmp_p2")
    if p1 is None or p2 is None:
        st.stop()

    sql = """
        SELECT person_id,
               AVG(points) AS ppg, AVG(reb) AS rpg, AVG(assists) AS apg,
               AVG(steals) AS spg, AVG(blocks) AS bpg,
               AVG(fg_pct) AS fg_pct, AVG(fg3_pct) AS fg3_pct,
               AVG(ft_pct) AS ft_pct, AVG(num_minutes) AS mpg,
               COUNT(*) AS gp, SUM(points) AS tot_pts
        FROM fact_player_game_stats
        WHERE person_id = ? GROUP BY person_id
    """
    a = q(sql, params=(p1,))
    b = q(sql, params=(p2,))
    if a.empty or b.empty:
        st.warning("No stats for one of the players.")
        st.stop()
    a, b = a.iloc[0], b.iloc[0]

    name_a = (
        q(
            "SELECT first_name || ' ' || last_name AS n FROM dim_player WHERE person_id = ?",
            params=(p1,),
        )
        .iloc[0]
        .n
    )
    name_b = (
        q(
            "SELECT first_name || ' ' || last_name AS n FROM dim_player WHERE person_id = ?",
            params=(p2,),
        )
        .iloc[0]
        .n
    )

    st.subheader("Career averages")
    cats = ["PPG", "RPG", "APG", "SPG", "BPG", "MPG"]
    vals_a = [
        float(a.ppg or 0),
        float(a.rpg or 0),
        float(a.apg or 0),
        float(a.spg or 0),
        float(a.bpg or 0),
        float(a.mpg or 0),
    ]
    vals_b = [
        float(b.ppg or 0),
        float(b.rpg or 0),
        float(b.apg or 0),
        float(b.spg or 0),
        float(b.bpg or 0),
        float(b.mpg or 0),
    ]
    fig = radar(cats, vals_a, name_a, vals_b, name_b)
    st.plotly_chart(fig, use_container_width=True)

    cmp = q(
        """
        SELECT p.first_name || ' ' || p.last_name AS player,
               COUNT(*) AS gp, SUM(pgs.points) AS career_pts,
               AVG(pgs.points) AS ppg, AVG(pgs.reb) AS rpg, AVG(pgs.assists) AS apg,
               AVG(pgs.fg_pct) AS fg_pct, AVG(pgs.fg3_pct) AS fg3_pct,
               AVG(pgs.ft_pct) AS ft_pct
        FROM fact_player_game_stats pgs JOIN dim_player p USING (person_id)
        WHERE p.person_id IN (?, ?)
        GROUP BY player
        """,
        params=(p1, p2),
    )
    st.dataframe(cmp, hide_index=True, use_container_width=True)

else:  # Team vs Team
    c1, c2, c3 = st.columns(3)
    with c1:
        t1 = team_picker(label="Team A", default_abbrev="LAL", key="cmp_t1")
    with c2:
        t2 = team_picker(label="Team B", default_abbrev="BOS", key="cmp_t2")
    with c3:
        season = season_picker(key="cmp_season")

    if not (t1 and t2 and season):
        st.stop()

    sql = """
        SELECT AVG(pts) AS ppg, AVG(off_rating) AS off_rtg, AVG(def_rating) AS def_rtg,
               AVG(net_rating) AS net_rtg, AVG(pace) AS pace, AVG(efg_pct) AS efg,
               AVG(tm_tov_pct) AS tov_pct, AVG(oreb_pct) AS oreb_pct,
               AVG(fta_rate) AS fta_rate
        FROM fact_team_game_stats tgs JOIN fact_game g USING (game_id)
        WHERE tgs.team_id = ? AND g.season_year = ?
    """
    a = q(sql, params=(t1, season))
    b = q(sql, params=(t2, season))
    if a.empty or b.empty:
        st.warning("No stats.")
        st.stop()
    a, b = a.iloc[0], b.iloc[0]

    name_a = (
        q(
            "SELECT team_city || ' ' || team_name AS n FROM v_team_current WHERE team_id = ?",
            params=(t1,),
        )
        .iloc[0]
        .n
    )
    name_b = (
        q(
            "SELECT team_city || ' ' || team_name AS n FROM v_team_current WHERE team_id = ?",
            params=(t2,),
        )
        .iloc[0]
        .n
    )

    st.subheader(f"{name_a} vs {name_b} — {season}")
    cats = ["PPG", "OffRtg", "Pace", "eFG%", "OREB%", "FTRate"]
    vals_a = [
        float(a.ppg or 0),
        float(a.off_rtg or 0),
        float(a.pace or 0),
        float((a.efg or 0) * 100),
        float((a.oreb_pct or 0) * 100),
        float(a.fta_rate or 0) * 100,
    ]
    vals_b = [
        float(b.ppg or 0),
        float(b.off_rtg or 0),
        float(b.pace or 0),
        float((b.efg or 0) * 100),
        float((b.oreb_pct or 0) * 100),
        float(b.fta_rate or 0) * 100,
    ]
    fig = radar(cats, vals_a, name_a, vals_b, name_b)
    st.plotly_chart(fig, use_container_width=True)
