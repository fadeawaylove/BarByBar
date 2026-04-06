param(
    [string]$Version = "",
    [string]$Tag = ""
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

if (-not $Version) {
    $Version = & .\.venv\Scripts\python.exe -c "from barbybar import __version__; print(__version__)" 2>$null
    if (-not $Version) {
        throw "Unable to determine package version."
    }
}

if ($Tag) {
    $normalizedTag = $Tag.Trim()
    if ($normalizedTag.StartsWith("refs/tags/")) {
        $normalizedTag = $normalizedTag.Substring(10)
    }
    if ($normalizedTag.StartsWith("v")) {
        $normalizedTag = $normalizedTag.Substring(1)
    }
    if ($normalizedTag -ne $Version) {
        throw "Release tag '$Tag' does not match package version '$Version'."
    }
}

$archiveName = "BarByBar-v$Version-windows-x64.zip"
$distDir = Join-Path $repoRoot "dist"
$releaseDir = Join-Path $distDir "release"
$bundleDir = Join-Path $releaseDir "BarByBar"
$archivePath = Join-Path $distDir $archiveName

Remove-Item -LiteralPath $releaseDir -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item -LiteralPath $archivePath -Force -ErrorAction SilentlyContinue

& .\.venv\Scripts\pyinstaller.exe --clean --noconfirm .\BarByBar.spec
if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller build failed with exit code $LASTEXITCODE."
}

New-Item -ItemType Directory -Path $releaseDir | Out-Null
Copy-Item -LiteralPath (Join-Path $distDir "BarByBar") -Destination $bundleDir -Recurse

Compress-Archive -Path (Join-Path $bundleDir "*") -DestinationPath $archivePath -Force

Write-Output "Created archive: $archivePath"
