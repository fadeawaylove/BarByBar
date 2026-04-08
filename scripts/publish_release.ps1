param(
    [string]$Remote = "origin",
    [string]$Branch = "",
    [string]$CommitMessage = "",
    [string]$BumpVersion = "",
    [switch]$StageAll,
    [switch]$ForceTag
)

$ErrorActionPreference = "Stop"

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

$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    throw "git was not found on PATH."
}

$versionFile = Join-Path $repoRoot "src\barbybar\__init__.py"
if (-not (Test-Path $versionFile)) {
    throw "Version file not found: $versionFile"
}

$versionFileContent = Get-Content $versionFile -Raw
$versionMatch = [regex]::Match($versionFileContent, '__version__\s*=\s*"(?<version>[^"]+)"')
if (-not $versionMatch.Success) {
    throw "Unable to read __version__ from $versionFile"
}

$version = $versionMatch.Groups["version"].Value
if ($BumpVersion) {
    if ($BumpVersion -notmatch '^\d+\.\d+\.\d+$') {
        throw "BumpVersion must use semantic version format X.Y.Z."
    }
    $updatedContent = [regex]::Replace(
        $versionFileContent,
        '__version__\s*=\s*"[^"]+"',
        "__version__ = ""$BumpVersion""",
        1
    )
    Set-Content -Path $versionFile -Value $updatedContent -NoNewline
    $version = $BumpVersion
}

$tag = "v$version"

if (-not $Branch) {
    $Branch = (Get-GitOutput -Arguments @("rev-parse", "--abbrev-ref", "HEAD")).Trim()
}

$statusLines = @(Get-GitOutput -Arguments @("status", "--short"))
$hasChanges = $statusLines.Count -gt 0

if ($hasChanges -and -not $StageAll) {
    throw "Working tree is not clean. Commit changes first or rerun with -StageAll."
}

if ($StageAll) {
    Invoke-Git -Arguments @("add", "--all")
    $postAddStatus = @(Get-GitOutput -Arguments @("status", "--short"))
    if ($postAddStatus.Count -gt 0) {
        $hasStagedChanges = $false
        foreach ($line in $postAddStatus) {
            if ($line.Length -ge 1 -and $line[0] -ne ' ') {
                $hasStagedChanges = $true
                break
            }
        }

        if ($hasStagedChanges) {
            if (-not $CommitMessage) {
                $CommitMessage = "Release $tag"
            }
            Invoke-Git -Arguments @("commit", "-m", $CommitMessage)
        }
    }
}

$localTagExists = $false
try {
    $existingLocalTag = (Get-GitOutput -Arguments @("tag", "--list", $tag)).Trim()
    $localTagExists = [string]::IsNullOrWhiteSpace($existingLocalTag) -eq $false
}
catch {
    $localTagExists = $false
}

$remoteTagExists = $false
try {
    $remoteTagLookup = Get-GitOutput -Arguments @("ls-remote", "--tags", $Remote, "refs/tags/$tag")
    $remoteTagExists = [string]::IsNullOrWhiteSpace(($remoteTagLookup -join "").Trim()) -eq $false
}
catch {
    $remoteTagExists = $false
}

if (($localTagExists -or $remoteTagExists) -and -not $ForceTag) {
    throw "Tag $tag already exists. Rerun with -ForceTag to replace it."
}

if ($localTagExists -and $ForceTag) {
    Invoke-Git -Arguments @("tag", "-d", $tag)
}

Invoke-Git -Arguments @("push", $Remote, $Branch)

if ($remoteTagExists -and $ForceTag) {
    Invoke-Git -Arguments @("push", $Remote, ":refs/tags/$tag")
}

Invoke-Git -Arguments @("tag", $tag)
Invoke-Git -Arguments @("push", $Remote, $tag)

Write-Output "Published release tag $tag from branch $Branch."
