## ADDED Requirements

### Requirement: Chart performance metrics
The system SHALL record lightweight timing metrics for performance-sensitive chart operations.

#### Scenario: Viewport update measured
- **WHEN** a chart viewport update runs
- **THEN** the system records elapsed time and context including visible bar count, loaded window size, timeframe, and whether the update was interactive

#### Scenario: Overlay refresh measured
- **WHEN** auxiliary overlays are refreshed
- **THEN** the system records elapsed time and context including dirty layer flags and relevant overlay counts

#### Scenario: Window load measured
- **WHEN** chart window data is loaded or extended
- **THEN** the system records elapsed time, requested range context, result size, and whether the work ran on the UI thread or worker thread

### Requirement: Diagnostics surface
The system SHALL expose recent performance metrics through a diagnostics UI or log view intended for troubleshooting.

#### Scenario: User opens diagnostics
- **WHEN** diagnostics are opened from the application
- **THEN** recent chart, overlay, data-window, and workflow timing metrics are visible without requiring external tooling

#### Scenario: Metrics update during use
- **WHEN** the user pans, zooms, steps, or triggers window extension
- **THEN** the diagnostics surface updates recent measurements without blocking the interaction

### Requirement: Performance regression coverage
The system SHALL include tests or smoke checks that detect regressions in high-frequency chart and workflow paths.

#### Scenario: Interaction rebuild count regression
- **WHEN** automated tests run for repeated pan and zoom interactions
- **THEN** tests verify heavy overlay rebuilds are deferred or coalesced rather than executed for every intermediate event

#### Scenario: Async stale result regression
- **WHEN** automated tests run for overlapping asynchronous viewport or session work
- **THEN** tests verify stale results do not overwrite current UI state

#### Scenario: Release smoke check
- **WHEN** release smoke checks are run
- **THEN** they cover import, session open, step forward, step back, zoom, backward window extension, save, and reopen workflows

### Requirement: Low-overhead instrumentation
The system SHALL keep performance instrumentation lightweight enough that diagnostics do not materially slow high-frequency interaction paths.

#### Scenario: Metrics disabled or passive
- **WHEN** diagnostics are not actively displayed
- **THEN** metric collection remains limited to cheap timing and bounded rolling storage

#### Scenario: High-frequency events logged
- **WHEN** high-frequency chart events occur
- **THEN** the system avoids expensive string formatting or unbounded log volume in the hot path
