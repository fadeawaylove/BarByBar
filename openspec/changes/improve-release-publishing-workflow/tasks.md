## 1. Release Notes Preview

- [x] 1.1 Extend `scripts/generate_release_notes.py` to support generating notes for a future tag or explicit commit range before the tag exists.
- [x] 1.2 Preserve the existing tag-based release workflow behavior for GitHub Actions.
- [x] 1.3 Add tests for future-tag preview, explicit previous tag/head range, first-release fallback, and release bump commit filtering.

## 2. Publish Script Safety and Modes

- [x] 2.1 Add `-Preview`, `-Yes`, and optional verification-related parameters to `scripts/publish_release.ps1`.
- [x] 2.2 Fetch tags before version calculation and check target tag collisions in both local tags and `origin`.
- [x] 2.3 Generate and print the release notes preview before any push/tag operation.
- [x] 2.4 Require interactive confirmation by default before pushing `master` or the release tag.
- [x] 2.5 Ensure preview-only mode performs no file writes, commits, pushes, or tag creation.
- [x] 2.6 Keep existing version bump, release commit, push, and tag behavior unchanged after confirmation.

## 3. Published Release Verification

- [x] 3.1 Add optional post-publish verification using `gh release view` when `gh` is available.
- [x] 3.2 Verify release body is non-empty and expected ZIP/setup asset names are present.
- [x] 3.3 Add bounded wait or clear timeout behavior for asynchronous GitHub Actions publication.
- [x] 3.4 Degrade gracefully with release/workflow links when `gh` is missing or unauthenticated.

## 4. GitHub Actions Workflow

- [x] 4.1 Normalize the release tag in `.github/workflows/release.yml` for both tag pushes and manual dispatch.
- [x] 4.2 Add validation that manual dispatch uses a `vX.Y.Z` style tag before build or release steps.
- [x] 4.3 Update the workflow release-notes generation step to use the shared generator behavior.
- [x] 4.4 Keep `softprops/action-gh-release` and final release body overwrite semantics compatible with existing releases.

## 5. Documentation and Validation

- [x] 5.1 Update README release instructions to document preview, confirmation, non-interactive mode, and optional verification.
- [x] 5.2 Add or update tests for release notes generation and publish-script helper behavior.
- [x] 5.3 Run release-notes tests and any focused publish-script validation that does not push refs.
- [x] 5.4 Run `openspec validate improve-release-publishing-workflow --strict`.
