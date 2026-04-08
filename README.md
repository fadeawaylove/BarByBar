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

`uv run python -m barbybar.app` starts the desktop app directly.

By default, the app stores data under the `data` folder next to the project or packaged `.exe`.

- Database: `data\barbybar.db`
- Logs: `data\logs\`

This makes the packaged app portable. If you copy the whole folder onto a USB drive, your data goes with it.

You can still override the data location with `BARBYBAR_DATA_DIR` when needed.

## Common Commands

```powershell
uv run pytest -q
uv run python -m barbybar.app
uv run python -m barbybar.desktop_app
uv run pyinstaller --clean --noconfirm BarByBar.spec
.\scripts\build_release.ps1
.\scripts\build_installer.ps1
.\scripts\publish_release.ps1 -BumpVersion 0.1.0 -StageAll
```

## Release

BarByBar publishes a Windows portable ZIP and a Windows setup installer to GitHub Releases. The release flow is split into two stages so packaging can be validated before you burn a version tag.

```powershell
# 1. run the Package workflow on your target commit and verify both artifacts
# 2. publish the validated commit with a new version tag
.\scripts\publish_release.ps1 -BumpVersion 0.1.0 -StageAll
```

The GitHub Actions workflows are:

- `Package`: manual or `master` push validation, uploads build artifacts only
- `Release`: tag-triggered publication after the commit has already been validated

The release artifacts are:

- `BarByBar-vX.Y.Z-windows-x64.zip`
- `BarByBar-vX.Y.Z-windows-x64-setup.exe`

For a local packaging dry run:

```powershell
uv sync --group release
.\scripts\build_release.ps1 -Tag v0.1.0
.\scripts\build_installer.ps1 -Tag v0.1.0
```

The setup installer installs per-user under `%LOCALAPPDATA%\Programs\BarByBar`. The portable ZIP remains the best choice if you want the app and data to live together on a USB drive.

## Logs

The app stores runtime logs under `data\logs` by default, or under `BARBYBAR_DATA_DIR\logs` if you override the data directory.

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
