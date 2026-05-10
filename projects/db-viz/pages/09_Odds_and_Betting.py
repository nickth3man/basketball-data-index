"""Odds & Betting — fact_game_odds_snapshot, fact_game_main_line, fact_game_market_odds."""

from __future__ import annotations

import plotly.express as px
import streamlit as st

from lib.db import q
from lib.filters import season_picker

st.title("💰 Odds & Betting")

tab1, tab2, tab3 = st.tabs(["Closing-line value", "Pinnacle main lines", "Market diversity"])

with tab1:
    season = season_picker(key="odds_season")
    st.subheader(f"Implied home win-prob vs actual margin — {season}")
    df = q(
        """
        SELECT g.game_id, g.game_date, g.home_score, g.away_score,
               g.home_score - g.away_score AS home_margin,
               o.decimal_home, o.decimal_away,
               1.0 / o.decimal_home AS implied_home_p
        FROM fact_game g
        JOIN fact_game_odds_snapshot o USING (game_id)
        WHERE o.odds_date = 'open' AND g.season_year = ?
              AND g.home_score IS NOT NULL
              AND o.decimal_home IS NOT NULL AND o.decimal_home > 1
        """,
        params=(season,),
    )
    if df.empty:
        st.info("No opening-line snapshots for this season.")
    else:
        fig = px.scatter(
            df,
            x="implied_home_p",
            y="home_margin",
            opacity=0.4,
            labels={"implied_home_p": "Implied home win prob", "home_margin": "Actual home margin"},
        )
        # Naive linear fit overlay (avoids the statsmodels dep)
        import numpy as np

        if len(df) > 2:
            m, b = np.polyfit(df["implied_home_p"], df["home_margin"], 1)
            xs = np.linspace(df["implied_home_p"].min(), df["implied_home_p"].max(), 50)
            fig.add_scatter(
                x=xs,
                y=m * xs + b,
                mode="lines",
                line_color="orange",
                name="linear fit",
                showlegend=False,
            )
        fig.update_layout(height=440, margin={"l": 20, "r": 20, "t": 20, "b": 20})
        st.plotly_chart(fig, use_container_width=True)

        st.metric("Sample size", f"{len(df):,} games")

with tab2:
    st.subheader("Pinnacle main lines (Money Line + Spread + Total)")
    pinn = q(
        """
        SELECT snapshot_ts, team1_name, team2_name,
               team1_moneyline, team2_moneyline,
               team1_spread, team2_spread,
               over_total, under_total,
               is_preseason
        FROM fact_game_main_line
        ORDER BY snapshot_ts DESC LIMIT 500
        """
    )
    st.dataframe(pinn, hide_index=True, use_container_width=True)

    n_resolved = q(
        """SELECT
              SUM(CASE WHEN team1_id IS NOT NULL THEN 1 ELSE 0 END) AS resolved,
              COUNT(*) AS total
           FROM fact_game_main_line"""
    ).iloc[0]
    st.caption(
        f"{int(n_resolved.resolved)}/{int(n_resolved.total)} rows have resolved team_ids "
        "(others are franchise renames/relocations not in `dim_team`)."
    )

with tab3:
    st.subheader("Markets per game (top matchups)")
    markets = q(
        """
        SELECT matchup, COUNT(DISTINCT market) AS distinct_markets,
               COUNT(*) AS total_quotes,
               MIN(snapshot_ts) AS first_seen,
               MAX(snapshot_ts) AS last_seen
        FROM fact_game_market_odds
        GROUP BY matchup
        ORDER BY distinct_markets DESC LIMIT 25
        """
    )
    st.dataframe(markets, hide_index=True, use_container_width=True)

    st.subheader("Market frequency")
    freq = q(
        """
        SELECT market, COUNT(*) AS quotes
        FROM fact_game_market_odds
        GROUP BY market
        ORDER BY quotes DESC LIMIT 30
        """
    )
    fig = px.bar(freq, x="quotes", y="market", orientation="h")
    fig.update_layout(
        height=600,
        yaxis={"categoryorder": "total ascending"},
        margin={"l": 20, "r": 20, "t": 20, "b": 20},
    )
    st.plotly_chart(fig, use_container_width=True)
