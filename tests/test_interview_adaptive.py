import time
from unittest.mock import patch

from flask import Flask

from app.database import create_interview_token, init_db, save_interview_session
from app.routes.interview import (
    get_interview_plan_for_role,
    interview_session,
    register_interview_routes,
)
from src.interview_bot import (
    generate_adaptive_followup,
    generate_interview_question,
    is_tech_role,
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


def test_is_tech_role_detection():
    # Technical roles
    assert is_tech_role("Senior Python Developer", "IT") is True
    assert is_tech_role("Backend Engineer", "Software") is True
    assert is_tech_role("DevOps Architect", "Cloud") is True
    assert is_tech_role("Data Scientist", "Analytics") is True
    assert is_tech_role("Full Stack Engineer", "") is True

    # Non-technical professional roles
    assert is_tech_role("Registered Nurse", "Healthcare") is False
    assert is_tech_role("Marketing Manager", "Digital Marketing") is False
    assert is_tech_role("Human Resources Director", "HR") is False
    assert is_tech_role("Financial Analyst", "Finance & Banking") is False
    assert is_tech_role("Graphic Designer", "Creative Arts") is False
    assert is_tech_role("Legal Counsel", "Corporate Law") is False


def test_interview_plan_for_roles():
    tech_plan = get_interview_plan_for_role("Software Engineer", "IT")
    assert len(tech_plan) == 5
    assert tech_plan[0][0] == "TECHNICAL"
    assert tech_plan[2] == ("TECHNICAL", "System Design")

    non_tech_plan = get_interview_plan_for_role("Marketing Director", "Marketing")
    assert len(non_tech_plan) == 5
    assert non_tech_plan[0][0] == "DOMAIN EXPERTISE"
    assert non_tech_plan[0][1] == "Introduction"
    assert non_tech_plan[2] == ("DOMAIN EXPERTISE", "Strategy & Execution")
    # Verify System Design is not present
    assert not any("System Design" in topic for _, topic in non_tech_plan)


def test_generate_interview_question_non_tech():
    with patch("src.common.call_ollama", side_effect=Exception("No LLM")):
        q = generate_interview_question(
            candidate_name="Sarah Jenkins",
            job_title="Registered Nurse",
            topic="Strategy & Execution",
            q_num=3,
            q_type="DOMAIN EXPERTISE",
            transcript="",
            skills=["Patient Triage", "ICU Care"],
            domain="Healthcare",
        )
        assert "?" in q
        assert "Registered Nurse" in q
        assert "Strategy & Execution" in q
        # Ensure it does not refer to technical challenge
        assert "technical" not in q.lower()
        assert "key professional challenge" in q.lower()


def test_non_technical_candidate_interview_flow(tmp_path, monkeypatch):
    test_db = tmp_path / "test_non_tech.db"
    monkeypatch.setattr("app.database.DB_PATH", test_db)
    init_db()

    app = Flask(__name__)
    app.config["SECRET_KEY"] = "test_secret_non_tech"
    register_interview_routes(app)
    client = app.test_client()

    token = create_interview_token("Elena Gomez", "elena_resume", "HR Specialist", 88)

    # Start non-technical interview
    with patch("app.routes.interview.generate_interview_question", return_value="Welcome Elena, tell us about your HR background."):
        res = client.post(
            "/api/candidate/interview/start",
            json={"token": token, "consent": True},
        )
        assert res.status_code == 200
        data = res.get_json()
        assert data["success"] is True
        first_q = data["questions"][0]
        assert first_q["type"] == "DOMAIN EXPERTISE"
        assert first_q["topic"] == "Introduction"
        sid = data["session_id"]
        skey = data["session_key"]

    headers = {"X-Interview-Session-Key": skey}

    # Submit answer to Q1
    eval_q1 = {"depth": 3, "clarity": 2, "relevance": 2, "correctness": 2, "total": 9, "feedback": "Great overview."}
    with patch("app.routes.interview.evaluate_answer", return_value=eval_q1), \
         patch("app.routes.interview.generate_interview_question", return_value="Describe a difficult employee relations scenario."):
        res2 = client.post(
            "/api/candidate/interview/answer",
            headers=headers,
            json={"session_id": sid, "question_num": 1, "answer": "I have 5 years managing employee relations and conflict resolution."},
        )
        assert res2.status_code == 200
        data2 = res2.get_json()
        assert data2["next_question"]["type"] == "DOMAIN EXPERTISE"
        assert data2["next_question"]["topic"] == "Problem Solving & Scenarios"

