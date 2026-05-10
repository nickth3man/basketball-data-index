"""DuckDB connection + query caching helpers (canonical pattern from
DuckDB's official Streamlit guide, 2025-03-28).

A single read-only connection is reused per Streamlit process via
`@st.cache_resource`; query results are memoized via `@st.cache_data`.
The underscore prefix on `_conn` tells Streamlit not to hash the
unhashable connection object.
"""

from __future__ import annotations

import datetime
import os
from pathlib import Path

import duckdb
import pandas as pd
import streamlit as st

DB_PATH = Path(
    os.environ.get(
        "NBA_DUCKDB_PATH",
        Path(__file__).parent.parent.parent / "test-db" / "nba.duckdb",
    )
).resolve()


@st.cache_resource(ttl=datetime.timedelta(hours=1), max_entries=2)
def get_conn() -> duckdb.DuckDBPyConnection:
    """One read-only DuckDB connection per Streamlit process."""
    if not DB_PATH.exists():
        raise FileNotFoundError(
            f"Database not found at {DB_PATH}. Run projects/test-db/build.py first."
        )
    con = duckdb.connect(str(DB_PATH), read_only=True)
    con.execute("PRAGMA threads=4")
    con.execute("PRAGMA memory_limit='4GB'")
    return con


@st.cache_data(ttl=3600, max_entries=300, show_spinner=False)
def q(sql: str, params: tuple = (), _conn=None) -> pd.DataFrame:
    """Execute SQL (with optional positional params) and return a DataFrame.
    Result is cached on (sql, params)."""
    conn = _conn or get_conn()
    if params:
        return conn.execute(sql, list(params)).fetchdf()
    return conn.execute(sql).fetchdf()


@st.cache_data(ttl=3600, max_entries=300, show_spinner=False)
def q_one(sql: str, params: tuple = (), _conn=None):
    """Execute SQL and return a single scalar value (first column of first row)."""
    df = q(sql, params, _conn=_conn)
    if df.empty:
        return None
    return df.iat[0, 0]


def db_mtime() -> datetime.datetime:
    """Last-modified time of the duckdb file (for 'Data as of' badge)."""
    return datetime.datetime.fromtimestamp(DB_PATH.stat().st_mtime)


def db_size_gb() -> float:
    return DB_PATH.stat().st_size / 1e9


def list_tables() -> list[str]:
    """All user tables in the main schema."""
    df = q(
        """SELECT table_name FROM information_schema.tables
           WHERE table_schema='main' AND table_type='BASE TABLE'
           ORDER BY table_name"""
    )
    return df["table_name"].tolist()
