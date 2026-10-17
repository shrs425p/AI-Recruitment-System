import datetime
import logging
import os
import socket
import ssl
import sys
import threading
import time
import traceback
from pathlib import Path

import webview
from waitress import serve as waitress_serve
from waitress.server import TcpWSGIServer

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

# Create the flask apps
from app import create_app, create_candidate_app
from app.core import add_log_line, log_queue
from src.common import APP_DATA_DIR

app = create_app()
candidate_app = create_candidate_app()


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

def _load_config():
    """On startup, read all previously saved settings from the SQLite database
    and apply them back to the live config object so they survive a restart."""
    try:
        import config as cfg
        from app.database import get_all_settings
        saved = get_all_settings()
        if not saved:
            # Fresh install or wiped DB — write current defaults so they persist
            _save_config(cfg)
            return
        for key, val in saved.items():
            if not hasattr(cfg, key):
                continue
            current = getattr(cfg, key)
            # Cast back to the original type
            try:
                if isinstance(current, bool):
                    setattr(cfg, key, str(val).lower() in ("1", "true", "yes"))
                elif isinstance(current, int):
                    setattr(cfg, key, int(val))
                elif isinstance(current, float):
                    setattr(cfg, key, float(val))
                else:
                    setattr(cfg, key, val)
            except (ValueError, TypeError):
                setattr(cfg, key, val)
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"[Config] Could not load settings from DB: {e}")


def _save_config(cfg):
    """Persist all config attributes directly to the SQLite database.
    No plain text config.py file or .env file is written to disk."""
    from app.database import save_settings_dict

    KEYS = [
        "LOGIN_ENABLED", "HR_USERNAME", "HR_PASSWORD", "HR_PASSWORD_HASH",
        "FLASK_SECRET_KEY", "HR_DISPLAY_NAME", "HR_EMAIL", "HR_COMPANY",
        "THEME", "COLOR_PALETTE", "OLLAMA_MODEL", "OLLAMA_BASE_URL",
        "OLLAMA_FALLBACK_MODEL", "OLLAMA_NUM_CTX", "OLLAMA_NUM_PREDICT", "OLLAMA_TEMPERATURE",
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


def _get_lan_ip_address() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        probe_target = os.environ.get("ROUTING_PROBE_HOST", "dns.google")
        s.connect((probe_target, 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def _is_cert_valid_and_current(cert_path: Path) -> bool:
    if not cert_path.exists():
        return False
    try:
        from cryptography import x509
        cert_data = cert_path.read_bytes()
        cert_obj = x509.load_pem_x509_certificate(cert_data)
        now = datetime.datetime.now(datetime.timezone.utc)
        expiry = getattr(cert_obj, "not_valid_after_utc", None)
        if expiry is None:
            expiry = cert_obj.not_valid_after.replace(tzinfo=datetime.timezone.utc)
        # Check if cert has expired or expires within 7 days
        return (expiry - now).total_seconds() > 7 * 86400
    except Exception:
        return False


def _generate_ssl_cert(cert: Path, key: Path):
    import ipaddress

    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509.oid import NameOID

    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, APP_NAME),
        x509.NameAttribute(NameOID.COMMON_NAME, "localhost"),
    ])

    san_entries = [
        x509.DNSName("localhost"),
        x509.IPAddress(ipaddress.IPv4Address("127.0.0.1")),
    ]
    lan_ip = _get_lan_ip_address()
    if lan_ip not in {"127.0.0.1", "localhost"}:
        try:
            san_entries.append(x509.IPAddress(ipaddress.ip_address(lan_ip)))
        except ValueError:
            pass

    now = datetime.datetime.now(datetime.timezone.utc)
    cert_obj = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(private_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now)
        .not_valid_after(now + datetime.timedelta(days=365))  # 1 year validity
        .add_extension(
            x509.SubjectAlternativeName(san_entries),
            critical=False,
        )
        .sign(private_key, hashes.SHA256())
    )
    cert.write_bytes(cert_obj.public_bytes(serialization.Encoding.PEM))
    key.write_bytes(private_key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.TraditionalOpenSSL,
        serialization.NoEncryption(),
    ))


def _ensure_ssl_cert():
    ssl_dir = APP_DATA_DIR / "data/output/ssl"
    ssl_dir.mkdir(parents=True, exist_ok=True)
    cert = ssl_dir / "cert.pem"
    key  = ssl_dir / "key.pem"
    if not _is_cert_valid_and_current(cert) or not key.exists():
        _generate_ssl_cert(cert, key)
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
    # ARS_CANDIDATE_HOST defaults to 0.0.0.0 so candidates can connect over the LAN.
    # This is intentional: candidate_app isolates candidate-only routes.
    candidate_host = os.environ.get("ARS_CANDIDATE_HOST", "0.0.0.0")

    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(certfile=cert_path, keyfile=key_path)

    bind_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    bind_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    bind_sock.bind((candidate_host, CANDIDATE_PORT))
    bind_sock.listen(128)

    ssl_sock = ctx.wrap_socket(bind_sock, server_side=True)
    class _SslHandshakeFilter(logging.Filter):
        def filter(self, record):
            if record.exc_info and isinstance(record.exc_info[1], ssl.SSLError):
                return False
            return True

    logging.getLogger("waitress").addFilter(_SslHandshakeFilter())

    _threads = _env_port("ARS_SERVER_THREADS", 8)
    server = TcpWSGIServer(
        candidate_app,
        _sock=ssl_sock,
        bind_socket=False,
        url_scheme="https",
        threads=_threads,
        ident=f"{APP_NAME}_Candidate",
    )
    server.run()


def run_flask_http_local():
    # The desktop UI is served only on loopback, but it is still a production
    # request server. Waitress avoids Flask's development server and debugger.
    _threads = _env_port("ARS_SERVER_THREADS", 8)  # env override for concurrency tuning
    waitress_serve(app, host="127.0.0.1", port=DESKTOP_PORT, threads=_threads, ident=APP_NAME)


def main():
    from app.database import init_db
    init_db()
    _load_config()  # Restore saved settings from DB

    global CANDIDATE_PORT, DESKTOP_PORT
    candidate_host = os.environ.get("ARS_CANDIDATE_HOST", "0.0.0.0")
    CANDIDATE_PORT = _pick_port(candidate_host, _env_port("ARS_CANDIDATE_PORT", 5000))
    DESKTOP_PORT = _pick_port("127.0.0.1", _env_port("ARS_DESKTOP_PORT", 5001))

    app.config["CANDIDATE_PORT"] = CANDIDATE_PORT
    app.config["DESKTOP_PORT"] = DESKTOP_PORT
    candidate_app.config["CANDIDATE_PORT"] = CANDIDATE_PORT
    candidate_app.config["DESKTOP_PORT"] = DESKTOP_PORT

    t_https = threading.Thread(target=run_flask_https, daemon=True)
    t_https.start()

    t_http = threading.Thread(target=run_flask_http_local, daemon=True)
    t_http.start()

    time.sleep(1)

    class Api:
        def __init__(self):
            self._is_maximized = False

        def minimize(self):
            webview.windows[0].minimize()

        def maximize(self):
            w = webview.windows[0]
            if self._is_maximized:
                w.restore()
                self._is_maximized = False
            else:
                w.maximize()
                self._is_maximized = True

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
