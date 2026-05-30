from flask import request, render_template, redirect, url_for, session
import config

def register_auth_routes(app):
    @app.route("/login", methods=["GET", "POST"])
    def login():
        if not config.LOGIN_ENABLED:
            session["logged_in"] = True
            return redirect(url_for("dashboard"))
        error = None
        if request.method == "POST":
            username = request.form.get("username", "").strip()
            password = request.form.get("password", "")
            if username == config.HR_USERNAME and password == config.HR_PASSWORD:
                session["logged_in"] = True
                session["username"]  = username
                return redirect(url_for("dashboard"))
            else:
                error = "Invalid credentials. Please try again."
        return render_template("login.html", error=error)

    @app.route("/logout")
    def logout():
        session.clear()
        return redirect(url_for("login"))
