## 1. Milestone Baseline and Flow Contract

- [ ] 1.1 Record v0.7 starting git tag, full-test result, database schema version, and current create/start/complete behavior in a baseline checkpoint.
- [ ] 1.2 Add focused characterization tests for fixed-index session creation, active/completed loading, manual completion, terminal auto-flattening, session-library actions, and legacy database migration.
- [ ] 1.3 Capture current dataset-to-workbench, active-session, completed-session, session-library, empty, failure, and narrow-window screenshots for before/after comparison.
- [ ] 1.4 Resolve the preparation UX open questions with a compact wireframe review: primary explicit-start input, prepared-case editing policy, and post-completion default destination.
- [ ] 1.5 Define the normalized training brief, lifecycle transition table, start-candidate constraints, completion facts, and privacy boundaries as pure view/domain models with unit tests.

## 2. Lifecycle Data Model and Migration

- [ ] 2.1 Add `prepared` to the session lifecycle model and reject unsupported state transitions without changing existing active/completed behavior.
- [ ] 2.2 Add training goal, ordered rules, start-strategy provenance, completion reflection, next focus, and completion time fields with safe defaults and serialization tests.
- [ ] 2.3 Implement an additive, idempotent SQLite migration for the new lifecycle and training-brief fields, including schema-version and repeated-run tests.
- [ ] 2.4 Add old-database fixtures covering active and completed cases with actions, trades, drawings, and order lines; verify migration preserves all existing business data.
- [ ] 2.5 Integrate the v0.6 verified-backup path before the first schema upgrade and test backup failure, migration failure, rollback, and successful retry.
- [ ] 2.6 Add repository mapping and query support for the new fields while keeping older create/load callers source-compatible during migration.
- [ ] 2.7 Add transactional repository operations for create-prepared, start-prepared, update-brief, and complete-session so partial state cannot be published.

## 3. Training Preparation

- [ ] 3.1 Implement a pure dataset preparation-inspection path that returns identity, range, usable bar count, candidate bounds, and blocking reasons without creating a session.
- [ ] 3.2 Implement explicit-start validation with observation-history and future-replay constraints, including first/last valid, too-early, too-late, empty, short, and changed-dataset tests.
- [ ] 3.3 Implement injectable random-start resolution that persists one stable result and add distribution-boundary, no-candidate, and repeat-open tests.
- [ ] 3.4 Add tests proving random preparation and prepared-session library data omit resolved timestamp, OHLC, future range, outcome, and unrevealed progress.
- [ ] 3.5 Build the preparation dialog with dataset summary, start strategy, goal, optional ordered rules, case name, inline validation, confirmation summary, keyboard focus, and cancellation behavior.
- [ ] 3.6 Keep entered values after recoverable validation or persistence failures and present actionable errors without leaving a partial session.
- [ ] 3.7 Replace direct fixed-index creation from the dataset manager with the reviewed preparation flow and refresh/open only after durable creation.
- [ ] 3.8 Add UI and repository regression tests for explicit start, random start, cancellation, invalid input, stale dataset, duplicate confirmation, persistence failure, and successful prepared creation.

## 4. Guided Training Lifecycle

- [ ] 4.1 Add the prepared-session start confirmation and atomically transition to active before loading market context into the workbench.
- [ ] 4.2 Ensure prepared sessions opened without starting expose only the training brief and allowed dataset metadata, with no resolved random-start market information.
- [ ] 4.3 Add a compact localized lifecycle badge and collapsible goal/rule summary to the workbench without moving chart or high-frequency controls.
- [ ] 4.4 Handle empty, long, and legacy training briefs with safe truncation, full-detail access, narrow-layout behavior, and accessible keyboard focus.
- [ ] 4.5 Extend session-library rows, filters, empty states, and primary actions for 未开始, 训练中, and 已完成 while preserving search and deletion behavior.
- [ ] 4.6 Make active-session resume restore the new brief and lifecycle fields alongside cursor, timeframe, orders, drawings, save state, and existing replay data.
- [ ] 4.7 Reuse persistent save-failure and retry behavior for brief edits and lifecycle transitions, including recovery after a later successful save.
- [ ] 4.8 Add transition and privacy regression tests for prepared→active, active resume, active→completed, invalid completed→active, legacy active, library filters, and concurrent/stale load callbacks.

## 5. Completion and Summary

- [ ] 5.1 Create a stable completion-summary view model from persisted session, action, and trade data with deterministic localized formatting.
- [ ] 5.2 Add summary tests for no trades, winning/losing/mixed trades, zero denominators, partial data, long holding periods, max drawdown, and reopened completed sessions.
- [ ] 5.3 Implement explicit completion confirmation for flat sessions and persist reflection, next focus, completion time, and completed state atomically.
- [ ] 5.4 Implement the open-position completion branch with “按当前 K 线平仓并完成” and non-destructive “返回训练”, reusing existing trade semantics.
- [ ] 5.5 Verify close-and-complete produces exactly one valid close action/trade, and any save failure keeps the session active and recoverable without reporting success.
- [ ] 5.6 Build the completion-summary dialog with goal/rule context, fact cards, optional reflection fields, deliberate no-trade state, and clear review/library/stay actions.
- [ ] 5.7 Open completed sessions in read-only summary/review mode and keep replay, order, drawing mutation, and trade-action controls disabled.
- [ ] 5.8 Add end-to-end UI tests for flat completion, open-position cancellation, close-and-complete, failure recovery, no-trade summary, reflection persistence, and post-completion navigation.

## 6. Product Polish, Validation, and Release

- [ ] 6.1 Apply the existing visual system to preparation, lifecycle, library, and completion surfaces; verify Chinese terminology, hierarchy, spacing, focus, disabled, loading, empty, and error states.
- [ ] 6.2 Re-capture and inspect the full v0.7 flow at common desktop sizes and 125% scaling, including explicit/random preparation, prepared library, active context, open-position completion, no-trade/traded summary, legacy, failure, and narrow states.
- [ ] 6.3 Run focused engine, model, repository, migration, main-window, session-library, chart, trade-history, data-safety, logging, update, and release regression suites.
- [ ] 6.4 Run the complete automated suite and a representative performance pass for preparation inspection, session load/resume, lifecycle saves, and unchanged replay interactions; document every warning.
- [ ] 6.5 Build the Windows portable ZIP and installer, then smoke-test fresh install, upgraded v0.6 database, prepared start, active resume, completion, Chinese font, high DPI, and isolated data paths.
- [ ] 6.6 Validate this OpenSpec change strictly and confirm every completed task has matching implementation, migration, test, visual, or packaged evidence.
- [ ] 6.7 Publish v0.7.0, verify the remote tag, Release page, installer, portable ZIP, notes, and updater recognition, then advance the roadmap to v0.8 and archive the change.
