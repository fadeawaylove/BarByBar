## ADDED Requirements

### Requirement: Confirmed and safe completion
The system SHALL require an explicit completion flow instead of immediately marking an active session completed.

#### Scenario: Flat session is completed
- **WHEN** the user chooses to complete an active session with no open position and confirms the summary
- **THEN** the system saves the reflection fields, completion time, and completed lifecycle state before presenting completion actions

#### Scenario: Session has an open position
- **WHEN** the user requests completion while a position remains open
- **THEN** the system offers an explicit choice to close at the current replay bar and complete or return to training, with return to training as the non-destructive path

#### Scenario: User returns to training
- **WHEN** the user cancels completion or chooses to handle the open position manually
- **THEN** no completion state, synthetic close action, or reflection change is persisted

#### Scenario: Completion save fails
- **WHEN** the close or completion transaction cannot be persisted
- **THEN** the session remains recoverable as active, the user sees a persistent actionable error, and completion is not reported as successful

### Requirement: Fact-based completion summary
The system SHALL present a completion summary derived from persisted session and trade facts without assigning a discipline score.

#### Scenario: Completed session has trades
- **WHEN** completion facts are available
- **THEN** the summary shows the training span, bars advanced, trade count, wins and losses, net PnL, maximum drawdown, and other stable existing facts using localized labels and deterministic formatting

#### Scenario: Completed session has no trades
- **WHEN** a session is completed without trades
- **THEN** the summary presents a deliberate no-trade result and available training facts without empty charts, divide-by-zero values, or implied failure

#### Scenario: Summary is reopened
- **WHEN** a completed session is reviewed later
- **THEN** the same factual summary is reproducible from persisted session, action, and trade data

### Requirement: Lightweight reflection and next step
The system SHALL let the user record a free-text completion reflection and next-training focus while leaving structured evaluation to a later milestone.

#### Scenario: User completes reflection
- **WHEN** the user enters a reflection and next focus during completion
- **THEN** both values are preserved separately from general session notes and are visible when the completion summary is reopened

#### Scenario: Reflection is left empty
- **WHEN** the user confirms completion without entering optional reflection text
- **THEN** the session can still complete and the summary shows an intentional empty prompt rather than placeholder data

### Requirement: Clear post-completion navigation
The system SHALL offer explicit next actions after successful completion.

#### Scenario: Completion succeeds
- **WHEN** the session is durably marked completed
- **THEN** the user can open trade review, return to the session library, or remain on the read-only completion summary

#### Scenario: Completed session is opened from the library
- **WHEN** the user opens a completed session
- **THEN** the system enters review/summary mode and does not enable replay or trade mutation controls
