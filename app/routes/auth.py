import hmac
import logging
import threading

from flask import current_app, jsonify, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash

import config
from app.auth import JWTError, generate_jwt, verify_jwt
from app.database import get_user_by_username

logger = logging.getLogger(__name__)

# -- Sentinel user used when no hr_users row exists yet (first boot) ----------
_DESKTOP_USER_ID = 0
_DESKTOP_USERNAME = "admin"
_DESKTOP_ROLE = "admin"


def _get_or_resolve_user(username: str) -> tuple[int, str]:
    """Return (user_id, role) from hr_users, or fallback defaults."""
    row = get_user_by_username(username)
    if row:
        return row["id"], row["role"]
    return _DESKTOP_USER_ID, _DESKTOP_ROLE


def register_auth_routes(app):
    @app.route("/desktop-bootstrap")
    def desktop_bootstrap():
        if session.get("logged_in") and session.get("desktop_session"):
            return redirect(url_for("dashboard"))

        return """
        <!DOCTYPE html>
        <html>
        <head>
            <title>Loading AI Recruitment System...</title>
            <style>body{background:#000;color:#fff;display:flex;justify-content:center;align-items:center;height:100vh;font-family:sans-serif;}</style>
        </head>
        <body>
            <div id="status">Initializing Secure Desktop Session...</div>
            <script>
                var authAttempted = false;
                window.addEventListener('pywebviewready', function() {
                    if (authAttempted) return;
                    authAttempted = true;
                    window.pywebview.api.get_auth_nonce().then(function(nonce) {
                        fetch('/api/desktop-login', {
                            method: 'POST',
                            headers: {'Content-Type': 'application/json'},
                            body: JSON.stringify({ nonce: nonce })
                        }).then(function(res) {
                            if (window.loginSuccess) return;
                            if (res.ok) {
                                window.loginSuccess = true;
                                window.location.href = '/dashboard';
                            } else {
                                document.getElementById('status').innerText = 'Authentication Failed. (HTTP ' + res.status + ')';
                            }
                        }).catch(function(err) {
                            if (window.loginSuccess) return;
                            document.getElementById('status').innerText = 'Connection Error: ' + err;
                        });
                    });
                });
                setTimeout(function() {
                    if (!window.pywebview && !window.loginSuccess) {
                        document.getElementById('status').innerText = 'Access Denied: Please use the Desktop Application.';
                    }
                }, 3000);
            </script>
        </body>
        </html>
        """

    @app.route("/api/desktop-login", methods=["POST"])
    def api_desktop_login():
        if session.get("logged_in") and session.get("desktop_session"):
            return jsonify({"success": True})

        data = request.get_json(silent=True, force=True) or {}
        nonce = data.get("nonce") if isinstance(data, dict) else None

        nonce_lock = app.config.get("_NONCE_LOCK")
        nonce_pool = app.config.get("_NONCE_POOL")

        is_valid = False
        if nonce and nonce_lock and nonce_pool is not None:
            with nonce_lock:
                if nonce in nonce_pool:
                    nonce_pool.discard(nonce)
                    is_valid = True

        if not is_valid:
            return jsonify({"error": "Unauthorized"}), 403

        # -- Issue JWT ---------------------------------------------------------
        user_id, role = _get_or_resolve_user(_DESKTOP_USERNAME)
        try:
            token = generate_jwt(user_id=user_id, username=_DESKTOP_USERNAME, role=role)
        except Exception as exc:
            logger.error("[AUTH] Failed to generate desktop JWT: %s", exc)
            return jsonify({"error": "Session creation failed."}), 500

        session.clear()
        session["logged_in"] = True
        session["desktop_session"] = True
        session["username"] = _DESKTOP_USERNAME
        session["jwt_token"] = token
        session.permanent = True
        logger.info("[AUTH] Desktop session authenticated -- user=%s", _DESKTOP_USERNAME)
        return jsonify({"success": True})

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if not config.LOGIN_ENABLED:
            return render_template(
                "login.html",
                error="HR login is disabled for browsers on this server. Please use the Desktop App.",
            ), 403
        error = None
        if request.method == "POST":
            username = request.form.get("username", "").strip()
            password = request.form.get("password", "")
            password_hash = getattr(config, "HR_PASSWORD_HASH", "")
            password_ok = (
                check_password_hash(password_hash, password)
                if password_hash
                else hmac.compare_digest(password, getattr(config, "HR_PASSWORD", ""))
            )
            if hmac.compare_digest(username, getattr(config, "HR_USERNAME", "")) and password_ok:
                # -- Issue JWT -------------------------------------------------
                user_id, role = _get_or_resolve_user(username)
                try:
                    token = generate_jwt(user_id=user_id, username=username, role=role)
                except Exception as exc:
                    logger.error("[AUTH] Failed to generate JWT for %s: %s", username, exc)
                    error = "Session creation failed. Please try again."
                    return render_template("login.html", error=error)

                session.clear()
                session["logged_in"] = True
                session["username"] = username
                session["jwt_token"] = token
                session.permanent = True
                logger.info("[AUTH] Browser login successful -- user=%s role=%s", username, role)
                return redirect(url_for("dashboard"))
            else:
                error = "Invalid credentials. Please try again."
        return render_template("login.html", error=error)

    @app.route("/logout")
    def logout():
        # -- Revoke the server-side session record -----------------------------
        token = session.get("jwt_token")
        if token:
            try:
                payload = verify_jwt(token)
                jti = payload.get("jti")
                if jti:
                    from app.database import revoke_session
                    revoke_session(jti)
                    logger.info("[AUTH] Session revoked -- jti=%s", jti)
            except JWTError:
                pass  # Token already expired -- nothing to revoke
        session.clear()
        return redirect(url_for("login"))
