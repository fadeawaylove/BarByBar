import io
from pathlib import Path

import pytest

import barbybar.update_service as update_service
from barbybar.update_service import UpdateInfo, check_for_update, download_installer, is_newer_version, parse_release_payload


class _FakeResponse:
    def __init__(self, data: bytes, headers: dict[str, str] | None = None) -> None:
        self._buffer = io.BytesIO(data)
        self.headers = headers or {}

    def read(self, size: int = -1) -> bytes:
        return self._buffer.read(size)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb) -> None:  # noqa: ANN001
        return None


def test_parse_release_payload_returns_update_info_for_newer_release() -> None:
    payload = {
        "tag_name": "v0.3.0",
        "draft": False,
        "prerelease": False,
        "body": "Bug fixes",
        "assets": [
            {
                "name": "BarByBar-v0.3.0-windows-x64-setup.exe",
                "browser_download_url": "https://example.com/setup.exe",
                "size": 1024,
            }
        ],
    }

    update_info = parse_release_payload(payload, "0.2.9")

    assert update_info is not None
    assert update_info.version == "0.3.0"
    assert update_info.installer_name.endswith("-setup.exe")


def test_parse_release_payload_ignores_prerelease() -> None:
    payload = {
        "tag_name": "v0.3.0",
        "draft": False,
        "prerelease": True,
        "assets": [],
    }

    assert parse_release_payload(payload, "0.2.9") is None


def test_parse_release_payload_requires_setup_asset() -> None:
    payload = {
        "tag_name": "v0.3.0",
        "draft": False,
        "prerelease": False,
        "assets": [
            {
                "name": "BarByBar-v0.3.0-windows-x64.zip",
                "browser_download_url": "https://example.com/app.zip",
            }
        ],
    }

    with pytest.raises(ValueError, match="setup installer"):
        parse_release_payload(payload, "0.2.9")


def test_is_newer_version_compares_semver() -> None:
    assert is_newer_version("0.3.0", "0.2.9") is True
    assert is_newer_version("0.2.9", "0.2.9") is False


def test_check_for_update_uses_latest_release_response(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = (
        '{"tag_name":"v0.3.0","draft":false,"prerelease":false,"body":"Notes",'
        '"assets":[{"name":"BarByBar-v0.3.0-windows-x64-setup.exe","browser_download_url":"https://example.com/setup.exe","size":1024}]}'
    ).encode("utf-8")
    monkeypatch.setattr(update_service, "urlopen", lambda request, timeout=15: _FakeResponse(payload))

    update_info = check_for_update("0.2.9")

    assert update_info is not None
    assert update_info.version == "0.3.0"


def test_download_installer_writes_file_and_reports_progress(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    update_info = UpdateInfo(
        version="0.3.0",
        tag="v0.3.0",
        release_notes="Notes",
        installer_url="https://example.com/setup.exe",
        installer_name="BarByBar-v0.3.0-windows-x64-setup.exe",
        asset_size=6,
    )
    progress: list[tuple[int, int]] = []
    monkeypatch.setattr(
        update_service,
        "urlopen",
        lambda request, timeout=30: _FakeResponse(b"abcdef", headers={"Content-Length": "6"}),
    )

    output = download_installer(
        update_info,
        tmp_path / update_info.installer_name,
        lambda current, total: progress.append((current, total)),
    )

    assert output.read_bytes() == b"abcdef"
    assert progress[-1] == (6, 6)


def test_download_installer_reuses_matching_existing_file(tmp_path: Path) -> None:
    update_info = UpdateInfo(
        version="0.3.0",
        tag="v0.3.0",
        release_notes="Notes",
        installer_url="https://example.com/setup.exe",
        installer_name="BarByBar-v0.3.0-windows-x64-setup.exe",
        asset_size=6,
    )
    target = tmp_path / update_info.installer_name
    target.write_bytes(b"abcdef")

    output = download_installer(update_info, target)

    assert output == target
