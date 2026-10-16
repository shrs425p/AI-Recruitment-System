from flask import Flask
from werkzeug.security import generate_password_hash

import config
from app import create_app
from app.routes.auth import register_auth_routes
from src.common import APP_RESOURCE_DIR


def _app():
    app = Flask(__name__, template_folder=str(APP_RESOURCE_DIR / "app" / "templates"))
    app.secret_key = "mock_test_key_for_flask"
    app.add_url_rule("/dashboard", "dashboard", lambda: "dashboard")
    register_auth_routes(app)

    @app.context_processor
    def inject_csrf():
        return {"csrf_token": lambda: "test-token"}

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

    response = app.test_client().get(
        "/dashboard",
        environ_base={"REMOTE_ADDR": "192.168.1.50"},
    )

    assert response.status_code in (302, 404)



def test_remote_candidate_api_stays_public_when_login_disabled(monkeypatch):
    monkeypatch.setattr(config, "LOGIN_ENABLED", False, raising=False)

    app = create_app()
    if "candidate_ping" not in app.view_functions:
        app.add_url_rule("/api/candidate/ping", "candidate_ping", lambda: "ok")

    response = app.test_client().get(
        "/api/candidate/ping",
        environ_base={"REMOTE_ADDR": "192.168.1.50"},
    )

    assert response.status_code == 200
    assert response.data == b"ok"


def test_remote_user_cannot_test_smtp_when_login_disabled(monkeypatch):
    monkeypatch.setattr(config, "LOGIN_ENABLED", False, raising=False)

    app = create_app()

    response = app.test_client().post(
        "/api/test-smtp",
        environ_base={"REMOTE_ADDR": "192.168.1.50"},
    )

    assert response.status_code in (401, 404)


def test_login_migrates_plaintext_password_to_hash_on_first_login(monkeypatch):
    saved_settings = {}
    import app.database as db
    monkeypatch.setattr(db, "save_settings_dict", lambda s: saved_settings.update(s))
    monkeypatch.setattr(config, "LOGIN_ENABLED", True, raising=False)
    monkeypatch.setattr(config, "HR_USERNAME", "hr_admin", raising=False)
    monkeypatch.setattr(config, "HR_PASSWORD", "plain_password_123", raising=False)
    monkeypatch.setattr(config, "HR_PASSWORD_HASH", "", raising=False)

    client = _app().test_client()
    res = client.post("/login", data={"username": "hr_admin", "password": "plain_password_123"})
    assert res.status_code == 302
    assert res.headers["Location"].endswith("/dashboard")

    # Verify migration occurred
    assert config.HR_PASSWORD_HASH != ""
    assert config.HR_PASSWORD == ""
    assert "HR_PASSWORD_HASH" in saved_settings
    assert saved_settings["HR_PASSWORD"] == ""

    # Second login works with the generated hash
    res2 = client.post("/login", data={"username": "hr_admin", "password": "plain_password_123"})
    assert res2.status_code == 302


def test_login_rejects_wrong_password_during_migration(monkeypatch):
    monkeypatch.setattr(config, "LOGIN_ENABLED", True, raising=False)
    monkeypatch.setattr(config, "HR_USERNAME", "hr_admin", raising=False)
    monkeypatch.setattr(config, "HR_PASSWORD", "plain_password_123", raising=False)
    monkeypatch.setattr(config, "HR_PASSWORD_HASH", "", raising=False)

    client = _app().test_client()
    res = client.post("/login", data={"username": "hr_admin", "password": "wrong_password"})
    assert res.status_code == 200
    assert b"Invalid credentials" in res.data
    # Hash should not be generated
    assert config.HR_PASSWORD_HASH == ""

