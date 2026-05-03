## 1. Regression Coverage

- [x] 1.1 Add a history sidebar click test with non-correlated trade numbers, visible order, and bar indices.
- [x] 1.2 Add entry-mode and exit-mode assertions proving clicked trades focus by `entry_bar_index` or `exit_bar_index`.
- [x] 1.3 Extend previous/next navigation coverage to assert chart focus points come from the navigated `TradeReviewItem`.

## 2. Object-Based Focus Path

- [x] 2.1 Update history card click handling to resolve the clicked row's `TradeReviewItem` and call the object-level selection path.
- [x] 2.2 Update previous/next navigation so the final chart focus receives the target `TradeReviewItem`, not only a trade number.
- [x] 2.3 Ensure sidebar refresh preserves the clicked or navigated selection after chart focus.

## 3. Verification

- [x] 3.1 Run `uv run pytest -q tests/test_main_window.py -k trade_history`.
- [x] 3.2 Run `uv run pytest -q tests/test_trade_history.py`.
- [x] 3.3 Record any unrelated pre-existing failures separately if broader test runs are attempted.
