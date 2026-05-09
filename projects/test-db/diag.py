import duckdb
con = duckdb.connect('nba.duckdb', read_only=True)
print('fact_game game_id samples:')
print(con.execute("SELECT game_id, length(game_id) FROM fact_game LIMIT 5").fetchall())
print('PBP game_id samples:')
print(con.execute("SELECT game_id, length(game_id) FROM fact_play_by_play LIMIT 5").fetchall())
print('Match attempt: strip leading zeros from PBP -> fact_game')
print(con.execute("""
    SELECT COUNT(*) FROM fact_play_by_play pbp
    WHERE LTRIM(pbp.game_id, '0') IN (SELECT game_id FROM fact_game)
""").fetchall())
print('Match attempt: pad fact_game to 10 chars')
print(con.execute("""
    SELECT COUNT(*) FROM fact_play_by_play pbp
    WHERE pbp.game_id IN (SELECT LPAD(game_id, 10, '0') FROM fact_game)
""").fetchall())
print('Distinct PBP game ids:', con.execute('SELECT COUNT(DISTINCT game_id) FROM fact_play_by_play').fetchone())
print('Distinct fact_game ids:', con.execute('SELECT COUNT(*) FROM fact_game').fetchone())
print('team_boxscores game_id sample:')
print(con.execute("SELECT game_id, length(game_id) FROM fact_team_game_stats LIMIT 5").fetchall())
print('player_game_stats game_id sample:')
print(con.execute("SELECT game_id, length(game_id) FROM fact_player_game_stats LIMIT 5").fetchall())
