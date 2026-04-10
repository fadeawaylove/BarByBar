from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Callable
from urllib.request import Request, urlopen


GITHUB_OWNER = "fadeawaylove"
GITHUB_REPO = "BarByBar"
LATEST_RELEASE_URL = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/releases/latest"
SETUP_ASSET_SUFFIX = "-windows-x64-setup.exe"
USER_AGENT = "BarByBar-Updater"


@dataclass(slots=True)
class UpdateInfo:
    version: str
    tag: str
    release_notes: str
    installer_url: str
    installer_name: str
    asset_size: int | None = None


def _normalize_version(version: str) -> str:
    value = version.strip()
    if value.lower().startswith("v"):
        value = value[1:]
    return value


def _version_key(version: str) -> tuple[int, ...]:
    normalized = _normalize_version(version)
    parts = normalized.split(".")
    if len(parts) != 3:
        raise ValueError(f"Unsupported version format: {version}")
    return tuple(int(part) for part in parts)


def is_newer_version(remote_version: str, current_version: str) -> bool:
    return _version_key(remote_version) > _version_key(current_version)


def parse_release_payload(payload: dict[str, object], current_version: str) -> UpdateInfo | None:
    if bool(payload.get("draft")) or bool(payload.get("prerelease")):
        return None
    tag = str(payload.get("tag_name") or "").strip()
    version = _normalize_version(tag)
    if not version:
        raise ValueError("Latest release is missing a tag name.")
    if not is_newer_version(version, current_version):
        return None
    assets = payload.get("assets")
    if not isinstance(assets, list):
        raise ValueError("Latest release does not contain any assets.")
    installer_asset = next(
        (
            item
            for item in assets
            if isinstance(item, dict)
            and str(item.get("name") or "").endswith(SETUP_ASSET_SUFFIX)
        ),
        None,
    )
    if installer_asset is None:
        raise ValueError("Latest release does not contain a Windows setup installer.")
    installer_name = str(installer_asset.get("name") or "").strip()
    installer_url = str(installer_asset.get("browser_download_url") or "").strip()
    if not installer_name or not installer_url:
        raise ValueError("Latest release installer asset is incomplete.")
    asset_size = installer_asset.get("size")
    return UpdateInfo(
        version=version,
        tag=tag,
        release_notes=str(payload.get("body") or "").strip(),
        installer_url=installer_url,
        installer_name=installer_name,
        asset_size=int(asset_size) if isinstance(asset_size, int) else None,
    )


def check_for_update(current_version: str, *, release_url: str = LATEST_RELEASE_URL) -> UpdateInfo | None:
    request = Request(
        release_url,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": USER_AGENT,
        },
    )
    with urlopen(request, timeout=15) as response:  # noqa: S310
        payload = json.loads(response.read().decode("utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Unexpected release response payload.")
    return parse_release_payload(payload, current_version)


def download_installer(
    update_info: UpdateInfo,
    target_path: str | Path,
    progress_callback: Callable[[int, int], None] | None = None,
) -> Path:
    destination = Path(target_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists() and update_info.asset_size is not None and destination.stat().st_size == update_info.asset_size:
        if progress_callback is not None:
            progress_callback(update_info.asset_size, update_info.asset_size)
        return destination
    temp_path = destination.with_suffix(destination.suffix + ".download")
    if temp_path.exists():
        temp_path.unlink()
    request = Request(update_info.installer_url, headers={"User-Agent": USER_AGENT})
    downloaded = 0
    total = max(update_info.asset_size or 0, 0)
    try:
        with urlopen(request, timeout=30) as response, temp_path.open("wb") as handle:  # noqa: S310
            header_total = response.headers.get("Content-Length")
            if header_total:
                total = max(total, int(header_total))
            while True:
                chunk = response.read(1024 * 64)
                if not chunk:
                    break
                handle.write(chunk)
                downloaded += len(chunk)
                if progress_callback is not None:
                    progress_callback(downloaded, total)
        temp_path.replace(destination)
    except Exception:
        if temp_path.exists():
            temp_path.unlink()
        raise
    if progress_callback is not None:
        progress_callback(downloaded, max(total, downloaded))
    return destination
