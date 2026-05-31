import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for folder in (ROOT, ROOT / "app", ROOT / "src", ROOT / "config"):
    path = str(folder)
    if path not in sys.path:
        sys.path.insert(0, path)
