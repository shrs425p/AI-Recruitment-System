import os
import sys
from pathlib import Path

APP_NAME = "AI Recruitment System"


def _get_app_data_dir() -> Path:
    if getattr(sys, "frozen", False):
        install_dir = Path(sys.executable).parent
        local_app_data = Path(os.environ.get("LOCALAPPDATA", str(install_dir)))
    else:
        install_dir = Path(__file__).parent.parent
        local_app_data = Path(os.environ.get("LOCALAPPDATA", str(install_dir)))

    primary = local_app_data / APP_NAME
    try:
        primary.mkdir(parents=True, exist_ok=True)
        return primary
    except Exception:
        fallback = Path.home() / ".ai_recruitment_system"
        fallback.mkdir(parents=True, exist_ok=True)
        return fallback


if getattr(sys, "frozen", False):
    APP_RESOURCE_DIR = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    APP_INSTALL_DIR = Path(sys.executable).parent
else:
    APP_RESOURCE_DIR = Path(__file__).parent.parent
    APP_INSTALL_DIR = Path(__file__).parent.parent

APP_DATA_DIR = _get_app_data_dir()


def resource_path(relative: str) -> Path:
    return APP_RESOURCE_DIR / relative


def install_path(relative: str) -> Path:
    return APP_INSTALL_DIR / relative


def data_path(relative: str) -> Path:
    path = APP_DATA_DIR / "data" / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    return path
