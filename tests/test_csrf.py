import json

from app import create_app


def _auth_client():
    app = create_app()
    client = app.test_client()
    with client.session_transaction() as sess:
        sess["logged_in"] = True
        sess["desktop_session"] = True
        sess["_csrf_token"] = "valid_csrf_token_12345"
    return client


def test_unauthenticated_api_request_rejected_by_auth():
    """Unauthenticated request is rejected by auth check with 401 before CSRF check."""
    app = create_app()
    client = app.test_client()
    response = client.post("/api/toggle-theme", json={"theme": "dark"})
    assert response.status_code == 401


def test_authenticated_api_post_without_csrf_token_returns_403():
    """Authenticated HR session making POST under /api/ without X-CSRF-Token is rejected with 403."""
    client = _auth_client()
    response = client.post(
        "/api/toggle-theme",
        data=json.dumps({"theme": "dark"}),
        content_type="application/json",
    )
    assert response.status_code == 403
    data = response.get_json()
    assert data["code"] == 403
    assert "CSRF token missing or invalid" in data["error"]


def test_authenticated_api_post_with_invalid_csrf_token_returns_403():
    """Authenticated HR session providing an invalid X-CSRF-Token is rejected with 403."""
    client = _auth_client()
    response = client.post(
        "/api/toggle-theme",
        data=json.dumps({"theme": "dark"}),
        content_type="application/json",
        headers={"X-CSRF-Token": "wrong_token_value"},
    )
    assert response.status_code == 403
    data = response.get_json()
    assert data["code"] == 403
    assert "CSRF token missing or invalid" in data["error"]


def test_authenticated_api_post_with_valid_csrf_token_accepted():
    """Authenticated HR session providing matching X-CSRF-Token passes CSRF check."""
    client = _auth_client()
    response = client.post(
        "/api/toggle-theme",
        data=json.dumps({}),
        content_type="application/json",
        headers={"X-CSRF-Token": "valid_csrf_token_12345"},
    )
    assert response.status_code == 200
    data = response.get_json()
    assert data["success"] is True
    assert "theme" in data


def test_authenticated_api_get_does_not_require_csrf_token():
    """GET requests under /api/ do not require X-CSRF-Token."""
    client = _auth_client()
    response = client.get("/api/stats")
    assert response.status_code == 200


def test_candidate_api_post_does_not_require_csrf_token():
    """Candidate endpoints under /api/candidate/ do not require X-CSRF-Token."""
    app = create_app()
    client = app.test_client()
    # Candidate answer without token returns 400 (session key required), not 403 CSRF
    response = client.post(
        "/api/candidate/answer",
        json={"answer": "hello"},
    )
    assert response.status_code != 403


def test_desktop_login_bootstrap_does_not_require_csrf_token():
    """Bootstrap endpoint /api/desktop-login does not require X-CSRF-Token."""
    app = create_app()
    client = app.test_client()
    response = client.post(
        "/api/desktop-login",
        json={"nonce": "invalid-nonce"},
    )
    assert response.status_code == 403
    # Returns Unauthorized from desktop-login logic, not CSRF error
    assert response.get_json().get("error") == "Unauthorized"


def test_csrf_token_generation_and_context_processor(monkeypatch):
    """Visiting a page generates a _csrf_token in session and injects it into template context."""
    import config
    monkeypatch.setattr(config, "LOGIN_ENABLED", True)
    app = create_app()
    client = app.test_client()
    response = client.get("/login")
    assert response.status_code == 200
    with client.session_transaction() as sess:
        assert "_csrf_token" in sess
        assert len(sess["_csrf_token"]) == 64  # 32 bytes hex
