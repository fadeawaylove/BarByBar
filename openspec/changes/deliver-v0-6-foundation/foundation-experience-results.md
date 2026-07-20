# Foundation Experience Results

Measurement date: 2026-07-20

## Chinese terminology slice

User-visible position states now use `空仓 / 做多 / 做空`, while the internal `flat / long / short` values remain unchanged for persistence, chart state, filters, and business logic. Trade directions consistently display as `多单 / 空单`, and neutral outcomes use `持平`.

Trading surfaces now use `盈亏` instead of `PnL`, `第 N 根K线` instead of `Bar N`, and `N 根K线` instead of `N bars`. The same copy is applied to the case header, position readout, session library, history table and cards, trade-note dialog, chart trade tooltips, and focused-trade progress feedback.

Unknown exit reasons, drawing tools, order previews, and trade action roles no longer fall back to raw internal enum strings. All currently supported drawing-tool values have explicit Chinese labels, and template fallback copy is Chinese.

Verification:

```text
Focused terminology tests: 9 passed
Complete automated suite: 750 passed
User-visible source copy scan: no remaining PnL, Bar/bars, Template, or raw direction-state labels
OpenSpec strict validation: passed
```

Next task: add a bounded adaptive initial chart viewport for short revealed histories in task 5.2.
