"""Plotly chart factories for non-court visualizations."""

from __future__ import annotations

import plotly.express as px
import plotly.graph_objects as go

NBA_RED = "#C9082A"
NBA_BLUE = "#17408B"


def line_by_season(df, x: str, y: str, color: str | None = None, title: str = ""):
    fig = px.line(df, x=x, y=y, color=color, markers=True, title=title or None)
    fig.update_layout(height=380, margin={"l": 20, "r": 20, "t": 40 if title else 20, "b": 20})
    return fig


def bar_grouped(df, x: str, y: str, color: str | None = None, title: str = ""):
    fig = px.bar(df, x=x, y=y, color=color, barmode="group", title=title or None)
    fig.update_layout(height=380, margin={"l": 20, "r": 20, "t": 40 if title else 20, "b": 20})
    return fig


def heatmap(df, x: str, y: str, z: str, title: str = "", colorscale: str = "RdBu_r"):
    fig = px.density_heatmap(
        df, x=x, y=y, z=z, color_continuous_scale=colorscale, title=title or None, histfunc="avg"
    )
    fig.update_layout(height=440, margin={"l": 20, "r": 20, "t": 40 if title else 20, "b": 20})
    return fig


def radar(
    categories: list[str],
    values_a: list[float],
    name_a: str,
    values_b: list[float] | None = None,
    name_b: str | None = None,
    title: str = "",
):
    fig = go.Figure()
    fig.add_trace(
        go.Scatterpolar(
            r=[*values_a, values_a[0]],
            theta=[*categories, categories[0]],
            fill="toself",
            name=name_a,
            line_color=NBA_RED,
        )
    )
    if values_b is not None and name_b is not None:
        fig.add_trace(
            go.Scatterpolar(
                r=[*values_b, values_b[0]],
                theta=[*categories, categories[0]],
                fill="toself",
                name=name_b,
                line_color=NBA_BLUE,
            )
        )
    fig.update_layout(
        height=420,
        polar={"radialaxis": {"visible": True}},
        title=title or None,
        margin={"l": 20, "r": 20, "t": 40 if title else 20, "b": 20},
    )
    return fig


def kpi_strip(metrics: dict[str, str]):
    """Convenience: render a strip of key→value metrics. Returns nothing."""
    import streamlit as st

    cols = st.columns(len(metrics))
    for col, (k, v) in zip(cols, metrics.items(), strict=False):
        col.metric(k, v)
