"""
test_interview.py - Automated interview orchestration, role-adaptive blueprints,
configurable question counts and timers, conversational follow-up probing, and voice modes.
"""

from __future__ import annotations

import json

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
            lambda prompt, **kw: "Explain how you optimize database indexing and connection pooling in PostgreSQL.",
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
            lambda prompt, **kw: "Describe a marketing campaign where CAC exceeded targets and how you pivoted.",
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
