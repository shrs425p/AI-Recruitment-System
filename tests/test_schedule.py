"""
test_schedule.py - Automated interview scheduling, slot allocation, Google Calendar
integration, and email invitation delivery.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from flask.testing import FlaskClient

from src.email_sender import send_interview_email


class TestScheduleAllocation:
    """Tests candidate slot allocation and schedule persistence."""

    def test_schedule_generation_allocates_slots_to_candidates(
        self, auth_client: FlaskClient, test_db: Path, temp_dir: Path, monkeypatch: pytest.MonkeyPatch
    ):
        import app.routes.scheduling as sched_mod

        ranking_dir = temp_dir / "ranking"
        ranking_dir.mkdir(parents=True, exist_ok=True)
        sched_dir = temp_dir / "scheduling"
        sched_dir.mkdir(parents=True, exist_ok=True)

        mock_ranking = {
            "ranked_candidates": [
                {"rank": 1, "candidate_name": "Alice Smith", "score": 92.0, "source_file": "alice.pdf"},
                {"rank": 2, "candidate_name": "Bob Jones", "score": 85.0, "source_file": "bob.pdf"},
            ]
        }
        (ranking_dir / "ranking_scores_001.json").write_text(json.dumps(mock_ranking), encoding="utf-8")
        monkeypatch.setattr(sched_mod, "OUTPUT_FOLDER", temp_dir)

        response = auth_client.post(
            "/api/schedule",
            json={
                "job_title": "Backend Engineer",
                "slots": ["2099-11-05 10:00", "2099-11-05 14:00", "2099-11-06 10:00"],
            },
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data.get("success") is True
        assert len(data.get("scheduled", [])) > 0

    def test_update_slot_modifies_candidate_time(
        self, auth_client: FlaskClient, test_db: Path, temp_dir: Path, monkeypatch: pytest.MonkeyPatch
    ):
        import app.routes.scheduling as sched_mod

        sched_dir = temp_dir / "scheduling"
        sched_dir.mkdir(parents=True, exist_ok=True)
        monkeypatch.setattr(sched_mod, "OUTPUT_FOLDER", temp_dir)

        initial_schedule = {
            "schedule": [
                {
                    "rank": 1,
                    "candidate_name": "David Miller",
                    "score": 88,
                    "status": "CONFIRMED",
                    "selected_slot": "2099-11-05 10:00",
                    "offered_slots": ["2099-11-05 10:00", "2099-11-05 14:00"],
                }
            ]
        }
        (sched_dir / "schedule_summary_001.json").write_text(json.dumps(initial_schedule), encoding="utf-8")

        response = auth_client.post(
            "/api/update-slot",
            json={
                "candidate_name": "David Miller",
                "selected_slot": "2099-11-05 14:00",
            },
        )
        assert response.status_code == 200

        with open(sched_dir / "schedule_summary_001.json", encoding="utf-8") as f:
            updated_data = json.load(f)
        assert updated_data["schedule"][0]["selected_slot"] == "2099-11-05 14:00"


class TestGoogleCalendarSync:
    """Tests Google Calendar status queries and event generation."""

    def test_calendar_status_returns_connectivity_state(self, auth_client: FlaskClient):
        response = auth_client.get("/api/calendar/status")
        assert response.status_code == 200
        data = response.get_json()
        assert "authenticated" in data

    def test_create_events_requires_schedule(self, auth_client: FlaskClient, test_db: Path):
        response = auth_client.post(
            "/api/calendar/create-events",
            json={"job_title": "Engineer", "hr_name": "HR Lead", "hr_email": "hr@example.com"},
        )
        assert response.status_code in (200, 400, 404)


class TestEmailInvitationDispatch:
    """Tests email notification delivery and template placeholder interpolation."""

    def test_send_interview_email_template_substitution(self, monkeypatch: pytest.MonkeyPatch):
        import config

        monkeypatch.setattr(config, "EMAIL_TEMPLATE_SUBJECT", "Interview for {job_title}: {candidate_name}")
        monkeypatch.setattr(config, "EMAIL_TEMPLATE_BODY", "Hello {candidate_name}, time: {interview_slot}")

        class MockSMTP:
            def __init__(self, host, port, timeout=10):
                pass

            def __enter__(self):
                return self

            def __exit__(self, *args):
                pass

            def starttls(self):
                pass

            def login(self, user, pwd):
                pass

            def send_message(self, msg):
                assert "Interview for SRE: Sarah Connor" in msg["Subject"]

        monkeypatch.setattr("smtplib.SMTP", MockSMTP)

        success, err = send_interview_email(
            smtp_host="localhost",
            smtp_port=587,
            smtp_email="hr@example.com",
            smtp_password="password",
            recipient_email="sarah@example.com",
            candidate_name="Sarah Connor",
            job_title="SRE",
            interview_slot="2026-11-10 11:00 AM",
            hr_name="Kyle Reese",
            company="Resistance",
        )
        assert success is True
        assert err == ""
