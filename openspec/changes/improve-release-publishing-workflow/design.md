## Context

BarByBar currently publishes Windows ZIP and setup assets through a tag-triggered GitHub Actions workflow. The local `scripts/publish_release.ps1` script owns version bumping, release commit creation, pushing `master`, creating the tag, and pushing the tag. The workflow then builds assets and generates the GitHub Release body from commits between the previous version tag and the pushed tag.

That split mostly works, but it leaves the local publisher blind at the most important moment: before pushing the tag, they cannot preview the exact release notes that users will see. It also means the script cannot confirm that the final GitHub Release page actually contains those notes and assets. The release workflow already has useful release-notes infrastructure, so this change should tighten the handoff rather than introduce a separate changelog system.

## Goals / Non-Goals

**Goals:**

- Generate release notes before the release tag exists, using the intended next tag and release commit range.
- Show the release notes preview before pushing any irreversible release refs.
- Require explicit confirmation by default before publishing.
- Keep local preview and GitHub Release body generation on the same code path.
- Improve safety checks around local and remote tag collisions.
- Optionally verify the published GitHub Release page after the workflow runs.
- Keep the current release artifact names and version bump semantics.

**Non-Goals:**

- Do not add a manual handwritten changelog file as the source of truth.
- Do not change the installer or portable build packaging format.
- Do not change application update-check semantics.
- Do not require `gh` for the core publishing path; it should only power optional post-publish verification when available.
- Do not attempt to summarize code diffs with an external AI service.

## Decisions

### Reuse the existing Python release-notes generator

`scripts/generate_release_notes.py` should remain the source for Markdown release notes. It should gain explicit arguments for previewing a future tag, such as previous tag, head/ref range, compare label, compare URL, and output path. This keeps release body formatting testable in Python while keeping the PowerShell script focused on orchestration.

Alternative considered: generate Markdown directly inside `publish_release.ps1`. That would duplicate categorization rules and make tests harder to keep focused.

### Preview before push/tag

`publish_release.ps1` should compute the next version/tag, determine the previous version tag, generate release notes from the unreleased commits plus the release bump commit as appropriate, print the preview, and require confirmation before it pushes `master` or creates/pushes the tag.

The preview should still filter the generated `Release vX.Y.Z` bump commit from user-facing summary, matching the existing remote workflow behavior.

Alternative considered: push first, then show notes. That is too late to catch poor release-page content without deleting tags or editing releases.

### Treat release notes as deterministic from git state

The release notes should be generated from a clear commit range:

- Preview before the release commit exists: latest tag through current `HEAD`, plus the planned release tag label.
- Preview after the release commit exists but before tag push: latest tag through `HEAD`, filtering out `Release vX.Y.Z`.
- Workflow after tag push: previous tag through the pushed tag.

These paths should produce equivalent user-facing notes for the same feature commits.

### Add explicit publish modes

The script should support:

- Default publish: preview notes, prompt for confirmation, then publish.
- `-Preview`: compute and print the next version/tag and release notes only, with no file changes, commits, pushes, or tags.
- `-Yes`: skip the interactive confirmation for trusted use.
- Optional verification switch, such as `-VerifyRelease`, to wait for or check the GitHub Release after tag push.

The names can be adjusted during implementation, but the behavior should be clear and test-covered.

### Harden release workflow dispatch

The `release.yml` workflow currently uses `github.ref_name` as the release tag. That is safe for tag-triggered runs, but ambiguous for manual dispatch. The workflow should either remove `workflow_dispatch` or require an explicit `tag` input and normalize one tag variable for all build/release steps.

Keeping a manual dispatch path is useful for reruns, so the preferred path is to add a required tag input and validate it starts with `v`.

## Risks / Trade-offs

- Preview notes may differ from remote notes if local tags are stale -> mitigate by fetching tags before computing previous tag and checking remote collisions.
- Interactive confirmation can break non-interactive use -> mitigate with `-Yes` and tests for both modes.
- `gh` may be unavailable or unauthenticated -> keep post-publish verification optional and degrade with clear instructions.
- Release workflow timing is asynchronous -> verification should use bounded polling and helpful timeout output rather than blocking indefinitely.
- Existing tests may not cover PowerShell deeply -> add focused Pester-free tests where possible by extracting pure helper behavior or using PowerShell dry-run invocations.

## Migration Plan

1. Add preview-capable arguments to the Python release-notes generator while preserving the existing tag-based workflow arguments.
2. Update `publish_release.ps1` to call the preview path before publishing.
3. Update `release.yml` to use the same generator path and harden manual dispatch tag handling.
4. Update README release instructions to describe preview, confirmation, and optional verification.
5. Keep existing tag-triggered releases compatible; no database or app migration is required.

Rollback is straightforward: revert the script/workflow changes. Existing version tags and GitHub Releases remain valid because artifact names and tag semantics stay unchanged.

## Open Questions

- Should post-publish verification be enabled by default when `gh` is installed, or remain opt-in to avoid long waits?
- Should the preview file be written under `dist/`, a temp path, or a user-provided path?
- Should manual workflow dispatch remain enabled, or should release reruns rely on GitHub's built-in rerun action for tag-triggered runs?
