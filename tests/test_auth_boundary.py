import datetime
from datetime import timezone

import app.routes.interview as interview_routes
from app import create_app, create_candidate_app


def _sample_token(used=0, created_at=None):
    if created_at is None:
        created_at = datetime.datetime.now(timezone.utc).isoformat()
    return {
        "used": used,
        "candidate_name": "Alice Candidate",
        "source_file": "alice_resume.pdf",
        "job_title": "Software Engineer",
        "score": 90,
        "rank": 1,
        "created_at": created_at,
    }


def _setup_interview_stubs(monkeypatch, token_data):
    monkeypatch.setattr(interview_routes, "get_interview_token", lambda token: token_data)
    monkeypatch.setattr(interview_routes, "start_proctoring_session", lambda session_id: None)
    monkeypatch.setattr(interview_routes, "stop_proctoring", lambda session_id: {"events": []})
    monkeypatch.setattr(
        interview_routes,
        "generate_interview_question",
        lambda **kwargs: f"Question {kwargs.get('q_num', 1)}",
    )
    monkeypatch.setattr(
        interview_routes,
        "evaluate_answer",
        lambda **kwargs: {"total": 8, "feedback": "Solid answer"},
    )
    monkeypatch.setattr(
        interview_routes,
        "proctor_check",
        lambda question_num, answer, time_taken: {"flagged": False, "flags": []},
    )
    interview_routes.interview_session.clear()
    interview_routes.active_token_sessions.clear()


def test_candidate_app_returns_404_for_all_hr_routes():
    """Any HR route requested through create_candidate_app must return 404."""
    cand_app = create_candidate_app()
    client = cand_app.test_client()

    hr_endpoints = [
        ("GET", "/dashboard"),
        ("GET", "/resumes"),
        ("GET", "/ranking"),
        ("GET", "/scheduling"),
        ("GET", "/interview"),
        ("GET", "/rules"),
        ("GET", "/reports"),
        ("GET", "/settings"),
        ("GET", "/logs"),
        ("POST", "/api/upload"),
        ("POST", "/api/extract-pdf-text"),
        ("POST", "/api/run-nlp"),
        ("POST", "/api/rank"),
        ("POST", "/api/generate-report"),
        ("POST", "/api/generate-interview-links"),
        ("GET", "/api/interviews/list"),
        ("GET", "/api/interview-links"),
        ("GET", "/api/stats"),
        ("POST", "/api/reset-pipeline"),
    ]

    for method, path in hr_endpoints:
        if method == "GET":
            res = client.get(path)
        else:
            res = client.post(path, json={})
        assert res.status_code == 404, f"Expected 404 for {method} {path} on candidate_app, got {res.status_code}"


def test_hr_app_blocks_unauthenticated_requests():
    """Unauthenticated requests to HR app return 302 for pages and 401 for API routes."""
    hr_app = create_app()
    client = hr_app.test_client()

    hr_pages = ["/dashboard", "/interview", "/rules", "/reports", "/settings", "/logs"]
    for page in hr_pages:
        res = client.get(page)
        assert res.status_code == 302, f"Expected 302 redirect for {page}, got {res.status_code}"
        assert "/login" in res.headers.get("Location", "")

    hr_apis = [
        ("POST", "/api/upload"),
        ("POST", "/api/extract-pdf-text"),
        ("POST", "/api/run-nlp"),
        ("POST", "/api/rank"),
        ("POST", "/api/generate-report"),
        ("POST", "/api/generate-interview-links"),
        ("GET", "/api/interviews/list"),
        ("GET", "/api/interview-links"),
        ("GET", "/api/stats"),
    ]
    for method, path in hr_apis:
        if method == "GET":
            res = client.get(path)
        else:
            res = client.post(path, json={})
        assert res.status_code == 401, f"Expected 401 JSON for {method} {path}, got {res.status_code}"
        assert res.is_json
        assert res.get_json().get("code") == 401


def test_candidate_happy_path_with_valid_token(monkeypatch):
    """Candidate can complete an interview flow with a valid, active token."""
    token = "T_VALID_123"
    _setup_interview_stubs(monkeypatch, _sample_token(used=0))

    cand_app = create_candidate_app()
    client = cand_app.test_client()

    # 1. Access portal view
    res = client.get(f"/candidate-interview/{token}")
    assert res.status_code == 200

    # 2. Start interview
    start_res = client.post("/api/candidate/interview/start", json={"token": token, "consent": True})
    assert start_res.status_code == 200
    start_data = start_res.get_json()
    assert start_data["success"] is True
    session_id = start_data["session_id"]
    session_key = start_data["session_key"]

    # 3. Answer questions (plan has 5 questions)
    for q_num in range(1, 6):
        ans_res = client.post(
            "/api/candidate/interview/answer",
            headers={"X-Interview-Session-Key": session_key},
            json={
                "session_id": session_id,
                "answer": f"Answer for question {q_num}",
                "question_num": q_num,
                "time_taken": 25,
            },
        )
        assert ans_res.status_code == 200
        ans_data = ans_res.get_json()
        assert ans_data["success"] is True

    # 4. Finish interview
    finish_res = client.post(
        "/api/candidate/interview/finish",
        headers={"X-Interview-Session-Key": session_key},
        json={"session_id": session_id},
    )
    assert finish_res.status_code == 200
    finish_data = finish_res.get_json()
    assert finish_data["success"] is True
    assert "result" in finish_data


def test_candidate_rejects_missing_and_invalid_tokens(monkeypatch):
    """Missing and invalid tokens are rejected."""
    _setup_interview_stubs(monkeypatch, None)
    cand_app = create_candidate_app()
    client = cand_app.test_client()

    # View rejects invalid token
    res = client.get("/candidate-interview/INVALID_TOKEN")
    assert res.status_code == 403

    # Start rejects invalid token
    res = client.post("/api/candidate/interview/start", json={"token": "INVALID_TOKEN"})
    assert res.status_code == 401

    # Start rejects missing token
    res = client.post("/api/candidate/interview/start", json={})
    assert res.status_code == 401


def test_candidate_rejects_used_tokens(monkeypatch):
    """Used tokens are rejected."""
    used_token = _sample_token(used=1)
    _setup_interview_stubs(monkeypatch, used_token)
    cand_app = create_candidate_app()
    client = cand_app.test_client()

    # View rejects used token
    res = client.get("/candidate-interview/T_USED")
    assert res.status_code == 403

    # Start rejects used token
    res = client.post("/api/candidate/interview/start", json={"token": "T_USED"})
    assert res.status_code == 401
    assert "already been completed" in res.get_json().get("error", "")


def test_candidate_rejects_expired_tokens(monkeypatch):
    """Expired tokens (>72h) are rejected."""
    four_days_ago = (datetime.datetime.now(timezone.utc) - datetime.timedelta(days=4)).isoformat()
    expired_token = _sample_token(used=0, created_at=four_days_ago)
    _setup_interview_stubs(monkeypatch, expired_token)
    cand_app = create_candidate_app()
    client = cand_app.test_client()

    # View rejects expired token
    res = client.get("/candidate-interview/T_EXPIRED")
    assert res.status_code == 403

    # Start rejects expired token
    res = client.post("/api/candidate/interview/start", json={"token": "T_EXPIRED"})
    assert res.status_code == 401
    assert "expired" in res.get_json().get("error", "")
