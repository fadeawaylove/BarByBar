from __future__ import annotations

import json
import os
import sqlite3
import sys
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from uuid import uuid4


APP_DIR_ENV_VAR = "BARBYBAR_DATA_DIR"
DATA_LOCATION_FILENAME = "data-location.json"
DATA_LOCATION_VERSION = 1
_REQUIRED_DATABASE_TABLES = frozenset({"datasets", "bars", "sessions"})
_USER_DATA_TABLES = ("datasets", "sessions", "trades", "order_lines", "drawings")


class DataLocationSource(StrEnum):
    ENVIRONMENT = "environment_override"
    LOCATOR = "persistent_locator"
    LEGACY = "legacy_database"
    STABLE = "stable_default"
    PROJECT = "project_default"


_DATA_LOCATION_SOURCE_LABELS = {
    DataLocationSource.ENVIRONMENT: "用户指定目录",
    DataLocationSource.LOCATOR: "已保存的数据位置",
    DataLocationSource.LEGACY: "已接管的旧版数据",
    DataLocationSource.STABLE: "系统默认数据目录",
    DataLocationSource.PROJECT: "项目数据目录",
}


@dataclass(frozen=True, slots=True)
class DataLocation:
    root: Path
    source: DataLocationSource
    locator_path: Path | None = None


@dataclass(frozen=True, slots=True)
class LegacyDatabaseCandidate:
    root: Path
    database_path: Path
    has_user_data: bool


class DataLocationError(RuntimeError):
    """Raised when a safe data directory cannot be selected."""


class DataLocationConflictError(DataLocationError):
    def __init__(self, candidates: tuple[LegacyDatabaseCandidate, ...]) -> None:
        self.candidates = candidates
        paths = "\n".join(f"- {candidate.database_path}" for candidate in candidates)
        super().__init__(f"发现多个包含历史数据的数据库，已停止自动选择：\n{paths}")


_configured_data_location: DataLocation | None = None


def _frozen_app_root() -> Path | None:
    if not getattr(sys, "frozen", False):
        return None
    executable = Path(sys.executable).resolve()
    return executable.parent


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _local_app_data_root() -> Path:
    configured = os.getenv("LOCALAPPDATA", "").strip()
    if configured:
        return Path(configured).expanduser().resolve()
    return (Path.home() / "AppData" / "Local").resolve()


def stable_app_data_root(local_app_data: str | Path | None = None) -> Path:
    local_root = Path(local_app_data).expanduser().resolve() if local_app_data else _local_app_data_root()
    return local_root / "BarByBar"


def data_location_file_path(local_app_data: str | Path | None = None) -> Path:
    return stable_app_data_root(local_app_data) / DATA_LOCATION_FILENAME


def data_location_source_label(source: DataLocationSource | str) -> str:
    try:
        normalized = DataLocationSource(source)
    except ValueError:
        return str(source)
    return _DATA_LOCATION_SOURCE_LABELS[normalized]


def _atomic_write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.parent / f".{path.name}.{uuid4().hex}.partial"
    try:
        with temporary.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except Exception:
        if temporary.exists():
            temporary.unlink()
        raise


def persist_data_location(root: str | Path, locator_path: str | Path) -> Path:
    resolved_root = Path(root).expanduser().resolve()
    resolved_locator = Path(locator_path).expanduser().resolve()
    try:
        _atomic_write_json(
            resolved_locator,
            {
                "version": DATA_LOCATION_VERSION,
                "data_root": str(resolved_root),
            },
        )
    except OSError as exc:
        raise DataLocationError(f"无法保存数据位置记录 {resolved_locator}: {exc}") from exc
    return resolved_locator


def _read_persisted_data_location(locator_path: Path) -> Path | None:
    if not locator_path.exists():
        return None
    try:
        payload = json.loads(locator_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise DataLocationError(f"数据位置记录无法读取：{locator_path}\n{exc}") from exc
    if not isinstance(payload, dict) or payload.get("version") != DATA_LOCATION_VERSION:
        raise DataLocationError(f"数据位置记录格式不受支持：{locator_path}")
    raw_root = payload.get("data_root")
    if not isinstance(raw_root, str) or not raw_root.strip():
        raise DataLocationError(f"数据位置记录缺少有效目录：{locator_path}")
    stored = Path(raw_root).expanduser()
    if not stored.is_absolute():
        raise DataLocationError(f"数据位置记录必须使用绝对目录：{locator_path}")
    resolved = stored.resolve()
    if not resolved.is_dir():
        raise DataLocationError(f"已保存的数据目录不存在或不可访问：{resolved}")
    return resolved


def inspect_legacy_database(root: str | Path) -> LegacyDatabaseCandidate | None:
    resolved_root = Path(root).expanduser().resolve()
    database_path = resolved_root / "barbybar.db"
    if not database_path.is_file():
        return None
    try:
        with database_path.open("rb") as handle:
            if handle.read(16) != b"SQLite format 3\x00":
                raise DataLocationError(f"旧数据文件不是有效的 SQLite 数据库：{database_path}")
        with sqlite3.connect(f"{database_path.as_uri()}?mode=ro", uri=True, timeout=5) as connection:
            connection.execute("PRAGMA query_only = ON")
            tables = {
                str(row[0])
                for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
            }
            if not _REQUIRED_DATABASE_TABLES.issubset(tables):
                raise DataLocationError(f"旧数据文件缺少 BarByBar 必要数据表：{database_path}")
            has_user_data = any(
                connection.execute(f'SELECT 1 FROM "{table}" LIMIT 1').fetchone() is not None
                for table in _USER_DATA_TABLES
                if table in tables
            )
    except DataLocationError:
        raise
    except (OSError, sqlite3.Error) as exc:
        raise DataLocationError(f"无法安全检查旧数据库 {database_path}: {exc}") from exc
    return LegacyDatabaseCandidate(
        root=resolved_root,
        database_path=database_path,
        has_user_data=has_user_data,
    )


def discover_legacy_databases(
    *,
    frozen_root: str | Path,
    local_app_data: str | Path | None = None,
) -> tuple[LegacyDatabaseCandidate, ...]:
    local_root = Path(local_app_data).expanduser().resolve() if local_app_data else _local_app_data_root()
    candidate_roots = (
        Path(frozen_root).expanduser().resolve() / "data",
        local_root / "Programs" / "BarByBar" / "data",
    )
    discovered: list[LegacyDatabaseCandidate] = []
    seen: set[Path] = set()
    for root in candidate_roots:
        resolved = root.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        candidate = inspect_legacy_database(resolved)
        if candidate is not None:
            discovered.append(candidate)
    return tuple(discovered)


def resolve_data_location(
    *,
    frozen_root: str | Path | None = None,
    local_app_data: str | Path | None = None,
    project_root: str | Path | None = None,
) -> DataLocation:
    override = os.getenv(APP_DIR_ENV_VAR, "").strip()
    if override:
        return DataLocation(Path(override).expanduser().resolve(), DataLocationSource.ENVIRONMENT)

    actual_frozen_root = Path(frozen_root).expanduser().resolve() if frozen_root else _frozen_app_root()
    if actual_frozen_root is None:
        root = (Path(project_root).expanduser().resolve() if project_root else _project_root()) / "data"
        return DataLocation(root, DataLocationSource.PROJECT)

    locator_path = data_location_file_path(local_app_data)
    persisted = _read_persisted_data_location(locator_path)
    if persisted is not None:
        return DataLocation(persisted, DataLocationSource.LOCATOR, locator_path)

    candidates = discover_legacy_databases(
        frozen_root=actual_frozen_root,
        local_app_data=local_app_data,
    )
    populated = tuple(candidate for candidate in candidates if candidate.has_user_data)
    if len(populated) > 1:
        raise DataLocationConflictError(populated)
    if len(populated) == 1:
        selected = populated[0].root
        persist_data_location(selected, locator_path)
        return DataLocation(selected, DataLocationSource.LEGACY, locator_path)

    stable_root = stable_app_data_root(local_app_data) / "data"
    stable_root.mkdir(parents=True, exist_ok=True)
    persist_data_location(stable_root, locator_path)
    return DataLocation(stable_root, DataLocationSource.STABLE, locator_path)


def configure_data_location(location: DataLocation | None) -> None:
    global _configured_data_location
    _configured_data_location = location


def initialize_data_location() -> DataLocation:
    location = resolve_data_location()
    location.root.mkdir(parents=True, exist_ok=True)
    configure_data_location(location)
    return location


def current_data_location() -> DataLocation:
    return _configured_data_location or resolve_data_location()


def default_data_root() -> Path:
    root = current_data_location().root
    root.mkdir(parents=True, exist_ok=True)
    return root


def default_db_path() -> Path:
    return default_data_root() / "barbybar.db"


def default_log_dir() -> Path:
    root = default_data_root() / "logs"
    root.mkdir(parents=True, exist_ok=True)
    return root


def default_drawing_templates_path() -> Path:
    return default_data_root() / "drawing_templates.json"


def default_ui_settings_path() -> Path:
    return default_data_root() / "ui_settings.json"


def default_updates_dir() -> Path:
    root = default_data_root() / "updates"
    root.mkdir(parents=True, exist_ok=True)
    return root


def default_restore_dir() -> Path:
    root = default_data_root() / "restore"
    root.mkdir(parents=True, exist_ok=True)
    return root


def default_pending_restore_manifest_path() -> Path:
    return default_restore_dir() / "pending_restore.json"


def default_backup_dir() -> Path:
    root = default_data_root() / "backups"
    root.mkdir(parents=True, exist_ok=True)
    return root


def default_exports_dir() -> Path:
    root = default_data_root() / "exports"
    root.mkdir(parents=True, exist_ok=True)
    return root
