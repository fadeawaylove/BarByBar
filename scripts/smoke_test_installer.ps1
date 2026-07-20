param(
    [string]$Version = "",
    [string]$InnoCompiler = ""
)

$ErrorActionPreference = "Stop"

$ProductionAppId = "A516BBBA-3B66-4A27-9F44-03D52CB9D89D"
$SmokeAppId = "{{D92AC99D-5311-4EFA-86BD-E783D15A04D3}"
$SmokeAppName = "BarByBar Installer Smoke"
$SmokeProgramGroup = "BarByBar Installer Smoke"
$repoRoot = Split-Path -Parent $PSScriptRoot
$runtimeTempRoot = if ($env:RUNNER_TEMP) { $env:RUNNER_TEMP } else { $env:TEMP }
if ([string]::IsNullOrWhiteSpace($runtimeTempRoot)) {
    throw "A temporary root is required for installer smoke validation."
}
$runtimeTempRoot = (Resolve-Path -LiteralPath $runtimeTempRoot).Path
$smokeRoot = Join-Path $runtimeTempRoot ("barbybar-installer-smoke-" + [guid]::NewGuid().ToString("N"))
$installDirOne = Join-Path $smokeRoot "install-one"
$installDirTwo = Join-Path $smokeRoot "install-two"
$profileRoot = Join-Path $smokeRoot "profile"
$expectedDataRoot = Join-Path $profileRoot "BarByBar\data"
$expectedDatabase = Join-Path $expectedDataRoot "barbybar.db"
$smokeOutputBaseName = "BarByBar-installer-smoke-" + [guid]::NewGuid().ToString("N")
$smokeSetupPath = Join-Path $repoRoot "dist\$smokeOutputBaseName.exe"
$originalLocalAppData = $env:LOCALAPPDATA
$originalDataOverride = $env:BARBYBAR_DATA_DIR
$activeProcess = $null

if (-not $InnoCompiler) {
    $innoCommand = Get-Command ISCC.exe -ErrorAction SilentlyContinue
    if ($innoCommand) {
        $InnoCompiler = $innoCommand.Source
    } else {
        $InnoCompiler = @(
            (Join-Path $originalLocalAppData "Programs\Inno Setup 6\ISCC.exe"),
            "C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
            "C:\Program Files\Inno Setup 6\ISCC.exe"
        ) | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
    }
}
if (-not $InnoCompiler) {
    throw "Inno Setup compiler is required for installer smoke validation."
}

function Get-ProductionShortcutState {
    $shortcutPath = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs\BarByBar\BarByBar.lnk"
    if (-not (Test-Path -LiteralPath $shortcutPath)) {
        return "missing"
    }
    $shell = New-Object -ComObject WScript.Shell
    $shortcut = $shell.CreateShortcut($shortcutPath)
    $hash = (Get-FileHash -LiteralPath $shortcutPath -Algorithm SHA256).Hash
    return "$hash|$($shortcut.TargetPath)|$($shortcut.WorkingDirectory)"
}

function Get-ProductionUninstallState {
    $roots = @(
        "HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall",
        "HKLM:\Software\Microsoft\Windows\CurrentVersion\Uninstall",
        "HKLM:\Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"
    )
    $records = @()
    foreach ($root in $roots) {
        if (-not (Test-Path -LiteralPath $root)) {
            continue
        }
        foreach ($key in Get-ChildItem -LiteralPath $root -ErrorAction SilentlyContinue) {
            $properties = Get-ItemProperty -LiteralPath $key.PSPath -ErrorAction SilentlyContinue
            $displayNameProperty = $properties.PSObject.Properties["DisplayName"]
            $displayName = if ($null -ne $displayNameProperty) { [string]$displayNameProperty.Value } else { "" }
            if ($key.Name -notmatch $ProductionAppId -and $displayName -ne "BarByBar") {
                continue
            }
            $displayVersionProperty = $properties.PSObject.Properties["DisplayVersion"]
            $installLocationProperty = $properties.PSObject.Properties["InstallLocation"]
            $uninstallStringProperty = $properties.PSObject.Properties["UninstallString"]
            $records += [pscustomobject]@{
                Key = $key.Name
                DisplayName = $displayName
                DisplayVersion = if ($null -ne $displayVersionProperty) { [string]$displayVersionProperty.Value } else { "" }
                InstallLocation = if ($null -ne $installLocationProperty) { [string]$installLocationProperty.Value } else { "" }
                UninstallString = if ($null -ne $uninstallStringProperty) { [string]$uninstallStringProperty.Value } else { "" }
            }
        }
    }
    return (($records | Sort-Object Key | ConvertTo-Json -Compress) -join "")
}

function Invoke-SmokeInstall {
    param([Parameter(Mandatory = $true)][string]$TargetDirectory)

    $process = Start-Process -FilePath $smokeSetupPath -ArgumentList @(
        "/VERYSILENT",
        "/SUPPRESSMSGBOXES",
        "/NORESTART",
        "/CLOSEAPPLICATIONS",
        "/DIR=$TargetDirectory"
    ) -Wait -PassThru -WindowStyle Hidden
    if ($process.ExitCode -ne 0) {
        throw "Smoke installer exited with code $($process.ExitCode)."
    }
}

function Invoke-SmokeApplication {
    param([Parameter(Mandatory = $true)][string]$InstallDirectory)

    $executable = Join-Path $InstallDirectory "BarByBar.exe"
    if (-not (Test-Path -LiteralPath $executable)) {
        throw "Smoke executable was not installed: $executable"
    }
    $script:activeProcess = Start-Process -FilePath $executable -WorkingDirectory $InstallDirectory -PassThru -WindowStyle Hidden
    Start-Sleep -Milliseconds 1500
    if ($script:activeProcess.HasExited) {
        throw "Smoke application exited unexpectedly during startup."
    }
    $deadline = (Get-Date).AddSeconds(30)
    while ((Get-Date) -lt $deadline -and -not (Test-Path -LiteralPath $expectedDatabase)) {
        if ($script:activeProcess.HasExited) {
            throw "Smoke application exited before creating its stable database."
        }
        Start-Sleep -Milliseconds 250
    }
    if (-not (Test-Path -LiteralPath $expectedDatabase)) {
        throw "Smoke application did not create the expected stable database: $expectedDatabase"
    }
    Stop-Process -Id $script:activeProcess.Id -Force -ErrorAction SilentlyContinue
    $script:activeProcess.WaitForExit()
    $script:activeProcess = $null
}

function Assert-ProductionStateUnchanged {
    param(
        [Parameter(Mandatory = $true)][AllowEmptyString()][string]$ShortcutBefore,
        [Parameter(Mandatory = $true)][AllowEmptyString()][string]$UninstallBefore
    )

    $shortcutAfter = Get-ProductionShortcutState
    $uninstallAfter = Get-ProductionUninstallState
    if ($shortcutAfter -ne $ShortcutBefore) {
        throw "Installer smoke modified the production BarByBar shortcut."
    }
    if ($uninstallAfter -ne $UninstallBefore) {
        throw "Installer smoke modified the production BarByBar uninstall registration."
    }
}

Set-Location $repoRoot
$productionShortcutBefore = Get-ProductionShortcutState
$productionUninstallBefore = Get-ProductionUninstallState

try {
    New-Item -ItemType Directory -Path $smokeRoot, $profileRoot -Force | Out-Null
    $env:LOCALAPPDATA = $profileRoot
    Remove-Item Env:BARBYBAR_DATA_DIR -ErrorAction SilentlyContinue

    $buildArguments = @{
        Version = $Version
        AppId = $SmokeAppId
        AppName = $SmokeAppName
        ProgramGroupName = $SmokeProgramGroup
        OutputBaseName = $smokeOutputBaseName
        SkipPortableBuild = $true
    }
    $buildArguments.InnoCompiler = $InnoCompiler
    & .\scripts\build_installer.ps1 @buildArguments
    if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $smokeSetupPath)) {
        throw "Isolated smoke installer build failed."
    }

    Invoke-SmokeInstall -TargetDirectory $installDirOne
    Invoke-SmokeApplication -InstallDirectory $installDirOne

    $locatorPath = Join-Path $profileRoot "BarByBar\data-location.json"
    $locator = Get-Content -LiteralPath $locatorPath -Raw | ConvertFrom-Json
    if ([IO.Path]::GetFullPath([string]$locator.data_root) -ne [IO.Path]::GetFullPath($expectedDataRoot)) {
        throw "Smoke locator did not select the stable profile data directory."
    }

    Invoke-SmokeInstall -TargetDirectory $installDirTwo
    Invoke-SmokeApplication -InstallDirectory $installDirTwo

    if (Test-Path -LiteralPath (Join-Path $installDirOne "data\barbybar.db")) {
        throw "First smoke install created an executable-adjacent database."
    }
    if (Test-Path -LiteralPath (Join-Path $installDirTwo "data\barbybar.db")) {
        throw "Second smoke install created an executable-adjacent database."
    }
    Assert-ProductionStateUnchanged -ShortcutBefore $productionShortcutBefore -UninstallBefore $productionUninstallBefore
    Write-Output "Installer smoke passed: data location remained stable across two install directories."
}
finally {
    if ($null -ne $activeProcess -and -not $activeProcess.HasExited) {
        Stop-Process -Id $activeProcess.Id -Force -ErrorAction SilentlyContinue
    }
    $uninstaller = @(
        (Join-Path $installDirTwo "unins000.exe"),
        (Join-Path $installDirOne "unins000.exe")
    ) | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
    if ($uninstaller) {
        Start-Process -FilePath $uninstaller -ArgumentList @("/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART") -Wait -WindowStyle Hidden
    }
    $env:LOCALAPPDATA = $originalLocalAppData
    if ($null -eq $originalDataOverride) {
        Remove-Item Env:BARBYBAR_DATA_DIR -ErrorAction SilentlyContinue
    } else {
        $env:BARBYBAR_DATA_DIR = $originalDataOverride
    }
    Assert-ProductionStateUnchanged -ShortcutBefore $productionShortcutBefore -UninstallBefore $productionUninstallBefore
    if (Test-Path -LiteralPath $smokeSetupPath) {
        Remove-Item -LiteralPath $smokeSetupPath -Force
    }
    if (Test-Path -LiteralPath $smokeRoot) {
        $resolvedSmokeRoot = (Resolve-Path -LiteralPath $smokeRoot).Path
        $resolvedParent = Split-Path -Parent $resolvedSmokeRoot
        if ($resolvedParent -ne $runtimeTempRoot -or (Split-Path -Leaf $resolvedSmokeRoot) -notlike "barbybar-installer-smoke-*") {
            throw "Refusing to remove unexpected smoke directory: $resolvedSmokeRoot"
        }
        Remove-Item -LiteralPath $resolvedSmokeRoot -Recurse -Force
    }
}
