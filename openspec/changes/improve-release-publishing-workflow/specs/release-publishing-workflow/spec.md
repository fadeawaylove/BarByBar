## ADDED Requirements

### Requirement: Release script previews user-facing notes before publishing
The system SHALL generate and display the Markdown release notes for the intended next release before pushing the release tag.

#### Scenario: Publisher runs a normal release
- **WHEN** the publisher runs `publish_release.ps1` for a version bump
- **THEN** the script displays the next version, target tag, previous tag or first-release label, and the release notes that will appear on the GitHub Release page before pushing the release tag

#### Scenario: Publisher previews without publishing
- **WHEN** the publisher runs the release script in preview-only mode
- **THEN** the script generates the next release notes without changing files, creating commits, pushing refs, or creating tags

### Requirement: Release script requires confirmation for irreversible publishing
The system SHALL require explicit confirmation before pushing `master` or a release tag unless the publisher has opted into non-interactive confirmation.

#### Scenario: Publisher rejects confirmation
- **WHEN** the release notes preview has been shown and the publisher declines confirmation
- **THEN** the script stops before pushing commits, creating local tags, or pushing tags

#### Scenario: Publisher passes non-interactive confirmation
- **WHEN** the publisher passes the approved non-interactive confirmation flag
- **THEN** the script publishes without prompting after all preflight checks and release-notes generation succeed

### Requirement: Release tag checks include local and remote refs
The system SHALL check for target release tag collisions in both local tags and the configured origin remote before creating a release tag.

#### Scenario: Target tag already exists locally
- **WHEN** the computed target release tag already exists in the local repository
- **THEN** the script fails before changing version files or pushing refs

#### Scenario: Target tag already exists remotely
- **WHEN** the computed target release tag exists on `origin`
- **THEN** the script fails before changing version files or pushing refs

### Requirement: Local preview and GitHub Release body use consistent release notes
The system SHALL use the same release-notes generation behavior for local preview and the GitHub Actions release body.

#### Scenario: Workflow publishes a tag-triggered release
- **WHEN** GitHub Actions creates or updates a Release for a pushed version tag
- **THEN** the Release body contains the generated release notes for the commit range between the previous version tag and the current version tag

#### Scenario: Release bump commit is present
- **WHEN** the release commit subject is `Release vX.Y.Z`
- **THEN** the generated release notes exclude that release bump commit from the user-facing summary and full commit list

### Requirement: Manual release workflow dispatch is tag-safe
The system SHALL prevent manual release workflow runs from accidentally using a branch name as the release tag.

#### Scenario: Manual workflow uses an explicit tag
- **WHEN** the release workflow is manually dispatched
- **THEN** it requires or derives a validated version tag that starts with `v` and uses that tag consistently for build, notes, and release steps

#### Scenario: Manual workflow tag is invalid
- **WHEN** the manually provided release tag is missing or invalid
- **THEN** the workflow fails before building artifacts or creating a GitHub Release

### Requirement: Published release can be verified after tag push
The system SHALL provide an optional way to verify that the GitHub Release page exists, has non-empty notes, and exposes the expected release assets after publishing.

#### Scenario: Verification succeeds
- **WHEN** post-publish verification is requested and the GitHub Release has notes plus the expected ZIP and setup assets
- **THEN** the script reports the release URL and asset URLs as verified

#### Scenario: Verification times out or cannot run
- **WHEN** post-publish verification is requested but the release cannot be verified within the bounded wait or required tooling is unavailable
- **THEN** the script reports a clear warning or failure with links to the release page and workflow page
