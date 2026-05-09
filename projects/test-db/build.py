"""Build the NBA historical DuckDB database from raw CSVs in csv/nba/.

Usage:
    cd projects/test-db
    python build.py [--keep] [--skip-pbp]

Flags:
    --keep      Keep existing nba.duckdb (default rebuilds from scratch).
    --skip-pbp  Skip the 18M-row play-by-play load (~70% faster build for dev).

End-to-end runtime ~5-10 min on a modern laptop; output ~3-5 GB.
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import duckdb

# ── Paths ──────────────────────────────────────────────────────────────────
HERE = Path(__file__).parent.resolve()
SQL_DIR = HERE / "sql"
DB_PATH = HERE / "nba.duckdb"
CSV_DIR = (HERE / ".." / ".." / "csv" / "nba").resolve()


def csv(filename: str) -> str:
    """Return a DuckDB-quoted read_csv_auto() expression for a CSV in CSV_DIR.

    `all_varchar=true` forces string typing so we can TRY_CAST every column
    explicitly — this makes ETL resilient to dirty/empty cells across 30 years
    of data without DuckDB's type inference choking on the first bad row.
    """
    path = (CSV_DIR / filename).as_posix()
    return f"read_csv_auto('{path}', all_varchar=true, ignore_errors=true)"


def step(con: duckdb.DuckDBPyConnection, label: str, sql: str) -> None:
    t0 = time.perf_counter()
    print(f"  - {label} ...", end=" ", flush=True)
    con.execute(sql)
    print(f"done ({time.perf_counter() - t0:5.1f}s)")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--keep", action="store_true", help="reuse existing DB")
    ap.add_argument("--skip-pbp", action="store_true", help="skip play-by-play load")
    args = ap.parse_args()

    if not args.keep and DB_PATH.exists():
        DB_PATH.unlink()
        print(f"removed existing {DB_PATH.name}")

    if not CSV_DIR.exists():
        print(f"ERROR: CSV directory not found: {CSV_DIR}", file=sys.stderr)
        return 1

    print(f"\nBuilding {DB_PATH}")
    print(f"  CSV source: {CSV_DIR}\n")
    overall = time.perf_counter()
    con = duckdb.connect(str(DB_PATH))
    con.execute("PRAGMA memory_limit='6GB'")
    con.execute("PRAGMA threads=4")
    con.execute("PRAGMA preserve_insertion_order=false")

    # ── 1. Schema ──────────────────────────────────────────────────────────
    print("[1/8] Schema")
    con.execute((SQL_DIR / "01_schema.sql").read_text())

    # ── 2. Dimensions ──────────────────────────────────────────────────────
    print("\n[2/8] Dimensions")

    step(con, "dim_player", f"""
        INSERT INTO dim_player
        SELECT
            TRY_CAST(personId AS BIGINT),
            firstName, lastName,
            TRY_CAST(birthDate AS DATE),
            NULLIF(school, ''), NULLIF(country, ''),
            TRY_CAST(heightInches AS SMALLINT),
            TRY_CAST(bodyWeightLbs AS SMALLINT),
            jersey,
            TRY_CAST(guard AS INTEGER)::BOOLEAN,
            TRY_CAST(forward AS INTEGER)::BOOLEAN,
            TRY_CAST(center AS INTEGER)::BOOLEAN,
            TRY_CAST(dleagueFlag AS INTEGER)::BOOLEAN,
            TRY_CAST(nbaFlag AS INTEGER)::BOOLEAN,
            TRY_CAST(gamesPlayedFlag AS INTEGER)::BOOLEAN,
            TRY_CAST(draftYear AS INTEGER),
            TRY_CAST(draftRound AS INTEGER),
            TRY_CAST(draftNumber AS INTEGER),
            TRY_CAST(fromYear AS INTEGER),
            TRY_CAST(toYear AS INTEGER)
        FROM {csv('Players.csv')}
        WHERE TRY_CAST(personId AS BIGINT) IS NOT NULL;
    """)

    step(con, "dim_team", f"""
        INSERT INTO dim_team
        SELECT DISTINCT
            TRY_CAST(teamId AS BIGINT),
            TRY_CAST(seasonFounded AS INTEGER),
            TRY_CAST(seasonActiveTill AS INTEGER),
            teamCity, teamName, TRIM(teamAbbrev), league
        FROM {csv('TeamHistories.csv')}
        WHERE TRY_CAST(teamId AS BIGINT) IS NOT NULL
          AND TRY_CAST(seasonFounded AS INTEGER) IS NOT NULL;
    """)

    step(con, "dim_arena", f"""
        INSERT INTO dim_arena
        SELECT
            arena_id, ANY_VALUE(arena_name),
            ANY_VALUE(arena_city), ANY_VALUE(arena_state)
        FROM (
            SELECT
                TRY_CAST(arenaId AS BIGINT) AS arena_id,
                arenaName AS arena_name,
                arenaCity AS arena_city,
                arenaState AS arena_state
            FROM {csv('Games1.csv')}
            WHERE TRY_CAST(arenaId AS BIGINT) IS NOT NULL
              AND TRY_CAST(arenaId AS BIGINT) > 0
        )
        GROUP BY arena_id;
    """)

    step(con, "dim_date", f"""
        INSERT INTO dim_date
        WITH dates AS (
            SELECT DISTINCT TRY_CAST(gameDate AS DATE) AS d
            FROM {csv('Games1.csv')}
            WHERE TRY_CAST(gameDate AS DATE) IS NOT NULL
        )
        SELECT
            d,
            CASE WHEN month(d) >= 10
                 THEN year(d)::VARCHAR || '-' || RIGHT((year(d)+1)::VARCHAR, 2)
                 ELSE (year(d)-1)::VARCHAR || '-' || RIGHT(year(d)::VARCHAR, 2) END,
            CASE WHEN month(d) >= 10 THEN year(d) ELSE year(d)-1 END,
            month(d) BETWEEN 10 AND 12 OR month(d) BETWEEN 1 AND 4,
            month(d) BETWEEN 4 AND 6,
            dayname(d), month(d), year(d)
        FROM dates;
    """)

    # ── 3. Games ───────────────────────────────────────────────────────────
    print("\n[3/8] Games")

    step(con, "fact_game", f"""
        INSERT INTO fact_game
        SELECT
            LPAD(g.gameId, 10, '0'),
            TRY_CAST(g.gameDate AS DATE),
            TRY_CAST(g.gameDateTimeEst AS TIMESTAMP),
            gi.season_year,
            CASE
                WHEN g.gameType ILIKE '%playoff%'  THEN 'Playoffs'
                WHEN g.gameType ILIKE '%preseason%' THEN 'Preseason'
                WHEN g.gameType ILIKE '%cup%'       THEN 'Cup'
                ELSE 'Regular'
            END,
            g.gameType, g.gameSubtype, g.gameLabel, g.gameSubLabel,
            TRY_CAST(g.seriesGameNumber AS INTEGER),
            TRY_CAST(g.hometeamId AS BIGINT),
            TRY_CAST(g.awayteamId AS BIGINT),
            TRY_CAST(g.homeScore AS INTEGER),
            TRY_CAST(g.awayScore AS INTEGER),
            TRY_CAST(g.winner AS BIGINT),
            TRY_CAST(g.arenaId AS BIGINT),
            g.arenaName, g.arenaCity, g.arenaState,
            TRY_CAST(g.attendance AS INTEGER),
            NULL,                                   -- is_overtime (refine later)
            TRY_CAST(gi.odds_home AS DOUBLE),
            TRY_CAST(gi.odds_away AS DOUBLE)
        FROM {csv('Games1.csv')} g
        LEFT JOIN {csv('games_index.csv')} gi
          ON gi.game_id = LPAD(g.gameId, 10, '0');
    """)

    step(con, "fact_game_official", f"""
        INSERT INTO fact_game_official
        SELECT DISTINCT LPAD(gameId, 10, '0'), TRIM(off_name)
        FROM (
            SELECT gameId, UNNEST(string_split(officials, ',')) AS off_name
            FROM {csv('Games1.csv')}
            WHERE officials IS NOT NULL AND officials != ''
        )
        WHERE TRIM(off_name) != '';
    """)

    step(con, "fact_scheduled_game", f"""
        INSERT INTO fact_scheduled_game
        WITH s AS (
            SELECT
                LPAD(gameId, 10, '0') AS game_id,
                TRY_CAST(gameDateTimeEst AS TIMESTAMP) AS game_datetime_est,
                '2024-25' AS season_year,
                TRY_CAST(hometeamId AS BIGINT) AS home_team_id,
                TRY_CAST(awayteamId AS BIGINT) AS away_team_id,
                arenaName AS arena_name,
                arenaCity AS arena_city,
                arenaState AS arena_state,
                gameLabel AS game_label,
                gameSubLabel AS game_sub_label,
                TRY_CAST(seriesGameNumber AS INTEGER) AS series_game_number,
                TRY_CAST(weekNumber AS INTEGER) AS week_number
            FROM {csv('LeagueSchedule24_25.csv')}
            UNION ALL
            SELECT
                LPAD(gameId, 10, '0'), TRY_CAST(gameDateTimeEst AS TIMESTAMP), '2025-26',
                TRY_CAST(homeTeamId AS BIGINT), TRY_CAST(awayTeamId AS BIGINT),
                arenaName, arenaCity, arenaState,
                gameLabel, gameSubLabel,
                TRY_CAST(seriesGameNumber AS INTEGER),
                TRY_CAST(weekNumber AS INTEGER)
            FROM {csv('LeagueSchedule25_26.csv')}
        )
        SELECT
            game_id, ANY_VALUE(game_datetime_est), ANY_VALUE(season_year),
            ANY_VALUE(home_team_id), ANY_VALUE(away_team_id),
            ANY_VALUE(arena_name), ANY_VALUE(arena_city), ANY_VALUE(arena_state),
            ANY_VALUE(game_label), ANY_VALUE(game_sub_label),
            ANY_VALUE(series_game_number), ANY_VALUE(week_number)
        FROM s
        WHERE game_id NOT IN (SELECT game_id FROM fact_game)
        GROUP BY game_id;
    """)

    # ── 4. Team-game stats ─────────────────────────────────────────────────
    print("\n[4/8] Team-game stats")

    step(con, "fact_team_game_stats", f"""
        INSERT INTO fact_team_game_stats
        WITH tb AS (
            SELECT * FROM {csv('team_boxscores.csv')}
            WHERE TRY_CAST(game_id AS VARCHAR) IS NOT NULL
              AND TRY_CAST(team_id AS BIGINT)  IS NOT NULL
        ),
        ts AS (
            SELECT
                LPAD(gameId, 10, '0') AS game_id,
                TRY_CAST(teamId AS BIGINT) AS team_id,
                TRY_CAST(benchPoints AS INTEGER) AS bench_points,
                TRY_CAST(biggestLead AS INTEGER) AS biggest_lead,
                TRY_CAST(biggestScoringRun AS INTEGER) AS biggest_scoring_run,
                TRY_CAST(leadChanges AS INTEGER) AS lead_changes,
                TRY_CAST(timesTied AS INTEGER) AS times_tied,
                TRY_CAST(timeoutsRemaining AS INTEGER) AS timeouts_remaining,
                TRY_CAST(coachId AS BIGINT) AS coach_id
            FROM {csv('TeamStatistics.csv')}
        ),
        joined AS (
            SELECT
                tb.game_id,
                TRY_CAST(tb.team_id AS BIGINT) AS team_id,
                tb.season_year,
                tb.team_abbreviation AS team_abbrev,
                tb.team_name,
                tb.matchup,
                TRY_CAST(tb.is_home AS INTEGER)::BOOLEAN AS is_home,
                TRY_CAST(tb.wl AS INTEGER)::BOOLEAN AS is_win,
                TRY_CAST(tb.min AS DOUBLE) AS min,
                TRY_CAST(tb.pts AS INTEGER) AS pts,
                TRY_CAST(tb.fgm AS INTEGER) AS fgm, TRY_CAST(tb.fga AS INTEGER) AS fga,
                TRY_CAST(tb.fg_pct AS DOUBLE) AS fg_pct,
                TRY_CAST(tb.fg3m AS INTEGER) AS fg3m, TRY_CAST(tb.fg3a AS INTEGER) AS fg3a,
                TRY_CAST(tb.fg3_pct AS DOUBLE) AS fg3_pct,
                TRY_CAST(tb.ftm AS INTEGER) AS ftm, TRY_CAST(tb.fta AS INTEGER) AS fta,
                TRY_CAST(tb.ft_pct AS DOUBLE) AS ft_pct,
                TRY_CAST(tb.oreb AS INTEGER) AS oreb,
                TRY_CAST(tb.dreb AS INTEGER) AS dreb,
                TRY_CAST(tb.reb AS INTEGER) AS reb,
                TRY_CAST(tb.ast AS INTEGER) AS ast,
                TRY_CAST(tb.tov AS INTEGER) AS tov,
                TRY_CAST(tb.stl AS INTEGER) AS stl,
                TRY_CAST(tb.blk AS INTEGER) AS blk,
                TRY_CAST(tb.blka AS INTEGER) AS blka,
                TRY_CAST(tb.pf AS INTEGER) AS pf,
                TRY_CAST(tb.pfd AS INTEGER) AS pfd,
                TRY_CAST(tb.plus_minus AS INTEGER) AS plus_minus,
                TRY_CAST(tb.off_rating AS DOUBLE) AS off_rating,
                TRY_CAST(tb.def_rating AS DOUBLE) AS def_rating,
                TRY_CAST(tb.net_rating AS DOUBLE) AS net_rating,
                TRY_CAST(tb.ast_pct AS DOUBLE) AS ast_pct,
                TRY_CAST(tb.ast_to AS DOUBLE) AS ast_to,
                TRY_CAST(tb.ast_ratio AS DOUBLE) AS ast_ratio,
                TRY_CAST(tb.oreb_pct AS DOUBLE) AS oreb_pct,
                TRY_CAST(tb.dreb_pct AS DOUBLE) AS dreb_pct,
                TRY_CAST(tb.reb_pct AS DOUBLE) AS reb_pct,
                TRY_CAST(tb.tm_tov_pct AS DOUBLE) AS tm_tov_pct,
                TRY_CAST(tb.efg_pct AS DOUBLE) AS efg_pct,
                TRY_CAST(tb.ts_pct AS DOUBLE) AS ts_pct,
                TRY_CAST(tb.pace AS DOUBLE) AS pace,
                TRY_CAST(tb.pace_per40 AS DOUBLE) AS pace_per40,
                TRY_CAST(tb.poss AS DOUBLE) AS poss,
                TRY_CAST(tb.pie AS DOUBLE) AS pie,
                TRY_CAST(tb.fta_rate AS DOUBLE) AS fta_rate,
                TRY_CAST(tb.opp_efg_pct AS DOUBLE) AS opp_efg_pct,
                TRY_CAST(tb.opp_fta_rate AS DOUBLE) AS opp_fta_rate,
                TRY_CAST(tb.opp_tov_pct AS DOUBLE) AS opp_tov_pct,
                TRY_CAST(tb.opp_oreb_pct AS DOUBLE) AS opp_oreb_pct,
                TRY_CAST(tb.pts_off_tov AS INTEGER) AS pts_off_tov,
                TRY_CAST(tb.pts_2nd_chance AS INTEGER) AS pts_2nd_chance,
                TRY_CAST(tb.pts_fb AS INTEGER) AS pts_fb,
                TRY_CAST(tb.pts_paint AS INTEGER) AS pts_paint,
                TRY_CAST(tb.opp_pts_off_tov AS INTEGER) AS opp_pts_off_tov,
                TRY_CAST(tb.opp_pts_2nd_chance AS INTEGER) AS opp_pts_2nd_chance,
                TRY_CAST(tb.opp_pts_fb AS INTEGER) AS opp_pts_fb,
                TRY_CAST(tb.opp_pts_paint AS INTEGER) AS opp_pts_paint,
                TRY_CAST(tb.pct_fga_2pt AS DOUBLE) AS pct_fga_2pt,
                TRY_CAST(tb.pct_fga_3pt AS DOUBLE) AS pct_fga_3pt,
                TRY_CAST(tb.pct_pts_2pt AS DOUBLE) AS pct_pts_2pt,
                TRY_CAST(tb.pct_pts_2pt_mr AS DOUBLE) AS pct_pts_2pt_mr,
                TRY_CAST(tb.pct_pts_3pt AS DOUBLE) AS pct_pts_3pt,
                TRY_CAST(tb.pct_pts_fb AS DOUBLE) AS pct_pts_fb,
                TRY_CAST(tb.pct_pts_ft AS DOUBLE) AS pct_pts_ft,
                TRY_CAST(tb.pct_pts_off_tov AS DOUBLE) AS pct_pts_off_tov,
                TRY_CAST(tb.pct_pts_paint AS DOUBLE) AS pct_pts_paint,
                TRY_CAST(tb.pct_ast_2pm AS DOUBLE) AS pct_ast_2pm,
                TRY_CAST(tb.pct_uast_2pm AS DOUBLE) AS pct_uast_2pm,
                TRY_CAST(tb.pct_ast_3pm AS DOUBLE) AS pct_ast_3pm,
                TRY_CAST(tb.pct_uast_3pm AS DOUBLE) AS pct_uast_3pm,
                TRY_CAST(tb.pct_ast_fgm AS DOUBLE) AS pct_ast_fgm,
                TRY_CAST(tb.pct_uast_fgm AS DOUBLE) AS pct_uast_fgm
            FROM tb
        )
        SELECT
            j.*,
            ts.bench_points, ts.biggest_lead, ts.biggest_scoring_run,
            ts.lead_changes, ts.times_tied, ts.timeouts_remaining, ts.coach_id
        FROM (
            -- dedupe in case of repeats
            SELECT * FROM joined
            QUALIFY ROW_NUMBER() OVER (PARTITION BY game_id, team_id ORDER BY pts DESC) = 1
        ) j
        LEFT JOIN (
            SELECT * FROM ts
            QUALIFY ROW_NUMBER() OVER (PARTITION BY game_id, team_id ORDER BY bench_points DESC NULLS LAST) = 1
        ) ts USING (game_id, team_id);
    """)

    step(con, "fact_team_game_period (UNPIVOT q1-q4)", f"""
        INSERT INTO fact_team_game_period
        WITH src AS (
            SELECT * FROM {csv('team_boxscores.csv')}
            WHERE TRY_CAST(game_id AS VARCHAR) IS NOT NULL
              AND TRY_CAST(team_id AS BIGINT) IS NOT NULL
        ),
        unp AS (
            SELECT game_id, TRY_CAST(team_id AS BIGINT) AS team_id, 1::SMALLINT AS period,
                   q1_wl AS wl,
                   TRY_CAST(q1_pts AS INTEGER) AS pts,
                   TRY_CAST(q1_fgm AS INTEGER) AS fgm, TRY_CAST(q1_fga AS INTEGER) AS fga,
                   TRY_CAST(q1_fg3m AS INTEGER) AS fg3m, TRY_CAST(q1_fg3a AS INTEGER) AS fg3a,
                   TRY_CAST(q1_ftm AS INTEGER) AS ftm, TRY_CAST(q1_fta AS INTEGER) AS fta,
                   TRY_CAST(q1_reb AS INTEGER) AS reb, TRY_CAST(q1_ast AS INTEGER) AS ast,
                   TRY_CAST(q1_stl AS INTEGER) AS stl, TRY_CAST(q1_tov AS INTEGER) AS tov,
                   TRY_CAST(q1_plus_minus AS INTEGER) AS plus_minus
            FROM src
            UNION ALL
            SELECT game_id, TRY_CAST(team_id AS BIGINT), 2,
                   q2_wl, TRY_CAST(q2_pts AS INTEGER),
                   TRY_CAST(q2_fgm AS INTEGER), TRY_CAST(q2_fga AS INTEGER),
                   TRY_CAST(q2_fg3m AS INTEGER), TRY_CAST(q2_fg3a AS INTEGER),
                   TRY_CAST(q2_ftm AS INTEGER), TRY_CAST(q2_fta AS INTEGER),
                   TRY_CAST(q2_reb AS INTEGER), TRY_CAST(q2_ast AS INTEGER),
                   TRY_CAST(q2_stl AS INTEGER), TRY_CAST(q2_tov AS INTEGER),
                   TRY_CAST(q2_plus_minus AS INTEGER)
            FROM src
            UNION ALL
            SELECT game_id, TRY_CAST(team_id AS BIGINT), 3,
                   q3_wl, TRY_CAST(q3_pts AS INTEGER),
                   TRY_CAST(q3_fgm AS INTEGER), TRY_CAST(q3_fga AS INTEGER),
                   TRY_CAST(q3_fg3m AS INTEGER), TRY_CAST(q3_fg3a AS INTEGER),
                   TRY_CAST(q3_ftm AS INTEGER), TRY_CAST(q3_fta AS INTEGER),
                   TRY_CAST(q3_reb AS INTEGER), TRY_CAST(q3_ast AS INTEGER),
                   TRY_CAST(q3_stl AS INTEGER), TRY_CAST(q3_tov AS INTEGER),
                   TRY_CAST(q3_plus_minus AS INTEGER)
            FROM src
            UNION ALL
            SELECT game_id, TRY_CAST(team_id AS BIGINT), 4,
                   q4_wl, TRY_CAST(q4_pts AS INTEGER),
                   TRY_CAST(q4_fgm AS INTEGER), TRY_CAST(q4_fga AS INTEGER),
                   TRY_CAST(q4_fg3m AS INTEGER), TRY_CAST(q4_fg3a AS INTEGER),
                   TRY_CAST(q4_ftm AS INTEGER), TRY_CAST(q4_fta AS INTEGER),
                   TRY_CAST(q4_reb AS INTEGER), TRY_CAST(q4_ast AS INTEGER),
                   TRY_CAST(q4_stl AS INTEGER), TRY_CAST(q4_tov AS INTEGER),
                   TRY_CAST(q4_plus_minus AS INTEGER)
            FROM src
        )
        SELECT game_id, team_id, period, wl,
               pts, fgm, fga, fg3m, fg3a, ftm, fta,
               reb, ast, stl, tov, plus_minus
        FROM unp
        WHERE pts IS NOT NULL
        QUALIFY ROW_NUMBER() OVER (PARTITION BY game_id, team_id, period ORDER BY pts DESC) = 1;
    """)

    # ── 5. Player-game stats ───────────────────────────────────────────────
    print("\n[5/8] Player-game stats")

    step(con, "fact_player_game_stats", f"""
        INSERT INTO fact_player_game_stats
        WITH ps AS (
            SELECT * FROM {csv('PlayerStatistics.csv')}
            WHERE TRY_CAST(personId AS BIGINT) IS NOT NULL
              AND gameId IS NOT NULL
        ),
        pe AS (
            SELECT
                LPAD(gameId, 10, '0') AS gameId, TRY_CAST(personId AS BIGINT) AS person_id,
                TRY_CAST(offensiveRating AS DOUBLE) AS off_rating,
                TRY_CAST(defensiveRating AS DOUBLE) AS def_rating,
                TRY_CAST(netRating AS DOUBLE) AS net_rating,
                TRY_CAST(assistPercentage AS DOUBLE) AS ast_pct,
                TRY_CAST(assistToTurnoverRatio AS DOUBLE) AS ast_to_turnover_ratio,
                TRY_CAST(assistRatio AS DOUBLE) AS ast_ratio,
                TRY_CAST(offensiveReboundPercentage AS DOUBLE) AS oreb_pct,
                TRY_CAST(defensiveReboundPercentage AS DOUBLE) AS dreb_pct,
                TRY_CAST(reboundPercentage AS DOUBLE) AS reb_pct,
                TRY_CAST(estimatedTurnoverPercentage AS DOUBLE) AS tov_pct,
                TRY_CAST(effectiveFieldGoalPercentage AS DOUBLE) AS efg_pct,
                TRY_CAST(trueShootingPercentage AS DOUBLE) AS ts_pct,
                TRY_CAST(usagePercentage AS DOUBLE) AS usg_pct,
                TRY_CAST(pace AS DOUBLE) AS pace,
                TRY_CAST(playerImpactEstimate AS DOUBLE) AS pie
            FROM {csv('PlayerStatisticsExtended.csv')}
            QUALIFY ROW_NUMBER() OVER (PARTITION BY gameId, person_id ORDER BY off_rating DESC NULLS LAST) = 1
        ),
        joined AS (
            SELECT
                LPAD(ps.gameId, 10, '0') AS game_id,
                TRY_CAST(ps.personId AS BIGINT) AS person_id,
                TRY_CAST(ps.playerteamId AS BIGINT) AS team_id,
                TRY_CAST(ps.opponentteamId AS BIGINT) AS opponent_team_id,
                TRY_CAST(ps.home AS INTEGER)::BOOLEAN AS is_home,
                TRY_CAST(ps.win AS INTEGER)::BOOLEAN AS is_win,
                ps.startingPosition AS starting_position,
                ps.comment,
                TRY_CAST(ps.numMinutes AS DOUBLE) AS num_minutes,
                TRY_CAST(ps.points AS INTEGER) AS points,
                TRY_CAST(ps.assists AS INTEGER) AS assists,
                TRY_CAST(ps.blocks AS INTEGER) AS blocks,
                TRY_CAST(ps.steals AS INTEGER) AS steals,
                TRY_CAST(ps.turnovers AS INTEGER) AS turnovers,
                TRY_CAST(ps.fieldGoalsAttempted AS INTEGER) AS fga,
                TRY_CAST(ps.fieldGoalsMade AS INTEGER) AS fgm,
                TRY_CAST(ps.fieldGoalsPercentage AS DOUBLE) AS fg_pct,
                TRY_CAST(ps.threePointersAttempted AS INTEGER) AS fg3a,
                TRY_CAST(ps.threePointersMade AS INTEGER) AS fg3m,
                TRY_CAST(ps.threePointersPercentage AS DOUBLE) AS fg3_pct,
                TRY_CAST(ps.freeThrowsAttempted AS INTEGER) AS fta,
                TRY_CAST(ps.freeThrowsMade AS INTEGER) AS ftm,
                TRY_CAST(ps.freeThrowsPercentage AS DOUBLE) AS ft_pct,
                TRY_CAST(ps.reboundsOffensive AS INTEGER) AS oreb,
                TRY_CAST(ps.reboundsDefensive AS INTEGER) AS dreb,
                TRY_CAST(ps.reboundsTotal AS INTEGER) AS reb,
                TRY_CAST(ps.foulsPersonal AS INTEGER) AS fouls_personal,
                TRY_CAST(ps.plusMinusPoints AS INTEGER) AS plus_minus,
                pe.off_rating, pe.def_rating, pe.net_rating,
                pe.ast_pct, pe.ast_to_turnover_ratio, pe.ast_ratio,
                pe.oreb_pct, pe.dreb_pct, pe.reb_pct,
                pe.tov_pct, pe.efg_pct, pe.ts_pct,
                pe.usg_pct, pe.pace, pe.pie
            FROM ps
            LEFT JOIN pe
              ON pe.gameId = LPAD(ps.gameId, 10, '0')
             AND pe.person_id = TRY_CAST(ps.personId AS BIGINT)
        )
        SELECT * FROM joined
        QUALIFY ROW_NUMBER() OVER (PARTITION BY game_id, person_id ORDER BY points DESC NULLS LAST) = 1;
    """)

    # ── 6. Play-by-play ────────────────────────────────────────────────────
    if args.skip_pbp:
        print("\n[6/8] Play-by-play SKIPPED (--skip-pbp)")
    else:
        print("\n[6/8] Play-by-play (~18M rows)")
        # Strategy: load raw into a temp table (no PK), then SELECT DISTINCT into the
        # PK-enforced fact table. This avoids the giant window-function OOM.
        step(con, "stage pbp raw", f"""
            CREATE TEMP TABLE _pbp_raw AS
            SELECT
                game_id,
                TRY_CAST(action_number AS INTEGER) AS action_number,
                TRY_CAST(period AS SMALLINT) AS period,
                clock,
                CASE WHEN clock LIKE 'PT%M%S' THEN
                    (CASE WHEN TRY_CAST(period AS INTEGER) <= 4
                          THEN (TRY_CAST(period AS INTEGER) - 1) * 720
                          ELSE 4 * 720 + (TRY_CAST(period AS INTEGER) - 5) * 300 END)
                    + (CASE WHEN TRY_CAST(period AS INTEGER) <= 4 THEN 720 ELSE 300 END)
                    - (TRY_CAST(regexp_extract(clock, 'PT(\\d+)M', 1) AS DOUBLE) * 60
                       + TRY_CAST(regexp_extract(clock, 'M([0-9.]+)S', 1) AS DOUBLE))
                END AS seconds_elapsed,
                NULLIF(TRY_CAST(team_id AS BIGINT), 0) AS team_id,
                NULLIF(TRY_CAST(person_id AS BIGINT), 0) AS person_id,
                team_tri_code,
                player_name,
                TRY_CAST(action_id AS BIGINT) AS action_id,
                action_type, subtype, description,
                TRY_CAST(is_field_goal AS INTEGER)::BOOLEAN AS is_field_goal,
                TRY_CAST(shot_value AS SMALLINT) AS shot_value,
                TRY_CAST(shot_distance AS DOUBLE) AS shot_distance,
                shot_result,
                TRY_CAST(xlegacy AS SMALLINT) AS x_legacy,
                TRY_CAST(ylegacy AS SMALLINT) AS y_legacy,
                location,
                TRY_CAST(score_home AS INTEGER) AS score_home,
                TRY_CAST(score_away AS INTEGER) AS score_away,
                TRY_CAST(points_total AS INTEGER) AS points_total,
                TRY_CAST(video_available AS INTEGER)::BOOLEAN AS video_available,
                TRY_CAST(game_date AS DATE) AS game_date
            FROM {csv('play_by_play.csv')}
            WHERE game_id IS NOT NULL
              AND TRY_CAST(action_number AS INTEGER) IS NOT NULL;
        """)

        # ON CONFLICT DO NOTHING handles the dedup without a giant window function.
        step(con, "fact_play_by_play (dedup insert)", """
            INSERT INTO fact_play_by_play
            SELECT * FROM _pbp_raw
            ON CONFLICT (game_id, action_number) DO NOTHING;
        """)
        step(con, "drop staging", "DROP TABLE _pbp_raw;")

    # ── 7. Odds ────────────────────────────────────────────────────────────
    print("\n[7/8] Odds")

    step(con, "fact_game_odds_snapshot", f"""
        INSERT INTO fact_game_odds_snapshot
        WITH src AS (
            SELECT
                game_id, odds_date,
                TRY_CAST(last_fetched AS TIMESTAMP) AS last_fetched,
                TRY_CAST(decimal_home AS DOUBLE) AS decimal_home,
                TRY_CAST(decimal_away AS DOUBLE) AS decimal_away,
                TRY_CAST(moneyline_home AS INTEGER) AS moneyline_home,
                TRY_CAST(moneyline_away AS INTEGER) AS moneyline_away,
                source_url
            FROM {csv('game_odds.csv')}
            WHERE game_id IS NOT NULL AND odds_date IS NOT NULL
        )
        SELECT * FROM src
        QUALIFY ROW_NUMBER() OVER (PARTITION BY game_id, odds_date ORDER BY last_fetched DESC NULLS LAST) = 1;
    """)

    # Pinnacle main lines: build a name lookup from current franchise rows.
    step(con, "fact_game_main_line", f"""
        INSERT INTO fact_game_main_line
        WITH lookup AS (
            SELECT team_id, team_city || ' ' || team_name AS full_name
            FROM v_team_current
        ),
        regular AS (
            SELECT team1, team2, game_link,
                   TRY_CAST(timestamp AS TIMESTAMP) AS snapshot_ts,
                   TRY_CAST(team1_moneyline AS DOUBLE) AS team1_moneyline,
                   TRY_CAST(team2_moneyline AS DOUBLE) AS team2_moneyline,
                   TRY_CAST(team1_spread AS DOUBLE) AS team1_spread,
                   TRY_CAST(team1_spread_odds AS DOUBLE) AS team1_spread_odds,
                   TRY_CAST(team2_spread AS DOUBLE) AS team2_spread,
                   TRY_CAST(team2_spread_odds AS DOUBLE) AS team2_spread_odds,
                   TRY_CAST(over_total AS DOUBLE) AS over_total,
                   TRY_CAST(over_total_odds AS DOUBLE) AS over_total_odds,
                   TRY_CAST(under_total AS DOUBLE) AS under_total,
                   TRY_CAST(under_total_odds AS DOUBLE) AS under_total_odds,
                   FALSE AS is_preseason
            FROM {csv('nba_main_lines.csv')}
            WHERE game_link IS NOT NULL
        ),
        preseason AS (
            SELECT team1, team2, game_link,
                   TRY_CAST(timestamp AS TIMESTAMP),
                   TRY_CAST(team1_moneyline AS DOUBLE), TRY_CAST(team2_moneyline AS DOUBLE),
                   TRY_CAST(team1_spread AS DOUBLE), TRY_CAST(team1_spread_odds AS DOUBLE),
                   TRY_CAST(team2_spread AS DOUBLE), TRY_CAST(team2_spread_odds AS DOUBLE),
                   TRY_CAST(over_total AS DOUBLE), TRY_CAST(over_total_odds AS DOUBLE),
                   TRY_CAST(under_total AS DOUBLE), TRY_CAST(under_total_odds AS DOUBLE),
                   TRUE
            FROM {csv('nba_preseason_main_lines.csv')}
            WHERE game_link IS NOT NULL
        ),
        combined AS (
            SELECT * FROM regular UNION ALL SELECT * FROM preseason
        )
        SELECT
            game_link, ANY_VALUE(snapshot_ts),
            ANY_VALUE(team1), ANY_VALUE(team2),
            ANY_VALUE(t1.team_id), ANY_VALUE(t2.team_id),
            ANY_VALUE(is_preseason),
            ANY_VALUE(team1_moneyline), ANY_VALUE(team2_moneyline),
            ANY_VALUE(team1_spread), ANY_VALUE(team1_spread_odds),
            ANY_VALUE(team2_spread), ANY_VALUE(team2_spread_odds),
            ANY_VALUE(over_total), ANY_VALUE(over_total_odds),
            ANY_VALUE(under_total), ANY_VALUE(under_total_odds)
        FROM combined c
        LEFT JOIN lookup t1 ON t1.full_name = c.team1
        LEFT JOIN lookup t2 ON t2.full_name = c.team2
        GROUP BY game_link;
    """)

    step(con, "fact_game_market_odds", f"""
        INSERT INTO fact_game_market_odds
        SELECT
            "Market", "Selection",
            TRY_CAST("Odds" AS DOUBLE),
            matchup,
            TRY_CAST(timestamp AS TIMESTAMP),
            FALSE
        FROM {csv('nba_detailed_odds.csv')}
        WHERE matchup IS NOT NULL AND TRY_CAST(timestamp AS TIMESTAMP) IS NOT NULL
        UNION ALL
        SELECT
            "Market", "Selection",
            TRY_CAST("Odds" AS DOUBLE),
            matchup,
            TRY_CAST(timestamp AS TIMESTAMP),
            TRUE
        FROM {csv('nba_preseason_detailed_odds.csv')}
        WHERE matchup IS NOT NULL AND TRY_CAST(timestamp AS TIMESTAMP) IS NOT NULL;
    """)

    # ── 8. Indexes & validation ────────────────────────────────────────────
    print("\n[8/8] Indexes & validation")
    con.execute((SQL_DIR / "08_indexes.sql").read_text())

    print("\nRow counts:")
    rows = con.execute((SQL_DIR / "09_validate.sql").read_text()).fetchall()
    for tname, cnt in rows:
        print(f"  {tname:30s} {cnt:>12,}")

    # Referential checks
    print("\nReferential integrity (each should be 0):")
    checks = [
        ("player_game_stats with unknown person_id",
         "SELECT COUNT(*) FROM fact_player_game_stats "
         "WHERE person_id NOT IN (SELECT person_id FROM dim_player)"),
        ("team_game_stats with unknown team_id",
         "SELECT COUNT(*) FROM fact_team_game_stats "
         "WHERE team_id NOT IN (SELECT team_id FROM dim_team)"),
        ("player_game_stats with unknown game_id",
         "SELECT COUNT(*) FROM fact_player_game_stats "
         "WHERE game_id NOT IN (SELECT game_id FROM fact_game)"),
    ]
    if not args.skip_pbp:
        checks.append((
            "play_by_play with unknown game_id",
            "SELECT COUNT(*) FROM fact_play_by_play "
            "WHERE game_id NOT IN (SELECT game_id FROM fact_game)"))
    for label, q in checks:
        print(f"  {label:50s} {con.execute(q).fetchone()[0]:>10,}")

    con.close()
    size_gb = DB_PATH.stat().st_size / 1e9
    print(f"\nDone in {time.perf_counter() - overall:.1f}s -- {DB_PATH.name} ({size_gb:.2f} GB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
