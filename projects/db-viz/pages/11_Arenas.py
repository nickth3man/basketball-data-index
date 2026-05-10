"""Arenas — surface dim_arena."""

from __future__ import annotations

import json
from pathlib import Path

import folium
import plotly.express as px
import streamlit as st
from streamlit_folium import st_folium

from lib.db import q

st.title("🏟️ Arenas")
st.caption("273 NBA arenas from `dim_arena`.")

GEO_PATH = Path(__file__).parent.parent / "assets" / "arena_geocodes.json"
geo = {}
if GEO_PATH.exists():
    geo = json.loads(GEO_PATH.read_text())

# Games per arena
df = q(
    """
    SELECT a.arena_id, a.arena_name, a.arena_city, a.arena_state,
           COUNT(g.game_id) AS games
    FROM dim_arena a
    LEFT JOIN fact_game g USING (arena_id)
    GROUP BY a.arena_id, a.arena_name, a.arena_city, a.arena_state
    ORDER BY games DESC
    """
)

# ─── Map (best-effort lat/lng from geo file)
st.subheader("Arena map")
if not geo:
    st.info(
        "No `assets/arena_geocodes.json` found — map shows city centroids only "
        "if you populate it. The bar chart below works regardless."
    )
else:
    m = folium.Map(location=[39.5, -98.35], zoom_start=4, tiles="CartoDB dark_matter")
    for r in df.itertuples(index=False):
        key = str(int(r.arena_id))
        if key not in geo:
            continue
        lat, lng = geo[key]
        folium.CircleMarker(
            location=[lat, lng],
            radius=max(3, min(20, (r.games or 0) ** 0.4)),
            popup=f"{r.arena_name}<br>{r.arena_city}, {r.arena_state}<br>{int(r.games):,} games",
            color="#C9082A",
            fill=True,
            fillOpacity=0.7,
        ).add_to(m)
    st_folium(m, height=520, use_container_width=True)

st.divider()

# Top arenas
st.subheader("Top 25 arenas by games hosted")
fig = px.bar(
    df.head(25),
    x="games",
    y="arena_name",
    orientation="h",
    hover_data=["arena_city", "arena_state"],
)
fig.update_layout(
    height=700,
    yaxis={"categoryorder": "total ascending"},
    margin={"l": 20, "r": 20, "t": 20, "b": 20},
)
st.plotly_chart(fig, use_container_width=True)

st.divider()

# Multi-tenant arenas
st.subheader("Arenas that hosted games for multiple home teams")
mt = q(
    """
    SELECT a.arena_name, a.arena_city, COUNT(DISTINCT g.home_team_id) AS distinct_home_teams,
           COUNT(*) AS games
    FROM dim_arena a
    JOIN fact_game g USING (arena_id)
    GROUP BY a.arena_name, a.arena_city
    HAVING COUNT(DISTINCT g.home_team_id) > 1
    ORDER BY distinct_home_teams DESC, games DESC
    LIMIT 30
    """
)
st.dataframe(mt, hide_index=True, use_container_width=True)

st.divider()

# Attendance caveat
st.subheader("Average attendance (caveat: only 2025-26 populated)")
att = q(
    """
    SELECT a.arena_name, AVG(g.attendance) AS avg_att, COUNT(*) AS games
    FROM dim_arena a JOIN fact_game g USING (arena_id)
    WHERE g.attendance > 0
    GROUP BY a.arena_name HAVING COUNT(*) > 5
    ORDER BY avg_att DESC LIMIT 25
    """
)
if att.empty:
    st.info("No attendance > 0 found (data limitation).")
else:
    st.dataframe(att, hide_index=True, use_container_width=True)
