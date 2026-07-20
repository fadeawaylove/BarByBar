# v0.6.0 Release Results

Release date: 2026-07-20

## Source and workflow

```text
Tag: v0.6.0
Tagged commit: b77ef1691c2cfdca2f05f201054163835fc1b360
Release workflow run: 29740913599
Workflow result: success
Release page: https://github.com/fadeawaylove/BarByBar/releases/tag/v0.6.0
```

The remote tag resolves to the expected final validation commit on `master`. All release workflow steps completed successfully, including tag ancestry verification, dependency synchronization, Inno Setup discovery, artifact build, release-note generation, asset upload, Release creation, and final release-body update.

## Published release

The GitHub Release API confirmed a public, non-draft, non-prerelease release with non-empty notes containing `v0.6.0` and exactly two uploaded assets:

| Asset | Remote size | State |
| --- | ---: | --- |
| `BarByBar-v0.6.0-windows-x64-setup.exe` | 47,654,497 bytes | uploaded |
| `BarByBar-v0.6.0-windows-x64.zip` | 69,745,958 bytes | uploaded |

The cloud-built asset sizes differ from the local Windows 11 validation build because GitHub Actions resolves its own locked Python 3.11 environment, while the local packaged smoke used Python 3.12. Both builds use the tagged 0.6.0 source and completed successfully; the local installer was additionally installed and launched against isolated data as recorded in `foundation-visual-smoke-results.md`.

The live application update path was also checked against the published GitHub API response: version 0.5.45 discovers update 0.6.0 and selects `BarByBar-v0.6.0-windows-x64-setup.exe`, while version 0.6.0 correctly reports no newer update.
