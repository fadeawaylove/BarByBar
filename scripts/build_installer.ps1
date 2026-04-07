param(
    [string]$Version = "",
    [string]$Tag = "",
    [string]$WixBin = ""
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

$versionToShow = if ($Version) { $Version } else { & .\.venv\Scripts\python.exe -c "from barbybar import __version__; print(__version__)" }

& .\scripts\build_release.ps1 -Version $Version -Tag $Tag
if ($LASTEXITCODE -ne 0) {
    throw "Portable build failed with exit code $LASTEXITCODE."
}

if (-not $WixBin) {
    $candidates = @(
        "C:\Program Files (x86)\WiX Toolset v3.11\bin",
        "C:\Program Files\WiX Toolset v3.11\bin"
    )
    $WixBin = $candidates | Where-Object { Test-Path (Join-Path $_ 'candle.exe') } | Select-Object -First 1
}

if (-not $WixBin) {
    throw "WiX Toolset not found. Install WiX Toolset, or pass -WixBin to the WiX bin directory."
}

$heatExe = Join-Path $WixBin "heat.exe"
$candleExe = Join-Path $WixBin "candle.exe"
$lightExe = Join-Path $WixBin "light.exe"
$installerDir = Join-Path $repoRoot "installer"
$sourceDir = Join-Path $repoRoot "dist\release\BarByBar"
$harvestPath = Join-Path $installerDir "HarvestedFiles.wxs"
$productPath = Join-Path $installerDir "BarByBar.wxs"
$msiPath = Join-Path $repoRoot "dist\BarByBar-$versionToShow-windows-x64.msi"
$assetsDir = Join-Path $repoRoot "src\barbybar\assets"

& $heatExe dir $sourceDir -nologo -cg AppFiles -dr INSTALLDIR -gg -scom -sreg -sfrag -srd -var var.SourceDir -out $harvestPath
if ($LASTEXITCODE -ne 0) {
    throw "WiX heat failed with exit code $LASTEXITCODE."
}

& $candleExe -nologo -arch x64 -dAppVersion=$versionToShow -dSourceDir=$sourceDir -dAssetsDir=$assetsDir $productPath $harvestPath
if ($LASTEXITCODE -ne 0) {
    throw "WiX candle failed with exit code $LASTEXITCODE."
}

& $lightExe -nologo -out $msiPath (Join-Path $installerDir 'BarByBar.wixobj') (Join-Path $installerDir 'HarvestedFiles.wixobj')
if ($LASTEXITCODE -ne 0) {
    throw "WiX light failed with exit code $LASTEXITCODE."
}

Write-Output "Created MSI: $msiPath"
