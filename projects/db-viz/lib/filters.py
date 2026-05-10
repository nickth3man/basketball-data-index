"""Reusable sidebar widgets shared across pages."""

from __future__ import annotations

from typing import Literal, overload

import pandas as pd
import streamlit as st

from lib.db import q


@st.cache_data(ttl=3600, show_spinner=False)
def _player_options() -> list[tuple[int, str]]:
    df = q("""
        SELECT person_id, first_name, last_name, from_year, to_year
        FROM dim_player
        WHERE first_name IS NOT NULL OR last_name IS NOT NULL
        ORDER BY last_name, first_name
    """)
    out: list[tuple[int, str]] = []
    for r in df.itertuples(index=False):
        first = r.first_name if pd.notna(r.first_name) else ""
        last = r.last_name if pd.notna(r.last_name) else ""
        name = f"{first} {last}".strip() or "(unknown)"
        years = ""
        if pd.notna(r.from_year) and pd.notna(r.to_year):
            years = f" ({int(r.from_year)}-{int(r.to_year)})"
        out.append((int(r.person_id), f"{name}{years}"))
    return out


@st.cache_data(ttl=3600, show_spinner=False)
def _team_options() -> list[tuple[int, str]]:
    df = q("""
        SELECT team_id, team_city || ' ' || team_name AS name, team_abbrev
        FROM v_team_current
        ORDER BY name
    """)
    return [(int(r.team_id), f"{r.name} ({r.team_abbrev})") for r in df.itertuples(index=False)]


def player_picker(
    label: str = "Player", default_name: str | None = None, key: str = "player_picker"
) -> int | None:
    """Searchable dropdown of all players. Returns person_id (or None)."""
    options = _player_options()
    if not options:
        st.warning("No players in dim_player.")
        return None
    labels = [lbl for _, lbl in options]
    default_idx = 0
    if default_name:
        for i, lbl in enumerate(labels):
            if default_name.lower() in lbl.lower():
                default_idx = i
                break
    sel = st.selectbox(label, labels, index=default_idx, key=key)
    return options[labels.index(sel)][0]


def team_picker(
    label: str = "Team", default_abbrev: str | None = None, key: str = "team_picker"
) -> int | None:
    """Dropdown of current franchises. Returns team_id."""
    options = _team_options()
    if not options:
        return None
    labels = [lbl for _, lbl in options]
    default_idx = 0
    if default_abbrev:
        for i, lbl in enumerate(labels):
            if f"({default_abbrev})" in lbl:
                default_idx = i
                break
    sel = st.selectbox(label, labels, index=default_idx, key=key)
    return options[labels.index(sel)][0]


@st.cache_data(ttl=3600, show_spinner=False)
def _season_options() -> list[str]:
    df = q("""
        SELECT DISTINCT season_year FROM fact_game
        WHERE season_year IS NOT NULL
        ORDER BY season_year DESC
    """)
    return df["season_year"].tolist()


@overload
def season_picker(
    label: str = ..., *, multi: Literal[False] = False, key: str = ...
) -> str | None: ...
@overload
def season_picker(label: str = ..., *, multi: Literal[True], key: str = ...) -> list[str]: ...


def season_picker(
    label: str = "Season", *, multi: bool = False, key: str = "season_picker"
) -> str | list[str] | None:
    options = _season_options()
    if not options:
        return [] if multi else None
    if multi:
        return st.multiselect(label, options, default=[options[0]], key=key)
    return st.selectbox(label, options, index=0, key=key)


def game_picker(
    team_id: int | None = None, season: str | None = None, key: str = "game_picker"
) -> str | None:
    """Pick a game by team+season. Returns game_id (10-char str)."""
    where = ["1=1"]
    params: list = []
    if team_id is not None:
        where.append("(home_team_id = ? OR away_team_id = ?)")
        params.extend([team_id, team_id])
    if season is not None:
        where.append("season_year = ?")
        params.append(season)
    sql = f"""
        SELECT game_id, game_date, home_team_id, away_team_id,
               home_score, away_score
        FROM fact_game
        WHERE {" AND ".join(where)} AND home_score IS NOT NULL
        ORDER BY game_date DESC
        LIMIT 500
    """
    df = q(sql, params=tuple(params))
    if df.empty:
        return None
    df["label"] = df.apply(
        lambda r: (
            f"{r.game_date}  |  {int(r.away_team_id)} @ {int(r.home_team_id)}  "
            f"({int(r.away_score)}-{int(r.home_score)})  [{r.game_id}]"
        ),
        axis=1,
    )
    sel = st.selectbox("Game", df["label"].tolist(), key=key)
    return df.loc[df["label"] == sel, "game_id"].iloc[0]
