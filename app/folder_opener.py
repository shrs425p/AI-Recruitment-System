"""Operating-system integration for opening application folders."""

import logging
import os
import subprocess
import sys
from pathlib import Path

logger = logging.getLogger(__name__)


def open_folder(folder: Path) -> str:
    """Open *folder* in the host file manager and return its absolute path."""
    folder.mkdir(parents=True, exist_ok=True)
    folder_path = str(folder.resolve())

    try:
        if os.name == "nt":
            try:
                subprocess.Popen(["explorer.exe", folder_path])
            except (FileNotFoundError, OSError):
                os.startfile(folder_path)
        elif sys.platform == "darwin":
            subprocess.Popen(["open", folder_path])
        else:
            subprocess.Popen(["xdg-open", folder_path])
    except (FileNotFoundError, OSError) as e:
        logger.warning("Could not launch file manager for %s: %s", folder_path, e)

    return folder_path
