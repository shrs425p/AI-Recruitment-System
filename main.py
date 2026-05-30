import os
import sys
import time
import logging
import threading
from pathlib import Path
import webview

# Add directories to search paths so imports load seamlessly
ROOT_DIR = Path(__file__).parent.resolve()
sys.path.insert(0, str(ROOT_DIR / "config"))
sys.path.insert(0, str(ROOT_DIR / "src"))
sys.path.insert(0, str(ROOT_DIR / "app"))
sys.path.insert(0, str(ROOT_DIR))

# Create the flask app
from app import create_app
from app.core import APP_DATA_DIR, log_queue

app = create_app()

# Bind dynamic route decorators
from app.routes.auth import register_auth_routes
from app.routes.dashboard import register_dashboard_routes
from app.routes.upload import register_upload_routes
from app.routes.nlp import register_nlp_routes
from app.routes.ranking import register_ranking_routes
from app.routes.scheduling import register_scheduling_routes
from app.routes.interview import register_interview_routes
from app.routes.reports import register_reports_routes
from app.routes.settings import register_settings_routes
from app.routes.logs import register_logs_routes

register_auth_routes(app)
register_dashboard_routes(app)
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
            self.log_queue.put_nowait(self.format(record))
        except Exception:
            pass

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
    """Persist all config module attributes back to config/config.py so
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
    # Layout mirrors config/config.py sections for readability.
    KEYS = [
        # Login
        ("LOGIN_ENABLED", bool), ("HR_USERNAME", str), ("HR_PASSWORD", str),
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

    lines = ['"""\nconfig.py — Central Configuration for AI Recruitment System\n'
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
        lines.append(f"{key} = {_q(val)}\n")

    content = "".join(lines)

    # Write to both locations so the live import and the on-disk file stay in sync
    config_file = ROOT_DIR / "config" / "config.py"
    data_config  = APP_DATA_DIR / "config.py"

    config_file.write_text(content, encoding="utf-8")
    data_config.parent.mkdir(parents=True, exist_ok=True)
    data_config.write_text(content, encoding="utf-8")

    # Reload the config module so the running process picks up the new values
    importlib.reload(cfg)

def _ensure_ssl_cert():
    ssl_dir = APP_DATA_DIR / "output/ssl"
    ssl_dir.mkdir(parents=True, exist_ok=True)
    cert = ssl_dir / "cert.pem"
    key  = ssl_dir / "key.pem"
    if not cert.exists() or not key.exists():
        import datetime
        from cryptography import x509
        from cryptography.x509.oid import NameOID
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import rsa

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

def run_flask_https():
    cert_path, key_path = _ensure_ssl_cert()
    app.run(host="0.0.0.0", port=5000, debug=False, use_reloader=False,
            ssl_context=(cert_path, key_path))

def run_flask_http_local():
    app.run(host="127.0.0.1", port=5001, debug=False, use_reloader=False)

if __name__ == "__main__":
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
    webview.create_window(
        title     = "Recruit Pipeline Manager",
        url       = "http://127.0.0.1:5001",
        width     = 1280,
        height    = 800,
        min_size  = (1024, 700),
        resizable = True,
        frameless = True,
        easy_drag = False,
        js_api=api
    )
    webview.start()
