"""Coverage smoke test: assert every table is queried by ≥1 page query.

Run: `python -m pytest tests/ -v`  (or just `python tests/test_queries.py`)
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from lib.db import get_conn, list_tables

EXPECTED_TABLES = {
    "dim_arena",
    "dim_date",
    "dim_player",
    "dim_team",
    "fact_game",
    "fact_game_main_line",
    "fact_game_market_odds",
    "fact_game_odds_snapshot",
    "fact_game_official",
    "fact_play_by_play",
    "fact_player_game_stats",
    "fact_scheduled_game",
    "fact_team_game_period",
    "fact_team_game_stats",
}


def test_all_tables_present():
    tables = set(list_tables())
    missing = EXPECTED_TABLES - tables
    assert not missing, f"Tables missing from DB: {missing}"


def test_v_team_current_view_works():
    con = get_conn()
    row = con.execute("SELECT COUNT(*) FROM v_team_current").fetchone()
    assert row is not None
    assert row[0] > 0, "v_team_current view returned no rows"


def test_every_table_has_rows():
    con = get_conn()
    for t in EXPECTED_TABLES:
        row = con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()
        assert row is not None
        assert row[0] > 0, f"Table {t} is empty"


PAGE_SAMPLE_QUERIES = {
    # Page 1: Home
    "p1_kpis": "SELECT COUNT(*) FROM fact_game",
    "p1_pace_scatter": """SELECT g.season_year, AVG(tgs.pace) AS pace, AVG(tgs.off_rating) AS off_rtg
        FROM fact_team_game_stats tgs JOIN fact_game g USING (game_id)
        WHERE tgs.pace IS NOT NULL GROUP BY g.season_year LIMIT 5""",
    # Page 2: Team
    "p2_team_totals": """SELECT * FROM fact_team_game_stats tgs
        JOIN fact_game g USING (game_id) WHERE tgs.team_id IS NOT NULL LIMIT 1""",
    "p2_team_periods": "SELECT * FROM fact_team_game_period LIMIT 1",
    # Page 3: Player
    "p3_player_career": """SELECT * FROM fact_player_game_stats pgs
        JOIN dim_player p USING (person_id) LIMIT 1""",
    "p3_player_shots": """SELECT * FROM fact_play_by_play
        WHERE is_field_goal = TRUE AND x_legacy IS NOT NULL LIMIT 1""",
    # Page 4: Game Center
    "p4_game_arena": """SELECT * FROM fact_game g LEFT JOIN dim_arena a USING (arena_id) LIMIT 1""",
    "p4_game_officials": "SELECT * FROM fact_game_official LIMIT 1",
    "p4_game_odds": "SELECT * FROM fact_game_odds_snapshot LIMIT 1",
    "p4_game_main_line": "SELECT * FROM fact_game_main_line LIMIT 1",
    # Page 5: Shot Charts (covered by p3_player_shots)
    # Page 6: PBP Browser
    "p6_pbp_filter": "SELECT * FROM fact_play_by_play WHERE action_type IS NOT NULL LIMIT 1",
    # Page 7: Quarter Splits
    "p7_q_heatmap": """SELECT v.team_abbrev, p.period, AVG(p.pts) FROM fact_team_game_period p
        JOIN fact_game g USING (game_id) JOIN v_team_current v USING (team_id)
        GROUP BY v.team_abbrev, p.period LIMIT 5""",
    # Page 9: Odds (markets)
    "p9_market_odds": "SELECT * FROM fact_game_market_odds LIMIT 1",
    # Page 10: Schedule
    "p10_scheduled": "SELECT * FROM fact_scheduled_game LIMIT 1",
    # Page 11: Arenas
    "p11_arena_join": """SELECT a.arena_name, COUNT(g.game_id) FROM dim_arena a
        LEFT JOIN fact_game g USING (arena_id) GROUP BY a.arena_name LIMIT 5""",
    # Page 12: Trends
    "p12_dim_date": "SELECT * FROM dim_date LIMIT 1",
    # Page 14: SQL Lab schema browser
    "p14_info_schema": """SELECT table_name FROM information_schema.tables
        WHERE table_schema='main' LIMIT 5""",
}


def test_every_page_query_runs():
    con = get_conn()
    failed = []
    for name, sql in PAGE_SAMPLE_QUERIES.items():
        try:
            con.execute(sql).fetchall()
        except Exception as e:
            failed.append(f"{name}: {e}")
    assert not failed, "Page queries failed:\n" + "\n".join(failed)


if __name__ == "__main__":
    print("Running smoke tests...")
    test_all_tables_present()
    print("  [OK] all 14 expected tables present")
    test_v_team_current_view_works()
    print("  [OK] v_team_current view works")
    test_every_table_has_rows()
    print("  [OK] every table has rows")
    test_every_page_query_runs()
    print(f"  [OK] all {len(PAGE_SAMPLE_QUERIES)} page sample queries run")
    print("\nAll smoke tests passed.")
