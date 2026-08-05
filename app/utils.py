import ipaddress
from functools import wraps
from flask import jsonify, redirect, request, session, url_for

PUBLIC_PATH_PREFIXES = (
    "/candidate-interview/",
    "/api/candidate/",
    "/api/health",
    "/static/",
    "/api/toggle-theme",
    "/api/change-theme",
    "/api/change-palette",
    "/api/toggle-ai-mode",
    "/api/provider-models",
    "/api/test-smtp",
)

def is_local_request() -> bool:
    remote_addr = request.remote_addr or ""
    try:
        return ipaddress.ip_address(remote_addr).is_loopback
    except ValueError:
        return remote_addr in {"localhost", "127.0.0.1", "::1"}

def is_public_candidate_path(path: str) -> bool:
    return path in {"/login", "/logout"} or path.startswith(PUBLIC_PATH_PREFIXES)

def _auth_failure_response():
    if request.path.startswith("/api/"):
        return jsonify({"error": "HR authentication required"}), 401
    try:
        return redirect(url_for("login"))
    except Exception:
        return redirect("/login")

def hr_access_allowed() -> bool:
    if session.get("logged_in"):
        return True
    return False

def protect_hr_routes(app):
    @app.before_request
    def _protect_hr_routes():
        if is_public_candidate_path(request.path):
            return None
        if hr_access_allowed():
            return None
        return _auth_failure_response()

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not hr_access_allowed():
            return _auth_failure_response()
        return f(*args, **kwargs)
    return decorated_function
