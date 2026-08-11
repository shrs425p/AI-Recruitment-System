"""
app/auth.py -- JWT Authentication, Session Validation & Role-Based Access Control
==================================================================================

Public API
----------
  generate_jwt(user_id, username, role)  -> token str
  verify_jwt(token)                      -> payload dict  (raises JWTError on failure)
  jwt_required                           -> route decorator
  require_role(*roles)                   -> route decorator factory
  JWTError                               -> exception class

The JWT is HS256-signed using the Flask app's SECRET_KEY.
Every issued token has a unique `jti` (JWT ID) stored in the `hr_sessions` table;
this allows individual sessions to be revoked server-side at logout.

Token sources (checked in order by `jwt_required`):
  1. Authorization: Bearer <token>   -- preferred for API calls
  2. session["jwt_token"]            -- used by the pywebview desktop flow
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone
from functools import wraps
from typing import Any

import jwt as pyjwt
from flask import g, jsonify, request, session

from app.database import create_session_record, get_session_record

logger = logging.getLogger(__name__)

# -- Token settings -----------------------------------------------------------
_ACCESS_TOKEN_TTL = timedelta(hours=8)
_ALGORITHM = "HS256"


# -- Custom exception ---------------------------------------------------------

class JWTError(Exception):
    """Raised when token validation fails for any reason."""


# -- Internal helpers ---------------------------------------------------------

def _secret_key() -> str:
    """Retrieve the Flask app secret key from the current application context."""
    from flask import current_app
    key = current_app.secret_key
    if not key:
        raise RuntimeError("Flask SECRET_KEY is not configured -- cannot sign JWTs.")
    return key if isinstance(key, str) else key.decode()


# -- Token generation ---------------------------------------------------------

def generate_jwt(user_id: int, username: str, role: str) -> str:
    """
    Issue a new signed JWT for the given user and persist the session record.

    Args:
        user_id:  Primary key from hr_users.
        username: Display / login name.
        role:     One of 'admin', 'hr', 'candidate'.

    Returns:
        A signed JWT string (HS256).
    """
    now = datetime.now(tz=timezone.utc)
    expires_at = now + _ACCESS_TOKEN_TTL
    jti = str(uuid.uuid4())

    payload: dict[str, Any] = {
        "sub": str(user_id),
        "username": username,
        "role": role,
        "jti": jti,
        "iat": now,
        "exp": expires_at,
    }

    token = pyjwt.encode(payload, _secret_key(), algorithm=_ALGORITHM)

    # Persist to DB so we can revoke later
    create_session_record(
        jti=jti,
        user_id=user_id,
        username=username,
        role=role,
        expires_at=expires_at.strftime("%Y-%m-%d %H:%M:%S"),
    )

    logger.info("[AUTH] JWT issued -- user=%s role=%s jti=%s", username, role, jti)
    return token


# -- Token verification -------------------------------------------------------

def verify_jwt(token: str) -> dict[str, Any]:
    """
    Decode and validate a JWT token.

    Checks:
      - Valid HS256 signature
      - Not expired
      - jti exists in hr_sessions and is not revoked

    Args:
        token: Raw JWT string.

    Returns:
        Decoded payload dict.

    Raises:
        JWTError: If the token is invalid, expired, or revoked.
    """
    try:
        payload = pyjwt.decode(token, _secret_key(), algorithms=[_ALGORITHM])
    except pyjwt.ExpiredSignatureError:
        raise JWTError("Token has expired.")
    except pyjwt.InvalidTokenError as exc:
        raise JWTError(f"Invalid token: {exc}") from exc

    jti = payload.get("jti")
    if not jti:
        raise JWTError("Token missing jti claim.")

    record = get_session_record(jti)
    if record is None:
        raise JWTError("Session not found.")
    if record["revoked"]:
        raise JWTError("Session has been revoked.")

    return payload


# -- Decorators ---------------------------------------------------------------

def jwt_required(f):
    """
    Route decorator that enforces JWT authentication.

    Token resolution order:
      1. ``Authorization: Bearer <token>`` request header
      2. ``session["jwt_token"]``  (set by the desktop / browser login flow)

    On success, sets ``g.current_user`` to the decoded JWT payload dict.
    On failure, returns 401 JSON for API routes or 404 for browser routes
    (preserving the existing ghost behaviour for unauthenticated browsers).
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        token = _extract_token()
        if not token:
            return _auth_error("No authentication token provided.", status=401)
        try:
            payload = verify_jwt(token)
        except JWTError as exc:
            logger.warning("[AUTH] JWT validation failed: %s", exc)
            return _auth_error(str(exc), status=401)

        g.current_user = {
            "user_id": payload.get("sub"),
            "username": payload.get("username"),
            "role": payload.get("role", "hr"),
            "jti": payload.get("jti"),
        }
        return f(*args, **kwargs)
    return decorated


def require_role(*roles: str):
    """
    Route decorator factory that enforces role-based access.

    Must be applied *after* ``@jwt_required`` (i.e., placed closer to the function).

    Usage::

        @app.route("/admin/settings")
        @jwt_required
        @require_role("admin")
        def admin_settings():
            ...

    Args:
        *roles: Allowed role strings (e.g. ``"admin"``, ``"hr"``).

    Returns 403 if the authenticated user's role is not in the allowed set.
    """
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            current = getattr(g, "current_user", None)
            if current is None:
                return _auth_error("Authentication required.", status=401)
            if current["role"] not in roles:
                logger.warning(
                    "[AUTH] Role check failed -- user=%s role=%s required=%s path=%s",
                    current.get("username"), current.get("role"), roles, request.path,
                )
                return jsonify({
                    "error": "Forbidden -- insufficient role.",
                    "required_roles": list(roles),
                    "your_role": current.get("role"),
                }), 403
            return f(*args, **kwargs)
        return decorated
    return decorator


# -- Convenience aliases ------------------------------------------------------

def admin_required(f):
    """Shorthand: @jwt_required + @require_role('admin')."""
    return jwt_required(require_role("admin")(f))


def hr_or_admin_required(f):
    """Shorthand: @jwt_required + @require_role('admin', 'hr')."""
    return jwt_required(require_role("admin", "hr")(f))


# -- Private helpers ----------------------------------------------------------

def _extract_token() -> str | None:
    """Extract the JWT from the request -- header first, then session cookie."""
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        return auth_header[7:].strip()
    return session.get("jwt_token")


def _auth_error(message: str, status: int = 401):
    """Return the appropriate auth error response based on request type."""
    if request.path.startswith("/api/"):
        return jsonify({"error": message}), status
    # Non-API routes: blank 404 to avoid leaking route existence
    return "", 404
