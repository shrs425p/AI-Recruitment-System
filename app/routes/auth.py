import hmac
import time

from flask import jsonify, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash

import config
from app.rate_limiter import SimpleRateLimiter

login_rate_limiter = SimpleRateLimiter(requests_per_minute=5, max_keys=1000)


def register_auth_routes(app):
    if "desktop_bootstrap" in app.view_functions:
        return
    @app.route("/desktop-bootstrap")
    def desktop_bootstrap():
        if session.get("logged_in") and session.get("desktop_session"):
            return redirect(url_for("dashboard"))

        return """
        <!DOCTYPE html>
        <html>
        <head>
            <title>Loading AI Recruitment System...</title>
            <style>body{background:#000; color:#fff; display:flex; justify-content:center; align-items:center; height:100vh; font-family:sans-serif;}</style>
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

        if is_valid:
            session.clear()
            session["logged_in"] = True
            session["desktop_session"] = True
            session.permanent = True
            return jsonify({"success": True})

        return jsonify({"error": "Unauthorized"}), 403

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if not config.LOGIN_ENABLED:
            return render_template(
                "login.html",
                error="HR login is disabled for browsers on this server. Please use the Desktop App.",
            ), 403
        error = None
        if request.method == "POST":
            # SEC-02: Rate limiting on authentication attempts
            client_ip = (
                request.headers.get("X-Forwarded-For", request.remote_addr or "127.0.0.1")
                .split(",")[0]
                .strip()
            )
            if not login_rate_limiter.is_allowed(client_ip):
                return render_template(
                    "login.html",
                    error="Too many login attempts. Please wait 1 minute before trying again.",
                ), 429

            # SEC-01: CSRF validation for HTML form POST
            expected_csrf = session.get("_csrf_token", "")
            if expected_csrf:
                provided_csrf = request.form.get("csrf_token", "") or request.headers.get("X-CSRF-Token", "")
                if not provided_csrf or not hmac.compare_digest(provided_csrf, expected_csrf):
                    return render_template(
                        "login.html",
                        error="Session expired or invalid CSRF token. Please refresh and try again.",
                    ), 403

            username = request.form.get("username", "").strip()
            password = request.form.get("password", "")
            password_hash = getattr(config, "HR_PASSWORD_HASH", "")

            password_ok = False
            if password_hash:
                password_ok = check_password_hash(password_hash, password)
            else:
                raw_configured = getattr(config, "HR_PASSWORD", "")
                if raw_configured and hmac.compare_digest(password, raw_configured):
                    from werkzeug.security import generate_password_hash

                    from app.database import save_settings_dict

                    new_hash = generate_password_hash(password)
                    config.HR_PASSWORD_HASH = new_hash
                    config.HR_PASSWORD = ""
                    try:
                        save_settings_dict({"HR_PASSWORD_HASH": new_hash, "HR_PASSWORD": ""})
                    except Exception:
                        pass
                    password_ok = True

            if hmac.compare_digest(username, getattr(config, "HR_USERNAME", "")) and password_ok:
                session.clear()
                session["logged_in"] = True
                session["username"]  = username
                session.permanent = True
                return redirect(url_for("dashboard"))
            else:
                time.sleep(1.0)
                error = "Invalid credentials. Please try again."
        return render_template("login.html", error=error)


    @app.route("/logout")
    def logout():
        session.clear()
        return redirect(url_for("login"))
