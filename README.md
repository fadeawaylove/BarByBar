# BarByBar

BarByBar is a Windows desktop review trainer for stepping through futures bars one candle at a time.

## Features

- Import minute-level OHLCV data from local CSV files
- Create review sessions with hidden future bars
- Step forward, step backward, and jump to a target bar
- Record trading decisions, notes, stop-loss, and take-profit rules
- Save sessions and actions into a local SQLite case library
- Review past sessions with basic performance statistics

## Quick Start

```powershell
uv sync --group dev
uv run python -m barbybar.app
```

The app stores its SQLite database under `%USERPROFILE%\.barbybar\barbybar.db`.

## Common Commands

```powershell
uv run pytest -q
uv run python -m barbybar.app
```

## Logs

The app stores runtime logs under `%USERPROFILE%\.barbybar\logs`.

- `app.log`: all application logs at `DEBUG` and above
- `error.log`: error and exception logs only

When diagnosing slow loads, import failures, or background worker issues, check `app.log` first and then `error.log` for stack traces.

## Assets

The application window icon is stored at [src/barbybar/assets/barbybar-icon.svg](/C:/code/BarByBar/src/barbybar/assets/barbybar-icon.svg).

## CSV Format

The importer supports configurable column mapping, but the target schema is:

- `datetime`
- `open`
- `high`
- `low`
- `close`
- `volume`
