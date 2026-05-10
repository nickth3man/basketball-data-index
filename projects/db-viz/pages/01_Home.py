"""Home / League Pulse — at-a-glance KPIs and trends."""

from __future__ import annotations

import datetime as _dt

import plotly.express as px
import streamlit as st

from lib.db import q
from lib.kpis import fmt_human, fmt_int

st.title("🏠 League Pulse")
st.caption("At-a-glance metrics across all of NBA history.")

# ─────────────────────────────── KPI strip
k = q("""
    SELECT
        (SELECT COUNT(*) FROM fact_game)               AS games,
        (SELECT COUNT(*) FROM dim_player)              AS players,
        (SELECT COUNT(*) FROM dim_team)                AS franchises,
        (SELECT COUNT(*) FROM fact_play_by_play)       AS pbp_events,
        (SELECT MAX(game_date) FROM fact_game)         AS latest_game,
        (SELECT season_year FROM fact_game
         ORDER BY game_date DESC LIMIT 1)              AS current_season
""").iloc[0]

c1, c2, c3, c4, c5, c6 = st.columns(6)
c1.metric("Games", fmt_int(k.games))
c2.metric("Players", fmt_int(k.players))
c3.metric("Franchises", fmt_int(k.franchises))
c4.metric("PBP events", fmt_human(k.pbp_events))
c5.metric("Latest game", str(k.latest_game) if k.latest_game else "—")
c6.metric("Current season", str(k.current_season) if k.current_season else "—")

st.divider()

# ─────────────────────────────── Scoring trend
left, right = st.columns(2)

with left:
    st.subheader("Average team PPG by season")
    df = q("""
        SELECT g.season_year,
               AVG(tgs.pts)::DOUBLE AS ppg,
               COUNT(*) AS team_games
        FROM fact_team_game_stats tgs
        JOIN fact_game g USING (game_id)
        WHERE g.season_year IS NOT NULL AND g.season_type='Regular'
        GROUP BY g.season_year
        HAVING COUNT(*) > 100
        ORDER BY g.season_year
    """)
    fig = px.line(
        df, x="season_year", y="ppg", markers=True, labels={"season_year": "Season", "ppg": "PPG"}
    )
    fig.update_layout(height=350, margin={"l": 20, "r": 20, "t": 20, "b": 20})
    st.plotly_chart(fig, use_container_width=True)

with right:
    st.subheader("3-point attempts per team-game")
    df = q("""
        SELECT g.season_year,
               AVG(tgs.fg3a)::DOUBLE AS fg3a_per_game
        FROM fact_team_game_stats tgs
        JOIN fact_game g USING (game_id)
        WHERE g.season_year IS NOT NULL AND g.season_type='Regular'
          AND tgs.fg3a IS NOT NULL
        GROUP BY g.season_year
        HAVING COUNT(*) > 100
        ORDER BY g.season_year
    """)
    fig = px.area(
        df,
        x="season_year",
        y="fg3a_per_game",
        labels={"season_year": "Season", "fg3a_per_game": "3PA / game"},
    )
    fig.update_traces(line_color="#C9082A", fillcolor="rgba(201,8,42,0.3)")
    fig.update_layout(height=350, margin={"l": 20, "r": 20, "t": 20, "b": 20})
    st.plotly_chart(fig, use_container_width=True)

st.divider()

# ─────────────────────────────── Pace × OffRtg scatter
st.subheader("Pace × Offensive rating (team-season)")
df = q("""
    SELECT g.season_year,
           tgs.team_id,
           v.team_city || ' ' || v.team_name AS team,
           AVG(tgs.pace) AS pace,
           AVG(tgs.off_rating) AS off_rating
    FROM fact_team_game_stats tgs
    JOIN fact_game g USING (game_id)
    LEFT JOIN v_team_current v USING (team_id)
    WHERE g.season_type='Regular' AND g.season_year IS NOT NULL
      AND tgs.pace IS NOT NULL AND tgs.off_rating IS NOT NULL
    GROUP BY g.season_year, tgs.team_id, team
    HAVING COUNT(*) >= 30
""")
if not df.empty:
    fig = px.scatter(
        df,
        x="pace",
        y="off_rating",
        color="season_year",
        hover_data=["team"],
        opacity=0.65,
        labels={"pace": "Pace (poss/48)", "off_rating": "Off Rating", "season_year": "Season"},
    )
    fig.update_layout(height=420, margin={"l": 20, "r": 20, "t": 20, "b": 20})
    st.plotly_chart(fig, use_container_width=True)

st.divider()

# ─────────────────────────────── Today / next slate + on-this-day
left, right = st.columns(2)

with left:
    st.subheader("Upcoming games (next 14 days)")
    upcoming = q("""
        SELECT game_id, game_datetime_est, season_year,
               home_team_id, away_team_id, arena_name, game_label
        FROM fact_scheduled_game
        WHERE game_datetime_est >= now() - INTERVAL 1 DAY
        ORDER BY game_datetime_est
        LIMIT 25
    """)
    if upcoming.empty:
        st.info("No upcoming games found in `fact_scheduled_game`.")
    else:
        st.dataframe(upcoming, use_container_width=True, hide_index=True)

with right:
    st.subheader("On this day in NBA history")
    today_md = _dt.date.today()
    on_this_day = q(
        """
        SELECT game_date, home_team_id, away_team_id, home_score, away_score, season_year, game_type
        FROM fact_game
        WHERE month(game_date) = ? AND day(game_date) = ?
              AND home_score IS NOT NULL
        ORDER BY game_date DESC
        LIMIT 15
    """,
        params=(today_md.month, today_md.day),
    )
    if on_this_day.empty:
        st.info("No historical games on this calendar day.")
    else:
        st.dataframe(on_this_day, use_container_width=True, hide_index=True)
