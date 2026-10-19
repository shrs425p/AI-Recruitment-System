"""Tests for Candidate Selection & Job Offer / Next Steps Hub.

Verifies:
- Ollama AI offer letter generation with verified strengths and onboarding next steps.
- Deterministic offline fallback template when Ollama is unavailable.
- Database persistence (save, list, fetch by ID, mark sent).
- SMTP email dispatch formatting (HTML banner, next steps, TLS).
- REST API endpoints for drafting and dispatching offers.
- Automatic HR notification generation on dispatch.
"""

from unittest.mock import MagicMock, patch

import pytest

from app.database import (
    create_hr_notification,
    get_candidate_offer_by_id,
    get_candidate_offers,
    get_hr_notifications,
    mark_offer_sent,
    save_candidate_offer,
)
from src.email_sender import send_selection_offer_email
from src.talent_intelligence import generate_candidate_offer_letter


# ─────────────────────────────────────────────────────────────
# 1. GENERATION & FALLBACK TESTS
# ─────────────────────────────────────────────────────────────

def test_generate_candidate_offer_letter_success():
    fake_candidate = {
        "personal_info": {"name": "Jordan Bell", "email": "jordan.bell@example.com"},
        "domain": "Systems & DevOps",
        "candidate_strength_summary": "Extensive experience scaling distributed Kubernetes clusters.",
        "skills": [{"name": "Kubernetes"}, {"name": "Go"}, {"name": "Terraform"}],
    }

    with patch("src.talent_intelligence.get_candidate_details", return_value=fake_candidate), \
         patch("src.talent_intelligence.call_ollama", return_value="Dear Jordan,\n\nWe are thrilled to offer you the role of Principal Systems Engineer."):

        result = generate_candidate_offer_letter(
            candidate_name="Jordan Bell",
            job_title="Principal Systems Engineer",
            start_date="December 1, 2026",
            compensation="₹28,00,000 PA",
            reporting_manager="VP of Infrastructure",
        )

        assert "error" not in result
        assert result["candidate_name"] == "Jordan Bell"
        assert result["email"] == "jordan.bell@example.com"
        assert result["job_title"] == "Principal Systems Engineer"
        assert result["start_date"] == "December 1, 2026"
        assert result["compensation"] == "₹28,00,000 PA"
        assert "Principal Systems Engineer" in result["offer_letter"]
        assert result["status"] == "DRAFT"
        assert result["offer_id"] > 0


def test_generate_candidate_offer_letter_fallback_when_ollama_fails():
    fake_candidate = {
        "personal_info": {"name": "Maya Lin", "email": "maya.lin@example.com"},
        "domain": "Frontend Architecture",
        "candidate_strength_summary": "High proficiency in modern reactive state architectures.",
        "skills": ["TypeScript", "React", "Next.js"],
    }

    with patch("src.talent_intelligence.get_candidate_details", return_value=fake_candidate), \
         patch("src.talent_intelligence.call_ollama", side_effect=Exception("Ollama connection timed out")):

        result = generate_candidate_offer_letter(
            candidate_name="Maya Lin",
            job_title="Lead Frontend Engineer",
            start_date="November 15, 2026",
            compensation="₹24,00,000 PA",
            reporting_manager="Head of Engineering",
        )

        assert "error" not in result
        letter = result["offer_letter"]
        assert "Dear Maya Lin" in letter
        assert "Lead Frontend Engineer" in letter
        assert "November 15, 2026" in letter
        assert "₹24,00,000 PA" in letter
        assert "Next Steps for Onboarding" in letter
        assert "Welcome aboard!" in letter
        assert result["status"] == "DRAFT"


def test_generate_candidate_offer_letter_candidate_not_found():
    with patch("src.talent_intelligence.get_candidate_details", return_value=None):
        result = generate_candidate_offer_letter(candidate_name="Ghost Applicant")
        assert "error" in result
        assert "not found" in result["error"].lower()


# ─────────────────────────────────────────────────────────────
# 2. DATABASE PERSISTENCE TESTS
# ─────────────────────────────────────────────────────────────

def test_database_candidate_offers_lifecycle():
    # 1. Save new offer
    offer_id = save_candidate_offer(
        candidate_name="Ethan Hunt",
        email="ethan.hunt@imf.gov",
        job_title="Special Operations Lead",
        start_date="Immediate",
        compensation="Top Secret Tier 5",
        offer_letter="Dear Ethan, Welcome to the team.",
        status="DRAFT",
    )
    assert offer_id > 0

    # 2. Fetch all and check filter by name
    all_offers = get_candidate_offers()
    assert any(o["id"] == offer_id for o in all_offers)

    ethan_offers = get_candidate_offers("Ethan Hunt")
    assert len(ethan_offers) >= 1
    assert ethan_offers[0]["job_title"] == "Special Operations Lead"
    assert ethan_offers[0]["status"] == "DRAFT"

    # 3. Fetch single offer by ID
    single = get_candidate_offer_by_id(offer_id)
    assert single is not None
    assert single["candidate_name"] == "Ethan Hunt"
    assert single["email"] == "ethan.hunt@imf.gov"

    # 4. Mark offer sent
    mark_offer_sent(offer_id)
    updated = get_candidate_offer_by_id(offer_id)
    assert updated["status"] == "SENT"
    assert updated["sent_at"] is not None


# ─────────────────────────────────────────────────────────────
# 3. SMTP DISPATCH TESTS
# ─────────────────────────────────────────────────────────────

def test_send_selection_offer_email_success():
    mock_smtp_instance = MagicMock()

    with patch("smtplib.SMTP", return_value=mock_smtp_instance):
        mock_smtp_instance.__enter__.return_value = mock_smtp_instance

        success, err = send_selection_offer_email(
            smtp_host="smtp.example.com",
            smtp_port=587,
            smtp_email="recruiting@example.com",
            smtp_password="test-secret-password",
            recipient_email="candidate@example.com",
            candidate_name="Alex Mercer",
            subject="Job Offer: Senior Architect",
            offer_letter="Congratulations Alex!\n\nWe offer you the role.\n\nNext steps:\n1. Accept.",
            job_title="Senior Architect",
            company="Acme Corp",
        )

        assert success is True
        assert err == ""
        assert mock_smtp_instance.starttls.called
        assert mock_smtp_instance.login.called
        assert mock_smtp_instance.send_message.called


def test_send_selection_offer_email_validation_failures():
    # Missing recipient
    ok, err = send_selection_offer_email(
        smtp_host="smtp.example.com",
        smtp_port=587,
        smtp_email="recruiting@example.com",
        smtp_password="secret",
        recipient_email="",
        candidate_name="Alex",
        subject="Offer",
        offer_letter="Text",
    )
    assert ok is False
    assert "No recipient" in err

    # Missing SMTP configuration
    ok, err = send_selection_offer_email(
        smtp_host="smtp.example.com",
        smtp_port=587,
        smtp_email="",
        smtp_password="",
        recipient_email="alex@example.com",
        candidate_name="Alex",
        subject="Offer",
        offer_letter="Text",
    )
    assert ok is False
    assert "SMTP credentials not configured" in err


# ─────────────────────────────────────────────────────────────
# 4. API ROUTE TESTS
# ─────────────────────────────────────────────────────────────

def test_api_generate_offer_validation_and_success(auth_client):
    # 1. Missing candidate_name -> 400
    res = auth_client.post("/api/intelligence/generate-offer", json={})
    assert res.status_code == 400
    assert "Candidate name is required" in res.get_json()["error"]

    # 2. Candidate not found -> 404
    with patch("src.talent_intelligence.get_candidate_details", return_value=None):
        res = auth_client.post(
            "/api/intelligence/generate-offer",
            json={"candidate_name": "Nonexistent Person"},
        )
        assert res.status_code == 404

    # 3. Successful draft
    fake_cand = {
        "personal_info": {"name": "Sarah Connor", "email": "sarah@resistance.org"},
        "domain": "Security Systems",
        "candidate_strength_summary": "Defensive infrastructure and incident response.",
        "skills": ["Firewall", "Security Audit"],
    }
    with patch("src.talent_intelligence.get_candidate_details", return_value=fake_cand), \
         patch("src.talent_intelligence.call_ollama", return_value="Dear Sarah, Welcome aboard."):
        res = auth_client.post(
            "/api/intelligence/generate-offer",
            json={
                "candidate_name": "Sarah Connor",
                "job_title": "Chief Security Architect",
                "start_date": "Immediately",
                "compensation": "Competitive",
            },
        )
        assert res.status_code == 200
        data = res.get_json()
        assert data["success"] is True
        assert data["offer"]["candidate_name"] == "Sarah Connor"
        assert data["offer"]["email"] == "sarah@resistance.org"


def test_api_send_offer_flow(auth_client):
    # Validation failures
    res_no_email = auth_client.post("/api/intelligence/send-offer", json={"offer_letter": "Hello"})
    assert res_no_email.status_code == 400

    res_no_letter = auth_client.post("/api/intelligence/send-offer", json={"email": "test@example.com"})
    assert res_no_letter.status_code == 400

    # Successful dispatch
    with patch("app.routes.intelligence.send_selection_offer_email", return_value=(True, "")):
        res = auth_client.post(
            "/api/intelligence/send-offer",
            json={
                "email": "sarah@resistance.org",
                "candidate_name": "Sarah Connor",
                "job_title": "Chief Security Architect",
                "subject": "Formal Offer",
                "offer_letter": "Welcome aboard Sarah!",
            },
        )
        assert res.status_code == 200
        data = res.get_json()
        assert data["success"] is True
        assert "dispatched" in data["message"].lower()

        # Verify HR notification was created
        notifs = get_hr_notifications(unread_only=True)
        assert any(n["candidate_name"] == "Sarah Connor" for n in notifs)


def test_api_offers_history(auth_client):
    res = auth_client.get("/api/intelligence/offers-history")
    assert res.status_code == 200
    data = res.get_json()
    assert data["success"] is True
    assert isinstance(data["offers"], list)


def test_api_unauthenticated_access_blocked(client):
    res = client.post("/api/intelligence/generate-offer", json={"candidate_name": "Test"})
    assert res.status_code == 401
    assert res.get_json()["error"] == "Unauthorized"

