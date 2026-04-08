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

$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    throw 'git was not found on PATH.'
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
$nextVersion = Get-IncrementedVersion -Version $currentVersion -Part $normalizedPart
$updatedContent = [regex]::Replace(
    $versionFileContent,
    '__version__\s*=\s*"[^"]+"',
    "__version__ = ""$nextVersion""",
    1
)
Set-Content -Path $versionFile -Value $updatedContent -NoNewline

$tag = "v$nextVersion"
$branch = (Get-GitOutput -Arguments @('rev-parse', '--abbrev-ref', 'HEAD')).Trim()

Invoke-Git -Arguments @('add', '.')
Invoke-Git -Arguments @('commit', '-m', "Release $tag")
Invoke-Git -Arguments @('push', 'origin', $branch)
Invoke-Git -Arguments @('tag', $tag)
Invoke-Git -Arguments @('push', 'origin', $tag)

Write-Output "Published $tag from branch $branch."

