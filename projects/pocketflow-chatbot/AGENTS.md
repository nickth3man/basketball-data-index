# pocketflow-chatbot

NBA Basketball Chatbot built with PocketFlow, DuckDB, and Gradio.

## Dev Environment

- **Package manager**: uv — all commands via `uv run ...`
- **Python**: 3.12+ (`.python-version` pins 3.12)
- **Deps**: `uv sync` to install everything (runtime + dev)

## Commands

```sh
uv sync                          # Install all deps (run after cloning or pulling new deps)
uv add <package>                 # Add a runtime dependency
uv add --dev <package>           # Add a dev dependency
uv run python <file.py>          # Run any Python file
```

### Lint & Format (ruff)

```sh
uv run ruff check .              # Lint all .py files
uv run ruff check --fix .        # Lint + auto-fix
uv run ruff format .             # Format all .py files
uv run ruff format --check .     # Check formatting (CI use)
```

### Type Check (ty + pyright)

```sh
uv run ty check .                # Fast type-check with ty
uv run pyright .                 # Full type-check with pyright
```

### Test (pytest)

```sh
uv run pytest                    # Run all tests
uv run pytest -v                 # Run all tests (verbose)
uv run pytest -k "keyword"       # Run tests matching keyword
uv run pytest tests/test_file.py # Run a specific test file
```

### All Checks (CI pipeline)

```sh
uv run ruff check . && uv run ruff format --check . && uv run ty check . && uv run pyright . && uv run pytest
```

## Conventions

- **ruff** handles both linting and formatting — don't use other formatters
- **ty** for fast type-check during development, **pyright** for comprehensive checks
- **pytest** for all testing; tests live in `tests/`
- Type annotations required on all function signatures
