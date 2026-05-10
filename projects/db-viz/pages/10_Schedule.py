"""Schedule — fact_scheduled_game + historical density."""

from __future__ import annotations

import plotly.express as px
import streamlit as st

from lib.db import q
from lib.filters import season_picker

st.title("📅 Schedule")

st.subheader("Upcoming games")
upc = q(
    """
    SELECT s.game_id, s.game_datetime_est, s.season_year,
           s.home_team_id, s.away_team_id,
           s.arena_name, s.arena_city, s.game_label, s.game_sub_label
    FROM fact_scheduled_game s
    WHERE s.game_datetime_est >= now() - INTERVAL 1 DAY
    ORDER BY s.game_datetime_est LIMIT 100
    """
)
if upc.empty:
    st.info("No upcoming games in `fact_scheduled_game`.")
else:
    st.dataframe(upc, hide_index=True, use_container_width=True)

st.divider()

# Historical density: games per team per week of season
st.subheader("Schedule density heatmap")
season = season_picker(key="sched_season")
if season:
    df = q(
        """
        SELECT v.team_abbrev AS team,
               WEEK(g.game_date) AS week_no,
               COUNT(*) AS games
        FROM fact_game g
        JOIN fact_team_game_stats tgs USING (game_id)
        JOIN v_team_current v ON v.team_id = tgs.team_id
        WHERE g.season_year = ? AND g.season_type='Regular'
        GROUP BY team, week_no
        """,
        params=(season,),
    )
    if not df.empty:
        pv = df.pivot(index="team", columns="week_no", values="games").fillna(0)
        fig = px.imshow(
            pv,
            color_continuous_scale="Reds",
            aspect="auto",
            labels={"x": "Week of year", "y": "Team", "color": "Games"},
        )
        fig.update_layout(height=700, margin={"l": 20, "r": 20, "t": 20, "b": 20})
        st.plotly_chart(fig, use_container_width=True)

st.divider()

# Back-to-back finder
st.subheader("Back-to-back games (consecutive days)")
if season:
    b2b = q(
        """
        WITH game_days AS (
            SELECT tgs.team_id, g.game_date, g.game_id
            FROM fact_team_game_stats tgs
            JOIN fact_game g USING (game_id)
            WHERE g.season_year = ? AND g.season_type='Regular'
        ),
        marked AS (
            SELECT *,
                   LAG(game_date) OVER (PARTITION BY team_id ORDER BY game_date) AS prev_date
            FROM game_days
        )
        SELECT v.team_abbrev AS team, COUNT(*) AS b2b_count
        FROM marked m
        JOIN v_team_current v ON v.team_id = m.team_id
        WHERE prev_date IS NOT NULL
              AND date_diff('day', prev_date, game_date) = 1
        GROUP BY team ORDER BY b2b_count DESC
        """,
        params=(season,),
    )
    if not b2b.empty:
        fig = px.bar(b2b, x="b2b_count", y="team", orientation="h")
        fig.update_layout(
            height=700,
            yaxis={"categoryorder": "total ascending"},
            margin={"l": 20, "r": 20, "t": 20, "b": 20},
        )
        st.plotly_chart(fig, use_container_width=True)
