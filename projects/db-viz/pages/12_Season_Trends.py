"""Season Trends — league-level evolution over 30 years."""

from __future__ import annotations

import plotly.express as px
import streamlit as st

from lib.db import q

st.title("📈 Season Trends")

# Pace
st.subheader("Pace evolution")
pace = q(
    """
    SELECT g.season_year, AVG(tgs.pace) AS pace
    FROM fact_team_game_stats tgs JOIN fact_game g USING (game_id)
    WHERE g.season_type='Regular' AND tgs.pace IS NOT NULL
    GROUP BY g.season_year HAVING COUNT(*) > 100 ORDER BY g.season_year
    """
)
fig = px.line(pace, x="season_year", y="pace", markers=True)
fig.update_layout(height=320, margin={"l": 20, "r": 20, "t": 20, "b": 20})
st.plotly_chart(fig, use_container_width=True)

st.divider()

# 3PT revolution
st.subheader("Shot diet — %FGA from 2pt vs 3pt")
diet = q(
    """
    SELECT g.season_year,
           AVG(tgs.pct_fga_2pt) AS pct_fga_2pt,
           AVG(tgs.pct_fga_3pt) AS pct_fga_3pt
    FROM fact_team_game_stats tgs JOIN fact_game g USING (game_id)
    WHERE g.season_type='Regular' AND tgs.pct_fga_3pt IS NOT NULL
    GROUP BY g.season_year HAVING COUNT(*) > 100 ORDER BY g.season_year
    """
)
diet_long = diet.melt(id_vars=["season_year"], var_name="shot_type", value_name="share")
fig = px.area(
    diet_long, x="season_year", y="share", color="shot_type", labels={"share": "Share of FGA"}
)
fig.update_layout(height=360, yaxis_tickformat=".0%", margin={"l": 20, "r": 20, "t": 20, "b": 20})
st.plotly_chart(fig, use_container_width=True)

st.divider()

# Off vs Def rating
left, right = st.columns(2)
with left:
    st.subheader("League Offensive Rating")
    off = q(
        """
        SELECT g.season_year, AVG(tgs.off_rating) AS off_rtg
        FROM fact_team_game_stats tgs JOIN fact_game g USING (game_id)
        WHERE g.season_type='Regular' AND tgs.off_rating IS NOT NULL
        GROUP BY g.season_year ORDER BY g.season_year
        """
    )
    fig = px.line(off, x="season_year", y="off_rtg", markers=True)
    fig.update_layout(height=320, margin={"l": 20, "r": 20, "t": 20, "b": 20})
    st.plotly_chart(fig, use_container_width=True)

with right:
    st.subheader("League Defensive Rating")
    de = q(
        """
        SELECT g.season_year, AVG(tgs.def_rating) AS def_rtg
        FROM fact_team_game_stats tgs JOIN fact_game g USING (game_id)
        WHERE g.season_type='Regular' AND tgs.def_rating IS NOT NULL
        GROUP BY g.season_year ORDER BY g.season_year
        """
    )
    fig = px.line(de, x="season_year", y="def_rtg", markers=True)
    fig.update_traces(line_color="#17408B")
    fig.update_layout(height=320, margin={"l": 20, "r": 20, "t": 20, "b": 20})
    st.plotly_chart(fig, use_container_width=True)

st.divider()

# Iron man decline
st.subheader("Iron man decline — % of players appearing in 75+ games")
iron = q(
    """
    WITH gp AS (
        SELECT g.season_year, pgs.person_id, COUNT(*) AS games_played
        FROM fact_player_game_stats pgs JOIN fact_game g USING (game_id)
        WHERE g.season_type='Regular' AND g.season_year IS NOT NULL
        GROUP BY g.season_year, pgs.person_id
    )
    SELECT season_year,
           AVG((games_played >= 75)::INT)::DOUBLE AS pct_75plus,
           COUNT(*) AS players
    FROM gp GROUP BY season_year HAVING COUNT(*) > 100
    ORDER BY season_year
    """
)
fig = px.line(
    iron,
    x="season_year",
    y="pct_75plus",
    markers=True,
    labels={"pct_75plus": "% players with 75+ games"},
)
fig.update_layout(height=340, yaxis_tickformat=".0%", margin={"l": 20, "r": 20, "t": 20, "b": 20})
st.plotly_chart(fig, use_container_width=True)
