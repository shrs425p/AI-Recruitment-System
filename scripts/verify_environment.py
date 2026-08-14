"""
verify_environment.py — Pre-flight Production Environment Diagnostics
======================================================================
Validates Python runtime environment, mandatory dependencies, Tesseract OCR
binary availability, database connectivity, and Ollama service reachability.
"""

import os
import sys
from pathlib import Path

# Add project root to sys.path
ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
if str(ROOT_DIR / "src") not in sys.path:
    sys.path.insert(0, str(ROOT_DIR / "src"))


def check_python_version():
    print("[1/5] Checking Python Version...", end=" ")
    if sys.version_info < (3, 10):  # noqa: UP036
        print(f"FAILED (Python {sys.version} < 3.10 required)")
        return False
    print(f"OK (Python {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro})")
    return True


def check_dependencies():
    print("[2/5] Checking Core Dependencies...", end=" ")
    required_modules = [
        "flask",
        "webview",
        "pymupdf",
        "pytesseract",
        "PIL",
        "numpy",
        "ollama",
        "icalendar",
        "fpdf",
    ]
    missing = []
    for mod in required_modules:
        try:
            __import__(mod)
        except ImportError:
            missing.append(mod)

    if missing:
        print(f"FAILED (Missing: {', '.join(missing)})")
        return False
    print("OK (All core dependencies installed)")
    return True


def check_database():
    print("[3/5] Checking Database & Indexes...", end=" ")
    try:
        from app.database import get_connection, init_db
        init_db()
        conn = get_connection()
        cur = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = {r[0] for r in cur.fetchall()}
        conn.close()
        expected = {"pipeline_runs", "candidates", "schedules", "email_log", "interview_tokens"}
        if not expected.issubset(tables):
            print(f"FAILED (Missing tables: {expected - tables})")
            return False
        print("OK (SQLite database initialized & verified)")
        return True
    except Exception as e:
        print(f"FAILED ({e})")
        return False


def check_tesseract():
    print("[4/5] Checking Tesseract OCR Executable...", end=" ")
    from src.common import install_path
    bundled_cmd = install_path("models/Tesseract-OCR") / "tesseract.exe"
    if bundled_cmd.exists():
        print(f"OK (Bundled binary found at {bundled_cmd})")
        return True
    import pytesseract
    cmd = pytesseract.pytesseract.tesseract_cmd
    if os.path.exists(cmd):
        print(f"OK (System binary found at {cmd})")
        return True
    else:
        print(f"WARNING (Bundled Tesseract binary not at {bundled_cmd} — fallback to system PATH)")
        return True


def check_ollama():
    print("[5/5] Checking Ollama Service Connectivity...", end=" ")
    try:
        import urllib.request
        req = urllib.request.Request("http://localhost:11434/api/tags")
        with urllib.request.urlopen(req, timeout=3) as resp:
            if resp.status == 200:
                print("OK (Ollama server reachable at http://localhost:11434)")
                return True
    except Exception as e:
        print(f"WARNING (Ollama service not responding on http://localhost:11434: {e})")
        print("      Note: Privacy AI mode requires Ollama. Run 'ollama serve' if needed.")
        return True
    return True


def main():
    print("=" * 60)
    print("  AI RECRUITMENT SYSTEM — PRODUCTION PRE-FLIGHT VERIFIER")
    print("=" * 60)

    results = [
        check_python_version(),
        check_dependencies(),
        check_database(),
        check_tesseract(),
        check_ollama(),
    ]

    print("-" * 60)
    if all(results):
        print("STATUS: SUCCESS — Environment is production-ready!")
        return 0
    else:
        print("STATUS: FAILED — Resolve reported errors before launch.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
