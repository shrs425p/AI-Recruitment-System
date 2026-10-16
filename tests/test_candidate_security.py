import app.routes.interview as interview_routes
from app import create_app


def _token_data():
    return {
        "used": 0,
        "candidate_name": "Candidate One",
        "source_file": "candidate_one.pdf",
        "job_title": "Engineer",
        "score": 81,
        "rank": 1,
    }


def _app(monkeypatch):
    monkeypatch.setattr(interview_routes, "get_interview_token", lambda token: _token_data())
    monkeypatch.setattr(interview_routes, "start_proctoring_session", lambda session_id: None)
    monkeypatch.setattr(interview_routes, "stop_proctoring", lambda session_id: {"events": []})
    monkeypatch.setattr(
        interview_routes,
        "generate_interview_question",
        lambda **kwargs: f"Question {kwargs['q_num']}",
    )
    monkeypatch.setattr(
        interview_routes,
        "evaluate_answer",
        lambda **kwargs: {"total": 7, "feedback": "Good", "strong_points": [], "weak_points": []},
    )
    monkeypatch.setattr(
        interview_routes,
        "proctor_check",
        lambda question_num, answer, time_taken: {"flagged": False, "flags": []},
    )
    interview_routes.interview_session.clear()
    interview_routes.active_token_sessions.clear()
    try:
        from app.database import db_session
        with db_session() as conn:
            conn.execute("DELETE FROM interview_sessions")
    except Exception:
        pass

    # create_app() already registers all blueprints/routes including interview.
    # Do NOT call register_interview_routes again — it would duplicate endpoints.
    app = create_app()
    return app



def test_candidate_answer_requires_session_key(monkeypatch):
    client = _app(monkeypatch).test_client()

    started = client.post("/api/candidate/interview/start", json={"token": "T_123", "consent": True})
    session_id = started.get_json()["session_id"]

    response = client.post(
        "/api/candidate/interview/answer",
        json={
            "session_id": session_id,
            "question": "Question 1",
            "answer": "Answer",
            "question_num": 1,
        },
    )

    assert response.status_code == 403


def test_candidate_answer_accepts_matching_session_key(monkeypatch):
    client = _app(monkeypatch).test_client()

    started = client.post("/api/candidate/interview/start", json={"token": "T_123", "consent": True})
    data = started.get_json()

    response = client.post(
        "/api/candidate/interview/answer",
        headers={"X-Interview-Session-Key": data["session_key"]},
        json={
            "session_id": data["session_id"],
            "question": "Question 1",
            "answer": "A real answer",
            "question_num": 1,
        },
    )

    assert response.status_code == 200
    assert response.get_json()["evaluation"]["total"] == 7


def test_candidate_session_is_bound_to_remote_client(monkeypatch):
    client = _app(monkeypatch).test_client()

    started = client.post(
        "/api/candidate/interview/start",
        json={"token": "T_123", "consent": True},
        environ_base={"REMOTE_ADDR": "192.168.1.20"},
    )
    data = started.get_json()

    response = client.post(
        "/api/candidate/interview/answer",
        headers={"X-Interview-Session-Key": data["session_key"]},
        json={
            "session_id": data["session_id"],
            "question": "Question 1",
            "answer": "A real answer",
            "question_num": 1,
        },
        environ_base={"REMOTE_ADDR": "192.168.1.99"},
    )

    assert response.status_code == 403


def test_candidate_answer_uses_server_issued_question(monkeypatch):
    recorded = {}

    app = _app(monkeypatch)
    monkeypatch.setattr(
        interview_routes,
        "evaluate_answer",
        lambda **kwargs: recorded.update(kwargs) or {"total": 7, "feedback": "Good"},
    )
    client = app.test_client()
    started = client.post("/api/candidate/interview/start", json={"token": "T_123", "consent": True}).get_json()

    response = client.post(
        "/api/candidate/interview/answer",
        headers={"X-Interview-Session-Key": started["session_key"]},
        json={
            "session_id": started["session_id"],
            "question": "Attacker controlled question",
            "topic": "Attacker controlled topic",
            "type": "BEHAVIORAL",
            "answer": "A real answer",
            "question_num": 1,
        },
    )

    assert response.status_code == 200
    assert recorded["question"] == "Question 1"
    assert recorded["domain"] == "Introduction"


def test_session_cookie_flags_for_hr_and_candidate_apps():
    from app import create_app, create_candidate_app
    hr_app = create_app()
    cand_app = create_candidate_app()

    assert hr_app.config["SESSION_COOKIE_HTTPONLY"] is True
    assert hr_app.config["SESSION_COOKIE_SECURE"] is False
    assert hr_app.config["SESSION_COOKIE_SAMESITE"] == "Lax"

    assert cand_app.config["SESSION_COOKIE_HTTPONLY"] is True
    assert cand_app.config["SESSION_COOKIE_SECURE"] is True
    assert cand_app.config["SESSION_COOKIE_SAMESITE"] == "Lax"

