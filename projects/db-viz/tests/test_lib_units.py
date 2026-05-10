"""Unit tests for lib/ modules — fast, no Streamlit harness needed.

Boosts coverage on `lib/kpis.py`, `lib/viz.py`, `lib/court.py`, `lib/db.py`
and exercises the alternate radio-mode of `pages/13_Compare.py`.
"""

from __future__ import annotations

import math

import pandas as pd
import plotly.graph_objects as go
import pytest

from lib import court, db, kpis, viz


# ─────────────────────────────────────── kpis.py
class TestKpis:
    def test_fmt_int_handles_none(self):
        assert kpis.fmt_int(None) == "—"

    def test_fmt_int_thousands_separator(self):
        assert kpis.fmt_int(1234567) == "1,234,567"

    def test_fmt_int_accepts_float(self):
        assert kpis.fmt_int(42.9) == "42"

    def test_fmt_pct_default_decimals(self):
        assert kpis.fmt_pct(0.4185) == "41.8%"

    def test_fmt_pct_zero_decimals(self):
        assert kpis.fmt_pct(0.5, decimals=0) == "50%"

    def test_fmt_pct_handles_none(self):
        assert kpis.fmt_pct(None) == "—"

    def test_fmt_float_default(self):
        assert kpis.fmt_float(3.14159) == "3.14"

    def test_fmt_float_custom_decimals(self):
        assert kpis.fmt_float(3.14159, decimals=4) == "3.1416"

    def test_fmt_float_handles_none(self):
        assert kpis.fmt_float(None) == "—"

    @pytest.mark.parametrize(
        "n,expected",
        [
            (1_500_000_000, "1.5B"),
            (2_300_000, "2.3M"),
            (14_400, "14.4K"),
            (999, "999"),
            (None, "—"),
        ],
    )
    def test_fmt_human(self, n, expected):
        assert kpis.fmt_human(n) == expected


# ─────────────────────────────────────── viz.py
class TestViz:
    @pytest.fixture
    def sample_df(self):
        return pd.DataFrame(
            {
                "season": ["2020-21", "2021-22", "2022-23"],
                "ppg": [110.0, 112.5, 114.7],
                "team": ["A", "B", "C"],
            }
        )

    def test_line_by_season(self, sample_df):
        fig = viz.line_by_season(sample_df, x="season", y="ppg")
        assert isinstance(fig, go.Figure)
        # height set in factory
        assert fig.layout.height == 380

    def test_line_by_season_with_title(self, sample_df):
        fig = viz.line_by_season(sample_df, x="season", y="ppg", title="Trend")
        assert fig.layout.title.text == "Trend"

    def test_bar_grouped(self, sample_df):
        fig = viz.bar_grouped(sample_df, x="team", y="ppg")
        assert isinstance(fig, go.Figure)
        assert fig.layout.barmode == "group"

    def test_heatmap(self, sample_df):
        fig = viz.heatmap(sample_df, x="season", y="team", z="ppg")
        assert isinstance(fig, go.Figure)

    def test_radar_single_series(self):
        fig = viz.radar(["A", "B", "C"], [1, 2, 3], "Series A")
        assert isinstance(fig, go.Figure)
        assert len(fig.data) == 1

    def test_radar_two_series(self):
        fig = viz.radar(["A", "B"], [1, 2], "Player A", [3, 4], "Player B")
        assert len(fig.data) == 2


# ─────────────────────────────────────── court.py
class TestCourt:
    @pytest.fixture
    def sample_shots(self):
        return pd.DataFrame(
            {
                "x_legacy": [0, 100, -150, 200, 0],
                "y_legacy": [0, 50, 75, 30, 200],
                "is_made": [True, False, True, False, True],
                "shot_value": [2, 3, 2, 3, 2],
            }
        )

    def test_to_court_ft_adds_columns(self, sample_shots):
        out = court.to_court_ft(sample_shots)
        assert "court_x" in out.columns
        assert "court_y" in out.columns

    def test_to_court_ft_origin_at_basket(self, sample_shots):
        # (0, 0) NBA Stats coords = right basket position (court_x = 41.75, court_y = 0)
        out = court.to_court_ft(sample_shots)
        assert math.isclose(out["court_x"].iloc[0], 41.75)
        assert math.isclose(out["court_y"].iloc[0], 0.0)

    def test_to_court_ft_handles_nan(self):
        df = pd.DataFrame({"x_legacy": [None, 10], "y_legacy": [20, None]})
        out = court.to_court_ft(df)
        assert pd.isna(out["court_x"].iloc[0])
        assert pd.isna(out["court_y"].iloc[1])

    def test_shot_chart_empty_returns_figure(self):
        fig = court.shot_chart_figure(pd.DataFrame(), title="empty")
        # matplotlib Figure
        assert hasattr(fig, "axes")
        import matplotlib.pyplot as plt

        plt.close(fig)

    @pytest.mark.parametrize("mode", ["scatter", "hexbin", "heatmap_fg", "heatmap_pps"])
    def test_shot_chart_all_modes(self, sample_shots, mode):
        out = court.to_court_ft(sample_shots)
        fig = court.shot_chart_figure(out, mode=mode)
        assert hasattr(fig, "axes")
        import matplotlib.pyplot as plt

        plt.close(fig)

    def test_shot_chart_unknown_mode_falls_back(self, sample_shots):
        out = court.to_court_ft(sample_shots)
        fig = court.shot_chart_figure(out, mode="not_a_real_mode")
        assert hasattr(fig, "axes")
        import matplotlib.pyplot as plt

        plt.close(fig)

    def test_shot_chart_scatter_without_is_made(self):
        df = pd.DataFrame({"court_x": [0.0, 5.0], "court_y": [10.0, 20.0]})
        fig = court.shot_chart_figure(df, mode="scatter")
        assert hasattr(fig, "axes")
        import matplotlib.pyplot as plt

        plt.close(fig)


# ─────────────────────────────────────── db.py
class TestDb:
    def test_db_path_resolves(self):
        # DB_PATH should point at the real test-db file
        assert db.DB_PATH.exists(), f"Expected DB at {db.DB_PATH}"

    def test_db_size_gb_returns_positive(self):
        assert db.db_size_gb() > 0.5  # nba.duckdb is ~1.95 GB

    def test_db_mtime_returns_datetime(self):
        import datetime

        assert isinstance(db.db_mtime(), datetime.datetime)

    def test_get_conn_returns_duckdb(self):
        con = db.get_conn()
        assert con is not None
        # Smoke-test a query
        rows = con.execute("SELECT 1 AS x").fetchall()
        assert rows == [(1,)]

    def test_q_returns_dataframe(self):
        df = db.q("SELECT 1 AS x")
        assert isinstance(df, pd.DataFrame)
        assert df["x"].iloc[0] == 1

    def test_q_with_params(self):
        df = db.q("SELECT ? AS x", params=(42,))
        assert df["x"].iloc[0] == 42

    def test_q_one_returns_scalar(self):
        n = db.q_one("SELECT COUNT(*) FROM dim_team")
        assert isinstance(n, int)
        assert n > 0

    def test_q_one_empty_returns_none(self):
        result = db.q_one("SELECT 1 WHERE 1=0")
        assert result is None

    def test_list_tables_includes_facts(self):
        tables = db.list_tables()
        assert "fact_game" in tables
        assert "dim_player" in tables
        assert len(tables) >= 14
