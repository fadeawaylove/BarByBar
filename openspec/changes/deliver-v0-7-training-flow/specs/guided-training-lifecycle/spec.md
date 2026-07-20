## ADDED Requirements

### Requirement: Explicit training lifecycle
The system SHALL model each session as prepared, active, or completed and enforce valid transitions.

#### Scenario: Prepared session starts
- **WHEN** the user opens a prepared session and confirms “开始训练”
- **THEN** the system atomically changes it to active, reveals only the allowed current and historical context, and opens the replay workbench

#### Scenario: Prepared session is opened without starting
- **WHEN** the user opens a prepared session but does not confirm the start action
- **THEN** the system shows its preparation summary without revealing resolved random-start market context or changing lifecycle state

#### Scenario: Active session resumes
- **WHEN** the user opens an active session
- **THEN** the system restores its saved cursor, timeframe, orders, drawings, training brief, and unsatisfied save-failure state using the existing recovery behavior

#### Scenario: Invalid lifecycle transition is requested
- **WHEN** code or UI requests an unsupported transition such as completed directly to active
- **THEN** the system rejects the transition without changing persisted session data

### Requirement: Focused training context
The system SHALL keep the training goal, rules, and current lifecycle understandable during replay without reducing chart dominance.

#### Scenario: Active workbench is visible
- **WHEN** an active session is loaded
- **THEN** the workbench shows a compact stage indicator and a discoverable, collapsible summary of the goal and rules while preserving the chart and high-frequency controls as the primary surfaces

#### Scenario: Brief contains long text
- **WHEN** the goal or rules exceed the compact display area
- **THEN** the UI truncates or scrolls safely and provides access to the complete text without overlapping replay or trade controls

#### Scenario: Save of lifecycle context fails
- **WHEN** a goal, rule, lifecycle, or completion-context save fails
- **THEN** the persistent save-failure state, retry action, and retained in-memory edits follow the v0.6 recovery behavior

### Requirement: Lifecycle-aware session library
The system SHALL make prepared, active, and completed sessions distinguishable and actionable in the session library.

#### Scenario: Session list is shown
- **WHEN** the session library contains sessions in multiple lifecycle states
- **THEN** each item shows a localized state label, progress context, goal summary when present, and the correct primary action for prepare/start, continue, or review

#### Scenario: Library is filtered by state
- **WHEN** the user filters the library to 未开始, 训练中, or 已完成
- **THEN** only sessions in the corresponding persisted state are shown and clearing the filter restores the complete list

#### Scenario: Legacy active session is listed
- **WHEN** an older active session has no training brief
- **THEN** it remains openable and the library shows a neutral missing-goal state rather than treating it as corrupt

### Requirement: No future-data leakage across preparation and resume
The system MUST not expose replay data later than the persisted current bar through preparation, library summaries, lifecycle badges, or completion-entry controls.

#### Scenario: Prepared random session is listed
- **WHEN** a prepared random-start session appears in the library
- **THEN** its item omits the resolved start timestamp, future time range, price values, trade outcomes, and progress derived from unrevealed bars

#### Scenario: Active session is summarized
- **WHEN** an active session appears outside the workbench
- **THEN** all displayed market and progress information is bounded by its saved current bar
