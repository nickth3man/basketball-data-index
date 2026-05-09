# Basketball Data

A collection of basketball datasets covering NBA game logs, play-by-play records, player and team statistics, betting odds, NCAA/WNBA odds, and international league odds.

## Directory Structure

```
basketball-data/
├── csv/            # All CSV data files
├── html/           # HTML debug/scraping artifacts
├── notebooks/      # Jupyter notebooks
├── parquet/        # Parquet-format data files
└── sql/            # SQLite databases
```

---

## csv/

Contains 600+ CSV files split between NBA-specific data in `csv/nba/` and other basketball league/competition data in `csv/other/`.

### CSV Layout

| Directory | Description |
|-----------|-------------|
| `csv/nba/` | NBA game logs, schedules, play-by-play, player/team stats, NBA odds, and NBA metadata files |
| `csv/other/` | NCAA, WNBA, international, club, national league, and other basketball odds files |

### NBA Game Data

| File | Description |
|------|-------------|
| `Games.csv` | NBA game results with scores, teams, arena, officials, game type (regular season / playoffs) |
| `Games1.csv` | Alternative NBA games index with similar schema |
| `games_index.csv` | Condensed game index with odds, home/away, winner, margin |
| `games_schedule.csv` | Full schedule including future games and series metadata |
| `LeagueSchedule24_25.csv` | 2024–25 season schedule |
| `LeagueSchedule25_26.csv` | 2025–26 season schedule |

### Play-by-Play

| File | Description |
|------|-------------|
| `pbp1997.csv` – `pbp2026.csv` | Season-by-season play-by-play from 1996–97 through 2025–26. Columns: `gameid`, `period`, `clock`, `team`, `player`, `type`, `subtype`, `result`, `x`, `y`, `dist`, `desc` |
| `play_by_play.csv` | Current-season play-by-play with extended columns: `action_type`, `shot_result`, `shot_value`, `score_home`, `score_away`, `video_available` |
| `PlayByPlay.parquet` *(in parquet/)* | Play-by-play in Parquet format |

### Player & Team Boxscores

| File | Description |
|------|-------------|
| `player_boxscores.csv` | Per-game player stats with 170+ columns including traditional, advanced, and on/off split metrics |
| `PlayerStatistics.csv` | Per-game player stats (points, rebounds, assists, etc.) |
| `PlayerStatisticsExtended.csv` | Extended player stats |
| `team_boxscores.csv` | Per-game team stats with quarter-by-quarter breakdowns and advanced metrics |
| `TeamStatistics.csv` | Per-game team stats |
| `TeamStatisticsExtended.csv` | Extended team stats |

### Scraped NBA Team Boxscores

| File | Description |
|------|-------------|
| `games_traditional.csv` | Traditional team box score stats per game |
| `games_advanced.csv` | Advanced team metrics including ratings, pace, and PIE |
| `games_four-factors.csv` | Four factors stats including eFG%, turnover rate, rebound rate, and free throw rate |
| `games_misc.csv` | Miscellaneous team stats including points off turnovers, fast break points, and paint points |
| `games_scoring.csv` | Team scoring breakdown by shot type and assisted/unassisted field goals |
| `games_boxscores.csv` | Home/away combined team boxscore view per game |
| `teams_boxscores.csv` | Team-level boxscores with combined traditional, advanced, four factors, misc, and scoring stats |
| `data_dictionary.csv` | Column descriptions for all non-metadata CSV data files in `csv/nba/` using repo-relative paths; excludes `data_dictionary.csv` itself |
| `column_mapping.json` | Mapping of observed `csv/nba/` CSV column names to standardized snake_case names |

### Rosters & Histories

| File | Description |
|------|-------------|
| `Players.csv` | Player directory with biographical info (birth date, school, country, height, weight, draft info) |
| `TeamHistories.csv` | Historical team records |

### NBA Betting Odds

| File | Description |
|------|-------------|
| `game_odds.csv` | NBA moneyline odds (open and close) sourced from TeamRankings |
| `nba_main_lines.csv` | NBA moneyline, spread, and totals from Pinnacle |
| `nba_detailed_odds.csv` | NBA detailed market-level odds (Money Line, Total) with timestamps |
| `nba_preseason_main_lines.csv` | NBA preseason main lines |
| `nba_preseason_detailed_odds.csv` | NBA preseason detailed odds |

### Other Basketball Odds

NCAA, WNCAA, WNBA, international, club, and national league odds live under `csv/other/`. Files generally follow the naming convention `{league}_main_lines.csv` and `{league}_detailed_odds.csv`.

### International League Odds

Odds data (main lines + detailed) for 250+ basketball leagues and competitions worldwide lives under `csv/other/`.

Regions covered include Europe (EuroLeague, EuroCup, national leagues across 30+ countries), the Americas (NBA G League adjacent competitions, South American leagues), Asia-Pacific (Japan B-League, Chinese CBA, Korean KBL, Australian NBL), Africa, and the Middle East, as well as FIBA international competitions.

---

## sql/

SQLite databases for querying the data without loading CSVs directly.

| File | Description |
|------|-------------|
| `nba_stats.sqlite` | NBA game and team statistics |
| `nba_stats_pbp.sqlite` | Play-by-play data |

---

## notebooks/

| File | Description |
|------|-------------|
| `__notebook__.ipynb` | Jupyter notebook for data exploration and analysis |

---

## html/

| File | Description |
|------|-------------|
| `debug_page.html` | HTML page captured during data scraping (debugging artifact) |

---

## Data Notes

- Play-by-play files (`pbp1997.csv`–`pbp2026.csv`) cover 30 seasons from 1996–97 through 2025–26.
- Odds data uses decimal format. Main lines files include spread and totals in addition to moneyline.
- `Games.csv` and `Games1.csv` contain the same schema but originate from different scraping pipelines; `Games.csv` uses a full 11-digit `gameId` while `Games1.csv` uses an 8-digit format.
- International odds files without a `_detailed_odds.csv` counterpart have main lines data only.
