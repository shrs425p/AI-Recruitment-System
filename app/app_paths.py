import os
import sys
from pathlib import Path

APP_NAME = "AI Recruitment System"


if getattr(sys, "frozen", False):
    APP_RESOURCE_DIR = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    APP_INSTALL_DIR = Path(sys.executable).parent
    local_app_data = Path(os.environ.get("LOCALAPPDATA", str(APP_INSTALL_DIR)))
    APP_DATA_DIR = local_app_data / APP_NAME
else:
    APP_RESOURCE_DIR = Path(__file__).parent.parent
    APP_INSTALL_DIR = Path(__file__).parent.parent
    APP_DATA_DIR = Path(__file__).parent.parent


APP_DATA_DIR.mkdir(parents=True, exist_ok=True)


def resource_path(relative: str) -> Path:
    return APP_RESOURCE_DIR / relative


def install_path(relative: str) -> Path:
    return APP_INSTALL_DIR / relative


def data_path(relative: str) -> Path:
    path = APP_DATA_DIR / "data" / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    return path
