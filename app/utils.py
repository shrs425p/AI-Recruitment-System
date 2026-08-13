import ipaddress
import logging
from functools import wraps

from flask import g, jsonify, redirect, request, session, url_for

logger = logging.getLogger(__name__)

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
    "/desktop-bootstrap",
    "/api/desktop-login",
)


def is_local_request() -> bool:
    remote_addr = request.remote_addr or ""
    try:
        return ipaddress.ip_address(remote_addr).is_loopback
    except ValueError:
        return remote_addr in {"localhost", "127.0.0.1", "::1"}


def is_public_candidate_path(path: str) -> bool:
    return path == "/logout" or path.startswith(PUBLIC_PATH_PREFIXES)


def _auth_failure_response():
    if request.path.startswith("/api/"):
        return jsonify({"error": "Not found"}), 404
    # Return absolutely nothing to unauthorized web browsers (blank white page)
    return "", 404


def hr_access_allowed() -> bool:
    """
    Return True if the current request carries a valid HR session.

    Checks (in order):
      1. JWT stored in session["jwt_token"] -- verified via app.auth.verify_jwt
         which checks signature, expiry, and server-side revocation in hr_sessions.
      2. Legacy fallback: session["logged_in"] + session["desktop_session"]
         (kept for backward compatibility during the transition period).
    """
    token = session.get("jwt_token")
    if token:
        try:
            from app.auth import verify_jwt
            payload = verify_jwt(token)
            # Inject user context into Flask g for downstream use
            g.current_user = {
                "user_id": payload.get("sub"),
                "username": payload.get("username"),
                "role": payload.get("role", "hr"),
                "jti": payload.get("jti"),
            }
            return True
        except Exception as exc:
            logger.debug("[AUTH] JWT check failed in hr_access_allowed: %s", exc)
            return False

    # Legacy fallback (no JWT in session yet -- e.g. first boot edge case)
    if session.get("logged_in") and session.get("desktop_session"):
        g.current_user = {
            "user_id": None,
            "username": session.get("username", "admin"),
            "role": "admin",
            "jti": None,
        }
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
    """Decorator: requires a valid JWT session. Returns 404 on failure."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not hr_access_allowed():
            return _auth_failure_response()
        return f(*args, **kwargs)
    return decorated_function


def admin_required(f):
    """Decorator: requires a valid JWT session with role='admin'. Returns 403 on role mismatch."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not hr_access_allowed():
            return _auth_failure_response()
        current = getattr(g, "current_user", {})
        if current.get("role") != "admin":
            if request.path.startswith("/api/"):
                return jsonify({"error": "Forbidden -- admin role required."}), 403
            return "", 404
        return f(*args, **kwargs)
    return decorated_function
