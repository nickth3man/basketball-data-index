"""Quarter Splits — surface fact_team_game_period."""

from __future__ import annotations

import plotly.express as px
import streamlit as st

from lib.db import q
from lib.filters import season_picker

st.title("⏱️ Quarter Splits")
st.caption("Period-by-period performance from `fact_team_game_period`.")

with st.sidebar:
    season = season_picker(key="qs_season")

if not season:
    st.stop()

# League heatmap
st.subheader(f"League quarter PPG heatmap — {season}")
df = q(
    """
    SELECT v.team_abbrev AS team, p.period, AVG(p.pts) AS avg_pts
    FROM fact_team_game_period p
    JOIN fact_game g USING (game_id)
    JOIN v_team_current v USING (team_id)
    WHERE g.season_year = ? AND p.period BETWEEN 1 AND 4
    GROUP BY team, period
    """,
    params=(season,),
)
if df.empty:
    st.info("No data for this season.")
    st.stop()

pivot = df.pivot(index="team", columns="period", values="avg_pts").round(1)
fig = px.imshow(
    pivot,
    color_continuous_scale="RdYlGn",
    aspect="auto",
    labels={"x": "Quarter", "y": "Team", "color": "Avg pts"},
    text_auto=".1f",
)
fig.update_layout(height=700, margin={"l": 20, "r": 20, "t": 20, "b": 20})
st.plotly_chart(fig, use_container_width=True)

st.divider()

# Best Q4 teams
left, right = st.columns(2)
with left:
    st.subheader("Best Q4 scoring (avg)")
    q4 = q(
        """
        SELECT v.team_city || ' ' || v.team_name AS team,
               AVG(p.pts) AS q4_ppg, COUNT(*) AS games
        FROM fact_team_game_period p
        JOIN fact_game g USING (game_id)
        JOIN v_team_current v USING (team_id)
        WHERE g.season_year = ? AND p.period = 4
        GROUP BY team HAVING COUNT(*) > 30
        ORDER BY q4_ppg DESC LIMIT 10
        """,
        params=(season,),
    )
    st.dataframe(q4, hide_index=True, use_container_width=True)

with right:
    st.subheader("Best Q1 starts (avg)")
    q1 = q(
        """
        SELECT v.team_city || ' ' || v.team_name AS team,
               AVG(p.pts) AS q1_ppg, COUNT(*) AS games
        FROM fact_team_game_period p
        JOIN fact_game g USING (game_id)
        JOIN v_team_current v USING (team_id)
        WHERE g.season_year = ? AND p.period = 1
        GROUP BY team HAVING COUNT(*) > 30
        ORDER BY q1_ppg DESC LIMIT 10
        """,
        params=(season,),
    )
    st.dataframe(q1, hide_index=True, use_container_width=True)

st.divider()

# Comeback finder
st.subheader("Comeback wins (trailed by ≥15 at half, won the game)")
comebacks = q(
    """
    WITH halves AS (
        SELECT game_id, team_id,
               SUM(CASE WHEN period IN (1,2) THEN pts ELSE 0 END) AS half_pts
        FROM fact_team_game_period WHERE period BETWEEN 1 AND 2
        GROUP BY game_id, team_id
    ),
    deficits AS (
        SELECT h1.game_id, h1.team_id,
               h1.half_pts - h2.half_pts AS half_diff
        FROM halves h1 JOIN halves h2
          ON h1.game_id = h2.game_id AND h1.team_id != h2.team_id
    )
    SELECT g.game_date, v.team_abbrev AS came_back_team,
           d.half_diff AS half_deficit,
           tgs.pts AS final_pts, tgs.is_win
    FROM deficits d
    JOIN fact_team_game_stats tgs ON tgs.game_id = d.game_id AND tgs.team_id = d.team_id
    JOIN fact_game g ON g.game_id = d.game_id
    LEFT JOIN v_team_current v ON v.team_id = d.team_id
    WHERE d.half_diff <= -15 AND tgs.is_win = TRUE
          AND g.season_year = ?
    ORDER BY d.half_diff
    LIMIT 25
    """,
    params=(season,),
)
st.dataframe(comebacks, hide_index=True, use_container_width=True)
