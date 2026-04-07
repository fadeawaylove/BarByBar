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
```

## Release

BarByBar publishes both a Windows portable ZIP and a Windows MSI installer to GitHub Releases when you push a version tag.

```powershell
# 1. update src/barbybar/__init__.py version
# 2. commit your changes
git tag v0.1.0
git push origin master --follow-tags
```

The release workflow will:

- sync dependencies with `uv`
- run the test suite
- build the Windows GUI app with `PyInstaller`
- build the Windows MSI installer with `WiX Toolset`
- upload `BarByBar-vX.Y.Z-windows-x64.zip` and `BarByBar-X.Y.Z-windows-x64.msi` to GitHub Releases

For a local packaging dry run:

```powershell
uv sync --group dev --group release
.\scripts\build_release.ps1 -Tag v0.1.0
.\scripts\build_installer.ps1 -Tag v0.1.0 -WixBin "C:\Program Files (x86)\WiX Toolset v3.11\bin"
```

The MSI installer defaults to a writable per-user directory and upgrades in place. If you want the app and data to live on a USB drive, choose your USB directory during installation.

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
