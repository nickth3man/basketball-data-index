# NBA Historical Database (DuckDB)

Single-file analytical database built from the 60 CSVs in `csv/nba/`. Covers ~30 years of NBA history including ~17.3M play-by-play events, 1.67M player-game lines, 73K games, and 514K odds snapshots.

## Quick start

```bash
cd projects/test-db
pip install duckdb            # tested with duckdb 1.5.2
python build.py               # full build: ~3 min, output ~1.95 GB
python build.py --skip-pbp    # skip 18M-row PBP table: ~25 s, ~270 MB
python build.py --keep        # don't delete existing nba.duckdb
```

The build is **idempotent** — by default `nba.duckdb` is deleted and rebuilt from scratch.

## Files

| File | Purpose |
|---|---|
| `build.py` | ETL orchestrator (Python + DuckDB) |
| `sql/01_schema.sql` | Table DDL — 15 tables (4 dim + 11 fact) |
| `sql/08_indexes.sql` | Post-load indexes on hot join keys |
| `sql/09_validate.sql` | Row-count sanity check |
| `nba.duckdb` | Output database (gitignored) |

## Schema

```
dim_team   dim_player   dim_arena   dim_date
    │          │            │           │
    └──────────┴──── fact_game ─────────┘
                       │  ├─► fact_game_official
                       │  ├─► fact_game_odds_snapshot
                       │  ├─► fact_game_main_line
                       │  └─► fact_game_market_odds
                       │
       ┌───────────────┼─────────────────┐
       ▼               ▼                 ▼
fact_team_game_   fact_player_game_   fact_play_by_play
   stats             stats
       │
       ▼
fact_team_game_period   (quarter splits)

fact_scheduled_game     (future games not in fact_game)
v_team_current          (view: most-recent franchise row per team_id)
```

**ID convention**: all `game_id` values are normalized to **10-character zero-padded strings** during ETL (e.g. `0022500165`). Source CSVs use a mix of stripped (`22500165`) and padded formats — see Gotchas below.

## Row counts (after full build)

| Table | Rows |
|---|---:|
| `dim_player` | 6,692 |
| `dim_team` | 140 |
| `dim_arena` | 273 |
| `dim_date` | 14,442 |
| `fact_game` | 73,246 |
| `fact_game_official` | 4,147 |
| `fact_team_game_stats` | 75,980 |
| `fact_team_game_period` | 303,920 |
| `fact_player_game_stats` | 1,667,844 |
| `fact_play_by_play` | **17,292,827** |
| `fact_game_odds_snapshot` | 513,913 |
| `fact_game_main_line` | 1,226 |
| `fact_game_market_odds` | 160,910 |
| `fact_scheduled_game` | 26 |

## Sample queries

```python
import duckdb
con = duckdb.connect('nba.duckdb', read_only=True)

# LeBron career points by season
con.execute("""
    SELECT g.season_year, SUM(pgs.points) AS pts, COUNT(*) AS games
    FROM fact_player_game_stats pgs
    JOIN dim_player p USING (person_id)
    JOIN fact_game g USING (game_id)
    WHERE p.first_name = 'LeBron' AND p.last_name = 'James'
    GROUP BY g.season_year ORDER BY g.season_year
""").fetchall()

# Stephen Curry career 3-point shots from PBP
con.execute("""
    SELECT shot_result, COUNT(*) AS attempts,
           ROUND(AVG(shot_distance), 1) AS avg_dist_ft
    FROM fact_play_by_play pbp
    JOIN dim_player p USING (person_id)
    WHERE p.first_name = 'Stephen' AND p.last_name = 'Curry'
      AND pbp.shot_value = 3 AND pbp.is_field_goal
    GROUP BY shot_result
""").fetchall()
# → 4,898 made / 6,805 missed = 41.8% career 3PT%

# 2024-25 offensive rating leaders
con.execute("""
    SELECT t.team_city || ' ' || t.team_name AS team,
           ROUND(AVG(tgs.off_rating), 2) AS off_rtg
    FROM fact_team_game_stats tgs
    JOIN v_team_current t USING (team_id)
    JOIN fact_game g USING (game_id)
    WHERE g.season_year = '2024-25' AND g.season_type = 'Regular'
    GROUP BY team
    HAVING COUNT(*) > 30
    ORDER BY off_rtg DESC LIMIT 10
""").fetchall()
```

## CSVs not loaded (subsumed by canonical sources)

The build deliberately skips these because their data is fully covered elsewhere:

| Skipped | Subsumed by |
|---|---|
| `Games.csv` | `Games1.csv` (superset; +13 newer rows) |
| `games_traditional.csv`, `games_advanced.csv`, `games_four-factors.csv`, `games_misc.csv`, `games_scoring.csv` | `team_boxscores.csv` |
| `teams_boxscores.csv`, `games_boxscores.csv` | `team_boxscores.csv` |
| `TeamStatisticsExtended.csv` | `team_boxscores.csv` |
| `player_boxscores.csv` | `PlayerStatistics.csv` + `PlayerStatisticsExtended.csv` (rank columns can be recomputed via window functions) |
| `pbp1997.csv` … `pbp2026.csv` (30 files) | `play_by_play.csv` (modern v3 schema, superset) |
| `data_dictionary.csv`, `column_mapping.json` | reference only — not loaded |

Net: **60 CSVs → 15 tables**, with 13+ files dropped as redundant.

## Gotchas (discovered during implementation)

1. **Game ID format**: `Games1.csv`, `PlayerStatistics.csv`, `TeamStatistics.csv`, and `LeagueSchedule*.csv` store `gameId` as a stripped integer (`22500165`). `team_boxscores.csv`, `play_by_play.csv`, `game_odds.csv`, `games_index.csv`, and `games_schedule.csv` store it zero-padded to 10 chars (`0022500165`). The ETL normalizes everything via `LPAD(game_id, 10, '0')`. **Always join on the padded form.**
2. **`team_id = 0` / `person_id = 0` in PBP** mark period boundaries and non-attributed events. ETL converts to `NULL`.
3. **`team_boxscores.csv` column names** differ from the older "games_*" set: it uses `fg3m`/`fg3a` (not `3pm`/`3pa`), `pts_off_tov` (not `pts_off_to`), `pts_2nd_chance` (not `2nd_pts`), `pts_fb` (not `fbps`), `pts_paint` (not `pitp`), `tm_tov_pct` (not `tov_pct`), `ast_to` (not `ast_turnover_ratio`).
4. **`TeamHistories.csv` `teamAbbrev`** is space-padded (`"TRI  "`). ETL applies `TRIM`.
5. **PBP load OOM**: dedup via `QUALIFY ROW_NUMBER` over 18M rows exceeded 6 GB RAM. Build uses a staging table + `INSERT ... ON CONFLICT DO NOTHING` instead, which streams safely.
6. **Pinnacle odds** (`nba_main_lines.csv`) reference teams by full name string, not ID. ETL resolves via `dim_team` lookup; some matches fail for relocated/renamed franchises (e.g. pre-2002 Charlotte Hornets ≠ current Charlotte Hornets) — those rows keep NULL `team_id`s but are not dropped.
7. **`game_odds.csv` `odds_date`** is `"open"` for opening lines and an ISO timestamp otherwise — kept as `VARCHAR`.
8. **Encoding corruption**: `games_advanced.csv`, `games_misc.csv`, `nba_detailed_odds.csv` have `Â` and `â€"` characters in headers/values. ETL projects columns explicitly so header corruption is sidestepped.
9. **`attendance` is sparse**: only the 2025-26 season (1,286 games) has populated attendance values in `Games1.csv`. All historical seasons store `NULL`/`0`.
10. **Players with duplicate names exist** — always join on `person_id`, never on `first_name + last_name`.
11. **DuckDB indexes are added post-load** (per official guidance — pre-load indexes slow inserts ~10×).

## Referential integrity status

After build, a small number of rows reference IDs not present in their parent dimension/fact (logged at end of build run):

| Check | Orphans | % of total |
|---|---:|---:|
| `fact_play_by_play.game_id` not in `fact_game` | 2,274 | 0.013% |
| `fact_player_game_stats.game_id` not in `fact_game` | 4,861 | 0.29% |
| `fact_player_game_stats.person_id` not in `dim_player` | 189 | 0.011% |
| `fact_team_game_stats.team_id` not in `dim_team` | 0 | 0.000% |

These reflect real source-data gaps (preseason exhibition games, players outside the canonical roster file) rather than ETL bugs. FK constraints are intentionally **not** enforced at the table level so these rows still load.

## Design rationale

For the full design plan (engine selection, schema rationale, ETL strategy, indexing notes), see:

```
~/.claude/plans/you-are-a-database-synthetic-flame.md
```
