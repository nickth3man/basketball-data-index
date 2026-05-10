"""Game Center — single-game deep-dive where ALL data converges."""

from __future__ import annotations

import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from lib.court import shot_chart_figure, to_court_ft
from lib.db import q
from lib.filters import game_picker, season_picker, team_picker

st.title("🎯 Game Center")

with st.sidebar:
    st.header("Filters")
    team_id = team_picker(default_abbrev="LAL", key="gc_team")
    season = season_picker(key="gc_season")
    game_id = game_picker(team_id=team_id, season=season, key="gc_game")

if not game_id:
    st.info("Pick a team, season, and game.")
    st.stop()

# ─── Header
hdr = q(
    """
    SELECT g.*, a.arena_name, a.arena_city, a.arena_state
    FROM fact_game g
    LEFT JOIN dim_arena a USING (arena_id)
    WHERE g.game_id = ?
    """,
    params=(game_id,),
)
if hdr.empty:
    st.error("Game not found.")
    st.stop()
h = hdr.iloc[0]

home = q(
    "SELECT team_city || ' ' || team_name AS name, team_abbrev FROM v_team_current WHERE team_id = ?",
    params=(int(h.home_team_id),),
)
away = q(
    "SELECT team_city || ' ' || team_name AS name, team_abbrev FROM v_team_current WHERE team_id = ?",
    params=(int(h.away_team_id),),
)
home_name = home.iloc[0]["name"] if not home.empty else "Home"
away_name = away.iloc[0]["name"] if not away.empty else "Away"

st.subheader(f"{away_name} @ {home_name}")
c = st.columns(5)
c[0].metric("Date", str(h.game_date))
c[1].metric(
    "Final",
    f"{int(h.away_score) if h.away_score else 0} – {int(h.home_score) if h.home_score else 0}",
)
c[2].metric("Type", h.season_type or "—")
c[3].metric("Arena", h.arena_name or "—")
c[4].metric("Attendance", f"{int(h.attendance):,}" if h.attendance else "—")

# ─── Officials
officials = q(
    "SELECT official_name FROM fact_game_official WHERE game_id = ? ORDER BY official_name",
    params=(game_id,),
)
if not officials.empty:
    st.caption("**Officials:** " + ", ".join(officials["official_name"].tolist()))

st.divider()

# ─── Box score side-by-side
tgs = q(
    """
    SELECT * FROM fact_team_game_stats WHERE game_id = ?
    """,
    params=(game_id,),
)
left, right = st.columns(2)
for col, side, label in [(left, True, away_name), (right, False, home_name)]:
    sub = tgs[tgs["is_home"] == side].iloc[0] if not tgs[tgs["is_home"] == side].empty else None
    with col:
        st.subheader(label)
        if sub is None:
            st.info("No team_game_stats row.")
            continue
        c = st.columns(5)
        c[0].metric("PTS", int(sub.pts) if sub.pts is not None else "—")
        c[1].metric("FG%", f"{(sub.fg_pct or 0) * 100:.1f}%" if sub.fg_pct else "—")
        c[2].metric("3P%", f"{(sub.fg3_pct or 0) * 100:.1f}%" if sub.fg3_pct else "—")
        c[3].metric("REB", int(sub.reb) if sub.reb is not None else "—")
        c[4].metric("AST", int(sub.ast) if sub.ast is not None else "—")
        c = st.columns(5)
        c[0].metric("Off Rtg", f"{sub.off_rating:.1f}" if sub.off_rating else "—")
        c[1].metric("Def Rtg", f"{sub.def_rating:.1f}" if sub.def_rating else "—")
        c[2].metric("eFG%", f"{(sub.efg_pct or 0) * 100:.1f}%" if sub.efg_pct else "—")
        c[3].metric("TOV%", f"{(sub.tm_tov_pct or 0) * 100:.1f}%" if sub.tm_tov_pct else "—")
        c[4].metric("Pace", f"{sub.pace:.1f}" if sub.pace else "—")

st.divider()

# ─── Quarter scoring
st.subheader("Quarter scoring")
qsplits = q(
    """
    SELECT p.team_id, p.period, p.pts
    FROM fact_team_game_period p
    WHERE p.game_id = ? ORDER BY p.team_id, p.period
    """,
    params=(game_id,),
)
if not qsplits.empty:
    qsplits["team"] = qsplits["team_id"].apply(
        lambda x: home_name if x == h.home_team_id else away_name
    )
    fig = px.bar(
        qsplits,
        x="period",
        y="pts",
        color="team",
        barmode="group",
        labels={"period": "Q", "pts": "Pts"},
    )
    fig.update_layout(height=300, margin={"l": 20, "r": 20, "t": 20, "b": 20})
    st.plotly_chart(fig, use_container_width=True)

# ─── Per-player box score
st.subheader("Per-player box score")
pgs = q(
    """
    SELECT pgs.team_id,
           p.first_name || ' ' || p.last_name AS player,
           pgs.starting_position AS pos,
           pgs.num_minutes AS min,
           pgs.points AS pts, pgs.reb, pgs.assists AS ast,
           pgs.steals AS stl, pgs.blocks AS blk, pgs.turnovers AS tov,
           pgs.fgm, pgs.fga, pgs.fg3m, pgs.fg3a, pgs.ftm, pgs.fta,
           pgs.plus_minus
    FROM fact_player_game_stats pgs
    LEFT JOIN dim_player p USING (person_id)
    WHERE pgs.game_id = ?
    ORDER BY pgs.team_id, pgs.points DESC NULLS LAST
    """,
    params=(game_id,),
)
left, right = st.columns(2)
with left:
    st.caption(f"**{away_name}**")
    st.dataframe(
        pgs[pgs["team_id"] == h.away_team_id].drop(columns=["team_id"]),
        hide_index=True,
        use_container_width=True,
    )
with right:
    st.caption(f"**{home_name}**")
    st.dataframe(
        pgs[pgs["team_id"] == h.home_team_id].drop(columns=["team_id"]),
        hide_index=True,
        use_container_width=True,
    )

st.divider()

# ─── PBP timeline
st.subheader("Score differential over game time")
pbp = q(
    """
    SELECT seconds_elapsed, score_home, score_away,
           score_home - score_away AS diff,
           description, team_tri_code, period
    FROM fact_play_by_play
    WHERE game_id = ? AND seconds_elapsed IS NOT NULL
    ORDER BY action_number
    """,
    params=(game_id,),
)
if not pbp.empty:
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=pbp["seconds_elapsed"] / 60,
            y=pbp["diff"],
            mode="lines",
            line_color="#C9082A",
            hovertext=pbp["description"],
            hoverinfo="x+y+text",
            name="Home margin",
        )
    )
    fig.add_hline(y=0, line_dash="dot", line_color="#888")
    for q_end in (12, 24, 36, 48):
        fig.add_vline(x=q_end, line_dash="dot", line_color="#444")
    fig.update_layout(
        height=320,
        xaxis_title="Game minutes",
        yaxis_title="Home – Away",
        margin={"l": 20, "r": 20, "t": 20, "b": 20},
    )
    st.plotly_chart(fig, use_container_width=True)

st.divider()

# ─── Shot chart for the game
st.subheader("Shot chart (both teams)")
shots = q(
    """
    SELECT x_legacy, y_legacy, shot_result, shot_value, team_id
    FROM fact_play_by_play
    WHERE game_id = ? AND is_field_goal = TRUE
          AND x_legacy IS NOT NULL AND y_legacy IS NOT NULL
    """,
    params=(game_id,),
)
if not shots.empty:
    shots["is_made"] = shots["shot_result"] == "Made"
    shots = to_court_ft(shots)
    fig = shot_chart_figure(shots, mode="scatter", title="All FGAs")
    st.pyplot(fig, clear_figure=True, use_container_width=False)
else:
    st.info("No shot-coordinate data for this game.")

st.divider()

# ─── Pre-game odds
st.subheader("Pre-game odds")
odds = q(
    """
    SELECT odds_date, decimal_home, decimal_away, moneyline_home, moneyline_away
    FROM fact_game_odds_snapshot WHERE game_id = ?
    ORDER BY odds_date
    """,
    params=(game_id,),
)
if odds.empty:
    st.caption("No odds snapshots for this game.")
else:
    st.dataframe(odds, use_container_width=True, hide_index=True)
