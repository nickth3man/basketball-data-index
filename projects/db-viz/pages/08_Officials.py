"""Officials — surface fact_game_official."""

from __future__ import annotations

import plotly.express as px
import streamlit as st

from lib.db import q

st.title("🦓 Officials")
st.caption("4,147 game-official assignments from `fact_game_official`.")

# Top officials by games
st.subheader("Top officials by games worked")
top = q(
    """
    SELECT official_name, COUNT(*) AS games
    FROM fact_game_official
    GROUP BY official_name
    ORDER BY games DESC LIMIT 25
    """
)
fig = px.bar(top, x="games", y="official_name", orientation="h")
fig.update_layout(
    height=600,
    yaxis={"categoryorder": "total ascending"},
    margin={"l": 20, "r": 20, "t": 20, "b": 20},
)
st.plotly_chart(fig, use_container_width=True)

st.divider()

# Avg pace / fouls per official
st.subheader("Officials by avg pace / fouls")
df = q(
    """
    SELECT o.official_name,
           AVG(tgs.pace) AS avg_pace,
           AVG(tgs.pf) AS avg_pf,
           COUNT(DISTINCT o.game_id) AS games
    FROM fact_game_official o
    JOIN fact_team_game_stats tgs USING (game_id)
    WHERE tgs.pace IS NOT NULL
    GROUP BY o.official_name
    HAVING COUNT(DISTINCT o.game_id) >= 25
    ORDER BY games DESC
    """
)
if not df.empty:
    fig = px.scatter(
        df,
        x="avg_pace",
        y="avg_pf",
        size="games",
        hover_data=["official_name"],
        opacity=0.7,
        labels={"avg_pace": "Avg pace (poss/48)", "avg_pf": "Avg fouls / team"},
    )
    fig.update_layout(height=480, margin={"l": 20, "r": 20, "t": 20, "b": 20})
    st.plotly_chart(fig, use_container_width=True)

st.divider()

# Crew chemistry — most common 3-ref combos
st.subheader("Most common 3-ref crews")
crews = q(
    """
    WITH crew AS (
        SELECT game_id,
               STRING_AGG(official_name, ' / ' ORDER BY official_name) AS crew_str,
               COUNT(*) AS n_refs
        FROM fact_game_official
        GROUP BY game_id
        HAVING COUNT(*) = 3
    )
    SELECT crew_str, COUNT(*) AS games
    FROM crew GROUP BY crew_str
    ORDER BY games DESC LIMIT 15
    """
)
st.dataframe(crews, hide_index=True, use_container_width=True)
