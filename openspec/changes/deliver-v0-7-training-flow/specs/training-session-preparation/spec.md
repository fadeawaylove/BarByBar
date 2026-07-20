## ADDED Requirements

### Requirement: Guided preparation before session creation
The system SHALL present a preparation flow before creating a training session from a dataset.

#### Scenario: User starts preparation from a dataset
- **WHEN** a user chooses to create a training session from an eligible dataset
- **THEN** the system shows the dataset identity, source timeframe, available date range, usable bar count, start configuration, case name, training goal, and optional training rules before any session is created

#### Scenario: User cancels preparation
- **WHEN** the user cancels the preparation flow before confirmation
- **THEN** the system returns to the previous screen without creating a session or changing the dataset

### Requirement: Validated start configuration
The system MUST validate the selected start strategy against the current dataset before persisting a prepared session.

#### Scenario: Explicit start is valid
- **WHEN** the user selects an explicit start that leaves the required observation history and at least one future replay bar
- **THEN** the system accepts the start and explains which bar or time will become the current training point

#### Scenario: Explicit start is invalid
- **WHEN** the selected start is outside the dataset or leaves insufficient observation or replay bars
- **THEN** the system blocks confirmation and displays a specific correction message

#### Scenario: Dataset changed during preparation
- **WHEN** the dataset no longer matches the inspected bar count or time range at confirmation
- **THEN** the system revalidates the configuration and refuses to create a stale or inconsistent session

### Requirement: Future-safe random start
The system SHALL support a random start strategy without revealing the resolved future context before training begins.

#### Scenario: Random start is being configured
- **WHEN** the user selects random start
- **THEN** the preparation flow shows the eligible range and candidate count but does not show the resolved timestamp, OHLC values, future end time, or outcome data

#### Scenario: Random start is confirmed
- **WHEN** a valid random preparation is confirmed
- **THEN** the system resolves one eligible start exactly once, persists it with the prepared session, and uses the same start when the session is later opened

#### Scenario: No random candidate exists
- **WHEN** the dataset contains no start satisfying the observation and replay constraints
- **THEN** random start is unavailable and the system explains why

### Requirement: Persisted training brief
The system SHALL persist a separate training brief containing the case name, goal, ordered rule list, and start-strategy provenance.

#### Scenario: Prepared session is saved
- **WHEN** preparation passes validation and the user confirms
- **THEN** the session and its normalized training brief are stored atomically with `prepared` lifecycle state

#### Scenario: Session creation fails
- **WHEN** validation, serialization, or database persistence fails
- **THEN** no partial session remains and the user receives an actionable error without losing the entered preparation values

#### Scenario: Existing session is loaded after migration
- **WHEN** a session created before v0.7 is loaded
- **THEN** the system supplies compatible empty goal, rule, reflection, and start-provenance defaults without changing its existing active or completed status
