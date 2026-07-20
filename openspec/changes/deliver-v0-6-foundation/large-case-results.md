# Large-Case Interaction Matrix

Measurement date: 2026-07-19

## Budgets and interpretation

- Step-forward warning budget: 40ms.
- Immediate viewport interaction warning budget: 16ms.
- P95 is the primary warning signal; median and maximum are retained to expose outliers.
- Deferred overlay settlement is reported separately because it occurs after continuous pan/zoom input, but it still remains visible work that can cause a pause.

## Replay and window-extension results

| Operation | Source bars | Samples | Median | P95 | Maximum | Result |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| Step forward | 50,000 | 30 | 11.19ms | 20.65ms | 34.90ms | Within 40ms warning budget |
| Step back | 50,000 | 30 | 9.52ms | 11.29ms | 16.89ms | Within 40ms warning budget |
| Cached 256-bar left extension | 50,000 revealed | 10 | 7.72ms | 8.35ms | 8.35ms | Within 16ms viewport budget |
| Forced-full 256-bar left extension | 50,000 revealed | 10 | 739.88ms | 742.58ms | 742.58ms | Fallback comparison only |

Step-forward and step-back measurements isolate click-to-render behavior by disabling persistence, which is measured and coalesced separately by the application. The cached extension rebuilt 2 chunks; the forced-full comparison rebuilt 391.

## Pan and zoom results

Both scenarios use a 50,000-bar source, a 2,000-bar loaded window, and 50 samples per operation.

| Scenario | Drawings | Trade actions | Order lines | Operation | Median | P95 | Maximum |
| --- | ---: | ---: | ---: | --- | ---: | ---: | ---: |
| Representative | 50 | 100 | 10 | Pan | 11.37ms | 14.23ms | 16.98ms |
| Representative | 50 | 100 | 10 | Zoom | 11.99ms | 13.48ms | 13.93ms |
| Extreme | 1,000 | 1,000 | 20 | Pan | 63.23ms | 78.71ms | 275.99ms |
| Extreme | 1,000 | 1,000 | 20 | Zoom | 64.30ms | 77.28ms | 233.58ms |

Deferred overlay settlement measured 64.61ms in the representative scenario and 181.10ms in the extreme scenario.

## Remaining warnings

1. Representative pan and zoom remain within the 16ms P95 warning budget, but the 16.98ms pan maximum shows limited headroom.
2. Deferred overlay settlement exceeds 16ms even in the representative scenario. It is kept off the continuous input path, but users may still notice a pause after interaction ends.
3. The 1,000-drawing stress case is well over budget. Profiling logs show drawing item relayout/repaint and deferred overlay refresh dominate; candlestick, EMA, and hover-candidate caches are no longer the primary cause.
4. `optimize-chart-performance-architecture` task 6.4 remains open. A future slice should make drawing rendering viewport-aware or reuse drawing graphics more aggressively before claiming the extreme case is responsive.
5. Offscreen Qt still reports that the development environment lacks a bundled font directory. Packaged-font verification remains assigned to v0.6 task 5.7/6.4.

## Reproduction commands

```text
uv run python scripts/benchmark_replay_latency.py --synthetic-bars 50000 --operation step-forward --steps 30 --warmup 3
uv run python scripts/benchmark_replay_latency.py --synthetic-bars 50000 --operation step-back --steps 30 --warmup 3
uv run python scripts/benchmark_candlestick_cache.py --bars 50000 --samples 10 --warmup 2
uv run python scripts/benchmark_chart_interactions.py --source-bars 50000 --window-bars 2000 --drawings 50 --trade-actions 100 --order-lines 10 --samples 50 --warmup 3
uv run python scripts/benchmark_chart_interactions.py --source-bars 50000 --window-bars 2000 --drawings 1000 --trade-actions 1000 --order-lines 20 --samples 50 --warmup 3
```

## Verification state

```text
Complete chart-widget tests after interaction optimizations: 265 passed
Complete automated suite after interaction optimizations: 689 passed
Strict v0.6 OpenSpec validation: passed
```

## Final milestone matrix

Measurement date: 2026-07-20

The final v0.6 validation repeated the representative matrix after all foundation-experience changes. The focused release regression selection completed with `702 passed in 39.09s`; the complete suite completed with `764 passed in 42.40s`.

| Operation | Scenario | Median | P95 | Maximum | Result |
| --- | --- | ---: | ---: | ---: | --- |
| Step forward | 50,000 source bars, 30 samples | 10.83ms | 30.28ms | 35.52ms | Within 40ms replay budget |
| Step back | 50,000 source bars, 30 samples | 9.03ms | 10.96ms | 16.27ms | Within 40ms replay budget |
| Cached left extension | 50,000 bars, 256-bar extension, 10 samples | 8.23ms | 9.37ms | 9.37ms | Within 16ms viewport budget |
| Incremental EMA | 50,000 bars, one-value advance, 20 samples | 2.95ms | 3.83ms | 3.91ms | Within 16ms viewport budget |
| Cached hover hit test | 10,000 objects, 100 samples | 0.075ms | 0.143ms | 0.303ms | Within 16ms viewport budget |
| Pan | Representative: 50 drawings, 100 trades, 10 orders | 9.92ms | 13.17ms | 14.96ms | Within 16ms viewport budget |
| Zoom | Representative: 50 drawings, 100 trades, 10 orders | 11.29ms | 20.73ms | 55.95ms | Warning: intermittent P95 regression |
| Pan | Extreme: 1,000 drawings, 1,000 trades, 20 orders | 60.43ms | 71.27ms | 74.82ms | Warning: stress case over budget |
| Zoom | Extreme: 1,000 drawings, 1,000 trades, 20 orders | 64.10ms | 77.33ms | 85.72ms | Warning: stress case over budget |

Representative deferred overlay settlement was 20.87ms; the extreme case measured 211.29ms. The final run therefore retains three explicit warnings for the v0.7 backlog: representative zoom has occasional frame misses, deferred overlay settlement remains visible after input ends, and a 1,000-drawing case is not yet responsive. Profiling continues to point to drawing relayout/repaint and overlay settlement rather than candlestick, EMA, or hover caches.

The offscreen development benchmark also reports a missing Qt font directory and `propagateSizeHints()` limitations. These are environment-only warnings: the v0.6 packaged-font and 125% high-DPI smoke pass rendered Chinese text correctly, as recorded in `foundation-visual-smoke-results.md`.

Additional final reproduction commands:

```text
uv run python scripts/benchmark_ema_cache.py --bars 50000 --samples 20 --warmup 2
uv run python scripts/benchmark_hover_prefilter.py --objects 10000 --samples 100 --warmup 5
```
