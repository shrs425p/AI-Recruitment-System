import hmac

from flask import jsonify, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash

import config
from app.utils import is_local_request


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
                            if (res.ok) {
                                window.location.href = '/dashboard';
                            } else {
                                document.getElementById('status').innerText = 'Authentication Failed. (HTTP ' + res.status + ')';
                            }
                        }).catch(function(err) {
                            document.getElementById('status').innerText = 'Connection Error: ' + err;
                        });
                    });
                });
                setTimeout(function() {
                    if (!window.pywebview) {
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
            
        data = request.json or {}
        nonce = data.get("nonce")
        import os
        
        valid_nonces = [n for n in os.environ.get("DESKTOP_AUTH_NONCES", "").split(",") if n]
        
        # Verify and immediately invalidate the nonce to prevent replay
        if nonce and nonce in valid_nonces:
            # Remove this specific nonce from the active pool
            valid_nonces.remove(nonce)
            os.environ["DESKTOP_AUTH_NONCES"] = ",".join(valid_nonces) + "," if valid_nonces else ""
            
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
            username = request.form.get("username", "").strip()
            password = request.form.get("password", "")
            password_hash = getattr(config, "HR_PASSWORD_HASH", "")
            password_ok = (
                check_password_hash(password_hash, password)
                if password_hash
                else hmac.compare_digest(password, getattr(config, "HR_PASSWORD", ""))
            )
            if hmac.compare_digest(username, getattr(config, "HR_USERNAME", "")) and password_ok:
                session.clear()
                session["logged_in"] = True
                session["username"]  = username
                session.permanent = True
                return redirect(url_for("dashboard"))
            else:
                error = "Invalid credentials. Please try again."
        return render_template("login.html", error=error)

    @app.route("/logout")
    def logout():
        session.clear()
        return redirect(url_for("login"))
