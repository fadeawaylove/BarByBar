from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def test_inno_identity_can_be_overridden_without_changing_production_default() -> None:
    text = _read("installer/BarByBar.iss")

    assert "#ifndef MyAppId" in text
    assert '#define MyAppId "{{A516BBBA-3B66-4A27-9F44-03D52CB9D89D}"' in text
    assert "#ifndef MyAppName" in text
    assert "#ifndef MyProgramGroupName" in text
    assert "DefaultGroupName={#MyProgramGroupName}" in text


def test_installer_builder_forwards_isolated_identity_defines() -> None:
    text = _read("scripts/build_installer.ps1")

    assert "[switch]$SkipPortableBuild" in text
    assert '"/DMyAppId=$AppId"' in text
    assert '"/DMyAppName=$AppName"' in text
    assert '"/DMyProgramGroupName=$ProgramGroupName"' in text
    assert "$resolvedOutputBaseName" in text


def test_smoke_installer_uses_dedicated_identity_and_checks_production_state() -> None:
    text = _read("scripts/smoke_test_installer.ps1")

    assert "D92AC99D-5311-4EFA-86BD-E783D15A04D3" in text
    assert "A516BBBA-3B66-4A27-9F44-03D52CB9D89D" in text
    assert "BarByBar Installer Smoke" in text
    assert "Get-ProductionShortcutState" in text
    assert "Get-ProductionUninstallState" in text
    assert "Assert-ProductionStateUnchanged" in text
    assert "$installDirOne" in text and "$installDirTwo" in text
    assert "data-location.json" in text
    assert "executable-adjacent database" in text


def test_release_workflow_runs_isolated_smoke_before_publishing() -> None:
    text = _read(".github/workflows/release.yml")

    build_index = text.index("Build release artifacts")
    smoke_index = text.index("Run isolated installer smoke")
    notes_index = text.index("Generate release notes")
    release_index = text.index("Create or update GitHub Release")

    assert build_index < smoke_index < notes_index < release_index
    assert r".\scripts\smoke_test_installer.ps1" in text
