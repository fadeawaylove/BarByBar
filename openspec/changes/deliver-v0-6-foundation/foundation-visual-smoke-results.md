# Foundation Visual and Packaged-App Smoke Results

Measurement date: 2026-07-20

## Critical-state screenshot matrix

The reproducible capture script generated and the reviewer inspected 19 current screenshots in `C:\tmp\reframe-review-workflow-shots`:

- empty startup and active replay;
- plan and drawing modes;
- review sidebar and full trade-review workspace;
- long, short, completed, and persistent save-failure states;
- settings and an actionable error dialog;
- dataset populated, batch-progress, and empty states;
- session library populated, filtered, and empty states;
- the 1240x820 supported narrow desktop layout.

The first inspection exposed two remaining raw `hover` labels. They were replaced with `浏览模式` and `悬停时间`, covered by focused tests, and the affected screenshots were regenerated. The capture harness now explicitly initializes the chart window, so the matrix also verifies the adaptive 29-bar viewport rather than inheriting a stale 20-bar zoom from startup.

No remaining clipping, overlap, inaccessible primary action, or inconsistent financial color state was observed in the accepted matrix. Save failure and retry controls remain compact at the bottom case header, the error dialog keeps recovery guidance and technical detail separate, and the narrow review layout preserves chart and note-editing workflows.

## Packaged Windows smoke

The release dependency group was synchronized from the lockfile and `scripts/build_release.ps1` completed with PyInstaller 6.19.0 on Windows 11. The resulting local validation artifacts were:

```text
Portable ZIP: dist/BarByBar-v0.5.45-windows-x64.zip (66,053,490 bytes)
Packaged EXE: dist/release/BarByBar/BarByBar.exe (6,527,911 bytes)
```

The packaged executable was launched against an isolated temporary database at forced 125% Qt scale. Two window captures were inspected:

```text
Default packaged window: 2016x1189 physical pixels
Narrow packaged window: 1550x1049 physical pixels
```

Both launches rendered Chinese text with the Windows system font, loaded the saved case, displayed the chart and EMA, and retained complete top navigation, replay controls, sidebar cards, and bottom actions without text clipping. Automated layout checks at 1240x820 and 1600x920 keep critical controls inside the window, and keyboard Tab focus advances between primary controls.

## Verification

```text
Focused terminology and layout checks: 5 passed
Complete automated suite: 764 passed
OpenSpec strict validation: passed
```

## Non-blocking packaging warnings

PyInstaller reported conditional POSIX modules that do not apply on Windows and optional pyqtgraph integrations such as OpenGL, SciPy, Matplotlib, CUDA, and CuPy. BarByBar does not use those integrations; the packaged application started and completed the exercised chart, storage, and UI paths without a missing-module error. No blocking font, high-DPI, text-fit, keyboard-focus, or common-size issue remains from this pass.
