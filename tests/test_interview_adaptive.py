import time
from unittest.mock import patch

from flask import Flask

from app.database import create_interview_token, init_db, save_interview_session
from app.routes.interview import interview_session, register_interview_routes
from src.interview_bot import (
    generate_adaptive_followup,
    should_probe_further,
)


def test_should_probe_further_skips_and_blanks():
    # Blanks and skips should never be probed
    assert not should_probe_further({"depth": 0, "total": 0}, "")
    assert not should_probe_further({"depth": 0, "total": 0}, "   ")
    assert not should_probe_further({"depth": 0, "total": 0}, "skip")
    assert not should_probe_further({"depth": 0, "total": 0}, "pass")
    assert not should_probe_further({"depth": 0, "total": 0}, "i don't know")
    assert not should_probe_further({"depth": 0, "total": 0}, "na")


def test_should_probe_further_triggers_on_low_depth():
    # Shallow answers with words should trigger probing
    shallow_eval = {"depth": 1, "clarity": 2, "relevance": 2, "correctness": 1, "total": 6}
    assert should_probe_further(shallow_eval, "I used Redis to cache data for our web application.")

    # High depth answers should not trigger probing
    deep_eval = {"depth": 3, "clarity": 2, "relevance": 2, "correctness": 2, "total": 9}
    assert not should_probe_further(deep_eval, "I implemented Redis with write-through caching and exponential backoff on cluster retry.")


def test_generate_adaptive_followup_fallback():
    with patch("src.interview_bot.call_ai", side_effect=Exception("API down")):
        probe = generate_adaptive_followup(
            question="Tell me about your caching strategy.",
            answer="I used Redis.",
            job_title="Backend Engineer",
            domain="Backend Development",
        )
        assert "?" in probe
        assert "Backend Development" in probe or "trade-offs" in probe


def test_interview_adaptive_followup_turn(tmp_path, monkeypatch):
    test_db = tmp_path / "test_adaptive.db"
    monkeypatch.setattr("app.database.DB_PATH", test_db)
    init_db()

    app = Flask(__name__)
    app.config["SECRET_KEY"] = "test_secret"
    register_interview_routes(app)
    client = app.test_client()

    # Create token and session
    token = create_interview_token("Alice Doe", "alice_resume", "Senior Engineer", 85)
    session_id = "S_ADAPTIVE_TEST"
    session_key = "SEC_KEY_ADAPTIVE"
    now = time.time()

    sess_data = {
        "session_id": session_id,
        "token": token,
        "session_key": session_key,
        "remote_addr": "127.0.0.1",
        "user_agent": "TestAgent",
        "candidate_name": "Alice Doe",
        "source_file": "alice_resume",
        "job_title": "Senior Engineer",
        "domain": "Software Engineering",
        "skills": ["Python", "Redis"],
        "responses": [],
        "started_at": now,
        "question_issued_at": now - 10,
        "pending_question": "How do you handle distributed caching?",
        "pending_topic": "System Design",
        "pending_q_type": "TECHNICAL",
        "webcam_log": [],
        "browser_log": [],
    }
    interview_session[session_id] = sess_data
    save_interview_session(session_id, sess_data)

    headers = {
        "X-Interview-Session-Key": session_key,
        "User-Agent": "TestAgent",
    }

    # Step 1: Candidate gives a shallow response that triggers adaptive follow-up
    shallow_eval = {
        "depth": 1, "clarity": 1, "relevance": 2, "correctness": 1, "total": 5,
        "feedback": "Lacks specific implementation details."
    }
    with patch("app.routes.interview.evaluate_answer", return_value=shallow_eval), \
         patch("app.routes.interview.generate_adaptive_followup", return_value="You mentioned Redis; how did you handle cache invalidation during write spikes?"):
        res1 = client.post(
            "/api/candidate/interview/answer",
            headers=headers,
            json={
                "session_id": session_id,
                "question_num": 1,
                "answer": "We used Redis for caching data in our application.",
            },
        )
        assert res1.status_code == 200
        data1 = res1.get_json()
        assert data1["is_followup"] is True
        assert "cache invalidation" in data1["followup_question"]
        assert len(sess_data["responses"]) == 0  # Not committed yet!

    # Step 2: Candidate submits their elaboration to the follow-up probe
    deep_eval = {
        "depth": 3, "clarity": 2, "relevance": 2, "correctness": 2, "total": 9,
        "feedback": "Solid architectural explanation of cache invalidation."
    }
    with patch("app.routes.interview.evaluate_answer", return_value=deep_eval), \
         patch("app.routes.interview.generate_interview_question", return_value="Next question on algorithms."):
        res2 = client.post(
            "/api/candidate/interview/answer",
            headers=headers,
            json={
                "session_id": session_id,
                "question_num": 1,  # Answering follow-up for Q1
                "answer": "We handled invalidation using a write-through cache pattern with TTL expiry and Redis pub/sub to purge stale entries.",
            },
        )
        assert res2.status_code == 200
        data2 = res2.get_json()
        assert data2.get("is_followup") is False
        assert data2.get("done") is False
        assert data2.get("q_num") == 2

        # Check recorded response
        assert len(sess_data["responses"]) == 1
        recorded = sess_data["responses"][0]
        assert recorded["was_probed"] is True
        assert "[Candidate Follow-Up Elaboration]" in recorded["answer"]
        assert recorded["score"] == 9
