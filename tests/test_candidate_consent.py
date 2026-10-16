import time

import app.routes.interview as interview_routes
from app import create_candidate_app
from app.database import create_interview_token, init_db


def _setup_candidate_app(tmp_path, monkeypatch):
    test_db = tmp_path / "test_consent.db"
    monkeypatch.setattr("app.database.DB_PATH", test_db)
    init_db()

    monkeypatch.setattr(interview_routes, "active_token_sessions", {})
    monkeypatch.setattr(interview_routes, "interview_session", {})
    monkeypatch.setattr(interview_routes, "start_proctoring_session", lambda session_id: None)
    monkeypatch.setattr(
        interview_routes,
        "generate_interview_question",
        lambda **kwargs: "What is your experience with Python?",
    )

    create_interview_token(
        token="CONSENT_TOKEN_123",
        candidate_name="Morgan Lee",
        source_file="morgan_resume.pdf",
        job_title="Backend Engineer",
    )

    app = create_candidate_app()
    return app


def test_consent_disclosures_present_on_candidate_portal(tmp_path, monkeypatch):
    """Candidate portal HTML must render full privacy and consent disclosures."""
    app = _setup_candidate_app(tmp_path, monkeypatch)
    client = app.test_client()

    response = client.get("/candidate-interview/CONSENT_TOKEN_123")
    assert response.status_code == 200
    html = response.get_data(as_text=True)

    # Required disclosures
    assert "Privacy Notice &amp; Candidate Consent" in html or "Privacy Notice & Candidate Consent" in html
    assert "Data Collected" in html
    assert "Purpose" in html
    assert "Retention &amp; Erasure" in html or "Retention & Erasure" in html
    assert "AI Processing Notice" in html
    assert "Voluntary Participation &amp; Withdrawal" in html or "Voluntary Participation & Withdrawal" in html
    assert 'id="consentCheckbox"' in html
    assert 'id="startInterviewBtn"' in html
    assert "disabled" in html


def test_start_interview_without_consent_rejected_with_400(tmp_path, monkeypatch):
    """Interview start endpoint must strictly reject requests missing consent."""
    app = _setup_candidate_app(tmp_path, monkeypatch)
    client = app.test_client()

    # Missing consent flag
    res1 = client.post("/api/candidate/interview/start", json={"token": "CONSENT_TOKEN_123"})
    assert res1.status_code == 400
    data1 = res1.get_json()
    assert "consent is required" in data1["error"].lower()

    # False consent flag
    res2 = client.post("/api/candidate/interview/start", json={"token": "CONSENT_TOKEN_123", "consent": False})
    assert res2.status_code == 400
    data2 = res2.get_json()
    assert "consent is required" in data2["error"].lower()


def test_start_interview_with_consent_succeeds(tmp_path, monkeypatch):
    """Interview start endpoint proceeds when consent: true is provided."""
    app = _setup_candidate_app(tmp_path, monkeypatch)
    client = app.test_client()

    t0 = time.time()
    res = client.post("/api/candidate/interview/start", json={"token": "CONSENT_TOKEN_123", "consent": True})
    assert res.status_code == 200
    data = res.get_json()
    assert data["success"] is True
    assert "session_id" in data
    assert "session_key" in data

    # Verify session recorded consent
    session_data = interview_routes.interview_session[data["session_id"]]
    assert session_data["consent_given"] is True
    assert session_data["consent_timestamp"] >= t0
