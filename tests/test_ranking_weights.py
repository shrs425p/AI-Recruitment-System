from unittest.mock import patch

from src.ranking_engine import (
    DEFAULT_WEIGHTS,
    check_knockout_rules,
    normalize_weights,
    score_candidate,
)


def test_normalize_weights_default():
    w = normalize_weights(None)
    assert w == DEFAULT_WEIGHTS
    assert sum(w.values()) == 100

    w_empty = normalize_weights({})
    assert w_empty == DEFAULT_WEIGHTS
    assert sum(w_empty.values()) == 100


def test_normalize_weights_custom():
    custom = {
        "domain_match": 10,
        "skills_match": 40,
        "experience_years": 30,
        "education": 10,
        "certifications": 10,
    }
    w = normalize_weights(custom)
    assert sum(w.values()) == 100
    assert w["skills_match"] == 40
    assert w["experience_years"] == 30

    # Test auto-balancing when weights don't sum to 100
    unbalanced = {
        "domain_match": 20,
        "skills_match": 20,
        "experience_years": 20,
        "education": 10,
        "certifications": 10,
    }  # Sum = 80
    w_balanced = normalize_weights(unbalanced)
    assert sum(w_balanced.values()) == 100


def test_check_knockout_min_experience():
    cand_junior = {"total_experience_years": 1.5, "skills": ["Python"]}
    cand_senior = {"total_experience_years": 5.0, "skills": ["Python"]}

    ko_rules = {"min_experience_years": 3.0}

    is_ko, reason = check_knockout_rules(cand_junior, ko_rules)
    assert is_ko is True
    assert "Requires min 3.0 years" in (reason or "")

    is_ko2, reason2 = check_knockout_rules(cand_senior, ko_rules)
    assert is_ko2 is False
    assert reason2 is None


def test_check_knockout_mandatory_skills():
    candidate = {
        "skills": {
            "technical_skills": ["Python", "Flask", "PostgreSQL"],
            "tools_and_technologies": ["Git", "Linux"],
        }
    }

    # Satisfied skills
    ko_rules_ok = {"required_skills": ["Python", "PostgreSQL"]}
    is_ko, _ = check_knockout_rules(candidate, ko_rules_ok)
    assert is_ko is False

    # Missing mandatory skill
    ko_rules_missing = {"required_skills": ["Python", "Kubernetes"]}
    is_ko, reason = check_knockout_rules(candidate, ko_rules_missing)
    assert is_ko is True
    assert "Missing mandatory skill 'Kubernetes'" in (reason or "")


def test_check_knockout_required_certifications():
    candidate = {
        "certifications": [
            {"name": "AWS Certified Solutions Architect"},
            "Certified Kubernetes Administrator",
        ]
    }

    # Satisfied cert
    ko_ok = {"required_certifications": ["AWS Certified"]}
    is_ko, _ = check_knockout_rules(candidate, ko_ok)
    assert is_ko is False

    # Missing cert
    ko_fail = {"required_certifications": ["GCP Professional Cloud Architect"]}
    is_ko, reason = check_knockout_rules(candidate, ko_fail)
    assert is_ko is True
    assert "Missing required certification 'GCP Professional Cloud Architect'" in (reason or "")


def test_score_candidate_knockout_saves_ai_tokens():
    """Verify that a candidate failing a knockout rule skips call_ai entirely (saving 100% of LLM tokens)."""
    cand = {
        "personal_info": {"name": "Bob Junior"},
        "total_experience_years": 1,
        "skills": ["JavaScript"],
    }
    jd = {"job_title": "Staff Engineer", "domain": "Backend"}
    ko_rules = {"min_experience_years": 5}

    with patch("src.ranking_engine.call_ai") as mock_ai:
        result = score_candidate(cand, jd, knockout_rules=ko_rules)
        # Verify AI was NEVER called!
        mock_ai.assert_not_called()

        assert result is not None
        assert result["is_knocked_out"] is True
        assert result["total_score"] == 0
        assert result["hire_recommendation"] == "Knocked Out"
        assert "Requires min 5.0 years" in result["knockout_reason"]


def test_score_candidate_custom_weights():
    cand = {
        "personal_info": {"name": "Alice Expert"},
        "domain": "Software",
        "total_experience_years": 8,
        "skills": ["Python", "Distributed Systems"],
    }
    jd = {"job_title": "Principal Architect", "domain": "Software"}
    custom_weights = {
        "domain_match": 10,
        "skills_match": 30,
        "experience_years": 50,  # Heavy weight on experience
        "education": 5,
        "certifications": 5,
    }

    fake_ai_response = {
        "candidate_name": "Alice Expert",
        "scores": {
            "domain_match": {"score": 10, "reason": "Direct"},
            "skills_match": {"score": 30, "reason": "Strong"},
            "experience_years": {"score": 50, "reason": "8 years"},
            "education": {"score": 5, "reason": "BS CS"},
            "certifications": {"score": 5, "reason": "None"},
        },
        "total_score": 100,
        "percentage": 100.0,
        "overall_verdict": "Outstanding",
        "strengths": ["Architecture"],
        "gaps": [],
        "hire_recommendation": "Strongly Recommend",
    }

    with patch("src.ranking_engine.call_ai", return_value=fake_ai_response):
        result = score_candidate(cand, jd, weights=custom_weights)
        assert result is not None
        assert result["is_knocked_out"] is False
        assert result["total_score"] == 100
        assert result["scores"]["experience_years"]["max"] == 50


def test_api_rank_integration_with_knockout(tmp_path, monkeypatch):
    from flask import Flask

    from app.database import init_db
    from app.routes.ranking import register_ranking_routes

    test_db = tmp_path / "test_rank_api.db"
    monkeypatch.setattr("app.database.DB_PATH", test_db)
    init_db()

    app = Flask(__name__)
    app.config["SECRET_KEY"] = "secret"
    register_ranking_routes(app)
    client = app.test_client()

    fake_candidates = [
        {
            "_source_file": "cand1.pdf",
            "personal_info": {"name": "Qualified Senior"},
            "total_experience_years": 5.0,
            "skills": ["Python", "FastAPI"],
            "domain": "Software",
        },
        {
            "_source_file": "cand2.pdf",
            "personal_info": {"name": "Junior Intern"},
            "total_experience_years": 1.0,
            "skills": ["Python"],
            "domain": "Software",
        },
    ]

    jd_parsed = {"job_title": "Senior Python Engineer", "domain": "Software"}
    senior_ai_score = {
        "candidate_name": "Qualified Senior",
        "scores": {
            "domain_match": {"score": 20, "reason": "Match"},
            "skills_match": {"score": 35, "reason": "Match"},
            "experience_years": {"score": 20, "reason": "5 yrs"},
            "education": {"score": 15, "reason": "Degree"},
            "certifications": {"score": 10, "reason": "None"},
        },
        "total_score": 100,
        "percentage": 100.0,
        "overall_verdict": "Great",
        "strengths": [],
        "gaps": [],
        "hire_recommendation": "Strongly Recommend",
    }

    with client.session_transaction() as sess:
        sess["logged_in"] = True
        sess["username"] = "admin"

    with patch("app.routes.ranking.load_candidates", return_value=fake_candidates), \
         patch("app.routes.ranking.call_ai", return_value=jd_parsed), \
         patch("src.ranking_engine.call_ai", return_value=senior_ai_score):

        res = client.post(
            "/api/rank",
            json={
                "jd_text": "Senior Python Engineer with 3+ years experience.",
                "weights": {"skills_match": 40, "experience_years": 30, "domain_match": 10, "education": 10, "certifications": 10},
                "knockout_rules": {"min_experience_years": 3.0},
            },
        )
        assert res.status_code == 200
        data = res.get_json()
        assert data["success"] is True
        ranked = data["ranked"]
        assert len(ranked) == 2

        # Qualified Senior is #1 with 100
        assert ranked[0]["candidate_name"] == "Qualified Senior"
        assert ranked[0]["is_knocked_out"] is False

        # Junior Intern is knocked out with score 0
        assert ranked[1]["candidate_name"] == "Junior Intern"
        assert ranked[1]["is_knocked_out"] is True
        assert ranked[1]["total_score"] == 0
        assert ranked[1]["hire_recommendation"] == "Knocked Out"
        assert "Requires min 3.0 years" in ranked[1]["knockout_reason"]


def test_settings_scoring_api(tmp_path, monkeypatch):
    import json

    from flask import Flask

    import config as cfg
    from app.database import init_db
    from app.routes.settings import register_settings_routes

    test_db = tmp_path / "test_settings_scoring.db"
    monkeypatch.setattr("app.database.DB_PATH", test_db)
    init_db()

    app = Flask(__name__)
    app.config["SECRET_KEY"] = "secret"
    register_settings_routes(app)
    client = app.test_client()

    with client.session_transaction() as sess:
        sess["logged_in"] = True
        sess["username"] = "admin"

    custom_weights = {"skills_match": 40, "experience_years": 30, "domain_match": 10, "education": 10, "certifications": 10}
    custom_ko = {"min_experience_years": 4.0, "required_skills": ["Python"], "required_certifications": []}

    res = client.post(
        "/api/settings/scoring",
        json={
            "preset": "architect",
            "weights": custom_weights,
            "knockout_rules": custom_ko,
        },
    )
    assert res.status_code == 200
    data = res.get_json()
    assert data["success"] is True
    assert data["preset"] == "architect"
    assert json.loads(data["weights"]) == custom_weights
    assert json.loads(data["knockout_rules"]) == custom_ko

    assert cfg.SCORING_PRESET == "architect"
    assert json.loads(cfg.SCORING_WEIGHTS) == custom_weights


def test_api_rank_fallback_to_saved_settings(tmp_path, monkeypatch):
    import json

    from flask import Flask

    import config as cfg
    from app.database import init_db
    from app.routes.ranking import register_ranking_routes

    test_db = tmp_path / "test_rank_fallback.db"
    monkeypatch.setattr("app.database.DB_PATH", test_db)
    init_db()

    # Set saved defaults in config
    saved_ko = {"min_experience_years": 4.0, "required_skills": ["Python"], "required_certifications": []}
    monkeypatch.setattr(cfg, "KNOCKOUT_RULES", json.dumps(saved_ko))
    saved_weights = {"skills_match": 50, "experience_years": 20, "domain_match": 10, "education": 10, "certifications": 10}
    monkeypatch.setattr(cfg, "SCORING_WEIGHTS", json.dumps(saved_weights))

    app = Flask(__name__)
    app.config["SECRET_KEY"] = "secret"
    register_ranking_routes(app)
    client = app.test_client()

    with client.session_transaction() as sess:
        sess["logged_in"] = True
        sess["username"] = "admin"

    fake_candidates = [
        {
            "_source_file": "senior.pdf",
            "personal_info": {"name": "Experienced Dev"},
            "total_experience_years": 5.0,
            "skills": ["Python"],
            "domain": "Software",
        },
        {
            "_source_file": "junior.pdf",
            "personal_info": {"name": "Junior Dev"},
            "total_experience_years": 2.0,
            "skills": ["Python"],
            "domain": "Software",
        },
    ]

    jd_parsed = {"job_title": "Python Lead", "domain": "Software"}
    senior_ai_score = {
        "candidate_name": "Experienced Dev",
        "scores": {
            "domain_match": {"score": 10, "reason": "Match"},
            "skills_match": {"score": 50, "reason": "Match"},
            "experience_years": {"score": 20, "reason": "5 yrs"},
            "education": {"score": 10, "reason": "Degree"},
            "certifications": {"score": 10, "reason": "None"},
        },
        "total_score": 100,
        "percentage": 100.0,
        "overall_verdict": "Great",
        "strengths": [],
        "gaps": [],
        "hire_recommendation": "Strongly Recommend",
    }

    with patch("app.routes.ranking.load_candidates", return_value=fake_candidates), \
         patch("app.routes.ranking.call_ai", return_value=jd_parsed), \
         patch("src.ranking_engine.call_ai", return_value=senior_ai_score):

        # Note: weights and knockout_rules are omitted from the request body
        res = client.post(
            "/api/rank",
            json={
                "jd_text": "Python Lead with strong skills.",
            },
        )
        assert res.status_code == 200
        data = res.get_json()
        assert data["success"] is True
        ranked = data["ranked"]
        assert len(ranked) == 2

        # Senior passed
        assert ranked[0]["candidate_name"] == "Experienced Dev"
        assert ranked[0]["is_knocked_out"] is False

        # Junior disqualified by saved knockout rule (min 4.0 years)
        assert ranked[1]["candidate_name"] == "Junior Dev"
        assert ranked[1]["is_knocked_out"] is True
        assert ranked[1]["total_score"] == 0
        assert "Requires min 4.0 years" in ranked[1]["knockout_reason"]
