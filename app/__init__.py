import os
import secrets

from flask import Flask, jsonify, render_template, request

import config
from src.common import APP_RESOURCE_DIR
from app.utils import protect_hr_routes


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
    register_error_handlers(app)
    protect_hr_routes(app)

    @app.context_processor
    def inject_config():
        return {"cfg": config, "config": config}

    return app
