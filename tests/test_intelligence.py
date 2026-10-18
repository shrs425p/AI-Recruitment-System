"""Tests for talent intelligence analytics engines, vector indexing, and candidate comparison.

Verifies skill supply/demand analytics, 4-quadrant experience matrix, question difficulty filter,
proctoring risk distribution, hiring velocity tracking, demographic mix, semantic talent search,
and empty-state resilience.
"""

import json
from unittest.mock import patch

from app.database import get_all_candidate_embeddings
from src.common import data_path
from src.talent_intelligence import (
    compare_candidates_matrix,
    compute_education_domain_mix,
    compute_experience_score_matrix,
    compute_hiring_velocity_metrics,
    compute_interview_difficulty_breakdown,
    compute_proctoring_risk_breakdown,
    compute_skill_gap_analytics,
    compute_talent_intelligence_analytics,
    generate_candidate_feedback_letter,
    index_talent_pool,
    semantic_search_talent,
)


def _seed_sample_candidates(nlp_dir, txt_dir):
    sample_c1 = {
        "personal_info": {"name": "Olivia Cox", "email": "olivia.cox@example.com"},
        "domain": "Software Engineering",
        "skills": {
            "technical_skills": ["Python", "FastAPI", "PostgreSQL", "Kubernetes", "Docker", "Java"],
            "soft_skills": ["Team Leadership", "Communication"],
        },
        "candidate_strength_summary": "Backend developer with Kubernetes cluster tuning and Postgres expertise.",
        "work_experience": [
            {
                "role": "Senior Software Engineer",
                "company": "TechCorp",
                "responsibilities": ["Kubernetes cluster troubleshooting and high-scale Postgres tuning."],
            }
        ],
        "projects": [
            {
                "name": "Data Engine",
                "description": "High performance ingestion engine",
                "technologies": ["Python", "PostgreSQL"],
            }
        ],
    }
    sample_c2 = {
        "personal_info": {"name": "Ava Lopez", "email": "ava.lopez@example.com"},
        "domain": "Cloud DevOps",
        "skills": {
            "technical_skills": ["AWS", "Terraform", "CI/CD", "Linux"],
            "soft_skills": ["Problem Solving"],
        },
        "candidate_strength_summary": "Cloud infrastructure engineer with extensive AWS and DevOps automation experience.",
        "work_experience": [
            {
                "role": "DevOps Engineer",
                "company": "CloudInc",
                "responsibilities": ["Automated CI/CD pipelines and AWS cloud architecture."],
            }
        ],
        "projects": [
            {"name": "Infra as Code", "description": "Terraform AWS provisioning", "technologies": ["AWS", "Terraform"]}
        ],
    }

    (nlp_dir / "resume_001_nlp.json").write_text(json.dumps(sample_c1), encoding="utf-8")
    (nlp_dir / "resume_002_nlp.json").write_text(json.dumps(sample_c2), encoding="utf-8")
    (txt_dir / "resume_001.txt").write_text(
        "Olivia Cox\nEmail: olivia.cox@example.com\nSenior Software Engineer...", encoding="utf-8"
    )
    (txt_dir / "resume_002.txt").write_text(
        "Ava Lopez\nEmail: ava.lopez@example.com\nDevOps Engineer...", encoding="utf-8"
    )


def test_index_talent_pool_and_sqlite_embeddings(test_db):
    nlp_dir = data_path("output/nlp")
    nlp_dir.mkdir(parents=True, exist_ok=True)
    txt_dir = data_path("output/txt")
    txt_dir.mkdir(parents=True, exist_ok=True)
    _seed_sample_candidates(nlp_dir, txt_dir)

    count = index_talent_pool()
    assert count >= 2

    stored = get_all_candidate_embeddings()
    assert len(stored) >= 2
    names = {c["candidate_name"] for c in stored}
    assert "Olivia Cox" in names
    assert "Ava Lopez" in names


def test_semantic_search_talent(test_db):
    nlp_dir = data_path("output/nlp")
    nlp_dir.mkdir(parents=True, exist_ok=True)
    txt_dir = data_path("output/txt")
    txt_dir.mkdir(parents=True, exist_ok=True)
    _seed_sample_candidates(nlp_dir, txt_dir)
    index_talent_pool()

    query = "Kubernetes cluster troubleshooting and high-scale Postgres tuning"
    res = semantic_search_talent(query, top_k=3)
    assert len(res) > 0
    top = res[0]
    assert "Olivia Cox" in top["candidate_name"]
    assert top["match_score"] > 50


def test_semantic_search_skill_filtering_avoids_schema_keys(test_db):
    nlp_dir = data_path("output/nlp")
    nlp_dir.mkdir(parents=True, exist_ok=True)
    txt_dir = data_path("output/txt")
    txt_dir.mkdir(parents=True, exist_ok=True)
    _seed_sample_candidates(nlp_dir, txt_dir)
    index_talent_pool()

    res = semantic_search_talent("java", top_k=5)
    assert len(res) > 0
    forbidden_keys = {"technical_skills", "tools_and_technologies", "soft_skills", "domain_specific_skills"}
    for candidate in res:
        for skill in candidate["all_skills"]:
            assert skill.lower() not in forbidden_keys


def test_compare_candidates_matrix(test_db):
    candidates = ["Olivia Cox", "Ava Lopez"]
    with patch(
        "src.talent_intelligence.call_ollama",
        return_value="### Executive Deliberation Brief\n- Verified candidates.\n- Recommendation: Proceed.",
    ):
        comp = compare_candidates_matrix(candidates, job_context="Senior Infrastructure Engineer")
        assert "candidates" in comp
        assert len(comp["candidates"]) == 2
        assert len(comp["radar_categories"]) > 0
        assert "Executive Deliberation Brief" in comp["executive_synthesis"]


def test_generate_candidate_feedback_letter_success_and_fallback(test_db):
    with patch(
        "src.talent_intelligence.call_ollama",
        return_value="Dear Olivia,\nThank you for interviewing. You demonstrated excellent knowledge of Postgres.",
    ):
        letter = generate_candidate_feedback_letter("Olivia Cox", "Senior Software Engineer")
        assert letter.get("candidate_name") == "Olivia Cox"
        assert "demonstrated excellent knowledge" in letter.get("feedback_text", "")

    # Fallback template when AI returns empty string
    with patch("src.talent_intelligence.call_ollama", return_value=""):
        fallback = generate_candidate_feedback_letter("Olivia Cox", "Senior Software Engineer")
        assert fallback.get("feedback_text")
        assert "Thank you for interviewing" in fallback.get("feedback_text")


def test_compute_skill_gap_analytics():
    gap = compute_skill_gap_analytics()
    assert "skills" in gap
    assert "surpluses" in gap
    assert "bottlenecks" in gap
    assert "insight_summary" in gap


def test_compute_experience_score_matrix():
    matrix = compute_experience_score_matrix()
    assert "points" in matrix
    assert "quadrants" in matrix
    quads = matrix["quadrants"]
    assert "rising_stars" in quads
    assert "seasoned_veterans" in quads
    assert "entry_level" in quads
    assert "mismatched" in quads
    assert "thresholds" in matrix


def test_compute_interview_difficulty_breakdown():
    diff = compute_interview_difficulty_breakdown()
    assert "topics" in diff
    assert "filter_questions" in diff
    assert "insight" in diff
    for topic_item in diff["topics"]:
        assert "topic" in topic_item
        assert "avg_score" in topic_item
        assert "difficulty" in topic_item


def test_compute_proctoring_risk_breakdown():
    proctor = compute_proctoring_risk_breakdown()
    assert "clean_pct" in proctor
    assert "warning_pct" in proctor
    assert "risk_pct" in proctor
    assert "violations" in proctor
    assert "verdict" in proctor


def test_compute_hiring_velocity_metrics():
    velocity = compute_hiring_velocity_metrics()
    assert "time_to_screen" in velocity
    assert "candidate_turnaround" in velocity
    assert "interview_duration" in velocity
    assert "time_to_report" in velocity
    assert "stages" in velocity
    assert len(velocity["stages"]) == 4
    assert "bottleneck_stage" in velocity


def test_compute_education_domain_mix():
    demographics = compute_education_domain_mix()
    assert "domain_mix" in demographics
    assert "education_mix" in demographics
    assert "insight" in demographics


def test_compute_talent_intelligence_analytics_master():
    analytics = compute_talent_intelligence_analytics()
    assert "skill_gap" in analytics
    assert "experience_matrix" in analytics
    assert "interview_difficulty" in analytics
    assert "proctoring_risk" in analytics
    assert "hiring_velocity" in analytics
    assert "demographics" in analytics


def test_intelligence_empty_state_resilience(tmp_path, monkeypatch):
    # Route all data paths to an empty folder to verify zero-division resilience
    monkeypatch.setattr("src.talent_intelligence.data_path", lambda p: tmp_path / p)
    (tmp_path / "output" / "nlp").mkdir(parents=True, exist_ok=True)
    (tmp_path / "output" / "interviews").mkdir(parents=True, exist_ok=True)
    (tmp_path / "output" / "ranking").mkdir(parents=True, exist_ok=True)

    gap = compute_skill_gap_analytics()
    assert isinstance(gap["skills"], list)
    assert all(s["supply_count"] == 0 for s in gap["skills"])
    assert "surpluses" in gap
    assert "bottlenecks" in gap

    matrix = compute_experience_score_matrix()
    assert isinstance(matrix["points"], list)
    assert "quadrants" in matrix
    assert "thresholds" in matrix

    diff = compute_interview_difficulty_breakdown()
    assert isinstance(diff["topics"], list)
    assert "filter_questions" in diff

    proctor = compute_proctoring_risk_breakdown()
    assert "clean_pct" in proctor
    assert "warning_pct" in proctor
    assert "risk_pct" in proctor
    assert "violations" in proctor

    velocity = compute_hiring_velocity_metrics()
    assert "time_to_screen" in velocity
    assert "stages" in velocity

    demographics = compute_education_domain_mix()
    assert "domain_mix" in demographics
    assert "education_mix" in demographics


def test_intelligence_routes(auth_client):
    res_page = auth_client.get("/intelligence")
    assert res_page.status_code == 200

    res_telemetry = auth_client.get("/api/intelligence/telemetry")
    assert res_telemetry.status_code == 200
    assert "funnel" in res_telemetry.get_json()

    res_analytics = auth_client.get("/api/intelligence/analytics")
    assert res_analytics.status_code == 200
    data = res_analytics.get_json()
    assert data["success"] is True
    assert "analytics" in data
