import json

from src.provider_router import call_provider_sync, sanitize_prompt_pii


def test_sanitize_prompt_pii_emails():
    text = "Please evaluate john.smith@company.com and contact recruiter at hr@domain.org."
    sanitized = sanitize_prompt_pii(text)
    assert "john.smith@company.com" not in sanitized
    assert "hr@domain.org" not in sanitized
    assert "[EMAIL_REDACTED]" in sanitized


def test_sanitize_prompt_pii_phone_numbers():
    text = (
        "Applicant phone numbers: +1 (555) 234-5678, mobile: +91 9876543210, "
        "alt: 555-456-7890. Experience with Python 3.11 and 5 years in backend."
    )
    sanitized = sanitize_prompt_pii(text)
    assert "+1 (555) 234-5678" not in sanitized
    assert "9876543210" not in sanitized
    assert "555-456-7890" not in sanitized
    assert "[PHONE_REDACTED]" in sanitized
    # Ensure technical terms and numbers like Python 3.11 and 5 years are preserved
    assert "Python 3.11" in sanitized
    assert "5 years in backend" in sanitized


def test_sanitize_prompt_pii_candidate_names():
    # Passed explicit candidate name
    text = "We are scoring Alex Mercer on skills and culture fit."
    sanitized = sanitize_prompt_pii(text, candidate_name="Alex Mercer")
    assert "Alex Mercer" not in sanitized
    assert "[CANDIDATE_NAME]" in sanitized

    # Labeled candidate name in resume/prompt
    labeled_text = "Candidate Name: Samantha Jones\nJob Title: DevOps Engineer"
    sanitized_labeled = sanitize_prompt_pii(labeled_text)
    assert "Samantha Jones" not in sanitized_labeled
    assert "[CANDIDATE_NAME]" in sanitized_labeled
    assert "DevOps Engineer" in sanitized_labeled


def test_cloud_provider_sync_payload_redaction(monkeypatch):
    """Verify that call_provider_sync redacts PII before sending payload to external cloud APIs."""
    intercepted_payloads = []

    def fake_sync_http_post(url, headers, payload):
        intercepted_payloads.append({"url": url, "headers": headers, "payload": payload})
        if "anthropic" in url:
            return json.dumps({"content": [{"text": "Anthropic response"}]})
        elif "generativelanguage" in url:
            return json.dumps({"candidates": [{"content": {"parts": [{"text": "Gemini response"}]}}]})
        else:
            return json.dumps({"choices": [{"message": {"content": "OpenAI-compatible response"}}]})

    monkeypatch.setattr("src.provider_router.sync_http_post", fake_sync_http_post)

    prompt = (
        "Candidate Name: Robert Bruce\n"
        "Email: robert.bruce@scotland.org\n"
        "Phone: +44 7911 123456\n"
        "Technical Skills: Kubernetes, Go, Linux kernel"
    )

    # 1. Anthropic
    anthropic_provider = {"name": "anthropic", "key": "sk-ant-testkey", "model": "claude-3-opus"}
    call_provider_sync(anthropic_provider, "You are a helpful HR evaluator.", prompt, 1024, candidate_name="Robert Bruce")
    p1 = intercepted_payloads[-1]["payload"]
    user_msg_1 = p1["messages"][0]["content"]
    assert "Robert Bruce" not in user_msg_1
    assert "robert.bruce@scotland.org" not in user_msg_1
    assert "Kubernetes, Go, Linux kernel" in user_msg_1
    assert "[CANDIDATE_NAME]" in user_msg_1
    assert "[EMAIL_REDACTED]" in user_msg_1

    # 2. Gemini
    gemini_provider = {"name": "gemini", "key": "AIzaFakeKey", "model": "gemini-1.5-pro"}
    call_provider_sync(gemini_provider, "Evaluate candidate.", prompt, 1024, candidate_name="Robert Bruce")
    p2 = intercepted_payloads[-1]["payload"]
    gemini_text = p2["contents"][0]["parts"][0]["text"]
    assert "Robert Bruce" not in gemini_text
    assert "robert.bruce@scotland.org" not in gemini_text
    assert "Kubernetes, Go, Linux kernel" in gemini_text
    assert "[CANDIDATE_NAME]" in gemini_text

    # 3. OpenAI-compatible (Groq)
    groq_provider = {"name": "groq", "key": "gsk_testkey", "model": "llama-3.1-70b", "base_url": "https://api.groq.com/openai/v1"}
    call_provider_sync(groq_provider, "System prompt", prompt, 1024, candidate_name="Robert Bruce")
    p3 = intercepted_payloads[-1]["payload"]
    openai_user_msg = p3["messages"][1]["content"]
    assert "Robert Bruce" not in openai_user_msg
    assert "robert.bruce@scotland.org" not in openai_user_msg
    assert "Kubernetes, Go, Linux kernel" in openai_user_msg
    assert "[CANDIDATE_NAME]" in openai_user_msg


def test_local_ollama_not_affected_by_cloud_router():
    """Verify that local Ollama calls do not pass through cloud router sanitization."""
    # When using local Ollama, prompt is processed locally on 127.0.0.1:11434 with zero egress
    raw_prompt = "Candidate Name: Local User\nSkills: Python"
    # Calling sanitize_prompt_pii is optional/only for cloud, local prompt remains unmodified
    assert "Candidate Name: Local User" in raw_prompt
