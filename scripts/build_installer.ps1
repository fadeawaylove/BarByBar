param(
    [string]$Version = "",
    [string]$Tag = "",
    [string]$InnoCompiler = ""
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

$versionToShow = if ($Version) { $Version } else { & .\.venv\Scripts\python.exe -c "from barbybar import __version__; print(__version__)" }

& .\scripts\build_release.ps1 -Version $Version -Tag $Tag
if ($LASTEXITCODE -ne 0) {
    throw "Portable build failed with exit code $LASTEXITCODE."
}

if (-not $InnoCompiler) {
    $isccCommand = Get-Command ISCC.exe -ErrorAction SilentlyContinue
    if ($isccCommand) {
        $InnoCompiler = $isccCommand.Source
    }
}

if (-not $InnoCompiler) {
    $candidates = @(
        "C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
        "C:\Program Files\Inno Setup 6\ISCC.exe",
        "C:\ProgramData\chocolatey\bin\ISCC.exe"
    )
    $InnoCompiler = $candidates | Where-Object { Test-Path $_ } | Select-Object -First 1
}

if (-not $InnoCompiler) {
    $innoInChocolateyLib = Get-ChildItem 'C:\ProgramData\chocolatey\lib' -Directory -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -like 'innosetup*' } |
        ForEach-Object {
            Get-ChildItem $_.FullName -Recurse -Filter 'ISCC.exe' -ErrorAction SilentlyContinue |
                Select-Object -ExpandProperty FullName
        } |
        Select-Object -First 1
    if ($innoInChocolateyLib) {
        $InnoCompiler = $innoInChocolateyLib
    }
}

if (-not $InnoCompiler) {
    throw "Inno Setup compiler not found. Install Inno Setup, ensure ISCC.exe is on PATH, or pass -InnoCompiler."
}

if (-not (Test-Path $InnoCompiler)) {
    throw "Inno Setup compiler not found at $InnoCompiler"
}

$installerDir = Join-Path $repoRoot "installer"
$sourceDir = Join-Path $repoRoot "dist\release\BarByBar"
$scriptPath = Join-Path $installerDir "BarByBar.iss"
$outputDir = Join-Path $repoRoot "dist"
$outputBaseName = "BarByBar-v$versionToShow-windows-x64-setup"
$setupPath = Join-Path $outputDir "$outputBaseName.exe"
$assetsDir = Join-Path $repoRoot "src\barbybar\assets"

if (-not (Test-Path $scriptPath)) {
    throw "Inno Setup script not found: $scriptPath"
}

if (-not (Test-Path $sourceDir)) {
    throw "Portable bundle directory not found: $sourceDir"
}

Remove-Item -LiteralPath $setupPath -Force -ErrorAction SilentlyContinue

Write-Output "Using Inno Setup compiler: $InnoCompiler"
Write-Output "Using source directory: $sourceDir"
Write-Output "Using output path: $setupPath"

& $InnoCompiler `
    "/DMyAppVersion=$versionToShow" `
    "/DSourceDir=$sourceDir" `
    "/DAssetsDir=$assetsDir" `
    "/DOutputDir=$outputDir" `
    "/DOutputBaseFilename=$outputBaseName" `
    $scriptPath
if ($LASTEXITCODE -ne 0) {
    throw "Inno Setup compilation failed with exit code $LASTEXITCODE."
}

Write-Output "Created setup installer: $setupPath"
