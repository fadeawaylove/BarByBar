# Step-Forward Fast-Path Results

Measurement date: 2026-07-19

## Behavioral result

The fast step-forward path now skips unchanged tick-size, position, order-line, draw-control, training-stat, trade-history, and trade-review updates. Cursor-dependent chart overlays, current price, progress, and case header continue to update every step. Full load and explicit refresh paths always reapply all regions.

Focused transition tests verify that position open, close, reverse, completed status, order trigger, trade updates, timeframe behavior, and save-state behavior invalidate the required regions.

## Baseline comparison

| Synthetic source bars | State | Samples | Median | P95 | Maximum |
| --- | --- | ---: | ---: | ---: | ---: |
| 2,000 | v0.5.45 baseline | 30 | 22.73ms | 26.38ms | 26.40ms |
| 2,000 | cached fast path | 30 | 23.51ms | 25.38ms | 26.13ms |
| 50,000 | v0.5.45 baseline | 30 | 21.91ms | 32.40ms | 42.00ms |
| 50,000 | cached fast path | 30 | 22.73ms | 48.07ms | 64.91ms |
| 50,000 | cached fast path extended run | 100 | 24.99ms | 38.28ms | 53.74ms |

The small-case latency is effectively unchanged while its P95 is slightly lower. The 50,000-bar 30-sample run contained tail outliers; the extended 100-sample run returned below the 40ms P95 warning budget but did not establish a median improvement.

The implementation is retained because focused call-count and transition tests prove that redundant work is removed without changing state behavior. No headline speedup is claimed from this slice. Large-case tail latency remains a warning and is carried into candlestick caching, incremental indicators, hit-test prefiltering, and the final large-case matrix.

## Verification

```text
Focused fast-path tests: 5 passed
Complete main-window tests: 254 passed
```

