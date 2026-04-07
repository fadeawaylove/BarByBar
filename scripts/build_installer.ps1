param(
    [string]$Version = "",
    [string]$Tag = "",
    [string]$WixBin = ""
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

$versionToShow = if ($Version) { $Version } else { & .\.venv\Scripts\python.exe -c "from barbybar import __version__; print(__version__)" }
$msiVersion = if ($versionToShow -match '^\d+\.\d+\.\d+$') { "$versionToShow.0" } else { $versionToShow }

& .\scripts\build_release.ps1 -Version $Version -Tag $Tag
if ($LASTEXITCODE -ne 0) {
    throw "Portable build failed with exit code $LASTEXITCODE."
}

if (-not $WixBin) {
    $candleCommand = Get-Command candle.exe -ErrorAction SilentlyContinue
    if ($candleCommand) {
        $WixBin = Split-Path -Parent $candleCommand.Source
    }
}

if (-not $WixBin) {
    $candidates = @(
        "C:\ProgramData\chocolatey\bin",
        "C:\ProgramData\chocolatey\lib\wixtoolset\tools",
        "C:\Program Files (x86)\WiX Toolset v3.11\bin",
        "C:\Program Files\WiX Toolset v3.11\bin",
        "C:\Program Files (x86)\WiX Toolset v3.14\bin",
        "C:\Program Files\WiX Toolset v3.14\bin"
    )
    $WixBin = $candidates | Where-Object { Test-Path (Join-Path $_ 'candle.exe') } | Select-Object -First 1
}

if (-not $WixBin) {
    $wixInChocolateyLib = Get-ChildItem 'C:\ProgramData\chocolatey\lib' -Directory -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -like 'wixtoolset*' } |
        ForEach-Object {
            Get-ChildItem $_.FullName -Directory -Recurse -ErrorAction SilentlyContinue |
                Where-Object { Test-Path (Join-Path $_.FullName 'candle.exe') } |
                Select-Object -ExpandProperty FullName
        } |
        Select-Object -First 1
    if ($wixInChocolateyLib) {
        $WixBin = $wixInChocolateyLib
    }
}

if (-not $WixBin) {
    throw "WiX Toolset not found. Install WiX Toolset, ensure candle.exe is on PATH, or pass -WixBin to the WiX bin directory."
}

$heatExe = Join-Path $WixBin "heat.exe"
$candleExe = Join-Path $WixBin "candle.exe"
$lightExe = Join-Path $WixBin "light.exe"
$installerDir = Join-Path $repoRoot "installer"
$sourceDir = Join-Path $repoRoot "dist\release\BarByBar"
$harvestPath = Join-Path $installerDir "HarvestedFiles.wxs"
$productPath = Join-Path $installerDir "BarByBar.wxs"
$productObjPath = Join-Path $installerDir "BarByBar.wixobj"
$harvestObjPath = Join-Path $installerDir "HarvestedFiles.wixobj"
$msiPath = Join-Path $repoRoot "dist\BarByBar-$versionToShow-windows-x64.msi"
$assetsDir = Join-Path $repoRoot "src\barbybar\assets"
$wixOutDir = ([System.IO.Path]::GetFullPath($installerDir)) + "\"

Remove-Item -LiteralPath $productObjPath -Force -ErrorAction SilentlyContinue
Remove-Item -LiteralPath $harvestObjPath -Force -ErrorAction SilentlyContinue

& $heatExe dir $sourceDir -nologo -cg AppFiles -dr INSTALLDIR -gg -scom -sreg -sfrag -srd -var var.SourceDir -out $harvestPath
if ($LASTEXITCODE -ne 0) {
    throw "WiX heat failed with exit code $LASTEXITCODE."
}

& $candleExe -nologo -arch x64 "-dAppVersion=$msiVersion" "-dSourceDir=$sourceDir" "-dAssetsDir=$assetsDir" -out $wixOutDir $productPath $harvestPath
if ($LASTEXITCODE -ne 0) {
    throw "WiX candle failed with exit code $LASTEXITCODE."
}

& $lightExe -nologo -out $msiPath $productObjPath $harvestObjPath
if ($LASTEXITCODE -ne 0) {
    throw "WiX light failed with exit code $LASTEXITCODE."
}

Write-Output "Created MSI: $msiPath"
