## ADDED Requirements

### Requirement: Uniform file log retention policy
The system SHALL apply the same file rotation, retention, and compression policy to every file log sink.

#### Scenario: File log sinks are configured
- **WHEN** application logging is initialized
- **THEN** `app.log`, `debug.log`, and `error.log` SHALL rotate after 5 MB
- **AND** each sink SHALL retain at most 5 rotated files
- **AND** new rotated logs SHALL NOT be compressed

### Requirement: Diagnostic log coverage
The system SHALL write a complete diagnostic stream to `debug.log`.

#### Scenario: Debug log receives diagnostic records
- **WHEN** application logging records DEBUG, INFO, WARNING, ERROR, or CRITICAL messages
- **THEN** `debug.log` SHALL contain those records

### Requirement: Operational and error log separation
The system SHALL preserve the existing purpose of the operational and error log files.

#### Scenario: App log filters debug records
- **WHEN** application logging records DEBUG and INFO messages
- **THEN** `app.log` SHALL contain the INFO message
- **AND** `app.log` SHALL NOT contain the DEBUG message

#### Scenario: Error log records failures
- **WHEN** application logging records an ERROR message or exception
- **THEN** `error.log` SHALL contain the failure record and available exception details

### Requirement: Existing diagnostics behavior remains available
The system SHALL preserve existing diagnostics entry points and exception capture behavior while changing log file policy.

#### Scenario: Diagnostics UI paths remain valid
- **WHEN** the user opens diagnostics settings or the log viewer
- **THEN** the UI SHALL continue to reference `app.log`, `debug.log`, and `error.log` in the configured log directory

#### Scenario: Unhandled exceptions are reported
- **WHEN** an unhandled main-thread or worker-thread exception occurs
- **THEN** the system SHALL continue to log the exception and notify the registered fatal-error handler with references to `error.log` and `debug.log`
