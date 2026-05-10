# AGENTS.md

Instructions for AI coding agents working in this repository.

## Project overview

Basketball data repository — CSV, SQLite, Parquet, and notebook files spanning NBA, NCAA, WNBA, and international leagues.

| Directory    | Purpose                                                  |
| ------------ | -------------------------------------------------------- |
| `csv/`        | 600+ CSV files: NBA game data, play-by-play, odds        |
| `sql/`        | SQLite databases (`nba_stats.sqlite`, `nba_stats_pbp.sqlite`) |
| `parquet/`    | Parquet-format data files (e.g., `PlayByPlay.parquet`)       |
| `notebooks/`   | Jupyter notebooks for exploration and analysis           |
| `html/`       | HTML debugging/scraping artifacts                        |
| `projects/`    | Sub-projects (e.g., `db-viz`)                                |

Data is READ-ONLY. Never modify files in `csv/`, `sql/`, `parquet/`, `notebooks/`, or `html/` unless explicitly instructed.

## Setup & verification

One-shot commands only. Never run long-running/blocking commands in the `bash` tool.

```
# Windows (preferred — uses PowerShell)
python -c "import sqlite3; sqlite3.connect('sql/nba_stats.sqlite')"
python -c "import pandas as pd; pd.read_parquet('parquet/PlayByPlay.parquet')"

# Lint/format (if applicable)
python -m ruff check .
python -m ruff format --check .
```

## Background / long-running processes

OpenCode's built-in `bash` tool runs commands synchronously — the agent blocks until the process exits. Any command that does not exit on its own will hang the agent forever.

### Rules

- MUST NOT run any of the following directly in the `bash` tool:
  - `npm run dev`, `pnpm dev`, `yarn dev`
  - `npm test -- --watch`, `vitest --watch`
  - `cargo watch`, `cargo run`
  - `python -m http.server`, `uvicorn`, `flask run`
  - Any database server, proxy, tunnel, or REPL
  - Any interactive program (python repl, node repl, sqlite3 interactive)
- MUST use `pty_spawn` (from the `opencode-pty` plugin) as the primary method for background processes
- If `pty_spawn` is unavailable, use the `dev-server` skill (`.opencode/skills/dev-server/SKILL.md`) for PowerShell-based backgrounding
- Always store process output in `.opencode/logs/<name>.log` and PID in `.opencode/pids/<name>.pid`
- Always clean up stale processes from prior sessions before starting new ones
- Always verify a server is reachable (curl/wget/Invoke-WebRequest) before proceeding to depend on it

### Windows backgrounding quick reference

```powershell
# Start (PowerShell — preferred)
$proc = Start-Process -FilePath "npm" -ArgumentList "run","dev" -NoNewWindow -PassThru -RedirectStandardOutput ".opencode\logs\dev-server.log" -RedirectStandardError ".opencode\logs\dev-server.err.log"
$proc.Id | Out-File -FilePath ".opencode\pids\dev-server.pid" -NoNewline

# Check output
Get-Content ".opencode\logs\dev-server.log" -Tail 50

# Kill
$pid = Get-Content ".opencode\pids\dev-server.pid"
Stop-Process -Id $pid -Force
```

### Platform notes

- The configured OpenCode shell is Git Bash (`C:\Program Files\Git\bin\bash.exe`). Backgrounding with `&` works but orphan cleanup is unreliable on Windows — prefer PowerShell `Start-Process` patterns.
- PowerShell execution policy may need `-ExecutionPolicy Bypass` for inline scripts.
- `cmd /c` redirection (`>`) is buffered; use `Start-Process -RedirectStandardOutput` for reliable log capture.

## File conventions

- CSV files use UTF-8 encoding unless otherwise noted
- SQLite databases: query with `sqlite3` CLI or Python `sqlite3` module
- Parquet files: read with `pandas.read_parquet()` or `pyarrow`
- `.opencode/` directory contains agent artifacts (logs, PIDs, skills) — gitignored

## Task routing

- Data analysis / exploration: work in `notebooks/` or create Python scripts
- SQL queries: query `sql/nba_stats.sqlite` or `sql/nba_stats_pbp.sqlite`
- Web scraping / data collection: output to `csv/` with consistent naming
- Visualization / dashboards: use `projects/db-viz/` or `html/`
- Documentation: update `README.md`

## Constraints

- READ-ONLY: `csv/`, `sql/`, `parquet/`, `notebooks/`, `html/`
- NEVER commit API keys, tokens, or credentials
- NEVER use interactive git commands (`rebase -i`, `add -i`)
- NEVER create files in the repo root without explicit instruction (use appropriate subdirectory)
