import json

import pytest

import src.provider_router as pr


def test_key_is_valid_rejects_placeholders_and_accepts_valid():
    router = pr.ProviderRouter()

    # Placeholders should be rejected
    assert router._key_is_valid({"name": "anthropic", "key": "sk-ant-..."}) is False
    assert router._key_is_valid({"name": "openai", "key": "sk-..."}) is False
    assert router._key_is_valid({"name": "gemini", "key": "AIza..."}) is False
    assert router._key_is_valid({"name": "groq", "key": "gsk_..."}) is False
    assert router._key_is_valid({"name": "nvidia", "key": ""}) is False

    # Real keys should be accepted
    assert router._key_is_valid({"name": "anthropic", "key": "sk-ant-live-real-key-12345"}) is True
    assert router._key_is_valid({"name": "groq", "key": "gsk_live_real_groq_key_999"}) is True
    assert router._key_is_valid({"name": "nvidia", "key": "nvapi-real-key-abc"}) is True

    # ollama_cloud does not require an API key
    assert router._key_is_valid({"name": "ollama_cloud", "key": ""}) is True


def test_validate_endpoint_enforces_scheme():
    # Valid HTTPS endpoints
    pr._validate_endpoint("https://api.openai.com/v1")
    pr._validate_endpoint("https://api.groq.com/openai/v1")

    # Local HTTP allowed
    pr._validate_endpoint("http://127.0.0.1:11434")
    pr._validate_endpoint("http://localhost:11434")

    # Remote plain HTTP rejected
    with pytest.raises(RuntimeError, match="Plain HTTP provider endpoints are only allowed for local Ollama"):
        pr._validate_endpoint("http://api.remote-llm.com/v1")

    # Invalid schemes rejected
    with pytest.raises(RuntimeError, match="Unsupported provider endpoint scheme"):
        pr._validate_endpoint("ftp://example.com")


def test_call_provider_sync_openai_compatible(monkeypatch):
    recorded_calls = []

    def mock_post(url, headers, payload):
        recorded_calls.append({"url": url, "headers": headers, "payload": payload})
        return json.dumps({
            "choices": [
                {
                    "message": {
                        "content": "Model evaluated response successfully."
                    }
                }
            ]
        })

    monkeypatch.setattr(pr, "sync_http_post", mock_post)

    provider = {
        "name": "groq",
        "key": "gsk_testkey123",
        "model": "llama-3.3-70b-versatile",
    }
    result = pr.call_provider_sync(
        provider=provider,
        system_msg="System prompt",
        user_msg="Candidate interview text",
        max_tokens=500,
        candidate_name="Alice Smith",
    )

    assert result == "Model evaluated response successfully."
    assert len(recorded_calls) == 1
    assert recorded_calls[0]["url"] == "https://api.groq.com/openai/v1/chat/completions"
    assert recorded_calls[0]["headers"]["Authorization"] == "Bearer gsk_testkey123"


def test_call_provider_sync_gemini(monkeypatch):
    recorded_calls = []

    def mock_post(url, headers, payload):
        recorded_calls.append({"url": url, "headers": headers, "payload": payload})
        return json.dumps({
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {"text": "Gemini generated report"}
                        ]
                    }
                }
            ]
        })

    monkeypatch.setattr(pr, "sync_http_post", mock_post)

    provider = {
        "name": "gemini",
        "key": "AIzaSyTestKey123",
        "model": "gemini-2.5-flash",
    }
    result = pr.call_provider_sync(
        provider=provider,
        system_msg="System instructions",
        user_msg="Evaluate resume",
        max_tokens=1000,
        candidate_name="Bob Jones",
    )

    assert result == "Gemini generated report"
    assert "https://generativelanguage.googleapis.com" in recorded_calls[0]["url"]
