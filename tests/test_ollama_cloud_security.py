import json
from unittest.mock import MagicMock

import pytest

import src.provider_router as provider_router
from app import create_app


def _auth_client():
    app = create_app()
    client = app.test_client()
    with client.session_transaction() as sess:
        sess["logged_in"] = True
        sess["desktop_session"] = True
        sess["_csrf_token"] = "csrf-ollama-test"
    client.environ_base["HTTP_X_CSRF_TOKEN"] = "csrf-ollama-test"
    return client


def test_ollama_cloud_rejects_plain_http(monkeypatch):
    client = _auth_client()

    response = client.post(
        "/api/provider-models",
        json={"provider": "ollama_cloud", "key": "http://example.com:11434"},
    )

    assert response.status_code == 400
    data = response.get_json()
    assert data["success"] is False
    assert "must use HTTPS" in data["error"]


def test_ollama_cloud_rejects_empty_url(monkeypatch):
    client = _auth_client()

    response = client.post(
        "/api/provider-models",
        json={"provider": "ollama_cloud", "key": ""},
    )

    assert response.status_code == 400
    data = response.get_json()
    assert data["success"] is False
    assert "required" in data["error"]


def test_ollama_cloud_accepts_https_url(monkeypatch):
    client = _auth_client()

    mock_resp = MagicMock()
    mock_resp.read.return_value = json.dumps({"models": [{"name": "llama3:latest"}]}).encode("utf-8")
    mock_resp.__enter__.return_value = mock_resp

    import urllib.request
    monkeypatch.setattr(urllib.request, "urlopen", lambda req, timeout=None: mock_resp)

    response = client.post(
        "/api/provider-models",
        json={"provider": "ollama_cloud", "key": "https://ollama.mycompany.com"},
    )

    assert response.status_code == 200
    data = response.get_json()
    assert data["success"] is True
    assert "llama3:latest" in data["models"]


def test_provider_router_rejects_non_https_for_ollama_cloud():
    provider = {
        "name": "ollama_cloud",
        "key": "http://remote-ollama.com:11434",
        "model": "llama3",
    }

    with pytest.raises(RuntimeError, match="must use HTTPS"):
        provider_router.call_provider_sync(provider, "system", "user", 100)


def test_provider_router_allows_local_http():
    # Local loopback HTTP is explicitly allowed for local Ollama
    provider_router._validate_endpoint("http://127.0.0.1:11434/api/generate")
    provider_router._validate_endpoint("http://localhost:11434/api/generate")

    # Remote plain HTTP is forbidden
    with pytest.raises(RuntimeError, match="Plain HTTP"):
        provider_router._validate_endpoint("http://evil-server.com/api")
