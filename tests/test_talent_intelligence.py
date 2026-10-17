import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import json
from unittest.mock import patch

from app import create_app
from app.database import get_all_candidate_embeddings, init_db
from src.common import data_path
from src.talent_intelligence import (
    compare_candidates_matrix,
    generate_candidate_feedback_letter,
    index_talent_pool,
    semantic_search_talent,
)


def test_talent_intelligence_suite():
    print("--- 1. Testing Database Initialization ---")
    init_db()

    # Ensure test candidate profiles exist in test environment
    nlp_dir = data_path("output/nlp")
    nlp_dir.mkdir(parents=True, exist_ok=True)
    if not list(nlp_dir.glob("*_nlp.json")):
        sample_c1 = {
            "personal_info": {"name": "Olivia Cox", "email": "olivia.cox@example.com"},
            "domain": "Software Engineering",
            "skills": {
                "technical_skills": ["Python", "FastAPI", "PostgreSQL", "Kubernetes", "Docker", "Java"],
                "soft_skills": ["Team Leadership", "Communication"],
            },
            "candidate_strength_summary": "Expert backend developer with Kubernetes and Postgres tuning expertise.",
            "work_experience": [
                {
                    "role": "Senior Software Engineer",
                    "company": "TechCorp",
                    "responsibilities": ["Kubernetes cluster troubleshooting and high-scale Postgres tuning."],
                }
            ],
            "projects": [
                {"name": "Data Engine", "description": "High performance ingestion engine", "technologies": ["Python", "PostgreSQL"]}
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
        with open(nlp_dir / "resume_001_nlp.json", "w", encoding="utf-8") as f:
            json.dump(sample_c1, f)
        with open(nlp_dir / "resume_002_nlp.json", "w", encoding="utf-8") as f:
            json.dump(sample_c2, f)
        txt_dir = data_path("output/txt")
        txt_dir.mkdir(parents=True, exist_ok=True)
        (txt_dir / "resume_001.txt").write_text("Olivia Cox\nEmail: olivia.cox@example.com\nSenior Software Engineer...", encoding="utf-8")
        (txt_dir / "resume_002.txt").write_text("Ava Lopez\nEmail: ava.lopez@example.com\nDevOps Engineer...", encoding="utf-8")

    print("--- 2. Testing Talent Pool Indexing ---")
    count = index_talent_pool()
    print(f"Indexed candidate profiles: {count}")
    stored = get_all_candidate_embeddings()
    print(f"Stored in SQLite: {len(stored)}")
    assert len(stored) > 0, "Expected stored candidate embeddings in SQLite"

    print("--- 3. Testing Semantic Search ---")
    query = "Kubernetes cluster troubleshooting and high-scale Postgres tuning"
    res = semantic_search_talent(query, top_k=3)
    print(f"Search query: '{query}'")
    for r in res:
        print(f"  Match: {r['candidate_name']} ({r['domain']}) -> {r['match_score']}% | Skills: {r['all_skills'][:3]}")
    assert len(res) > 0, "Expected semantic search results"

    print("--- 3b. Testing Java Query Filtering & Skill Accuracy ---")
    java_res = semantic_search_talent("java", top_k=5)
    print(f"Java search match count: {len(java_res)}")
    for r in java_res:
        print(f"  Candidate: {r['candidate_name']} ({r['domain']}) -> {r['match_score']}% | Matched: {r['matched_skills']}")
        # Verify skills are actual skills, not generic schema keys
        for sk in r['all_skills']:
            assert sk.lower() not in ("technical_skills", "tools_and_technologies", "soft_skills", "domain_specific_skills"), f"Schema key leaked into skills: {sk}"

    print("--- 4. Testing Candidate Comparison Matrix ---")
    candidates = [stored[0]["candidate_name"], stored[1]["candidate_name"]]
    with patch("src.talent_intelligence.call_ollama", return_value="### Executive Deliberation Brief\n- Evaluated candidates.\n- Recommendation: Proceed."):
        comp = compare_candidates_matrix(candidates, job_context="Senior Infrastructure Engineer")
        print(f"Compared: {[c['name'] for c in comp['candidates']]}")
        print(f"Radar axes: {comp['radar_categories']}")
        print(f"Synthesis preview: {comp['executive_synthesis'][:120]}...")
        assert "candidates" in comp
        assert len(comp["candidates"]) == 2
        assert comp.get("executive_synthesis"), "Expected executive synthesis text"

    print("--- 5. Testing Candidate Feedback Generation ---")
    with patch("src.talent_intelligence.call_ollama", return_value="Dear Candidate,\nThank you for interviewing with us."):
        fb = generate_candidate_feedback_letter(candidates[0], "Cloud DevOps Specialist")
        print(f"Feedback ID: {fb.get('feedback_id')}, Candidate: {fb.get('candidate_name')}")
        print(f"Feedback letter preview:\n{fb.get('feedback_text')[:160]}...")
        assert fb.get("feedback_text"), "Expected generated feedback letter text"

    # Also explicitly verify fallback template when AI service returns empty or is unreachable
    with patch("src.talent_intelligence.call_ollama", return_value=""):
        fb_fallback = generate_candidate_feedback_letter(candidates[0], "Cloud DevOps Specialist")
        assert fb_fallback.get("feedback_text"), "Expected non-empty fallback feedback letter"
        assert "Thank you for interviewing" in fb_fallback.get("feedback_text")

    print("--- 6. Testing Flask Endpoints ---")
    app = create_app()
    client = app.test_client()
    with client.session_transaction() as sess:
        sess["logged_in"] = True
        sess["username"] = "admin"
        sess["_csrf_token"] = "test_csrf_token_value_12345"
        csrf = sess["_csrf_token"]

    resp = client.get("/intelligence")
    print(f"GET /intelligence status: {resp.status_code}")
    assert resp.status_code == 200, f"Expected 200 but got {resp.status_code}"

    search_resp = client.post(
        "/api/intelligence/search",
        json={"query": "Python data science", "top_k": 5},
        headers={"X-CSRF-Token": csrf}
    )
    print(f"POST /api/intelligence/search status: {search_resp.status_code}, count: {search_resp.get_json().get('count')}")
    assert search_resp.status_code == 200

    metrics_resp = client.get("/api/intelligence/telemetry")
    print(f"GET /api/intelligence/telemetry status: {metrics_resp.status_code}")
    m_data = metrics_resp.get_json()
    print(f"Funnel sourced: {m_data.get('funnel', {}).get('resumes_sourced')}")
    assert metrics_resp.status_code == 200

    print("\n>>> ALL TALENT INTELLIGENCE ENGINE & ROUTE TESTS PASSED SUCCESSFULLY! <<<")

if __name__ == "__main__":
    test_talent_intelligence_suite()
