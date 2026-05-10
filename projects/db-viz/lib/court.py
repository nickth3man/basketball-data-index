"""NBA court drawing + coordinate transform.

This module is the SOLE consumer of `sportypy` (GPL-3.0) — see README §
"GPL-3.0 isolation strategy". All shot-chart pages call into here.

PBP shot coords (`x_legacy`, `y_legacy`) follow the NBA Stats convention:
    - units: 1/10 ft
    - origin: center of the basket
    - rotated 90° from sportypy's NBACourt default (which has the long axis x)

We rotate + rescale so coords land on sportypy's NBA court directly.
"""

from __future__ import annotations

from typing import Literal

import matplotlib.pyplot as plt
import pandas as pd


# Defer sportypy import to function level so test discovery without sportypy
# installed still imports the module.
def _nba_court(**kwargs):
    from sportypy.surfaces.basketball import NBACourt

    return NBACourt(**kwargs)


def to_court_ft(df: pd.DataFrame, x_col: str = "x_legacy", y_col: str = "y_legacy") -> pd.DataFrame:
    """NBA Stats coords -> sportypy NBACourt feet coords.

    sportypy NBA court: origin = half-court line; baskets at (±41.75, 0).
    NBA Stats: origin = center of the basket; long axis = y; units 1/10 ft.

    For an offensive-half shot chart we want all shots on one half of the
    court (defaults to the right basket at +41.75). Many NBA Stats data
    feeds give shots relative to the offensive basket, so we just translate.
    """
    df = df.copy()
    # Convert from 1/10 ft to ft (cast to Series for downstream arithmetic typing)
    x: pd.Series = pd.to_numeric(df[x_col], errors="coerce").astype("float64") / 10.0  # type: ignore[assignment]
    y: pd.Series = pd.to_numeric(df[y_col], errors="coerce").astype("float64") / 10.0  # type: ignore[assignment]
    # NBA Stats: x is sideline-to-sideline, y is baseline-to-baseline (positive = into court).
    # sportypy: x is baseline-to-baseline (long axis), y is sideline-to-sideline.
    # Translate to right-basket side: court_x = 41.75 - y, court_y = -x
    df["court_x"] = 41.75 - y
    df["court_y"] = -x
    return df


ShotChartMode = Literal["scatter", "hexbin", "heatmap_fg", "heatmap_pps"]


def shot_chart_figure(
    shots: pd.DataFrame,
    mode: ShotChartMode | str = "hexbin",
    title: str = "",
    figsize: tuple[float, float] = (8, 7),
):
    """Render a shot chart on a regulation NBA half-court.

    `shots` must contain columns `court_x`, `court_y` (in feet, sportypy frame)
    plus `is_made` (bool/0-1) for FG% modes and `shot_value` (2 or 3) for PPS.

    Returns a matplotlib Figure for `st.pyplot()`.
    """
    fig, ax = plt.subplots(figsize=figsize, facecolor="#0E1117")
    ax.set_facecolor("#0E1117")

    court = _nba_court()
    court.draw(ax=ax, display_range="offense")

    if shots.empty:
        ax.set_title(title or "No shots match filters", color="white")
        return fig

    s = shots.dropna(subset=["court_x", "court_y"])

    if mode == "scatter":
        if "is_made" in s.columns:
            made = s[s["is_made"] == True]
            missed = s[s["is_made"] != True]
            court.scatter(
                missed["court_x"],
                missed["court_y"],
                ax=ax,
                color="#666666",
                alpha=0.4,
                s=14,
                zorder=20,
            )
            court.scatter(
                made["court_x"], made["court_y"], ax=ax, color="#C9082A", alpha=0.7, s=18, zorder=21
            )
        else:
            court.scatter(
                s["court_x"], s["court_y"], ax=ax, color="#C9082A", alpha=0.5, s=14, zorder=20
            )
    elif mode == "hexbin":
        court.hexbin(
            s["court_x"],
            s["court_y"],
            ax=ax,
            binsize=2.0,
            plot_range="offense",
            zorder=15,
            alpha=0.9,
        )
    elif mode == "heatmap_fg" and "is_made" in s.columns:
        court.heatmap(
            s["court_x"],
            s["court_y"],
            values=s["is_made"].astype(int),
            ax=ax,
            alpha=0.75,
            cmap="hot",
            statistic="mean",
            plot_range="offense",
            binsize=2.5,
        )
    elif mode == "heatmap_pps":
        if "shot_value" in s.columns and "is_made" in s.columns:
            pts = s["shot_value"].fillna(2).astype(int) * s["is_made"].fillna(False).astype(int)
            court.heatmap(
                s["court_x"],
                s["court_y"],
                values=pts,
                ax=ax,
                alpha=0.75,
                cmap="viridis",
                statistic="mean",
                plot_range="offense",
                binsize=2.5,
            )
    else:
        court.scatter(
            s["court_x"], s["court_y"], ax=ax, color="#C9082A", alpha=0.5, s=14, zorder=20
        )

    if title:
        ax.set_title(title, color="white", fontsize=12)
    return fig
