## Why

Trade review data currently behaves as session-wide state while drawings are already isolated by chart timeframe. This makes trades, order lines, positions, statistics, and review notes bleed across 5m/15m/60m/1d views, which breaks the user's expectation that each timeframe is an independent training surface.

## What Changes

- Persist trade actions and order lines under `session_id + chart_timeframe`, matching the drawing isolation model.
- Load, save, rebuild, display, and review trades only for the active chart timeframe.
- Keep each timeframe's position state, statistics, trade history cards, trade notes, trade markers, and trade links independent.
- Migrate legacy actions and order lines into the session's saved `chart_timeframe`.
- Preserve session-level metadata such as title, tags, current time anchor, tick size, and drawing style presets as shared session state.

## Capabilities

### New Capabilities

- `chart-timeframe-trade-isolation`: Defines full trade, order-line, position/statistics, and trade-review isolation by active chart timeframe.

### Modified Capabilities

None.

## Impact

- Affected persistence code: `src/barbybar/storage/database.py` and `src/barbybar/storage/repository.py`.
- Affected domain models and engine object creation: `src/barbybar/domain/models.py` and `src/barbybar/domain/engine.py`.
- Affected session loading, timeframe switching, saving, and UI synchronization: `src/barbybar/ui/main_window.py`.
- Affected chart overlays indirectly through current timeframe-filtered inputs: `src/barbybar/ui/chart_widget.py`.
- Affected tests: repository migration/persistence, engine-created action/order-line metadata, main-window timeframe switching, chart trade overlays, and trade review behavior.
