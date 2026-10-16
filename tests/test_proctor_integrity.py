import time

import app.routes.interview as interview_routes
from app import create_app
from app.database import init_db


def _mock_env(monkeypatch, tmp_path):
    test_db = tmp_path / "test_proctor.db"
    monkeypatch.setattr("app.database.DB_PATH", test_db)
    init_db()

    interview_routes.interview_session.clear()
    interview_routes.active_token_sessions.clear()

    token_data = {
        "used": 0,
        "candidate_name": "Proctor Candidate",
        "source_file": "cand.pdf",
        "job_title": "Python Developer",
        "score": 90,
        "rank": 1,
    }
    monkeypatch.setattr(interview_routes, "get_interview_token", lambda token: token_data)
    monkeypatch.setattr(interview_routes, "start_proctoring_session", lambda session_id: None)
    monkeypatch.setattr(interview_routes, "stop_proctoring", lambda session_id: {"events": []})
    monkeypatch.setattr(
        interview_routes,
        "generate_interview_question",
        lambda **kwargs: f"Interview Question {kwargs['q_num']}",
    )
    monkeypatch.setattr(
        interview_routes,
        "evaluate_answer",
        lambda **kwargs: {"total": 8, "feedback": "Good", "strong_points": [], "weak_points": []},
    )

    app = create_app()
    return app.test_client()


def test_server_calculates_actual_response_time_not_client_forged(monkeypatch, tmp_path):
    client = _mock_env(monkeypatch, tmp_path)

    # Start interview
    started = client.post("/api/candidate/interview/start", json={"token": "PROCTOR_TOK_1", "consent": True})
    assert started.status_code == 200
    sess_id = started.get_json()["session_id"]
    sess_key = started.get_json()["session_key"]

    # Candidate attempts to forge time_taken: 60 in JSON, but actually submits immediately
    resp = client.post(
        "/api/candidate/interview/answer",
        json={
            "session_id": sess_id,
            "session_key": sess_key,
            "question_num": 1,
            "time_taken": 60,  # Forged client time
            "answer": "This is a pre-copied text from another tab or chat application.",
        },
        headers={"X-Interview-Session-Key": sess_key},
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["success"] is True

    # Server should detect instant paste flag (<2.0s for >5 words)
    flags = data["proctor"]["flags"]
    assert "INSTANT_PASTE_DETECTED" in flags
    # Server-verified time should be under 2s regardless of the forged 60s
    assert data["proctor"]["server_verified_time"] < 2.0


def test_prolonged_response_delay_flag(monkeypatch, tmp_path):
    client = _mock_env(monkeypatch, tmp_path)

    started = client.post("/api/candidate/interview/start", json={"token": "PROCTOR_TOK_2", "consent": True})
    sess_id = started.get_json()["session_id"]
    sess_key = started.get_json()["session_key"]

    # Artificially age the question_issued_at timestamp in the session by 350 seconds
    interview_routes.interview_session[sess_id]["question_issued_at"] = time.time() - 350.0

    resp = client.post(
        "/api/candidate/interview/answer",
        json={
            "session_id": sess_id,
            "session_key": sess_key,
            "question_num": 1,
            "time_taken": 30,  # Client attempts to report normal 30s
            "answer": "Finally answering after prolonged delay.",
        },
        headers={"X-Interview-Session-Key": sess_key},
    )
    assert resp.status_code == 200
    data = resp.get_json()
    flags = data["proctor"]["flags"]
    assert "PROLONGED_RESPONSE_DELAY" in flags or "TIME_LIMIT_EXCEEDED" in flags


def test_reasonable_response_interval_no_timing_flags(monkeypatch, tmp_path):
    client = _mock_env(monkeypatch, tmp_path)

    started = client.post("/api/candidate/interview/start", json={"token": "PROCTOR_TOK_3", "consent": True})
    sess_id = started.get_json()["session_id"]
    sess_key = started.get_json()["session_key"]

    # Artificially set question_issued_at to 25 seconds ago
    interview_routes.interview_session[sess_id]["question_issued_at"] = time.time() - 25.0

    resp = client.post(
        "/api/candidate/interview/answer",
        json={
            "session_id": sess_id,
            "session_key": sess_key,
            "question_num": 1,
            "time_taken": 25,
            "answer": "A well-thought-out answer explaining my background in Python development and software engineering.",
        },
        headers={"X-Interview-Session-Key": sess_key},
    )
    assert resp.status_code == 200
    data = resp.get_json()
    flags = data["proctor"]["flags"]
    assert "INSTANT_PASTE_DETECTED" not in flags
    assert "PROLONGED_RESPONSE_DELAY" not in flags
    assert "SUSPICIOUSLY_FAST_ANSWER" not in flags
