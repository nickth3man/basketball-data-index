"""SQL Lab — power-user query interface."""

from __future__ import annotations

from pathlib import Path

import streamlit as st
from st_aggrid import AgGrid, GridOptionsBuilder

from lib.db import list_tables, q

st.title("🧪 SQL Lab")
st.caption("Read-only query interface. DDL/DML statements will error.")

# ─── Schema browser
with st.sidebar:
    st.header("Schema browser")
    tables = list_tables()
    for t in tables:
        with st.expander(t):
            cols = q(
                """SELECT column_name, data_type FROM information_schema.columns
                   WHERE table_name = ? ORDER BY ordinal_position""",
                params=(t,),
            )
            for r in cols.itertuples(index=False):
                st.caption(f"`{r.column_name}` — {r.data_type}")

# ─── Canned queries
CANNED_PATH = Path(__file__).parent.parent / "assets" / "canned_queries.sql"
canned = []
if CANNED_PATH.exists():
    raw = CANNED_PATH.read_text()
    # Split on "-- @name " markers
    chunks = raw.split("-- @name ")
    for chunk in chunks[1:]:
        lines = chunk.splitlines()
        name = lines[0].strip()
        sql = "\n".join(lines[1:]).strip()
        canned.append((name, sql))

st.subheader("Pre-canned examples")
if canned:
    pick = st.selectbox("Load example", ["—"] + [n for n, _ in canned])
    default_sql = ""
    if pick != "—":
        default_sql = dict(canned)[pick]
else:
    default_sql = ""

# ─── Editor
sql = st.text_area(
    "SQL",
    value=default_sql or "SELECT 'hello, NBA' AS greeting, COUNT(*) AS games FROM fact_game;",
    height=200,
    key="sql_editor",
)

if st.button("▶ Run", type="primary"):
    try:
        with st.spinner("Running..."):
            df = q(sql)
        st.success(f"Returned {len(df):,} rows × {len(df.columns)} cols")
        if df.empty:
            st.info("(empty result)")
        else:
            gb = GridOptionsBuilder.from_dataframe(df)
            gb.configure_default_column(filter=True, sortable=True, resizable=True)
            gb.configure_pagination(paginationPageSize=50)
            AgGrid(df, gridOptions=gb.build(), height=480)
            st.download_button(
                "Download CSV",
                df.to_csv(index=False).encode("utf-8"),
                file_name="query_result.csv",
                mime="text/csv",
            )
    except Exception as e:
        st.error(f"Query error: {e}")
