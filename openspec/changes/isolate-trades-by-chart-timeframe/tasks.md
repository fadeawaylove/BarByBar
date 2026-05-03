## 1. Persistence Schema

- [x] 1.1 Add `chart_timeframe` columns to `actions` and `order_lines` schema definitions.
- [x] 1.2 Add migrations that backfill legacy rows from each related session's `chart_timeframe`.
- [x] 1.3 Add indexes for action and order-line lookups by `session_id + chart_timeframe`.
- [x] 1.4 Add repository tests for legacy migration of actions and order lines.

## 2. Repository Isolation

- [x] 2.1 Update `get_session_actions` and `get_order_lines` to require and normalize a chart timeframe.
- [x] 2.2 Update action saving to replace only rows for the active `session.chart_timeframe`.
- [x] 2.3 Update order-line insert, update, and stale deletion logic to operate only within the active `session.chart_timeframe`.
- [x] 2.4 Add repository tests proving 5m and 60m actions/order lines persist independently.
- [x] 2.5 Add repository tests proving saving one timeframe does not delete another timeframe's trade state.

## 3. Domain and Engine State

- [x] 3.1 Add `chart_timeframe` to `SessionAction` and `OrderLine` domain models.
- [x] 3.2 Stamp new recorded actions with `ReviewEngine.session.chart_timeframe`.
- [x] 3.3 Stamp new order lines, including protective lines, with `ReviewEngine.session.chart_timeframe`.
- [x] 3.4 Update action/order-line signatures, equality-sensitive tests, and fixtures to include timeframe where needed.
- [x] 3.5 Add engine tests proving newly created actions and order lines use the active chart timeframe.

## 4. Session Loading and Timeframe Switching

- [x] 4.1 Update `SessionLoadWorker` to load actions and order lines for the requested chart timeframe only.
- [x] 4.2 Update main-window save paths to pass current-timeframe trade state without overwriting other timeframes.
- [x] 4.3 Update `change_chart_timeframe` so source trades are saved before switching and are not written into the target timeframe.
- [x] 4.4 Add main-window tests proving switching to a blank timeframe does not clone source trades, order lines, statistics, or review items.
- [x] 4.5 Add main-window tests proving returning to the source timeframe restores its trades and review notes.

## 5. Chart and Review Verification

- [x] 5.1 Update chart overlay tests so trade markers and links reflect only current-timeframe action inputs.
- [x] 5.2 Update trade history/review tests so completed trade lists and note edits are timeframe-local.
- [x] 5.3 Run `uv run pytest -q tests/test_repository.py`.
- [x] 5.4 Run `uv run pytest -q tests/test_engine.py`.
- [x] 5.5 Run `uv run pytest -q tests/test_main_window.py`.
- [x] 5.6 Run `uv run pytest -q tests/test_chart_widget.py`.
- [x] 5.7 Run `uv run pytest -q tests/test_trade_history.py`.
