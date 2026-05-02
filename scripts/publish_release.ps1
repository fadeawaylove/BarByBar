param(
    [Parameter(Position = 0)]
    [string]$BumpPart,
    [switch]$Preview,
    [switch]$Yes,
    [switch]$VerifyRelease,
    [int]$VerifyTimeoutSeconds = 600,
    [int]$VerifyPollSeconds = 15
)

$ErrorActionPreference = 'Stop'
$script:Utf8NoBom = [System.Text.UTF8Encoding]::new($false)
$OutputEncoding = $script:Utf8NoBom
[Console]::OutputEncoding = $script:Utf8NoBom

function Show-Usage {
    Write-Host 'Usage: .\scripts\publish_release.ps1 major|minor|patch [-Preview] [-Yes] [-VerifyRelease]' -ForegroundColor Yellow
    Write-Host 'Examples:' -ForegroundColor DarkGray
    Write-Host '  .\scripts\publish_release.ps1 patch -Preview' -ForegroundColor DarkGray
    Write-Host '  .\scripts\publish_release.ps1 patch' -ForegroundColor DarkGray
    Write-Host '  .\scripts\publish_release.ps1 patch -Yes -VerifyRelease' -ForegroundColor DarkGray
}

if ([string]::IsNullOrWhiteSpace($BumpPart)) {
    Show-Usage
    exit 1
}

$normalizedPart = $BumpPart.Trim().ToLowerInvariant()
if ($normalizedPart -notin @('major', 'minor', 'patch')) {
    Show-Usage
    exit 1
}

function Invoke-Git {
    param(
        [Parameter(Mandatory = $true)]
        [string[]]$Arguments
    )

    & git @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "git $($Arguments -join ' ') failed with exit code $LASTEXITCODE."
    }
}

function Get-GitOutput {
    param(
        [Parameter(Mandatory = $true)]
        [string[]]$Arguments
    )

    $output = & git @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "git $($Arguments -join ' ') failed with exit code $LASTEXITCODE."
    }
    return $output
}

function Test-GitRefExists {
    param(
        [Parameter(Mandatory = $true)]
        [string[]]$Arguments
    )

    $output = & git @Arguments 2>$null
    $exitCode = $LASTEXITCODE
    if ($exitCode -eq 0) {
        return -not [string]::IsNullOrWhiteSpace(($output | Select-Object -First 1))
    }
    if ($exitCode -eq 2) {
        return $false
    }
    throw "git $($Arguments -join ' ') failed with exit code $exitCode."
}

function Get-IncrementedVersion {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Version,
        [Parameter(Mandatory = $true)]
        [string]$Part
    )

    if ($Version -notmatch '^(?<major>\d+)\.(?<minor>\d+)\.(?<patch>\d+)$') {
        throw "Current version '$Version' must use semantic version format X.Y.Z."
    }

    $major = [int]$Matches['major']
    $minor = [int]$Matches['minor']
    $patch = [int]$Matches['patch']

    switch ($Part) {
        'major' {
            $major += 1
            $minor = 0
            $patch = 0
        }
        'minor' {
            $minor += 1
            $patch = 0
        }
        default {
            $patch += 1
        }
    }

    return "$major.$minor.$patch"
}

function Get-GitHubRepositoryInfo {
    param(
        [Parameter(Mandatory = $true)]
        [string]$RemoteUrl
    )

    $trimmed = $RemoteUrl.Trim()
    if ($trimmed -match '^git@github\.com:(?<slug>[^/]+/[^/]+?)(?:\.git)?$') {
        $slug = $Matches['slug']
    } elseif ($trimmed -match '^https://github\.com/(?<slug>[^/]+/[^/]+?)(?:\.git)?/?$') {
        $slug = $Matches['slug']
    } else {
        return $null
    }

    return [pscustomobject]@{
        Slug    = $slug
        BaseUrl = "https://github.com/$slug"
    }
}

function Get-PythonCommand {
    $venvPython = Join-Path $repoRoot '.venv\Scripts\python.exe'
    if (Test-Path $venvPython) {
        return $venvPython
    }
    $pythonCommand = Get-Command python -ErrorAction SilentlyContinue
    if ($pythonCommand) {
        return $pythonCommand.Source
    }
    throw 'python was not found. Run uv sync first or ensure python is on PATH.'
}

function New-ReleaseNotesPreview {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Tag,
        [Parameter(Mandatory = $true)]
        [string]$PreviousTag,
        [Parameter(Mandatory = $true)]
        [string]$RepoUrl
    )

    $python = Get-PythonCommand
    $arguments = @(
        (Join-Path $repoRoot 'scripts\generate_release_notes.py'),
        '--tag', $Tag,
        '--repo-url', $RepoUrl,
        '--output', '-',
        '--previous-tag', $PreviousTag,
        '--head-ref', 'HEAD'
    )
    $output = & $python @arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Release notes preview failed with exit code $LASTEXITCODE."
    }
    return ($output -join [Environment]::NewLine)
}

function Confirm-ReleasePublish {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Tag
    )

    if ($Yes) {
        return
    }
    $answer = Read-Host "Publish $Tag now? Type 'yes' to push master and the release tag"
    if ($answer -ne 'yes') {
        throw 'Release publishing cancelled before pushing refs.'
    }
}

function Test-ReleaseAssetNames {
    param(
        [Parameter(Mandatory = $true)]
        [object[]]$Assets,
        [Parameter(Mandatory = $true)]
        [string[]]$ExpectedNames
    )

    $assetNames = @($Assets | ForEach-Object { $_.name })
    foreach ($expected in $ExpectedNames) {
        if ($assetNames -notcontains $expected) {
            return $false
        }
    }
    return $true
}

function Test-GitHubRelease {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Tag,
        [Parameter(Mandatory = $true)]
        [string[]]$ExpectedAssets
    )

    $json = & gh release view $Tag --json url,body,assets 2>$null
    if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($json)) {
        return $null
    }
    $release = $json | ConvertFrom-Json
    if ([string]::IsNullOrWhiteSpace($release.body)) {
        return $null
    }
    if (-not (Test-ReleaseAssetNames -Assets @($release.assets) -ExpectedNames $ExpectedAssets)) {
        return $null
    }
    return $release
}

function Wait-GitHubRelease {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Tag,
        [Parameter(Mandatory = $true)]
        [string[]]$ExpectedAssets,
        [Parameter(Mandatory = $true)]
        [pscustomobject]$GitHubRepo
    )

    if (-not (Get-Command gh -ErrorAction SilentlyContinue)) {
        Write-Warning 'gh was not found on PATH; skipping GitHub Release verification.'
        Write-Output "Release page: $($GitHubRepo.BaseUrl)/releases/tag/$Tag"
        Write-Output "Workflow page: $($GitHubRepo.BaseUrl)/actions/workflows/release.yml"
        return
    }

    $null = & gh auth status 2>$null
    if ($LASTEXITCODE -ne 0) {
        Write-Warning 'gh is not authenticated; skipping GitHub Release verification.'
        Write-Output "Release page: $($GitHubRepo.BaseUrl)/releases/tag/$Tag"
        Write-Output "Workflow page: $($GitHubRepo.BaseUrl)/actions/workflows/release.yml"
        return
    }

    $deadline = (Get-Date).AddSeconds([Math]::Max($VerifyTimeoutSeconds, 1))
    $pollSeconds = [Math]::Max($VerifyPollSeconds, 1)
    while ((Get-Date) -lt $deadline) {
        $release = Test-GitHubRelease -Tag $Tag -ExpectedAssets $ExpectedAssets
        if ($null -ne $release) {
            Write-Output ''
            Write-Output 'Verified GitHub Release'
            Write-Output "Release page: $($release.url)"
            foreach ($asset in $release.assets) {
                if ($ExpectedAssets -contains $asset.name) {
                    Write-Output "Asset: $($asset.name) -> $($asset.url)"
                }
            }
            return
        }
        Start-Sleep -Seconds $pollSeconds
    }

    Write-Warning "Timed out waiting for GitHub Release $Tag to contain notes and expected assets."
    Write-Output "Release page: $($GitHubRepo.BaseUrl)/releases/tag/$Tag"
    Write-Output "Workflow page: $($GitHubRepo.BaseUrl)/actions/workflows/release.yml"
}

function Write-ReleaseSummary {
    param(
        [Parameter(Mandatory = $true)]
        [string]$CurrentVersion,
        [Parameter(Mandatory = $true)]
        [string]$NextVersion,
        [Parameter(Mandatory = $true)]
        [string]$Branch,
        [Parameter(Mandatory = $true)]
        [string]$Tag,
        [Parameter(Mandatory = $true)]
        [string]$CommitSha,
        [Parameter()]
        [pscustomobject]$GitHubRepo
    )

    $zipAsset = "BarByBar-$Tag-windows-x64.zip"
    $setupAsset = "BarByBar-$Tag-windows-x64-setup.exe"

    Write-Output ''
    Write-Output 'Published'
    Write-Output "Version: $CurrentVersion -> $NextVersion"
    Write-Output "Branch: $Branch"
    Write-Output "Tag: $Tag"
    Write-Output "Commit: $CommitSha"

    if ($null -ne $GitHubRepo) {
        $releasesPage = "$($GitHubRepo.BaseUrl)/releases"
        $tagPage = "$($GitHubRepo.BaseUrl)/releases/tag/$Tag"
        $workflowPage = "$($GitHubRepo.BaseUrl)/actions/workflows/release.yml"
        $tagsPage = "$($GitHubRepo.BaseUrl)/tags"

        Write-Output ''
        Write-Output "Release page: $releasesPage"
        Write-Output "Tag page: $tagPage"
        Write-Output "Workflow page: $workflowPage"
        Write-Output "Tags page: $tagsPage"

        Write-Output ''
        Write-Output 'Expected assets:'
        Write-Output "  $zipAsset"
        Write-Output "  $($GitHubRepo.BaseUrl)/releases/download/$Tag/$zipAsset"
        Write-Output "  $setupAsset"
        Write-Output "  $($GitHubRepo.BaseUrl)/releases/download/$Tag/$setupAsset"
        Write-Output 'Assets are built and uploaded by the GitHub Actions release workflow; after pushing the tag it may take a few minutes to appear.'
    } else {
        Write-Output ''
        Write-Output 'GitHub links: unavailable (origin is not a recognized GitHub remote)'
    }
}

$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    throw 'git was not found on PATH.'
}

$statusLines = @(Get-GitOutput -Arguments @('status', '--porcelain'))
if ($statusLines.Count -gt 0) {
    throw 'Working tree is not clean. Commit or stash changes before publishing a release tag.'
}

$versionFile = Join-Path $repoRoot 'src\barbybar\__init__.py'
if (-not (Test-Path $versionFile)) {
    throw "Version file not found: $versionFile"
}

$versionFileContent = Get-Content $versionFile -Raw
$versionMatch = [regex]::Match($versionFileContent, '__version__\s*=\s*"(?<version>[^"]+)"')
if (-not $versionMatch.Success) {
    throw "Unable to read __version__ from $versionFile"
}

$currentVersion = $versionMatch.Groups['version'].Value
Invoke-Git -Arguments @('fetch', '--tags', 'origin')
$latestTag = (Get-GitOutput -Arguments @('tag', '--list', 'v*', '--sort=-version:refname') | Select-Object -First 1).Trim()
$latestVersion = if ($latestTag) { $latestTag.TrimStart('v') } else { $currentVersion }
$nextVersion = Get-IncrementedVersion -Version $latestVersion -Part $normalizedPart
$tag = "v$nextVersion"
$branch = (Get-GitOutput -Arguments @('rev-parse', '--abbrev-ref', 'HEAD')).Trim()
$remoteUrl = (Get-GitOutput -Arguments @('remote', 'get-url', 'origin')).Trim()
$githubRepo = Get-GitHubRepositoryInfo -RemoteUrl $remoteUrl
$existingTagOutput = Get-GitOutput -Arguments @('tag', '--list', $tag) | Select-Object -First 1
$existingTag = if ($existingTagOutput) { $existingTagOutput.Trim() } else { '' }
$remoteTagExists = Test-GitRefExists -Arguments @('ls-remote', '--exit-code', '--tags', 'origin', $tag)

if ($branch -ne 'master') {
    throw "Release tags must be created from master. Current branch: $branch"
}

if ($existingTag) {
    throw "Release tag $tag already exists locally."
}

if ($remoteTagExists) {
    throw "Release tag $tag already exists on origin."
}

$repoUrl = if ($null -ne $githubRepo) { $githubRepo.BaseUrl } else { 'https://github.com/local/BarByBar' }
$releaseNotesPreview = New-ReleaseNotesPreview -Tag $tag -PreviousTag $latestTag -RepoUrl $repoUrl

Write-Output ''
Write-Output 'Release preview'
Write-Output "Version: $currentVersion -> $nextVersion"
Write-Output "Previous tag: $(if ($latestTag) { $latestTag } else { 'none' })"
Write-Output "Target tag: $tag"
Write-Output ''
Write-Output $releaseNotesPreview

if ($Preview) {
    Write-Output 'Preview complete; no files, commits, pushes, or tags were changed.'
    exit 0
}

Confirm-ReleasePublish -Tag $tag

if ($currentVersion -ne $nextVersion) {
    $updatedContent = [regex]::Replace(
        $versionFileContent,
        '__version__\s*=\s*"[^"]+"',
        "__version__ = `"$nextVersion`"",
        1
    )
    Set-Content -Path $versionFile -Value $updatedContent -NoNewline
}

Invoke-Git -Arguments @('add', $versionFile)
$null = & git diff --cached --quiet
$diffExitCode = $LASTEXITCODE
if ($diffExitCode -eq 1) {
    Invoke-Git -Arguments @('commit', '-m', "Release $tag")
} elseif ($diffExitCode -eq 0) {
    if ($currentVersion -ne $nextVersion) {
        throw "No version changes were staged for $tag."
    }
    Write-Output "Version file is already at $nextVersion; reusing current HEAD for $tag."
} else {
    throw "git diff --cached --quiet failed with exit code $diffExitCode."
}

Invoke-Git -Arguments @('push', 'origin', $branch)
Invoke-Git -Arguments @('tag', $tag)
Invoke-Git -Arguments @('push', 'origin', $tag)

$commitSha = (Get-GitOutput -Arguments @('rev-parse', '--short', 'HEAD')).Trim()
Write-ReleaseSummary -CurrentVersion $currentVersion -NextVersion $nextVersion -Branch $branch -Tag $tag -CommitSha $commitSha -GitHubRepo $githubRepo

if ($VerifyRelease) {
    if ($null -eq $githubRepo) {
        Write-Warning 'GitHub Release verification requires a recognized GitHub origin remote.'
    } else {
        $expectedAssets = @("BarByBar-$tag-windows-x64.zip", "BarByBar-$tag-windows-x64-setup.exe")
        Wait-GitHubRelease -Tag $tag -ExpectedAssets $expectedAssets -GitHubRepo $githubRepo
    }
}
