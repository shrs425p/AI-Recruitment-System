import logging
import os
import socket
import sys
import threading
import time
import traceback
from pathlib import Path

import webview

# Add directories to search paths so imports load seamlessly
ROOT_DIR = Path(__file__).parent.resolve()
APP_NAME = "AI Recruitment System"
CRASH_LOG = None
DESKTOP_PORT = None
CANDIDATE_PORT = None

# All configuration is database-backed. No DEFAULT_CONFIG string or .py file is written.
if getattr(sys, "frozen", False):
    app_data_root = Path(os.environ.get("LOCALAPPDATA", str(ROOT_DIR))) / APP_NAME
    app_data_root.mkdir(parents=True, exist_ok=True)
    CRASH_LOG = app_data_root / "crash.log"
sys.path.insert(0, str(ROOT_DIR / "config"))
sys.path.insert(0, str(ROOT_DIR / "src"))
sys.path.insert(0, str(ROOT_DIR / "app"))
sys.path.insert(0, str(ROOT_DIR))


def _write_crash_log(exc_type, exc_value, exc_tb):
    if CRASH_LOG is None:
        return
    try:
        CRASH_LOG.write_text(
            "".join(traceback.format_exception(exc_type, exc_value, exc_tb)),
            encoding="utf-8",
        )
    except Exception as e:
        logger.warning('Caught exception: %s', e, exc_info=True)


def _handle_unhandled_exception(exc_type, exc_value, exc_tb):
    _write_crash_log(exc_type, exc_value, exc_tb)
    sys.__excepthook__(exc_type, exc_value, exc_tb)


sys.excepthook = _handle_unhandled_exception

# Create the flask app
from app import create_app
from app.core import add_log_line, log_queue
from src.common import APP_DATA_DIR

app = create_app()


# Logging Setup
class QueueHandler(logging.Handler):
    def __init__(self, log_queue):
        super().__init__()
        self.log_queue = log_queue
    def emit(self, record):
        try:
            formatted = self.format(record)
            add_log_line(formatted)
        except Exception as e:
            logger.warning('Caught exception: %s', e, exc_info=True)

logger = logging.getLogger()
logger.setLevel(logging.INFO)
formatter = logging.Formatter("[%(asctime)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S")

qh = QueueHandler(log_queue)
qh.setFormatter(formatter)
logger.addHandler(qh)

sh = logging.StreamHandler(sys.stdout)
sh.setFormatter(formatter)
logger.addHandler(sh)

# Suppress flask engine logs
logging.getLogger("werkzeug").setLevel(logging.WARNING)

def _save_config(cfg):
    """Persist all config attributes directly to the SQLite database.
    No plain text config.py file or .env file is written to disk."""
    from app.database import save_settings_dict

    KEYS = [
        "LOGIN_ENABLED", "HR_USERNAME", "HR_PASSWORD", "HR_PASSWORD_HASH",
        "FLASK_SECRET_KEY", "HR_DISPLAY_NAME", "HR_EMAIL", "HR_COMPANY",
        "THEME", "COLOR_PALETTE", "OLLAMA_MODEL", "OLLAMA_BASE_URL",
        "CLOUD_ENABLED", "CLOUD_MODEL", "SMTP_HOST", "SMTP_PORT",
        "SMTP_EMAIL", "SMTP_PASSWORD", "EMAIL_TEMPLATE_SUBJECT", "EMAIL_TEMPLATE_BODY",
        "AI_RETRY_ATTEMPTS", "AI_RETRY_BACKOFF", "APP_MODE",
        "ANTHROPIC_KEY", "GEMINI_KEY", "GROQ_KEY", "OPENAI_KEY",
        "NVIDIA_KEY", "OPENROUTER_KEY", "GITHUB_KEY", "OLLAMA_CLOUD_KEY",
        "PRIVACY_MODEL", "ANTHROPIC_MODEL", "GEMINI_MODEL", "GROQ_MODEL",
        "OPENAI_MODEL", "NVIDIA_MODEL", "OPENROUTER_MODEL", "GITHUB_MODEL", "OLLAMA_CLOUD_MODEL",
        "ANTHROPIC_ENABLED", "GEMINI_ENABLED", "GROQ_ENABLED", "OPENAI_ENABLED",
        "NVIDIA_ENABLED", "OPENROUTER_ENABLED", "GITHUB_ENABLED", "OLLAMA_CLOUD_ENABLED"
    ]

    settings_to_save = {}
    for key in KEYS:
        val = getattr(cfg, key, None)
        if val is not None:
            settings_to_save[key] = val

    save_settings_dict(settings_to_save)

    # Remove obsolete config.py files from disk if present
    for old_file in [APP_DATA_DIR / "config.py", ROOT_DIR / "config" / "config.py"]:
        try:
            if old_file.exists():
                old_file.unlink()
        except Exception:
            pass


def _ensure_ssl_cert():
    ssl_dir = APP_DATA_DIR / "data/output/ssl"
    ssl_dir.mkdir(parents=True, exist_ok=True)
    cert = ssl_dir / "cert.pem"
    key  = ssl_dir / "key.pem"
    if not cert.exists() or not key.exists():
        import datetime

        from cryptography import x509
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import rsa
        from cryptography.x509.oid import NameOID

        private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

        subject = issuer = x509.Name([
            x509.NameAttribute(NameOID.ORGANIZATION_NAME,    APP_NAME),
            x509.NameAttribute(NameOID.COMMON_NAME,          "localhost"),
        ])
        cert_obj = (
            x509.CertificateBuilder()
            .subject_name(subject)
            .issuer_name(issuer)
            .public_key(private_key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(datetime.datetime.now(datetime.timezone.utc))
            .not_valid_after(
                datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=3650)
            )
            .sign(private_key, hashes.SHA256())
        )
        cert.write_bytes(cert_obj.public_bytes(serialization.Encoding.PEM))
        key.write_bytes(private_key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.TraditionalOpenSSL,
            serialization.NoEncryption(),
        ))
    return str(cert), str(key)


def _env_port(name: str, default: int) -> int:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        port = int(raw)
    except ValueError:
        return default
    return port if 1 <= port <= 65535 else default


def _pick_port(host: str, preferred_port: int) -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind((host, preferred_port))
        except OSError:
            sock.bind((host, 0))
        return int(sock.getsockname()[1])


def _debug_mode() -> bool:
    """Keep Flask's debugger off unless a developer explicitly enables it."""
    return not getattr(sys, "frozen", False) and os.environ.get("ARS_DEBUG", "").lower() in {
        "1", "true", "yes",
    }


def run_flask_https():
    cert_path, key_path = _ensure_ssl_cert()
    candidate_host = os.environ.get("ARS_CANDIDATE_HOST", "0.0.0.0")
    app.run(host=candidate_host, port=CANDIDATE_PORT, debug=_debug_mode(), use_reloader=False,
            ssl_context=(cert_path, key_path))

def run_flask_http_local():
    from waitress import serve as waitress_serve
    # The desktop UI is served only on loopback, but it is still a production
    # request server. Waitress avoids Flask's development server and debugger.
    _threads = _env_port("ARS_SERVER_THREADS", 8)  # env override for concurrency tuning
    waitress_serve(app, host="127.0.0.1", port=DESKTOP_PORT, threads=_threads, ident=APP_NAME)

def main():
    from app.database import init_db
    init_db()

    global CANDIDATE_PORT, DESKTOP_PORT
    candidate_host = os.environ.get("ARS_CANDIDATE_HOST", "0.0.0.0")
    CANDIDATE_PORT = _pick_port(candidate_host, _env_port("ARS_CANDIDATE_PORT", 5000))
    DESKTOP_PORT = _pick_port("127.0.0.1", _env_port("ARS_DESKTOP_PORT", 5001))

    app.config["CANDIDATE_PORT"] = CANDIDATE_PORT
    app.config["DESKTOP_PORT"] = DESKTOP_PORT

    t_https = threading.Thread(target=run_flask_https, daemon=True)
    t_https.start()

    t_http = threading.Thread(target=run_flask_http_local, daemon=True)
    t_http.start()

    time.sleep(1)

    class Api:
        def minimize(self):
            webview.windows[0].minimize()
        def maximize(self):
            webview.windows[0].toggle_fullscreen()
        def close(self):
            webview.windows[0].close() if hasattr(webview.windows[0], 'close') else webview.windows[0].destroy()
        def get_auth_nonce(self):
            import secrets
            nonce = secrets.token_urlsafe(32)
            lock = app.config.get("_NONCE_LOCK")
            pool = app.config.get("_NONCE_POOL")
            if lock and pool is not None:
                with lock:
                    pool.add(nonce)
            return nonce

    api = Api()

    webview.create_window(
        title     = "AI Recruitment System",
        url       = f"http://127.0.0.1:{DESKTOP_PORT}/desktop-bootstrap",
        width     = 1280,
        height    = 800,
        min_size  = (1024, 700),
        resizable = True,
        frameless = True,
        easy_drag = True,
        js_api=api
    )
    webview.start()


if __name__ == "__main__":
    try:
        main()
    except Exception:
        _write_crash_log(*sys.exc_info())
        raise
