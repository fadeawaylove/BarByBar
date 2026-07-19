# v0.6 Baseline Checkpoint

Baseline date: 2026-07-19

Baseline version: `0.5.45`

Planning checkpoint commit: `fcfeb0c 建立 v0.6 长期迭代路线`

## Automated Tests

Command:

```powershell
uv run pytest -q
```

Result:

```text
671 passed in 48.44s
```

## Reproducible Replay Latency Matrix

The benchmark script can now create isolated deterministic source data, so it does not require or mutate a user's database.

Small case command:

```powershell
.\.venv\Scripts\python.exe scripts\benchmark_replay_latency.py --synthetic-bars 2000 --steps 30 --warmup 3
```

Result:

```text
source=synthetic source_bars=2000
samples=30 median_ms=22.73 p95_ms=26.38 max_ms=26.40
```

Large source-data command:

```powershell
.\.venv\Scripts\python.exe scripts\benchmark_replay_latency.py --synthetic-bars 50000 --steps 30 --warmup 3
```

Result:

```text
source=synthetic source_bars=50000
samples=30 median_ms=21.91 p95_ms=32.40 max_ms=42.00
```

Both P95 results are below the initial 40ms step-forward warning budget. The 50,000-source-bar case recorded a 42.00ms maximum and a 113.58ms session-window load, so tail latency and data-window loading remain explicit optimization targets.

The current synthetic matrix isolates click-to-render latency and disables persistence enqueueing, matching the existing benchmark contract. It currently contains no dense trade, order-line, or drawing population; those density cases remain required by tasks 2.5 and 2.9.

## Packaged-App and Visual Gaps

The following gaps remain open at the v0.6 baseline:

- Offscreen Qt reports that its bundled font directory is missing; screenshot text cannot be used to verify packaged Chinese font rendering.
- Normal, missing, and failed log-viewer screenshots are not yet accepted.
- Update, error, and notice dialog screenshots are not yet accepted.
- The Windows packaged application has not yet completed a v0.6 high-DPI, text-fit, keyboard-focus, and common-size smoke pass.
- Installer and portable ZIP construction belong to the final milestone gate and have not been rerun for this planning-only checkpoint.

These gaps map to v0.6 tasks 5.6, 5.7, 6.3, and 6.4 and to the focused older changes listed in `overlap-audit.md`.

