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

DEFAULT_CONFIG = '''"""
config.py - Runtime configuration for AI Recruitment System.
Generated automatically on first run.
"""

# Login / Security
LOGIN_ENABLED: bool = False
HR_USERNAME: str = ''
HR_PASSWORD: str = ''
HR_PASSWORD_HASH: str = ''
FLASK_SECRET_KEY: str = ''

# HR Profile
HR_DISPLAY_NAME: str = 'HR Admin'
HR_EMAIL: str = ''
HR_COMPANY: str = ''

# UI Theme
THEME: str = 'light'
COLOR_PALETTE: str = 'lavender'

# Ollama
OLLAMA_MODEL: str = 'llama3.2:3b'
OLLAMA_BASE_URL: str = 'http://localhost:11434'

# Legacy cloud aliases (kept for compatibility)
CLOUD_ENABLED: bool = False
CLOUD_MODEL: str = 'claude-3-5-haiku-latest'

# SMTP / Email
SMTP_HOST: str = 'smtp.gmail.com'
SMTP_PORT: int = 587
SMTP_EMAIL: str = ''
SMTP_PASSWORD: str = ''
EMAIL_TEMPLATE_SUBJECT: str = ''
EMAIL_TEMPLATE_BODY: str = ''

# Retry / Backoff
AI_RETRY_ATTEMPTS: int = 3
AI_RETRY_BACKOFF: int = 2

# AI Mode  ('privacy' = local Ollama, 'cloud' = external API)
APP_MODE: str = 'privacy'

# API Keys
ANTHROPIC_KEY: str = ''
GEMINI_KEY: str = ''
GROQ_KEY: str = ''
OPENAI_KEY: str = ''
NVIDIA_KEY: str = ''
OPENROUTER_KEY: str = ''
GITHUB_KEY: str = ''
OLLAMA_CLOUD_KEY: str = ''

# Models
PRIVACY_MODEL: str = 'llama3.2:3b'
ANTHROPIC_MODEL: str = 'claude-3-5-haiku-latest'
GEMINI_MODEL: str = 'gemini-1.5-flash'
GROQ_MODEL: str = 'llama3-8b-8192'
OPENAI_MODEL: str = 'gpt-4o-mini'
NVIDIA_MODEL: str = 'meta/llama-3.3-70b-instruct'
OPENROUTER_MODEL: str = 'meta-llama/llama-3.1-8b-instruct:free'
GITHUB_MODEL: str = 'gpt-4o-mini'
OLLAMA_CLOUD_MODEL: str = 'llama3.2:3b'

# Enabled Providers
ANTHROPIC_ENABLED: bool = False
GEMINI_ENABLED: bool = False
GROQ_ENABLED: bool = False
OPENAI_ENABLED: bool = False
NVIDIA_ENABLED: bool = False
OPENROUTER_ENABLED: bool = False
GITHUB_ENABLED: bool = False
OLLAMA_CLOUD_ENABLED: bool = False
'''

if getattr(sys, "frozen", False):
    app_data_root = Path(os.environ.get("LOCALAPPDATA", str(ROOT_DIR))) / APP_NAME
    app_data_root.mkdir(parents=True, exist_ok=True)
    CRASH_LOG = app_data_root / "crash.log"
    runtime_config = app_data_root / "config.py"
    if not runtime_config.exists():
        runtime_config.write_text(DEFAULT_CONFIG, encoding="utf-8")
    sys.path.insert(0, str(app_data_root))
else:
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
from src.common import APP_DATA_DIR
from app.core import add_log_line, log_queue

app = create_app()

# Bind dynamic route decorators
from app.routes.auth import register_auth_routes
from app.routes.dashboard import register_dashboard_routes
from app.routes.health import register_health_routes
from app.routes.interview import register_interview_routes
from app.routes.logs import register_logs_routes
from app.routes.nlp import register_nlp_routes
from app.routes.ranking import register_ranking_routes
from app.routes.reports import register_reports_routes
from app.routes.scheduling import register_scheduling_routes
from app.routes.settings import register_settings_routes
from app.routes.upload import register_upload_routes

register_auth_routes(app)
register_dashboard_routes(app)
register_health_routes(app)
register_upload_routes(app)
register_nlp_routes(app)
register_ranking_routes(app)
register_scheduling_routes(app)
register_interview_routes(app)
register_reports_routes(app)
register_settings_routes(app)
register_logs_routes(app)

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
    """Persist all config module attributes back to the runtime config so
    settings survive restarts. Rewrites the file from a known-good template
    rather than doing fragile regex substitution on arbitrary Python source."""
    import importlib

    def _q(v):
        """Quote a value for Python source: strings get quotes, others are bare."""
        if isinstance(v, bool):
            return str(v)
        if isinstance(v, str):
            escaped = v.replace("\\", "\\\\").replace("'", "\\'")
            return f"'{escaped}'"
        return str(v)

    # Ordered list of all config keys we want to persist.
    # Layout mirrors the generated config sections for readability.
    KEYS = [
        # Login
        ("LOGIN_ENABLED", bool), ("HR_USERNAME", str), ("HR_PASSWORD", str), ("HR_PASSWORD_HASH", str),
        ("FLASK_SECRET_KEY", str),
        # Profile
        ("HR_DISPLAY_NAME", str), ("HR_EMAIL", str), ("HR_COMPANY", str),
        # Theme
        ("THEME", str), ("COLOR_PALETTE", str),
        # Ollama
        ("OLLAMA_MODEL", str), ("OLLAMA_BASE_URL", str),
        # Legacy cloud aliases
        ("CLOUD_ENABLED", bool), ("CLOUD_MODEL", str),
        # SMTP
        ("SMTP_HOST", str), ("SMTP_PORT", int),
        ("SMTP_EMAIL", str), ("SMTP_PASSWORD", str),
        ("EMAIL_TEMPLATE_SUBJECT", str), ("EMAIL_TEMPLATE_BODY", str),
        # Retry
        ("AI_RETRY_ATTEMPTS", int), ("AI_RETRY_BACKOFF", int),
        # AI Mode
        ("APP_MODE", str),
        # API Keys
        ("ANTHROPIC_KEY", str), ("GEMINI_KEY", str), ("GROQ_KEY", str),
        ("OPENAI_KEY", str), ("NVIDIA_KEY", str), ("OPENROUTER_KEY", str),
        ("GITHUB_KEY", str), ("OLLAMA_CLOUD_KEY", str),
        # Models
        ("PRIVACY_MODEL", str),
        ("ANTHROPIC_MODEL", str), ("GEMINI_MODEL", str), ("GROQ_MODEL", str),
        ("OPENAI_MODEL", str), ("NVIDIA_MODEL", str), ("OPENROUTER_MODEL", str),
        ("GITHUB_MODEL", str), ("OLLAMA_CLOUD_MODEL", str),
        # Enabled providers
        ("ANTHROPIC_ENABLED", bool), ("GEMINI_ENABLED", bool),
        ("GROQ_ENABLED", bool), ("OPENAI_ENABLED", bool),
        ("NVIDIA_ENABLED", bool), ("OPENROUTER_ENABLED", bool),
        ("GITHUB_ENABLED", bool), ("OLLAMA_CLOUD_ENABLED", bool),
    ]

    SECTION_COMMENTS = {
        "LOGIN_ENABLED":     "\n# Login / Security\n",
        "HR_DISPLAY_NAME":   "\n# HR Profile\n",
        "THEME":             "\n# UI Theme\n",
        "OLLAMA_MODEL":      "\n# Ollama\n",
        "CLOUD_ENABLED":     "\n# Legacy cloud aliases (kept for compatibility)\n",
        "SMTP_HOST":         "\n# SMTP / Email\n",
        "AI_RETRY_ATTEMPTS": "\n# Retry / Backoff\n",
        "APP_MODE":          "\n# AI Mode  ('privacy' = local Ollama, 'cloud' = external API)\n",
        "ANTHROPIC_KEY":     "\n# API Keys\n",
        "PRIVACY_MODEL":     "\n# Models\n",
        "ANTHROPIC_ENABLED": "\n# Enabled Providers\n",
    }

    lines = ['"""\nconfig.py - Central Configuration for AI Recruitment System\n'
             'All settings are written here automatically when saved via the Settings UI.\n"""\n']

    for key, typ in KEYS:
        val = getattr(cfg, key, None)
        # Type-coerce in case the live attribute was set from form input (str)
        if typ is bool and isinstance(val, str):
            val = val.lower() in ("true", "1", "on", "yes")
        elif typ is int:
            try:
                val = int(val)
            except (TypeError, ValueError):
                val = getattr(cfg, key, 0)
        if val is None:
            val = "" if typ is str else (False if typ is bool else 0)

        if key in SECTION_COMMENTS:
            lines.append(SECTION_COMMENTS[key])
        tname = "bool" if typ is bool else ("int" if typ is int else "str")
        lines.append(f"{key}: {tname} = {_q(val)}\n")

    content = "".join(lines)

    data_config = APP_DATA_DIR / "config.py"
    data_config.parent.mkdir(parents=True, exist_ok=True)
    data_config.write_text(content, encoding="utf-8")

    if not getattr(sys, "frozen", False):
        # Write only to config/config.py — never to the root folder (security)
        config_dir_file = ROOT_DIR / "config" / "config.py"
        config_dir_file.parent.mkdir(parents=True, exist_ok=True)
        config_dir_file.write_text(content, encoding="utf-8")

    # Reload the config module so the running process picks up the new values
    if "config.config" in sys.modules:
        importlib.reload(sys.modules["config.config"])
    importlib.reload(cfg)

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
            x509.NameAttribute(NameOID.COUNTRY_NAME,         "IN"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME,    "ARS"),
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
    candidate_host = os.environ.get("ARS_CANDIDATE_HOST", "127.0.0.1")
    app.run(host=candidate_host, port=CANDIDATE_PORT, debug=_debug_mode(), use_reloader=False,
            ssl_context=(cert_path, key_path))

def run_flask_http_local():
    from waitress import serve as waitress_serve
    # The desktop UI is served only on loopback, but it is still a production
    # request server. Waitress avoids Flask's development server and debugger.
    waitress_serve(app, host="127.0.0.1", port=DESKTOP_PORT, threads=8, ident="ARS")

def main():
    from app.database import init_db
    init_db()

    global CANDIDATE_PORT, DESKTOP_PORT
    candidate_host = os.environ.get("ARS_CANDIDATE_HOST", "0.0.0.0")
    CANDIDATE_PORT = _pick_port(candidate_host, _env_port("ARS_CANDIDATE_PORT", 5000))
    DESKTOP_PORT = _pick_port("127.0.0.1", _env_port("ARS_DESKTOP_PORT", 5001))

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

    api = Api()
    
    import secrets
    if "DESKTOP_AUTH_TOKEN" not in os.environ:
        os.environ["DESKTOP_AUTH_TOKEN"] = secrets.token_urlsafe(32)
        
    webview.create_window(
        title     = "AI Recruitment System",
        url       = f"http://127.0.0.1:{DESKTOP_PORT}/desktop-login?token={os.environ['DESKTOP_AUTH_TOKEN']}",
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
