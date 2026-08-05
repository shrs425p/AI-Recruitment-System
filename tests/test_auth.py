from flask import Flask
from werkzeug.security import generate_password_hash

import config
from app import create_app
from src.common import APP_RESOURCE_DIR
from app.routes.auth import register_auth_routes


def _app():
    app = Flask(__name__, template_folder=str(APP_RESOURCE_DIR / "app" / "templates"))
    app.secret_key = "mock_test_key_for_flask"
    app.add_url_rule("/dashboard", "dashboard", lambda: "dashboard")
    register_auth_routes(app)
    return app


def test_login_accepts_hashed_password(monkeypatch):
    monkeypatch.setattr(config, "LOGIN_ENABLED", True, raising=False)
    monkeypatch.setattr(config, "HR_USERNAME", "hr", raising=False)
    monkeypatch.setattr(config, "HR_PASSWORD", "", raising=False)
    monkeypatch.setattr(config, "HR_PASSWORD_HASH", generate_password_hash("secret-pass"), raising=False)

    client = _app().test_client()
    response = client.post("/login", data={"username": "hr", "password": "secret-pass"})

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/dashboard")


def test_login_rejects_wrong_password(monkeypatch):
    monkeypatch.setattr(config, "LOGIN_ENABLED", True, raising=False)
    monkeypatch.setattr(config, "HR_USERNAME", "hr", raising=False)
    monkeypatch.setattr(config, "HR_PASSWORD", "", raising=False)
    monkeypatch.setattr(config, "HR_PASSWORD_HASH", generate_password_hash("secret-pass"), raising=False)

    client = _app().test_client()
    response = client.post("/login", data={"username": "hr", "password": "wrong"})

    assert response.status_code == 200
    assert b"Invalid credentials" in response.data


def test_remote_user_cannot_open_hr_screen_when_login_disabled(monkeypatch):
    monkeypatch.setattr(config, "LOGIN_ENABLED", False, raising=False)

    app = create_app()
    app.add_url_rule("/dashboard", "dashboard", lambda: "dashboard")
    register_auth_routes(app)

    response = app.test_client().get(
        "/dashboard",
        environ_base={"REMOTE_ADDR": "192.168.1.50"},
    )

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/login")


def test_remote_candidate_api_stays_public_when_login_disabled(monkeypatch):
    monkeypatch.setattr(config, "LOGIN_ENABLED", False, raising=False)

    app = create_app()
    app.add_url_rule("/api/candidate/ping", "candidate_ping", lambda: "ok")
    register_auth_routes(app)

    response = app.test_client().get(
        "/api/candidate/ping",
        environ_base={"REMOTE_ADDR": "192.168.1.50"},
    )

    assert response.status_code == 200
    assert response.data == b"ok"
