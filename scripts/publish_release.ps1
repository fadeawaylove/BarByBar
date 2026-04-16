param(
    [Parameter(Position = 0)]
    [string]$BumpPart
)

$ErrorActionPreference = 'Stop'

function Show-Usage {
    Write-Host 'Usage: .\\scripts\\publish_release.ps1 major|minor|patch' -ForegroundColor Yellow
    Write-Host 'Example: .\\scripts\\publish_release.ps1 patch' -ForegroundColor DarkGray
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
$latestTag = (Get-GitOutput -Arguments @('tag', '--list', 'v*', '--sort=-version:refname') | Select-Object -First 1).Trim()
$latestVersion = if ($latestTag) { $latestTag.TrimStart('v') } else { $currentVersion }
$nextVersion = Get-IncrementedVersion -Version $latestVersion -Part $normalizedPart
$tag = "v$nextVersion"
$branch = (Get-GitOutput -Arguments @('rev-parse', '--abbrev-ref', 'HEAD')).Trim()
$remoteUrl = (Get-GitOutput -Arguments @('remote', 'get-url', 'origin')).Trim()
$githubRepo = Get-GitHubRepositoryInfo -RemoteUrl $remoteUrl

if ($branch -ne 'master') {
    throw "Release tags must be created from master. Current branch: $branch"
}

$updatedContent = [regex]::Replace(
    $versionFileContent,
    '__version__\s*=\s*"[^"]+"',
    "__version__ = `"$nextVersion`"",
    1
)
Set-Content -Path $versionFile -Value $updatedContent -NoNewline

Invoke-Git -Arguments @('add', $versionFile)
Invoke-Git -Arguments @('commit', '-m', "Release $tag")

Invoke-Git -Arguments @('push', 'origin', $branch)
Invoke-Git -Arguments @('tag', $tag)
Invoke-Git -Arguments @('push', 'origin', $tag)

$commitSha = (Get-GitOutput -Arguments @('rev-parse', '--short', 'HEAD')).Trim()
Write-ReleaseSummary -CurrentVersion $currentVersion -NextVersion $nextVersion -Branch $branch -Tag $tag -CommitSha $commitSha -GitHubRepo $githubRepo
