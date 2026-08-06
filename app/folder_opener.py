"""Operating-system integration for opening application folders."""

import os
import subprocess
import sys
from pathlib import Path


def open_folder(folder: Path) -> str:
    """Open *folder* in the host file manager and return its absolute path."""
    folder.mkdir(parents=True, exist_ok=True)
    folder_path = str(folder.resolve())

    if os.name == "nt":
        try:
            subprocess.Popen(["explorer.exe", folder_path])
        except (FileNotFoundError, OSError):
            os.startfile(folder_path)
    elif sys.platform == "darwin":
        subprocess.Popen(["open", folder_path])
    else:
        subprocess.Popen(["xdg-open", folder_path])

    return folder_path
