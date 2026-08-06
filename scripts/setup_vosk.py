"""
setup_vosk.py — Download the Vosk Indian-English speech model (Apache 2.0, offline)

Run once:   python scripts/setup_vosk.py
Optional:   python scripts/setup_vosk.py --large    (downloads 1 GB high-accuracy model)

Models downloaded from https://alphacephei.com/vosk/models (Apache 2.0 licence).
"""

import sys
import urllib.request
import zipfile
from pathlib import Path

# Always download into models/ at project root, regardless of where this script lives
BASE_DIR = Path(__file__).parent.parent / "models"
BASE_DIR.mkdir(exist_ok=True)

MODELS = {
    "small": {
        "name":  "vosk-model-small-en-in-0.4",
        "url":   "https://alphacephei.com/vosk/models/vosk-model-small-en-in-0.4.zip",
        "size":  "36 MB",
        "notes": "Lightweight Indian-English model — recommended for desktop",
        "license": "Apache 2.0",
    },
    "large": {
        "name":  "vosk-model-en-in-0.5",
        "url":   "https://alphacephei.com/vosk/models/vosk-model-en-in-0.5.zip",
        "size":  "1.0 GB",
        "notes": "High-accuracy Indian-English model — best for interview transcription",
        "license": "Apache 2.0",
    },
}


def _progress(count, block_size, total):
    pct = min(count * block_size * 100 // total, 100)
    bar = "█" * (pct // 2) + "░" * (50 - pct // 2)
    mb_done = count * block_size / 1_048_576
    mb_total = total / 1_048_576
    print(f"\r  [{bar}] {pct:3d}%  {mb_done:.1f}/{mb_total:.1f} MB", end="", flush=True)


def download_model(which: str = "small"):
    m = MODELS[which]
    dest_dir = BASE_DIR / m["name"]
    zip_path = BASE_DIR / (m["name"] + ".zip")

    if dest_dir.exists():
        print(f"✓ Model already present: {dest_dir.name}")
        return True

    print(f"\nVosk Indian-English model ({which})")
    print(f"  {m['notes']}")
    print(f"  Size   : {m['size']}")
    print(f"  Licence: {m['license']}")
    print(f"  URL    : {m['url']}\n")
    print(f"Downloading to: {zip_path}")

    try:
        urllib.request.urlretrieve(m["url"], zip_path, reporthook=_progress)
        print()  # newline after progress bar
    except Exception as e:
        print(f"\n  ERROR downloading: {e}")
        if zip_path.exists():
            zip_path.unlink()
        return False

    print(f"Extracting to: {BASE_DIR}")
    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(BASE_DIR)
        zip_path.unlink()  # remove zip after extraction
    except Exception as e:
        print(f"  ERROR extracting: {e}")
        return False

    if dest_dir.exists():
        print(f"\n✓ Model ready: {dest_dir.name}")
        print("  Restart the app — speech recognition is now fully offline.")
        return True
    else:
        print(f"  ERROR: Expected folder not found after extraction: {dest_dir}")
        return False


if __name__ == "__main__":
    which = "large" if "--large" in sys.argv else "small"
    ok = download_model(which)
    sys.exit(0 if ok else 1)
