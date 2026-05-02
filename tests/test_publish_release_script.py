from pathlib import Path


def _script_text() -> str:
    return (Path(__file__).resolve().parents[1] / "scripts" / "publish_release.ps1").read_text(encoding="utf-8")


def test_publish_release_script_exposes_safe_publish_modes() -> None:
    text = _script_text()

    assert "[Console]::OutputEncoding = $script:Utf8NoBom" in text
    assert "$OutputEncoding = $script:Utf8NoBom" in text
    assert "[switch]$Preview" in text
    assert "[switch]$Yes" in text
    assert "[switch]$VerifyRelease" in text
    assert "New-ReleaseNotesPreview" in text
    assert "'--output', '-'" in text
    assert "Confirm-ReleasePublish -Tag $tag" in text
    assert "ls-remote" in text
    assert "fetch', '--tags', 'origin" in text


def test_publish_release_script_confirms_before_writing_version_file() -> None:
    text = _script_text()

    preview_index = text.index("if ($Preview)")
    confirm_index = text.index("Confirm-ReleasePublish -Tag $tag")
    write_index = text.index("Set-Content -Path $versionFile")
    commit_index = text.index("Invoke-Git -Arguments @('commit', '-m', \"Release $tag\")")

    assert preview_index < confirm_index < write_index < commit_index
