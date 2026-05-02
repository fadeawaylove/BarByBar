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
.\scripts\publish_release.ps1 patch
```

## Release

BarByBar publishes a Windows portable ZIP and a Windows setup installer to GitHub Releases when you push a version tag that points at a commit already contained in `master`.

```powershell
# 1. make sure the feature commits you want to release are already on master
# 2. run the publish script to bump the version, create the release commit, and push the tag
.\scripts\publish_release.ps1 patch
```

`publish_release.ps1` verifies that:

- the working tree is clean
- the current branch is `master`

Then it automatically:

- bumps `src\barbybar\__init__.py` to the next semantic version
- creates a `Release vX.Y.Z` commit when the version file needs a bump
- pushes `master`
- creates and pushes the matching tag

The release workflow summarizes the commits between the previous tag and the current tag into Chinese release notes automatically, and filters out the release bump commit from the summary.

The GitHub Actions workflows are:

- `Package`: manual-only packaging validation, uploads workflow artifacts only
- `Release`: tag-triggered publication, and it fails if the tagged commit is not in `master`

The release artifacts are:

- `BarByBar-vX.Y.Z-windows-x64.zip`
- `BarByBar-vX.Y.Z-windows-x64-setup.exe`

For a local packaging dry run:

```powershell
uv sync --group release
.\scripts\build_release.ps1 -Tag v0.1.0
.\scripts\build_installer.ps1 -Tag v0.1.0
```

The setup installer defaults to `%LOCALAPPDATA%\Programs\BarByBar`, but it now lets you choose any writable install directory during setup, including a USB drive.

When the packaged app runs, it stores its runtime data next to the installed executable under `data\`. That means if you install BarByBar onto a USB drive, the app binary, database, logs, and other runtime files all move together when you plug that drive into another Windows machine.

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
