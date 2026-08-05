import hmac

from flask import redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash

import config
from app.utils import is_local_request


def register_auth_routes(app):
    @app.route("/desktop-login")
    def desktop_login():
        import os
        token = request.args.get("token")
        if token and token == os.environ.get("DESKTOP_AUTH_TOKEN"):
            session.clear()
            session["logged_in"] = True
            session.permanent = True
            return redirect(url_for("dashboard"))
        return "Unauthorized", 403

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
