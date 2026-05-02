## Why

The current release script can bump, commit, push, and tag a release, but the release notes that appear on GitHub are only generated later inside the tag workflow. That makes it hard to preview the user-facing update content before publishing, and it gives the local script no way to verify that the final GitHub Release page actually contains the expected notes and assets.

## What Changes

- Add a release-notes preview path that can generate notes for a not-yet-created next tag from the latest version tag to the intended release commit.
- Update `publish_release.ps1` so it previews the exact user-facing release notes before pushing the release tag.
- Add an explicit confirmation step before irreversible publishing, with a bypass flag for trusted scripted use.
- Improve tag safety by fetching tags and checking both local and remote tag collisions before creating the release tag.
- Make the GitHub Actions release workflow consume the same release-notes behavior used by local preview.
- Add optional post-publish verification that the GitHub Release page exists, has non-empty notes, and exposes the expected ZIP and setup assets.
- Clarify or harden manual workflow dispatch so it cannot accidentally treat a branch name as a release tag.

## Capabilities

### New Capabilities

- `release-publishing-workflow`: Covers local release publishing, release notes preview, confirmation, GitHub Release body consistency, and post-publish verification.

### Modified Capabilities

None.

## Impact

- Affected scripts: `scripts/publish_release.ps1`, `scripts/generate_release_notes.py`, and possibly release helper functions in `src/barbybar/release_notes.py`.
- Affected workflow: `.github/workflows/release.yml`.
- Affected docs/tests: README release instructions and release-notes/publish-script tests.
- External tooling: existing `git`; optional `gh` for post-publish verification when available/authenticated.
- No application runtime behavior or database schema changes.
