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

## Candlestick window-extension cache

Candlestick pictures are now cached in 128-bar chunks aligned to global bar indexes. Extending a loaded window reuses chunks whose OHLC data and render geometry are unchanged, while cursor movement rebuilds only the active partial chunk. Color and horizontal-scale changes retain a full-rebuild fallback.

The forced-full comparison below clears the chunk render signature before applying the same extension. It measures the current full-rebuild fallback rather than claiming a historical binary comparison.

| Synthetic revealed bars | Extension | Path | Samples | Rebuilt chunks | Median | P95 | Maximum |
| ---: | ---: | --- | ---: | ---: | ---: | ---: | ---: |
| 2,000 | 256 bars left | cached | 20 | 2 | 4.66ms | 6.71ms | 7.26ms |
| 2,000 | 256 bars left | forced full | 20 | 16 | 34.07ms | 38.35ms | 38.63ms |
| 50,000 | 256 bars left | cached | 10 | 2 | 9.22ms | 9.92ms | 9.92ms |
| 50,000 | 256 bars left | forced full | 10 | 391 | 829.13ms | 892.81ms | 892.81ms |

Reproduction commands:

```text
uv run python scripts/benchmark_candlestick_cache.py --bars 2000 --samples 20 --warmup 2
uv run python scripts/benchmark_candlestick_cache.py --bars 50000 --samples 10 --warmup 2
```

Verification after this slice:

```text
Focused candle/window tests: 15 passed
Complete chart-widget tests: 255 passed
Complete automated suite: 679 passed
```

## Incremental EMA cache

The 20-period EMA cache now appends only newly revealed closes when the cursor advances, retains calculated prefixes when the cursor moves backward, and verifies compatible prefixes when a bounded data window is replaced. A changed window start, timeframe, period key, or historical close prefix triggers the full-rebuild fallback.

The benchmark includes updating the PyQtGraph curve, not only the EMA arithmetic. The forced-full path clears the cache key before the same one-bar cursor advance.

| Synthetic revealed bars | Path | Samples | Calculated EMA values | Median | P95 | Maximum |
| ---: | --- | ---: | ---: | ---: | ---: | ---: |
| 2,000 | incremental | 20 | 1 | 0.22ms | 0.29ms | 0.56ms |
| 2,000 | forced full | 20 | 2,000 | 0.38ms | 0.55ms | 0.62ms |
| 50,000 | incremental | 20 | 1 | 3.00ms | 3.54ms | 3.62ms |
| 50,000 | forced full | 20 | 50,000 | 8.42ms | 9.07ms | 9.20ms |

Reproduction commands:

```text
uv run python scripts/benchmark_ema_cache.py --bars 2000 --samples 20 --warmup 2
uv run python scripts/benchmark_ema_cache.py --bars 50000 --samples 20 --warmup 2
```

Verification after this slice:

```text
Focused EMA tests: 9 passed
Complete chart-widget tests: 261 passed
Complete automated suite: 685 passed
```
