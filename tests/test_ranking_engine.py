import json

from src.ranking_engine import WEIGHTS, load_candidates


def test_weights_sum_to_100():
    total_weights = sum(WEIGHTS.values())
    assert total_weights == 100


def test_load_candidates_deduplication(tmp_path):
    nlp_dir = tmp_path / "nlp"
    nlp_dir.mkdir()

    cand1 = {
        "personal_info": {"name": "Alice Smith"},
        "domain": "Software Engineering",
    }
    cand2 = {
        "personal_info": {"name": "Alice Smith"},
        "domain": "Software Engineering",
    }
    cand3 = {
        "personal_info": {"name": "Bob Jones"},
        "domain": "Data Science",
    }

    (nlp_dir / "c1_nlp.json").write_text(json.dumps(cand1), encoding="utf-8")
    (nlp_dir / "c2_nlp.json").write_text(json.dumps(cand2), encoding="utf-8")
    (nlp_dir / "c3_nlp.json").write_text(json.dumps(cand3), encoding="utf-8")

    loaded = load_candidates(nlp_dir)
    assert len(loaded) == 2
    names = [c["personal_info"]["name"] for c in loaded]
    assert "Alice Smith" in names
    assert "Bob Jones" in names


def test_api_export_ranking_csv(tmp_path, monkeypatch):
    from flask import Flask

    from app.routes.ranking import register_ranking_routes

    ranking_dir = tmp_path / "ranking"
    ranking_dir.mkdir(parents=True)
    sample_ranking = {
        "job_description": {"job_title": "Senior Cloud Engineer"},
        "total_candidates": 2,
        "ranked_candidates": [
            {
                "rank": 1,
                "candidate_name": "Marcus Vance",
                "email": "marcus@example.com",
                "total_score": 92,
                "scores": {
                    "skills_match": {"score": 35},
                    "experience_years": {"score": 20},
                    "domain_match": {"score": 18},
                    "education": {"score": 12},
                },
                "strengths": ["AWS Certified", "Terraform expert"],
                "hire_recommendation": "Strong Recommend",
            },
            {
                "rank": 2,
                "candidate_name": "Lila Thorne",
                "email": "lila@example.com",
                "total_score": 84,
                "scores": {
                    "skills_match": {"score": 30},
                    "experience_years": {"score": 18},
                    "domain_match": {"score": 16},
                    "education": {"score": 10},
                },
                "strengths": ["Kubernetes", "CI/CD"],
                "hire_recommendation": "Recommend",
            },
        ],
    }
    (ranking_dir / "ranking_scores_latest.json").write_text(json.dumps(sample_ranking), encoding="utf-8")
    monkeypatch.setattr("app.routes.ranking.OUTPUT_FOLDER", tmp_path)

    app = Flask(__name__)
    app.config["SECRET_KEY"] = "test_key"
    register_ranking_routes(app)
    client = app.test_client()

    with client.session_transaction() as sess:
        sess["logged_in"] = True
        sess["username"] = "admin"

    resp = client.get("/api/ranking/export/csv")
    assert resp.status_code == 200
    assert resp.content_type == "text/csv; charset=utf-8"
    assert "attachment; filename=candidate_rankings_Senior_Cloud_Engineer.csv" in resp.headers["Content-Disposition"]

    csv_text = resp.get_data(as_text=True)
    lines = csv_text.strip().split("\r\n" if "\r\n" in csv_text else "\n")
    assert "Rank,Name,Email,Total Score,Skills Match,Experience Score,Strengths,Hire Recommendation" in lines[0]
    assert "1,Marcus Vance,marcus@example.com,92,35,20,AWS Certified; Terraform expert,Strong Recommend" in lines[1]
    assert "2,Lila Thorne,lila@example.com,84,30,18,Kubernetes; CI/CD,Recommend" in lines[2]
