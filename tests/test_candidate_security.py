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

    app = create_app()
    interview_routes.register_interview_routes(app)
    return app


def test_candidate_answer_requires_session_key(monkeypatch):
    client = _app(monkeypatch).test_client()

    started = client.post("/api/candidate/interview/start", json={"token": "T_123"})
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

    started = client.post("/api/candidate/interview/start", json={"token": "T_123"})
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
        json={"token": "T_123"},
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
