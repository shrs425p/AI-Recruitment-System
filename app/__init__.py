import os
import secrets
import threading
from datetime import timedelta

from flask import Flask, jsonify, render_template, request

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
        SESSION_COOKIE_SAMESITE="Lax",
        PERMANENT_SESSION_LIFETIME=timedelta(hours=8),
        _NONCE_POOL=set(),
        _NONCE_LOCK=threading.Lock(),
    )
    register_error_handlers(app)
    protect_hr_routes(app)

    @app.after_request
    def add_security_headers(response):
        response.headers.setdefault("Cache-Control", "no-store")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
        return response

    @app.context_processor
    def inject_config():
        return {"cfg": config, "config": config}

    return app
