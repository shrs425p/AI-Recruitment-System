"""
test_interview.py - Automated interview orchestration, role-adaptive blueprints,
configurable question counts and timers, conversational follow-up probing, and voice modes.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from flask.testing import FlaskClient

from src.interview_bot import (
    evaluate_answer,
    generate_adaptive_followup,
    generate_interview_question,
    is_tech_role,
    should_probe_further,
)


class TestRoleAdaptiveBlueprints:
    """Tests technical vs non-technical role detection and domain-specific question planning."""

    def test_is_tech_role_detection(self):
        assert is_tech_role("Senior Backend Developer") is True
        assert is_tech_role("DevOps / Cloud Engineer") is True
        assert is_tech_role("Data Scientist") is True

        assert is_tech_role("Director of Sales") is False
        assert is_tech_role("Head of Brand Marketing") is False
        assert is_tech_role("HR Operations Lead") is False

    def test_technical_role_generates_architecture_and_code_topics(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setattr(
            "src.interview_bot.call_ai",
            lambda *args, **kw: "Explain how you optimize database indexing and connection pooling in PostgreSQL.",
        )
        q = generate_interview_question(
            candidate_name="Tech Candidate",
            job_title="Software Architect",
            topic="Database Architecture",
            q_num=2,
            q_type="TECHNICAL",
        )
        assert isinstance(q, str)
        assert len(q) > 10

    def test_non_technical_role_generates_strategy_topics(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setattr(
            "src.interview_bot.call_ai",
            lambda *args, **kw: "Describe a marketing campaign where CAC exceeded targets and how you pivoted.",
        )
        q = generate_interview_question(
            candidate_name="Marketing Lead",
            job_title="VP of Marketing",
            topic="Campaign ROI & Strategy",
            q_num=2,
            q_type="TECHNICAL",
        )
        assert isinstance(q, str)
        assert len(q) > 10


class TestAdaptiveConversationalProbing:
    """Tests dynamic follow-up generation when initial answers lack technical depth."""

    def test_should_probe_further_triggers_on_vague_answers(self):
        vague_eval = {
            "total": 5,
            "relevance": 3,
            "depth": 1,
            "clarity": 2,
            "correctness": 2,
            "feedback": "Answer touched on basic concepts but lacked implementation depth.",
        }
        vague_ans = "We basically used databases to store information and it worked fine."
        assert should_probe_further(vague_eval, vague_ans) is True

    def test_should_probe_further_skips_when_answer_is_thorough(self):
        thorough_eval = {
            "total": 9,
            "relevance": 3,
            "depth": 3,
            "clarity": 2,
            "correctness": 2,
            "feedback": "Exceptional answer detailing distributed locks, Redis backoff, and idempotency.",
        }
        thorough_ans = "We utilized Redis with exponential backoff and distributed redlock for high concurrency."
        assert should_probe_further(thorough_eval, thorough_ans) is False

    def test_generate_adaptive_followup_creates_drill_down_question(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setattr(
            "src.interview_bot.call_ai",
            lambda prompt, **kw: (
                "You mentioned using Redis for cache invalidation. How do you handle cache stampedes under high concurrency?"
            ),
        )
        followup = generate_adaptive_followup(
            question="How do you handle application caching?",
            answer="We use Redis to store database queries so it runs faster.",
            job_title="Backend Engineer",
            domain="Software Engineering",
        )
        assert "Redis" in followup or len(followup) > 20


class TestEvaluationRubric:
    """Tests scoring answers across relevance, depth, clarity, and correctness dimensions."""

    def test_evaluate_answer_returns_structured_score_and_feedback(self, monkeypatch: pytest.MonkeyPatch):
        mock_eval = {
            "total": 9,
            "relevance": 3,
            "depth": 2,
            "clarity": 2,
            "correctness": 2,
            "feedback": "Clear explanation with good technical grounding.",
            "strong_points": ["Solid concept clarity"],
            "weak_points": ["Could mention edge case handling"],
        }
        monkeypatch.setattr("src.interview_bot.call_ai", lambda *args, **kwargs: json.dumps(mock_eval))

        result = evaluate_answer(
            question="What is a Python generator and how does it manage memory?",
            answer="Generators use yield to produce values on the fly without loading the whole list into memory.",
            job_title="Python Developer",
            domain="Software Engineering",
        )
        assert result["total"] == 9
        assert "feedback" in result
        assert result["relevance"] <= 3
        assert result["depth"] <= 3


class TestInterviewSessionEndpoints:
    """Tests HTTP endpoints for candidate interview initialization and answer submissions."""

    def test_candidate_interview_answer_flow(
        self, candidate_client: FlaskClient, sample_token_payload: dict, monkeypatch: pytest.MonkeyPatch
    ):
        import app.routes.interview as int_mod

        monkeypatch.setattr(int_mod, "get_interview_token", lambda tok: sample_token_payload)
        monkeypatch.setattr("src.interview_bot.call_ai", lambda *args, **kw: "Tell me about your background.")

        # 1. Start session
        start_res = candidate_client.post(
            "/api/candidate/interview/start",
            json={"token": sample_token_payload["token"], "consent": True},
        )
        assert start_res.status_code == 200
        data_start = start_res.get_json()
        session_id = data_start["session_id"]
        session_key = data_start["session_key"]
        assert session_id is not None
        assert session_key is not None

        # 2. Submit answer
        monkeypatch.setattr(
            int_mod,
            "evaluate_answer",
            lambda **kw: {"total": 8, "feedback": "Good answer", "strong_points": [], "weak_points": []},
        )
        ans_res = candidate_client.post(
            "/api/candidate/interview/answer",
            json={
                "session_id": session_id,
                "session_key": session_key,
                "question_num": 1,
                "answer": "Microservices communicate via gRPC and message queues.",
                "time_taken": 45,
            },
            headers={"X-Interview-Session-Key": session_key},
        )
        assert ans_res.status_code == 200
        data = ans_res.get_json()
        assert "evaluation" in data
        assert data["evaluation"]["total"] == 8


class TestInterviewLinkGenerationEndpoints:
    """Tests /api/generate-interview-links and /api/interview-links endpoints."""

    def test_first_time_link_generation_creates_distinct_tokens(
        self, auth_client: FlaskClient, temp_dir: Path, monkeypatch: pytest.MonkeyPatch
    ):
        """First-time generation assigns unique tokens to all candidates without raising errors or cross-assigning."""
        import app.routes.interview as int_mod
        from app.database import get_all_tokens

        scheduling_dir = temp_dir / "scheduling"
        scheduling_dir.mkdir(parents=True, exist_ok=True)
        monkeypatch.setattr(int_mod, "OUTPUT_FOLDER", temp_dir)

        schedule_data = {
            "job_title": "Senior Backend Engineer",
            "schedule": [
                {
                    "candidate_name": "Alice Martin",
                    "email": "alice@example.com",
                    "source_file": "alice_resume.pdf",
                    "status": "CONFIRMED",
                    "rank": 1,
                    "score": 95.0,
                },
                {
                    "candidate_name": "Bob Vance",
                    "email": "bob@example.com",
                    "source_file": "bob_resume.pdf",
                    "status": "CONFIRMED",
                    "rank": 2,
                    "score": 88.0,
                },
            ],
        }
        with open(scheduling_dir / "schedule_20261019_120000.json", "w", encoding="utf-8") as f:
            json.dump(schedule_data, f)

        res = auth_client.post("/api/generate-interview-links")
        assert res.status_code == 200
        data = res.get_json()
        assert data["success"] is True
        links = data["links"]
        assert len(links) == 2

        alice_link = next(lnk for lnk in links if lnk["candidate_name"] == "Alice Martin")
        bob_link = next(lnk for lnk in links if lnk["candidate_name"] == "Bob Vance")

        # Distinct unique tokens
        assert alice_link["url"] != bob_link["url"]
        assert "candidate-interview/T_" in alice_link["url"]
        assert "candidate-interview/T_" in bob_link["url"]
        assert alice_link["used"] == 0
        assert bob_link["used"] == 0

        # Verify in DB
        db_tokens = get_all_tokens()
        assert len(db_tokens) == 2
        names_in_db = {t["candidate_name"] for t in db_tokens}
        assert names_in_db == {"Alice Martin", "Bob Vance"}

    def test_repeated_link_generation_reuses_existing_tokens_without_duplication(
        self, auth_client: FlaskClient, temp_dir: Path, monkeypatch: pytest.MonkeyPatch
    ):
        """Subsequent calls reuse existing tokens without creating redundant active tokens in DB."""
        import app.routes.interview as int_mod
        from app.database import get_all_tokens

        scheduling_dir = temp_dir / "scheduling"
        scheduling_dir.mkdir(parents=True, exist_ok=True)
        monkeypatch.setattr(int_mod, "OUTPUT_FOLDER", temp_dir)

        schedule_data = {
            "job_title": "Data Engineer",
            "schedule": [
                {
                    "candidate_name": "Charlie Day",
                    "email": "charlie@example.com",
                    "source_file": "charlie_resume.pdf",
                    "status": "CONFIRMED",
                    "rank": 1,
                    "score": 90.0,
                }
            ],
        }
        with open(scheduling_dir / "schedule_20261019_120000.json", "w", encoding="utf-8") as f:
            json.dump(schedule_data, f)

        # Call 1
        res1 = auth_client.post("/api/generate-interview-links")
        assert res1.status_code == 200
        data1 = res1.get_json()
        token1_url = data1["links"][0]["url"]

        # Call 2
        res2 = auth_client.post("/api/generate-interview-links")
        assert res2.status_code == 200
        data2 = res2.get_json()
        token2_url = data2["links"][0]["url"]

        # Reuses the exact same URL/token
        assert token1_url == token2_url

        # Database contains exactly 1 token record, not 2
        db_tokens = get_all_tokens()
        assert len(db_tokens) == 1
        assert db_tokens[0]["candidate_name"] == "Charlie Day"

    def test_generate_interview_links_missing_schedule_returns_404(
        self, auth_client: FlaskClient, temp_dir: Path, monkeypatch: pytest.MonkeyPatch
    ):
        """Missing scheduling files returns 404 error."""
        import app.routes.interview as int_mod

        scheduling_dir = temp_dir / "scheduling"
        scheduling_dir.mkdir(parents=True, exist_ok=True)
        monkeypatch.setattr(int_mod, "OUTPUT_FOLDER", temp_dir)

        res = auth_client.post("/api/generate-interview-links")
        assert res.status_code == 404
        data = res.get_json()
        assert "error" in data

    def test_api_interview_links_get_returns_stored_tokens(
        self, auth_client: FlaskClient
    ):
        """GET /api/interview-links lists all tokens and their statuses."""
        from app.database import create_interview_token

        create_interview_token(
            token="T_TEST_GET_TOKEN_1",
            candidate_name="Diana Prince",
            source_file="diana.pdf",
            job_title="Security Lead",
            rank=1,
            score=98.0,
        )

        res = auth_client.get("/api/interview-links")
        assert res.status_code == 200
        data = res.get_json()
        assert data["success"] is True
        links = data["links"]
        assert any(lnk["candidate_name"] == "Diana Prince" and "T_TEST_GET_TOKEN_1" in lnk["url"] for lnk in links)

    def test_interview_token_entropy_and_uniqueness(self):
        """Tokens must have high cryptographic entropy (256 bits) and be non-predictable."""
        from app.database import generate_interview_token

        tokens = [generate_interview_token() for _ in range(100)]
        assert len(set(tokens)) == 100

        for tok in tokens:
            assert tok.startswith("T_")
            assert len(tok) == 66  # "T_" + 64 hex chars (256 bits of entropy)
            parts = tok.split("_")
            assert len(parts) == 2, "Token should be T_<high_entropy_hex>"
            int(parts[1], 16)

    def test_create_interview_token_auto_generates_token_when_none(self):
        """create_interview_token auto-generates high-entropy token when none is specified."""
        from app.database import create_interview_token, get_interview_token

        tok = create_interview_token(candidate_name="Auto Candidate", source_file="auto.pdf", job_title="Engineer")
        assert tok.startswith("T_")
        assert len(tok) == 66

        stored = get_interview_token(tok)
        assert stored is not None
        assert stored["candidate_name"] == "Auto Candidate"

    def test_candidate_interview_validation_page_rate_limiting(self, candidate_client: FlaskClient):
        """Validation page /candidate-interview/<token> throttles requests and rejects excessive attempts with HTTP 429."""
        from app.database import create_interview_token
        from app.routes.interview import rate_limiter

        with rate_limiter.lock:
            rate_limiter.requests.clear()

        valid_tok = create_interview_token(
            candidate_name="Rate Limited Candidate", source_file="rl.pdf", job_title="DevOps"
        )

        res_ok = candidate_client.get(f"/candidate-interview/{valid_tok}")
        assert res_ok.status_code == 200

        for _ in range(29):
            candidate_client.get("/candidate-interview/invalid_probe_token")

        res_throttled = candidate_client.get(f"/candidate-interview/{valid_tok}")
        assert res_throttled.status_code == 429

        with rate_limiter.lock:
            rate_limiter.requests.clear()

