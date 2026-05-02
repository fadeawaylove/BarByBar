## ADDED Requirements

### Requirement: Latest-result task application
The system SHALL apply results from asynchronous UI tasks only when the result still matches the latest relevant request.

#### Scenario: Stale viewport extension result
- **WHEN** an older viewport window extension finishes after a newer request has been made
- **THEN** the older result is discarded without replacing the current chart window

#### Scenario: Stale session load result
- **WHEN** an older session load finishes after the user has started loading another session
- **THEN** the older result is discarded without changing the active session

### Requirement: Single-flight coalescing
The system SHALL coalesce high-frequency background requests where only the newest pending request can affect the UI.

#### Scenario: Repeated backward viewport extension
- **WHEN** the user keeps panning left while a backward window extension is running
- **THEN** the system keeps only the latest pending backward extension request

#### Scenario: Deferred heavy chart work
- **WHEN** multiple chart interactions request expensive overlay preparation before a worker or timer completes
- **THEN** the system prepares or applies results for the most recent chart state

### Requirement: Shared worker lifecycle semantics
The system SHALL use consistent lifecycle handling for asynchronous UI tasks, including start, success, failure, cleanup, and close-event shutdown.

#### Scenario: Worker succeeds
- **WHEN** an asynchronous task finishes successfully
- **THEN** its result is delivered on the UI thread, the worker and thread references are cleaned up, and pending eligible work can start

#### Scenario: Worker fails
- **WHEN** an asynchronous task raises an exception
- **THEN** the failure is logged with task context, UI state remains usable, and worker resources are cleaned up

#### Scenario: Window closes with active task
- **WHEN** the application window closes while a UI-related worker is running
- **THEN** the system requests worker shutdown and waits within a bounded timeout

### Requirement: Main window responsibility reduction
The system SHALL move chart window coordination, session state transitions, settings persistence, and worker coordination out of the main window into focused controller or coordinator objects.

#### Scenario: Chart viewport extension
- **WHEN** viewport extension logic is maintained
- **THEN** repository window loading, latest-request tracking, and chart window application are owned by chart coordination code rather than general UI setup code

#### Scenario: Session step flow
- **WHEN** step forward, step backward, or jump behavior is maintained
- **THEN** replay state transitions and save scheduling are owned by session coordination code rather than mixed with unrelated UI construction
