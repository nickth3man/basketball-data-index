-- Canned queries for the SQL Lab.
-- Format: each query begins with `-- @name <Display Name>` on its own line.

-- @name LeBron points by season
SELECT g.season_year, SUM(pgs.points) AS pts, COUNT(*) AS games
FROM fact_player_game_stats pgs
JOIN dim_player p USING (person_id)
JOIN fact_game g USING (game_id)
WHERE p.first_name = 'LeBron' AND p.last_name = 'James'
GROUP BY g.season_year ORDER BY g.season_year;

-- @name Curry career 3-point splits
SELECT shot_result, COUNT(*) AS attempts,
       ROUND(AVG(shot_distance), 1) AS avg_dist_ft
FROM fact_play_by_play pbp
JOIN dim_player p USING (person_id)
WHERE p.first_name = 'Stephen' AND p.last_name = 'Curry'
  AND pbp.shot_value = 3 AND pbp.is_field_goal
GROUP BY shot_result;

-- @name 2024-25 OffRtg leaders
SELECT t.team_city || ' ' || t.team_name AS team,
       ROUND(AVG(tgs.off_rating), 2) AS off_rtg,
       COUNT(*) AS games
FROM fact_team_game_stats tgs
JOIN v_team_current t USING (team_id)
JOIN fact_game g USING (game_id)
WHERE g.season_year = '2024-25' AND g.season_type = 'Regular'
GROUP BY team HAVING COUNT(*) > 30
ORDER BY off_rtg DESC LIMIT 15;

-- @name Highest single-game scoring outputs
SELECT p.first_name || ' ' || p.last_name AS player,
       g.game_date, pgs.points,
       pgs.fgm || '-' || pgs.fga AS fg,
       pgs.fg3m || '-' || pgs.fg3a AS fg3,
       pgs.ftm || '-' || pgs.fta AS ft
FROM fact_player_game_stats pgs
JOIN dim_player p USING (person_id)
JOIN fact_game g USING (game_id)
ORDER BY pgs.points DESC NULLS LAST LIMIT 25;

-- @name Officials by total games worked
SELECT official_name, COUNT(*) AS games
FROM fact_game_official
GROUP BY official_name ORDER BY games DESC LIMIT 25;

-- @name Closing-line coverage by season
SELECT g.season_year, COUNT(DISTINCT g.game_id) AS games_with_open_line
FROM fact_game g JOIN fact_game_odds_snapshot o USING (game_id)
WHERE o.odds_date = 'open'
GROUP BY g.season_year ORDER BY g.season_year DESC;

-- @name Quarter-by-quarter totals for a single team
SELECT period, AVG(pts) AS avg_pts, COUNT(*) AS team_games
FROM fact_team_game_period p
JOIN fact_game g USING (game_id)
WHERE p.team_id = 1610612747  -- Lakers
  AND g.season_year = '2023-24'
GROUP BY period ORDER BY period;

-- @name Most common 3-ref crews
WITH crew AS (
  SELECT game_id,
         STRING_AGG(official_name, ' / ' ORDER BY official_name) AS crew_str
  FROM fact_game_official GROUP BY game_id HAVING COUNT(*) = 3
)
SELECT crew_str, COUNT(*) AS games
FROM crew GROUP BY crew_str ORDER BY games DESC LIMIT 10;

-- @name Arenas hosting multiple franchises
SELECT a.arena_name, a.arena_city,
       COUNT(DISTINCT g.home_team_id) AS distinct_home_teams,
       COUNT(*) AS games
FROM dim_arena a JOIN fact_game g USING (arena_id)
GROUP BY a.arena_name, a.arena_city
HAVING COUNT(DISTINCT g.home_team_id) > 1
ORDER BY distinct_home_teams DESC;

-- @name Schema browser (information_schema)
SELECT table_name, COUNT(*) AS columns
FROM information_schema.columns
WHERE table_schema = 'main'
GROUP BY table_name ORDER BY table_name;
