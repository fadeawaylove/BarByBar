## 1. Milestone Baseline and Recovery

- [x] 1.1 Add the repository roadmap, v0.6 OpenSpec artifacts, and start/end recovery protocol, then validate their internal links and status.
- [x] 1.2 Audit unfinished existing OpenSpec changes and map overlapping performance or polish tasks into v0.6 without duplicating implementation.
- [x] 1.3 Record the current full-test result, packaged-app smoke gaps, and a reproducible performance baseline matrix for small and representative large cases.
- [x] 1.4 Commit the roadmap and v0.6 planning checkpoint as a standalone non-behavioral change.

## 2. Replay and Chart Responsiveness

- [x] 2.1 Add focused tests that identify which workbench regions currently update during an unchanged step-forward fast path.
- [x] 2.2 Introduce stable state signatures or equivalent comparisons for position, order lines, statistics, price controls, drawing controls, and case header updates.
- [x] 2.3 Skip unchanged workbench region updates during deferred step-forward while preserving the complete refresh path for load, restore, step-back, and state transitions.
- [x] 2.4 Add transition tests for order trigger, position open/close/reverse, completed session, timeframe switch, save state, and trade review refresh.
- [x] 2.5 Benchmark the optimized fast path and record median, P95, maximum latency, and scenario sizes against the baseline.
- [x] 2.6 Add chunked or cached candlestick picture rebuilding and verify window extension does not redraw unchanged chunks.
- [x] 2.7 Add incremental EMA or indicator updates for cursor and bounded-window changes, with full rebuild fallback tests.
- [x] 2.8 Add viewport-aware prefiltering for drawing, trade marker, and trade link hover hit testing and verify selection correctness.
- [x] 2.9 Re-run large-case pan, zoom, step-forward, step-back, and window-extension benchmarks and document remaining budget warnings.

## 3. Local Data Safety and Export

- [x] 3.1 Add a data-safety service that creates a SQLite-consistent temporary backup, validates it, and atomically publishes the final backup file.
- [x] 3.2 Add backup success and failure tests covering active connections, unwritable targets, incomplete temporary files, and preservation of the source database.
- [ ] 3.3 Add restore-file validation and a pending-restore manifest that cannot overwrite the current database during an active application session.
- [ ] 3.4 Apply a pending restore before Repository creation, automatically preserve the current database, and retain the original database on any failure.
- [ ] 3.5 Add settings or data-management UI for backup, restore selection, restart guidance, paths, progress, and actionable errors.
- [ ] 3.6 Define a stable session/trade export view model independent of internal database column names.
- [ ] 3.7 Export selected session summaries and trades as UTF-8 CSV and JSON with deterministic headers and formatting.
- [ ] 3.8 Add export UI, success feedback, empty-session behavior, write-failure handling, and automated tests.

## 4. CSV Import Quality Review

- [ ] 4.1 Extract a pure CSV inspection path that returns detected columns, suggested mapping, sample rows, valid-row count, and time range without persisting data.
- [ ] 4.2 Detect missing required fields, parse failures, empty data, duplicate timestamps, reversed ordering, OHLC inconsistencies, and abnormal intervals with row-level examples.
- [ ] 4.3 Classify findings into blocking errors and confirmable warnings, and add focused parser and quality-rule tests.
- [ ] 4.4 Build an import review dialog that presents mapping, samples, summary, warnings, and disabled confirmation for blocking errors.
- [ ] 4.5 Ensure confirmed single-file import uses exactly the reviewed mapping and reports imported, skipped, and failed results.
- [ ] 4.6 Integrate the same inspection and reporting rules into folder import without blocking the UI thread.
- [ ] 4.7 Add UI and repository regression tests for successful review, remapping, blocked import, warned import, duplicate dataset, batch progress, and cancellation or failure cleanup.

## 5. Foundation Experience Polish

- [ ] 5.1 Replace user-visible `flat`, `long`, `short`, `hover`, and other inconsistent status copy with clear Chinese terminology while preserving internal enum values.
- [ ] 5.2 Add a bounded adaptive initial chart viewport for sessions with fewer revealed bars than the default viewport and preserve right-side planning space.
- [ ] 5.3 Add tests for adaptive viewport behavior at empty, short, normal, minimum-zoom, reset, and narrow-window states.
- [ ] 5.4 Make saving, saved, and save-failed states explicit; prevent ordinary transient hints from overwriting an unresolved save failure.
- [ ] 5.5 Add retry or detail access for save failures and verify recovery after a later successful save.
- [ ] 5.6 Re-capture and inspect startup, active session, long, short, completed, plan, drawing, review, settings, dataset, session library, error, and narrow-layout screenshots.
- [ ] 5.7 Run a packaged-app font, high-DPI, text-fit, keyboard-focus, and common desktop-size smoke pass and record unresolved issues.

## 6. Milestone Validation and Release

- [ ] 6.1 Run all focused engine, repository, async-task, main-window, chart, trade-history, logging, update, and release tests affected by v0.6.
- [ ] 6.2 Run the complete automated test suite and record the final result in the milestone checkpoint.
- [ ] 6.3 Run the final representative performance matrix and confirm or explicitly document every remaining budget warning.
- [ ] 6.4 Build the Windows portable package and installer, then complete the v0.6 packaged-app smoke checklist.
- [ ] 6.5 Validate the OpenSpec change strictly and confirm every completed task has matching implementation or verification evidence.
- [ ] 6.6 Update the roadmap current milestone to v0.7, archive the completed v0.6 OpenSpec change, and preserve the archived specifications.
- [ ] 6.7 Publish the v0.6 release, verify the remote tag, Release page, installer, portable ZIP, and release notes.
