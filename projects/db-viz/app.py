"""NBA DuckDB Dashboard — entry point.

Run with: `streamlit run app.py`
Streamlit auto-discovers the pages/ directory and renders sidebar nav.
"""

from __future__ import annotations

import streamlit as st

from lib.db import db_mtime, db_size_gb, get_conn, list_tables, q_one

st.set_page_config(
    page_title="NBA DuckDB Dashboard",
    page_icon="🏀",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Sidebar branding + data freshness badge
with st.sidebar:
    st.title("🏀 NBA Dashboard")
    st.caption("DuckDB-powered, 30 years of NBA history")
    st.divider()
    try:
        get_conn()  # warm the cache
        mtime = db_mtime()
        size = db_size_gb()
        st.caption(f"**Data as of:** {mtime:%Y-%m-%d %H:%M}")
        st.caption(f"**DB size:** {size:.2f} GB")
    except FileNotFoundError as e:
        st.error(str(e))
        st.stop()
    st.divider()
    st.caption("Pick a page above ↑")

# Landing page content (also accessible by clicking the app name)
st.title("NBA Historical Database — Visualizer")
st.markdown(
    """
Welcome to a single-file Streamlit dashboard over the NBA DuckDB built in
`projects/test-db/`. Every one of the 15 tables is reachable from a dedicated
page — pick one from the sidebar to begin, or jump straight to the high-level
**🏠 Home / League Pulse** page for league-wide KPIs.
"""
)

# Coverage check: show the table list inline so the user knows what's loaded.
st.subheader("Tables in this database")
tables = list_tables()
cols = st.columns(3)
for i, t in enumerate(tables):
    cnt = q_one(f"SELECT COUNT(*) FROM {t}")
    cols[i % 3].metric(t, f"{int(cnt):,}" if cnt is not None else "—")

st.subheader("Pages")
st.markdown(
    """
| # | Page | What it shows |
|---|---|---|
| 1 | 🏠 Home / League Pulse | At-a-glance KPIs, scoring trend, today's slate |
| 2 | 🏀 Team Profile | Per-team season deep dive |
| 3 | 👤 Player Profile | Career trajectory + shot chart |
| 4 | 🎯 Game Center | Single-game everything view |
| 5 | 🗺️ Shot Charts | Slice 17M-row PBP by location |
| 6 | 📜 PBP Browser | Raw event log explorer |
| 7 | ⏱️ Quarter Splits | Period-by-period analysis |
| 8 | 🦓 Officials | Refs and crew chemistry |
| 9 | 💰 Odds & Betting | Lines, line movement, ROI |
| 10 | 📅 Schedule | Upcoming + density |
| 11 | 🏟️ Arenas | Map of NBA venues |
| 12 | 📈 Season Trends | League evolution over 30 yrs |
| 13 | ⚖️ Compare | Player/team head-to-head |
| 14 | 🧪 SQL Lab | Power-user query interface |
"""
)
