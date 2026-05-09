# NBA Historical Database (DuckDB)

Single-file analytical database built from the 60 CSVs in `csv/nba/`.

## Build

```bash
cd projects/test-db
pip install duckdb            # tested with duckdb 1.5+
python build.py               # full build (~5-10 min, output ~3-5 GB)
python build.py --skip-pbp    # skip the 18M-row PBP table (~70% faster, dev/iteration)
python build.py --keep        # don't delete existing nba.duckdb (debugging)
```

The build is **idempotent** — by default `nba.duckdb` is deleted and rebuilt from scratch.

## Files

| File | Purpose |
|---|---|
| `build.py` | ETL orchestrator (Python + DuckDB) |
| `sql/01_schema.sql` | Table DDL (15 tables: 4 dim + 11 fact) |
| `sql/08_indexes.sql` | Post-load indexes on hot join keys |
| `sql/09_validate.sql` | Row-count sanity check |
| `nba.duckdb` | Output database (gitignored) |

## Schema overview

```
dim_team, dim_player, dim_arena, dim_date
    │
    ▼
fact_game ─┬─► fact_game_official
           ├─► fact_game_odds_snapshot
           ├─► fact_game_main_line
           └─► fact_game_market_odds
    │
    ├─► fact_team_game_stats ─► fact_team_game_period
    ├─► fact_player_game_stats
    └─► fact_play_by_play

fact_scheduled_game (future games not yet in fact_game)
```

See `../../you-are-a-database-synthetic-flame.md` (or `~/.claude/plans/`) for full design notes.

## Quick query

```bash
python -c "
import duckdb
con = duckdb.connect('nba.duckdb', read_only=True)
print(con.execute('''
    SELECT season_year, SUM(points) AS pts, COUNT(*) AS games
    FROM fact_player_game_stats pgs
    JOIN dim_player p USING (person_id)
    JOIN fact_game g USING (game_id)
    WHERE p.first_name = 'LeBron' AND p.last_name = 'James'
    GROUP BY season_year ORDER BY season_year
''').fetchall())
"
```

## Notes on dropped CSVs

The build deliberately **does not load** the following because they are subsumed by canonical sources:
- `Games.csv` (subset of `Games1.csv`)
- `games_traditional.csv`, `games_advanced.csv`, `games_four-factors.csv`, `games_misc.csv`, `games_scoring.csv` (subset of `team_boxscores.csv`)
- `teams_boxscores.csv`, `games_boxscores.csv`, `TeamStatisticsExtended.csv` (subset of `team_boxscores.csv`)
- `player_boxscores.csv` (rank columns; covered by `PlayerStatistics{,Extended}.csv`)
- `pbp1997.csv` … `pbp2026.csv` (legacy v2; superseded by `play_by_play.csv` v3)
