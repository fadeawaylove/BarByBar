from __future__ import annotations

import os
import sys
from pathlib import Path


APP_DIR_ENV_VAR = "BARBYBAR_DATA_DIR"


def _frozen_app_root() -> Path | None:
    if not getattr(sys, "frozen", False):
        return None
    executable = Path(sys.executable).resolve()
    return executable.parent


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def default_data_root() -> Path:
    override = os.getenv(APP_DIR_ENV_VAR, "").strip()
    if override:
        root = Path(override).expanduser().resolve()
    else:
        root = (_frozen_app_root() or _project_root()) / "data"
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
