"""
test_ranking.py - test suite for candidate ranking, multi-dimensional scoring,
customizable rubric weights, knockout disqualification rules, and CSV/Excel exports.
"""

from __future__ import annotations

import csv
import io
import json
from pathlib import Path

import pytest
from flask.testing import FlaskClient

from src.ranking_engine import (
    DEFAULT_WEIGHTS,
    check_knockout_rules,
    normalize_weights,
    score_candidate,
)


class TestRankingWeightsAndPresets:
    """Tests weight normalization, custom rubrics, and role-based presets."""

    def test_normalize_weights_default(self):
        w = normalize_weights(None)
        assert w == DEFAULT_WEIGHTS
        assert sum(w.values()) == 100

        w_empty = normalize_weights({})
        assert w_empty == DEFAULT_WEIGHTS
        assert sum(w_empty.values()) == 100

    def test_normalize_weights_custom_balanced(self):
        custom = {
            "domain_match": 15,
            "skills_match": 45,
            "experience_years": 25,
            "education": 10,
            "certifications": 5,
        }
        w = normalize_weights(custom)
        assert sum(w.values()) == 100
        assert w["skills_match"] == 45
        assert w["experience_years"] == 25

    def test_normalize_weights_auto_balances_when_sum_not_100(self):
        unbalanced = {
            "domain_match": 20,
            "skills_match": 20,
            "experience_years": 20,
            "education": 10,
            "certifications": 10,
        }  # Sum = 80
        balanced = normalize_weights(unbalanced)
        assert sum(balanced.values()) == 100


class TestKnockoutDisqualificationRules:
    """Tests strict automated candidate knockout rules before qualitative evaluation."""

    def test_knockout_minimum_experience_filter(self):
        cand_junior = {"total_experience_years": 1.5, "skills": ["Python", "Flask"]}
        cand_senior = {"total_experience_years": 6.0, "skills": ["Python", "Flask"]}
        ko_rules = {"min_experience_years": 3.0}

        ko_junior, reason_junior = check_knockout_rules(cand_junior, ko_rules)
        ko_senior, reason_senior = check_knockout_rules(cand_senior, ko_rules)

        assert ko_junior is True
        assert "experience" in reason_junior.lower()

        assert ko_senior is False
        assert reason_senior is None or reason_senior == ""

    def test_knockout_mandatory_required_skills(self):
        cand_with_skill = {"skills": ["Python", "Docker", "AWS", "PostgreSQL"]}
        cand_missing_skill = {"skills": ["Python", "JavaScript"]}
        ko_rules = {"required_skills": ["Docker", "AWS"]}

        ko_valid, _ = check_knockout_rules(cand_with_skill, ko_rules)
        ko_invalid, reason = check_knockout_rules(cand_missing_skill, ko_rules)

        assert ko_valid is False
        assert ko_invalid is True
        assert "Docker" in reason or "AWS" in reason or "missing" in reason.lower()

    def test_canonical_skill_matching_avoids_substring_false_positives(self):
        """ARS-001: Verifies that skills are matched exactly, not as substrings."""
        # Django contains "go", C++ contains "c". Previously, this would incorrectly pass.
        candidate = {"skills": ["Django", "C++"]}

        # Test 1: Require 'Go', candidate has 'Django' -> Should fail
        ko_rules_go = {"required_skills": ["Go"]}
        ko_go, reason_go = check_knockout_rules(candidate, ko_rules_go)
        assert ko_go is True
        assert "Go" in reason_go

        # Test 2: Require 'C', candidate has 'C++' -> Should fail
        ko_rules_c = {"required_skills": ["C"]}
        ko_c, reason_c = check_knockout_rules(candidate, ko_rules_c)
        assert ko_c is True
        assert "C" in reason_c

    def test_canonical_skill_matching_uses_alias_map(self):
        """ARS-001: Verifies that alias mappings (e.g., js -> javascript) work correctly."""
        candidate = {"skills": ["JS"]}
        ko_rules = {"required_skills": ["JavaScript"]}
        ko_valid, reason = check_knockout_rules(candidate, ko_rules)
        assert ko_valid is False
        assert reason is None or reason == ""

    def test_empty_knockout_rules_pass_all_candidates(self):
        candidate = {"total_experience_years": 0.5, "skills": []}
        ko, reason = check_knockout_rules(candidate, {})
        assert ko is False
        assert reason is None or reason == ""


class TestCandidateScoringEngine:
    """Tests composite score calculations, skills matching ratios, and confidence tiering."""

    def test_scoring_candidate_with_high_fit(self, monkeypatch: pytest.MonkeyPatch):
        mock_ai_response = {
            "candidate_name": "Alice Candidate",
            "scores": {
                "domain_match": {"score": 20, "max": 20, "reason": "Exact domain match"},
                "skills_match": {"score": 35, "max": 35, "reason": "All required skills present"},
                "experience_years": {"score": 20, "max": 20, "reason": "5+ years experience"},
                "education": {"score": 9, "max": 15, "reason": "BS Computer Science"},
                "certifications": {"score": 0, "max": 10, "reason": "None"},
            },
            "total_score": 84,
            "percentage": 84.0,
            "overall_verdict": "Strong match",
            "strengths": ["Python", "FastAPI"],
            "gaps": [],
            "hire_recommendation": "Strongly Recommend",
        }
        monkeypatch.setattr("src.ranking_engine.call_ai", lambda prompt: mock_ai_response)

        jd_data = {
            "required_skills": ["Python", "FastAPI", "Docker", "SQL"],
            "preferred_skills": ["Kubernetes", "AWS"],
            "min_experience_years": 3.0,
            "domain": "Backend Engineering",
        }
        cand_data = {
            "skills": ["Python", "FastAPI", "Docker", "SQL", "Kubernetes", "AWS"],
            "total_experience_years": 5.0,
            "domain": "Backend Engineering",
            "education": [{"degree": "Bachelor of Science in Computer Science"}],
        }

        result = score_candidate(cand_data, jd_data, weights=DEFAULT_WEIGHTS)
        assert result is not None
        assert result["total_score"] >= 80.0
        assert "Strongly" in result["hire_recommendation"] or "Recommend" in result["hire_recommendation"]

    def test_scoring_candidate_with_low_fit(self, monkeypatch: pytest.MonkeyPatch):
        mock_ai_response = {
            "candidate_name": "Bob Candidate",
            "scores": {
                "domain_match": {"score": 0, "max": 20, "reason": "Different domain"},
                "skills_match": {"score": 7, "max": 35, "reason": "Minimal skill overlap"},
                "experience_years": {"score": 14, "max": 20, "reason": "1 year experience"},
                "education": {"score": 0, "max": 15, "reason": "None"},
                "certifications": {"score": 0, "max": 10, "reason": "None"},
            },
            "total_score": 21,
            "percentage": 21.0,
            "overall_verdict": "Weak match",
            "strengths": [],
            "gaps": ["Missing core skills"],
            "hire_recommendation": "Do Not Recommend",
        }
        monkeypatch.setattr("src.ranking_engine.call_ai", lambda prompt: mock_ai_response)

        jd_data = {
            "required_skills": ["Go", "Kubernetes", "gRPC", "Rust"],
            "min_experience_years": 5.0,
            "domain": "Systems Engineering",
        }
        cand_data = {
            "skills": ["PHP", "WordPress", "HTML"],
            "total_experience_years": 1.0,
            "domain": "Web Design",
            "education": [],
        }

        result = score_candidate(cand_data, jd_data, weights=DEFAULT_WEIGHTS)
        assert result is not None
        assert result["total_score"] < 50.0
        assert "Not" in result["hire_recommendation"] or "Consider" in result["hire_recommendation"]


class TestCsvExportEndpoints:
    """Verifies candidate spreadsheet export for ATS integration and executive sharing."""

    def test_csv_export_requires_hr_auth(self, client: FlaskClient):
        response = client.get("/api/ranking/export/csv")
        assert response.status_code in (401, 302, 403)

    def test_csv_export_returns_valid_spreadsheet_format(
        self, auth_client: FlaskClient, temp_dir: Path, monkeypatch: pytest.MonkeyPatch
    ):
        import app.routes.ranking as rank_mod

        ranking_dir = temp_dir / "ranking"
        ranking_dir.mkdir(parents=True, exist_ok=True)
        ranking_file = ranking_dir / "ranking_scores_test.json"
        mock_payload = {
            "job_description": {"job_title": "Senior Python Engineer"},
            "ranked_candidates": [
                {
                    "candidate_name": "Jane Doe",
                    "email": "jane@example.com",
                    "total_score": 94.5,
                    "skills_score": 96.0,
                    "experience_score": 90.0,
                    "strengths": ["Python", "Distributed Systems"],
                    "hire_recommendation": "Strongly Recommend",
                },
                {
                    "candidate_name": "John Smith",
                    "email": "john@example.com",
                    "total_score": 82.0,
                    "skills_score": 80.0,
                    "experience_score": 85.0,
                    "strengths": ["Docker"],
                    "hire_recommendation": "Recommend",
                },
            ],
        }
        ranking_file.write_text(json.dumps(mock_payload), encoding="utf-8")
        monkeypatch.setattr(rank_mod, "OUTPUT_FOLDER", temp_dir)

        response = auth_client.get("/api/ranking/export/csv")
        assert response.status_code == 200
        assert "text/csv" in response.content_type
        assert "attachment" in response.headers.get("Content-Disposition", "")

        csv_reader = csv.reader(io.StringIO(response.data.decode("utf-8")))
        rows = list(csv_reader)
        assert len(rows) >= 2  # Header + at least 1 data row
        header = rows[0]
        assert "Rank" in header
        assert "Name" in header
        assert "Total Score" in header
        assert "Hire Recommendation" in header
