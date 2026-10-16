import hmac
import os
import secrets
import threading
from datetime import timedelta

from flask import Flask, jsonify, render_template, request, session

import config
from app.utils import protect_hr_routes
from src.common import APP_RESOURCE_DIR


def _max_upload_size() -> int:
    default = 25 * 1024 * 1024
    try:
        configured = int(os.environ.get("ARS_MAX_UPLOAD_BYTES", default))
    except ValueError:
        return default
    return max(1 * 1024 * 1024, min(configured, 100 * 1024 * 1024))


def register_error_handlers(app: Flask):
    """Register centralized HTTP error handlers."""

    def _error_response(code: int, message: str):
        if request.path.startswith("/api/"):
            return jsonify({"error": message, "code": code}), code
        try:
            return render_template("error.html", code=code, message=message), code
        except Exception:
            return f"<h1>Error {code}</h1><p>{message}</p>", code

    @app.errorhandler(400)
    def bad_request_error(e):
        return _error_response(400, str(getattr(e, "description", "Bad Request")))

    @app.errorhandler(403)
    def forbidden_error(e):
        return _error_response(403, str(getattr(e, "description", "Access Denied")))

    @app.errorhandler(404)
    def not_found_error(e):
        return _error_response(404, "The requested resource was not found.")

    @app.errorhandler(429)
    def too_many_requests_error(e):
        return _error_response(429, "Rate limit exceeded. Please wait before retrying.")

    @app.errorhandler(413)
    def request_too_large_error(e):
        return _error_response(413, "Upload exceeds the maximum allowed size.")

    @app.errorhandler(500)
    def internal_server_error(e):
        return _error_response(500, "An internal server error occurred.")


def register_csrf_protection(app: Flask):
    """Enforce CSRF protection on state-changing endpoints for authenticated HR sessions."""

    @app.before_request
    def ensure_csrf_token():
        if "_csrf_token" not in session:
            session["_csrf_token"] = secrets.token_hex(32)

    @app.context_processor
    def inject_csrf_token():
        def get_csrf_token():
            if "_csrf_token" not in session:
                session["_csrf_token"] = secrets.token_hex(32)
            return session["_csrf_token"]
        return {"csrf_token": get_csrf_token}

    @app.before_request
    def validate_csrf():
        # Only validate state-changing methods
        if request.method in ("GET", "HEAD", "OPTIONS"):
            return None
        # Only protect /api/ endpoints
        if not request.path.startswith("/api/"):
            return None
        # Allowlist candidate-facing endpoints and desktop login bootstrap
        is_candidate_api = request.path.startswith("/api/candidate/") and request.method != "DELETE" and not request.path.split("/")[-1].isdigit()
        if is_candidate_api or request.path in ("/api/desktop-login", "/api/health"):
            return None
        # If an HR session is active, require a valid X-CSRF-Token
        if session.get("logged_in"):
            expected = session.get("_csrf_token")
            provided = request.headers.get("X-CSRF-Token")
            if not expected or not provided or not hmac.compare_digest(provided, expected):
                return jsonify({"error": "CSRF token missing or invalid", "code": 403}), 403
        return None


def _apply_security_headers(response):
    response.headers.setdefault("Cache-Control", "no-store")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
    csp = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline'; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "font-src 'self' https://fonts.gstatic.com data:; "
        "img-src 'self' data: blob:; "
        "media-src 'self' blob:; "
        "connect-src 'self'; "
        "frame-ancestors 'self';"
    )
    response.headers.setdefault("Content-Security-Policy", csp)
    return response


def create_app():
    templates_dir = str(APP_RESOURCE_DIR / "app" / "templates")
    static_dir = str(APP_RESOURCE_DIR / "app" / "static")

    app = Flask("ARS", template_folder=templates_dir, static_folder=static_dir)
    app.secret_key = (
        os.environ.get("FLASK_SECRET_KEY")
        or getattr(config, "FLASK_SECRET_KEY", "")
        or secrets.token_hex(32)
    )
    app.config.update(
        MAX_CONTENT_LENGTH=_max_upload_size(),
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SECURE=False,  # Plain HTTP on loopback (127.0.0.1:5001) for HR desktop UI
        SESSION_COOKIE_SAMESITE="Lax",
        PERMANENT_SESSION_LIFETIME=timedelta(hours=8),
        WTF_CSRF_ENABLED=True,
        _NONCE_POOL=set(),
        _NONCE_LOCK=threading.Lock(),
    )
    register_error_handlers(app)
    protect_hr_routes(app)
    register_csrf_protection(app)

    @app.after_request
    def add_security_headers(response):
        return _apply_security_headers(response)

    @app.context_processor
    def inject_config():
        return {"cfg": config, "config": config}

    # Register application routes
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

    return app


def create_candidate_app():
    """Create a lightweight Flask app containing ONLY candidate-facing routes.

    This app is exposed to the local network (LAN) over HTTPS so candidates can
    take interviews. It has NO HR routes (uploads, ranking, reports, settings, etc.),
    ensuring that even if an attacker on the LAN attempts to call HR endpoints,
    Flask returns 404 Not Found.
    """
    templates_dir = str(APP_RESOURCE_DIR / "app" / "templates")
    static_dir = str(APP_RESOURCE_DIR / "app" / "static")

    app = Flask("ARS_Candidate", template_folder=templates_dir, static_folder=static_dir)
    app.secret_key = (
        os.environ.get("FLASK_SECRET_KEY")
        or getattr(config, "FLASK_SECRET_KEY", "")
        or secrets.token_hex(32)
    )
    app.config.update(
        MAX_CONTENT_LENGTH=_max_upload_size(),
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SECURE=True,  # Candidate portal is served strictly over HTTPS
        SESSION_COOKIE_SAMESITE="Lax",
        PERMANENT_SESSION_LIFETIME=timedelta(hours=4),
        WTF_CSRF_ENABLED=True,
    )
    register_error_handlers(app)
    register_csrf_protection(app)

    @app.after_request
    def add_security_headers(response):
        return _apply_security_headers(response)

    @app.context_processor
    def inject_config():
        return {"cfg": config, "config": config}

    from app.routes.health import register_health_routes
    from app.routes.interview import register_candidate_interview_routes

    register_health_routes(app)
    register_candidate_interview_routes(app)

    return app

