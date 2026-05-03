## Context

Drawings are already persisted and loaded by `session_id + chart_timeframe`, and `Repository.save_session_state()` only replaces drawings for the active chart timeframe. Trade data does not follow that boundary: `actions` and `order_lines` are stored by session only, and session loading passes all actions/order lines into `ReviewEngine`. As a result, switching chart timeframe can rebuild position, statistics, trade review items, and chart trade overlays from actions created on another timeframe.

The implementation must keep the current single-session workflow intact while making each chart timeframe an independent trading and review surface. Timeframe switching should still use the current timestamp as the anchor so the user lands near the same market moment.

## Goals / Non-Goals

**Goals:**

- Persist and load actions and order lines by chart timeframe.
- Rebuild position, statistics, completed trades, history review, trade notes, markers, and links from the active timeframe only.
- Preserve other session-level state across timeframes, including title, tags, notes, current time anchor, tick size, supported timeframe choices, and drawing style presets.
- Migrate legacy action/order-line rows to the session's saved chart timeframe.
- Keep chart overlay code simple by passing already-filtered trade data into `ChartWidget`.

**Non-Goals:**

- Do not merge, copy, or aggregate trades across timeframes.
- Do not change order execution rules, trigger semantics, PnL math, or trade review scoring.
- Do not isolate drawings differently from their current behavior.
- Do not add a UI for moving trades between timeframes in this change.
- Do not change source dataset or replay timeframe support.

## Decisions

### Store timeframe on action and order-line rows

Add `chart_timeframe` to `actions` and `order_lines`, with repository queries scoped by `session_id + chart_timeframe`.

Rationale: this mirrors the existing drawing model, keeps old sessions in the same database, and makes reads/writes cheap and explicit.

Alternative considered: store per-timeframe trade state as JSON on `sessions`. This would reduce table migration work but make querying, preserving ids, and future review features harder.

### Treat session save as current-timeframe save for trade rows

`save_session_state()` will replace actions for only `session.chart_timeframe` and reconcile order lines only within that timeframe. Rows from other timeframes remain untouched.

Rationale: this is the behavior users already rely on for drawings and prevents saving 5m from deleting 60m training state.

Alternative considered: add separate save methods for trade state and session metadata. That is cleaner long term, but it would create a larger first refactor across auto-save and step-forward paths.

### Keep engine state timeframe-local by construction

`SessionLoadWorker` will load only current-timeframe actions and order lines before `_build_engine()` replays actions into `ReviewEngine`. `ReviewEngine` will stamp newly created `SessionAction` and `OrderLine` objects with `session.chart_timeframe`.

Rationale: if engine inputs are timeframe-local, position, stats, trade review items, notes, and chart overlays naturally become timeframe-local without adding filter logic in every consumer.

Alternative considered: keep loading all actions and filter in UI/chart/review code. That risks missed call sites and still lets engine statistics bleed across timeframes.

### Timeframe switching saves source state but does not seed target trades

When switching timeframe, the source timeframe is saved first. Then session metadata is updated to the target timeframe and saved without writing the source action/order-line lists into the target timeframe. The target load fetches its own trade rows.

Rationale: this preserves the user's source work while preventing accidental cloning into a blank target period.

Alternative considered: automatically copy source trades to a newly visited timeframe. The user selected full isolation, so copying would surprise them and create duplicate review histories.

### Migrate legacy data to current saved chart timeframe

During database migration, existing `actions` and `order_lines` rows get `chart_timeframe` from their related session's `chart_timeframe`, falling back to `1m` only when no session value is available.

Rationale: this matches the existing drawing migration strategy and preserves old trade visibility in the timeframe where the session was last saved.

Alternative considered: duplicate legacy rows into every supported timeframe. That would preserve visibility everywhere but violates the intended isolation model and multiplies history records.

## Risks / Trade-offs

- [Risk] Autosave or timeframe-switch paths may still call `save_session()` with source timeframe objects after changing the session timeframe. -> Mitigation: update the switch path carefully and add tests that verify target timeframe remains empty after switching.
- [Risk] Existing tests assume `get_session_actions(session_id)` and `get_order_lines(session_id)` return all rows. -> Mitigation: update callers and tests to pass explicit chart timeframe, and keep helper compatibility only if it cannot hide incorrect behavior.
- [Risk] Legacy migration may place old trades on a timeframe the user no longer expects. -> Mitigation: use the session's persisted `chart_timeframe`, which is the best available source of truth and matches drawing migration.
- [Risk] Active order-line ids are only unique globally, but stale reconciliation becomes timeframe-scoped. -> Mitigation: query existing ids inside the current timeframe and update rows with both `id`, `session_id`, and `chart_timeframe`.
- [Risk] Chart focus from history may request bars that exist in the current timeframe but not in the current window. -> Mitigation: keep using existing session/window loading behavior and current trade item's own bar indices.

## Migration Plan

1. Add nullable-safe schema migration for `actions.chart_timeframe` and `order_lines.chart_timeframe`, backfill from `sessions.chart_timeframe`, and create indexes.
2. Update models, repository read/write methods, and engine-created objects to carry normalized chart timeframe.
3. Update session loading, saving, auto-save, and timeframe switching to load/save current-timeframe trade state only.
4. Update tests for repository isolation, migration, engine stamping, and main-window timeframe switching.
5. Rollback, if needed, is to read all rows by session again and ignore the new columns; no destructive data migration is required.

## Open Questions

None for the first implementation. The default behavior is full isolation, and legacy rows migrate to the saved session chart timeframe.
