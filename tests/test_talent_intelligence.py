import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import create_app
from app.database import get_all_candidate_embeddings, get_telemetry_metrics, init_db
from src.talent_intelligence import (
    compare_candidates_matrix,
    generate_candidate_feedback_letter,
    index_talent_pool,
    semantic_search_talent,
)

def run_tests():
    print("--- 1. Testing Database Initialization ---")
    init_db()

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
        print(f"  Match: {r['candidate_name']} ({r['domain']}) -> {r['match_score']}%")
    assert len(res) > 0, "Expected semantic search results"

    print("--- 4. Testing Candidate Comparison Matrix ---")
    candidates = [stored[0]["candidate_name"], stored[1]["candidate_name"]]
    comp = compare_candidates_matrix(candidates, job_context="Senior Infrastructure Engineer")
    print(f"Compared: {[c['name'] for c in comp['candidates']]}")
    print(f"Radar axes: {comp['radar_categories']}")
    print(f"Synthesis preview: {comp['executive_synthesis'][:120]}...")
    assert "candidates" in comp
    assert len(comp["candidates"]) == 2

    print("--- 5. Testing Candidate Feedback Generation ---")
    fb = generate_candidate_feedback_letter(candidates[0], "Cloud DevOps Specialist")
    print(f"Feedback ID: {fb.get('feedback_id')}, Candidate: {fb.get('candidate_name')}")
    print(f"Feedback letter preview:\n{fb.get('feedback_text')[:160]}...")
    assert fb.get("feedback_text"), "Expected generated feedback letter text"

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
    run_tests()
