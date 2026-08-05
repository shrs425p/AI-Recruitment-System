import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
config_dir = str(ROOT / "config")
if config_dir in sys.path:
    sys.path.remove(config_dir)
sys.path.insert(0, config_dir)

for folder in (ROOT, ROOT / "app", ROOT / "src"):
    path = str(folder)
    if path not in sys.path:
        sys.path.append(path)
