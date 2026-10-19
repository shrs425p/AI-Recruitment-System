"""
test_auth.py - authentication, session security, single-use desktop
token/nonce verification, and strict network boundary access control tests.
"""

from __future__ import annotations

import secrets

import pytest
from flask import Flask
from flask.testing import FlaskClient
from werkzeug.security import generate_password_hash

import config
from app import create_app, create_candidate_app
from app.routes.auth import register_auth_routes
from src.common import APP_RESOURCE_DIR


def _isolated_auth_app() -> Flask:
    """Creates a lightweight Flask app dedicated to testing authentication routines."""
    app = Flask(__name__, template_folder=str(APP_RESOURCE_DIR / "app" / "templates"))
    app.secret_key = "commercial_test_auth_secret_key"
    app.add_url_rule("/dashboard", "dashboard", lambda: "dashboard")
    register_auth_routes(app)

    @app.context_processor
    def inject_csrf():
        return {"csrf_token": lambda: "test-auth-token"}

    return app


class TestUserCredentialsAuthentication:
    """Tests HR manager username/password authentication, hashing, and password migration."""

    @pytest.fixture(autouse=True)
    def reset_limiter(self):
        from app.routes.auth import login_rate_limiter

        login_rate_limiter.requests.clear()
        yield
        login_rate_limiter.requests.clear()

    def test_login_accepts_hashed_password(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setattr(config, "LOGIN_ENABLED", True, raising=False)
        monkeypatch.setattr(config, "HR_USERNAME", "hr_admin", raising=False)
        monkeypatch.setattr(config, "HR_PASSWORD", "", raising=False)
        monkeypatch.setattr(
            config,
            "HR_PASSWORD_HASH",
            generate_password_hash("StrongSecretPass123!"),
            raising=False,
        )

        client = _isolated_auth_app().test_client()
        response = client.post(
            "/login",
            data={"username": "hr_admin", "password": "StrongSecretPass123!"},
        )

        assert response.status_code == 302
        assert response.headers["Location"].endswith("/dashboard")

    def test_login_rejects_incorrect_password(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setattr(config, "LOGIN_ENABLED", True, raising=False)
        monkeypatch.setattr(config, "HR_USERNAME", "hr_admin", raising=False)
        monkeypatch.setattr(config, "HR_PASSWORD", "", raising=False)
        monkeypatch.setattr(
            config,
            "HR_PASSWORD_HASH",
            generate_password_hash("StrongSecretPass123!"),
            raising=False,
        )

        monkeypatch.setattr("time.sleep", lambda s: None)
        client = _isolated_auth_app().test_client()
        response = client.post(
            "/login",
            data={"username": "hr_admin", "password": "WrongPasswordAttempt"},
        )

        assert response.status_code == 200
        assert b"Invalid credentials" in response.data

    def test_login_migrates_plaintext_password_on_first_success(self, monkeypatch: pytest.MonkeyPatch):
        saved_settings = {}
        import app.database as db

        monkeypatch.setattr(db, "save_settings_dict", lambda s: saved_settings.update(s))
        monkeypatch.setattr(config, "LOGIN_ENABLED", True, raising=False)
        monkeypatch.setattr(config, "HR_USERNAME", "hr_admin", raising=False)
        monkeypatch.setattr(config, "HR_PASSWORD", "legacy_plain_pass_2026", raising=False)
        monkeypatch.setattr(config, "HR_PASSWORD_HASH", "", raising=False)

        client = _isolated_auth_app().test_client()
        response = client.post(
            "/login",
            data={"username": "hr_admin", "password": "legacy_plain_pass_2026"},
        )

        assert response.status_code == 302
        assert config.HR_PASSWORD_HASH != ""
        assert config.HR_PASSWORD == ""
        assert "HR_PASSWORD_HASH" in saved_settings
        assert saved_settings["HR_PASSWORD"] == ""

    def test_login_disabled_mode_returns_403(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setattr(config, "LOGIN_ENABLED", False, raising=False)
        app = create_app()
        client = app.test_client()
        response = client.get("/login")
        assert response.status_code == 403

    def test_login_csrf_validation(self, monkeypatch: pytest.MonkeyPatch):
        from app.routes.auth import login_rate_limiter

        login_rate_limiter.requests.clear()
        monkeypatch.setattr(config, "LOGIN_ENABLED", True, raising=False)
        monkeypatch.setattr(config, "HR_USERNAME", "hr_admin", raising=False)
        monkeypatch.setattr(
            config,
            "HR_PASSWORD_HASH",
            generate_password_hash("Secret123!"),
            raising=False,
        )
        monkeypatch.setattr("time.sleep", lambda s: None)

        client = _isolated_auth_app().test_client()

        # Set CSRF token in session
        with client.session_transaction() as sess:
            sess["_csrf_token"] = "valid-csrf-token-12345"

        # Missing CSRF token
        r_missing = client.post(
            "/login",
            data={"username": "hr_admin", "password": "Secret123!"},
        )
        assert r_missing.status_code == 403
        assert b"CSRF token" in r_missing.data

        # Invalid CSRF token
        r_invalid = client.post(
            "/login",
            data={"username": "hr_admin", "password": "Secret123!", "csrf_token": "wrong-token"},
        )
        assert r_invalid.status_code == 403

        # Valid CSRF token
        r_valid = client.post(
            "/login",
            data={"username": "hr_admin", "password": "Secret123!", "csrf_token": "valid-csrf-token-12345"},
        )
        assert r_valid.status_code == 302
        assert r_valid.headers["Location"].endswith("/dashboard")

    def test_login_rate_limiting_enforces_lockout(self, monkeypatch: pytest.MonkeyPatch):
        from app.routes.auth import login_rate_limiter

        login_rate_limiter.requests.clear()
        monkeypatch.setattr(config, "LOGIN_ENABLED", True, raising=False)
        monkeypatch.setattr(config, "HR_USERNAME", "hr_admin", raising=False)
        monkeypatch.setattr(
            config,
            "HR_PASSWORD_HASH",
            generate_password_hash("Secret123!"),
            raising=False,
        )
        monkeypatch.setattr("time.sleep", lambda s: None)

        client = _isolated_auth_app().test_client()

        test_ip = "192.168.1.100"
        headers = {"X-Forwarded-For": test_ip}

        # 5 failed attempts allowed
        for _ in range(5):
            r = client.post(
                "/login",
                data={"username": "hr_admin", "password": "WrongPassword"},
                headers=headers,
            )
            assert r.status_code == 200

        # 6th attempt should be blocked with 429
        r_blocked = client.post(
            "/login",
            data={"username": "hr_admin", "password": "Secret123!"},
            headers=headers,
        )
        assert r_blocked.status_code == 429
        assert b"Too many login attempts" in r_blocked.data
        login_rate_limiter.requests.clear()


class TestDesktopNonceSecurity:
    """Verifies single-use desktop bootstrap nonces and anti-replay defenses."""

    def test_desktop_login_rejects_bogus_nonce(self, client: FlaskClient):
        response = client.post(
            "/api/desktop-login",
            json={"nonce": "totally_fabricated_nonce_string"},
        )
        assert response.status_code == 403

    def test_desktop_login_rejects_empty_or_null_nonce(self, client: FlaskClient):
        assert client.post("/api/desktop-login", json={}).status_code == 403
        assert client.post("/api/desktop-login", json={"nonce": ""}).status_code == 403
        assert client.post("/api/desktop-login", json={"nonce": None}).status_code == 403

    def test_desktop_login_rejects_non_json_payload(self, client: FlaskClient):
        response = client.post(
            "/api/desktop-login",
            data="not_a_json_payload",
            headers={"Content-Type": "text/plain"},
        )
        assert response.status_code in (400, 403, 415)

    def test_desktop_login_single_use_replay_prevention(self, client: FlaskClient):
        test_nonce = secrets.token_urlsafe(32)
        nonce_pool = client.application.config.get("_NONCE_POOL")
        assert nonce_pool is not None
        nonce_pool.add(test_nonce)

        # First attempt with valid registered nonce
        r1 = client.post("/api/desktop-login", json={"nonce": test_nonce})
        assert r1.status_code == 200

        # Clear session to test anti-replay rejection without active login
        with client.session_transaction() as sess:
            sess.clear()

        # Second attempt with consumed nonce must be rejected
        r2 = client.post("/api/desktop-login", json={"nonce": test_nonce})
        assert r2.status_code == 403


class TestAccessControlBoundaries:
    """Validates that HR administrative routes cannot be accessed without session authentication."""

    def test_hr_web_routes_blocked_without_session(self, client: FlaskClient):
        for route in ("/dashboard", "/ranking", "/scheduling", "/reports", "/settings"):
            response = client.get(route)
            assert response.status_code in (302, 401, 403, 404)

    def test_hr_api_routes_return_401_json(self, client: FlaskClient):
        for route in ("/api/stats", "/api/logs", "/api/task-status"):
            response = client.get(route, headers={"Accept": "application/json"})
            assert response.status_code == 401
            assert response.is_json

    def test_candidate_portal_app_returns_404_for_all_hr_routes(self):
        cand_app = create_candidate_app()
        cand_client = cand_app.test_client()

        hr_routes = [
            ("GET", "/dashboard"),
            ("GET", "/ranking"),
            ("GET", "/scheduling"),
            ("GET", "/interview"),
            ("GET", "/reports"),
            ("GET", "/settings"),
            ("POST", "/api/upload"),
            ("POST", "/api/extract-text"),
            ("POST", "/api/run-nlp"),
            ("POST", "/api/run-ranking"),
            ("POST", "/api/generate-reports"),
        ]
        for method, route in hr_routes:
            if method == "GET":
                resp = cand_client.get(route)
            else:
                resp = cand_client.post(route, json={})
            assert resp.status_code == 404, f"Candidate portal exposed HR route {route}"

    def test_remote_candidate_interview_route_accessible_without_hr_session(self, client: FlaskClient):
        # Candidate interview link is public; it validates access token, not HR session
        response = client.get("/candidate-interview/T_NONEXISTENT_TEST_TOKEN")
        assert response.status_code != 401
