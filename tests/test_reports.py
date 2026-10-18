"""Tests for report generation, PDF export, and completion notifications.

Verifies scoring weight calculations, transcript loading, AI summary structuring,
PDF binary rendering with character sanitization, and HR desktop notification workflows.
"""

import json

import src.report_generator as rg
from app.database import (
    create_hr_notification,
    get_unread_notification_count,
)


def test_calculate_combined_score():
    # 40% ranking (80 -> 32) + 60% interview (90 -> 54) = 86.0
    transcript = {"ranking_score": 80, "percentage": 90}
    assert rg.calculate_combined_score(transcript) == 86.0

    # 40% ranking (100 -> 40) + 60% interview (50 -> 30) = 70.0
    transcript2 = {"ranking_score": 100, "percentage": 50}
    assert rg.calculate_combined_score(transcript2) == 70.0

    # Edge cases
    assert rg.calculate_combined_score({"ranking_score": 0, "percentage": 0}) == 0.0
    assert rg.calculate_combined_score({"ranking_score": 100, "percentage": 100}) == 100.0


def test_load_interview_transcripts_empty_and_valid(tmp_path):
    assert rg.load_interview_transcripts(tmp_path) == []

    f1 = tmp_path / "interview_candidate_1.json"
    f2 = tmp_path / "interview_candidate_2.json"
    f_other = tmp_path / "not_an_interview.json"
    f1.write_text(json.dumps({"candidate_name": "Jane Doe", "score": 85}), encoding="utf-8")
    f2.write_text(json.dumps({"candidate_name": "John Smith", "score": 92}), encoding="utf-8")
    f_other.write_text(json.dumps({"info": "irrelevant"}), encoding="utf-8")

    loaded = rg.load_interview_transcripts(tmp_path)
    assert len(loaded) == 2
    names = {item["candidate_name"] for item in loaded}
    assert names == {"Jane Doe", "John Smith"}
    assert all("_source_file" in item for item in loaded)


def test_generate_ai_report_mocked(monkeypatch):
    mock_report = {
        "overall_summary": "Strong candidate with solid foundations.",
        "technical_assessment": "Proficient in Python, databases, and microservices.",
        "behavioral_assessment": "Collaborative, calm under pressure.",
        "key_strengths": ["Python", "Architecture", "Communication"],
        "key_gaps": ["Kubernetes"],
        "proctoring_remarks": "Clean session, no anomalies.",
        "risk_level": "LOW",
        "combined_score": 85,
        "combined_score_explanation": "Consistent high scores across technical rubrics.",
        "hire_recommendation": "RECOMMEND",
        "hire_justification": "Candidate meets and exceeds core technical criteria.",
        "suggested_next_steps": ["Schedule offer review call"],
    }

    monkeypatch.setattr(rg, "call_ai", lambda sys_msg, usr_msg: json.dumps(mock_report))

    transcript = {
        "candidate_name": "Alice Wonder",
        "job_title": "Backend Developer",
        "domain": "Engineering",
        "ranking_score": 88,
        "total_score": 9,
        "max_score": 10,
        "percentage": 90,
        "technical_score": 5,
        "technical_max": 5,
        "technical_pct": 100,
        "behavioral_score": 4,
        "behavioral_max": 5,
        "behavioral_pct": 80,
        "proctoring_status": "CLEAN",
        "flagged_count": 0,
        "responses": [
            {
                "question": "What is Python GIL?",
                "answer": "Global Interpreter Lock",
                "type": "TECHNICAL",
                "topic": "Python",
                "score": 5,
                "evaluation": {"feedback": "Exact answer", "weak_points": [], "strong_points": ["GIL"]},
            }
        ],
    }

    report = rg.generate_ai_report(transcript)
    assert report["hire_recommendation"] == "RECOMMEND"
    assert "Alice Wonder" not in report.get("overall_summary", "")  # Prompt instructs anonymized focus
    assert report["risk_level"] == "LOW"
    assert len(report["key_strengths"]) == 3


def test_save_report_txt_json_and_pdf(tmp_path):
    transcript = {
        "candidate_name": "Marcus Aurelius",
        "job_title": "Platform Engineer",
        "domain": "DevOps",
        "ranking_score": 85,
        "percentage": 90,
        "total_score": 45,
        "max_score": 50,
        "technical_score": 25,
        "technical_max": 25,
        "technical_pct": 100,
        "behavioral_score": 20,
        "behavioral_max": 25,
        "behavioral_pct": 80,
        "proctoring_status": "CLEAN",
        "flagged_count": 0,
        "responses": [
            {
                "question_num": 1,
                "question": "Explain Docker networking.",
                "answer": "Bridge, host, and overlay networks.",
                "type": "TECHNICAL",
                "topic": "Containers",
                "score": 5,
                "evaluation": {"feedback": "Good explanation", "weak_points": [], "strong_points": ["Networking"]},
            }
        ],
    }

    ai_report = {
        "overall_summary": "Top performing DevOps specialist.",
        "technical_assessment": "Comprehensive infrastructure depth.",
        "behavioral_assessment": "Pragmatic and disciplined.",
        "key_strengths": ["Docker", "Linux", "Kubernetes"],
        "key_gaps": [],
        "proctoring_remarks": "No integrity violations.",
        "risk_level": "LOW",
        "hire_recommendation": "STRONGLY RECOMMEND",
        "hire_justification": "Exceptional fit.",
        "suggested_next_steps": ["Prepare formal compensation offer"],
    }

    rg.save_report_txt(transcript, ai_report, 88.0, tmp_path)
    txt_files = list(tmp_path.glob("report_Marcus_Aurelius_*.txt"))
    assert len(txt_files) == 1
    txt_content = txt_files[0].read_text(encoding="utf-8")
    assert "Marcus Aurelius" in txt_content
    assert "STRONGLY RECOMMEND" in txt_content

    rg.save_report_json(transcript, ai_report, 88.0, tmp_path)
    json_files = list(tmp_path.glob("report_Marcus_Aurelius_*.json"))
    assert len(json_files) == 1
    loaded_json = json.loads(json_files[0].read_text(encoding="utf-8"))
    assert loaded_json["candidate_name"] == "Marcus Aurelius"
    assert loaded_json["scores"]["combined_score"] == 88.0

    pdf_file = rg.save_report_pdf(transcript, ai_report, 88.0, tmp_path)
    assert pdf_file.exists()
    assert pdf_file.stat().st_size > 1000  # Non-trivial PDF binary generated


def test_reports_route_unauthenticated_redirect(client):
    res = client.get("/reports")
    assert res.status_code == 302
    assert "/login" in res.headers["Location"]


def test_reports_route_authenticated(auth_client, tmp_path, monkeypatch):
    monkeypatch.setattr("app.routes.reports.OUTPUT_FOLDER", tmp_path)
    rep_dir = tmp_path / "reports"
    rep_dir.mkdir(parents=True, exist_ok=True)

    sample_rep = {
        "candidate_name": "Test Candidate",
        "job_title": "Tester",
        "scores": {"combined_score": 85.0, "ranking_score": 80, "interview_pct": 90},
        "proctoring": {"status": "CLEAN", "flagged_count": 0},
        "ai_report": {
            "hire_recommendation": "RECOMMEND",
            "overall_summary": "Solid candidate.",
            "key_strengths": ["Testing"],
            "key_gaps": [],
        },
        "responses": [],
    }
    (rep_dir / "report_Test_Candidate.json").write_text(json.dumps(sample_rep), encoding="utf-8")

    res = auth_client.get("/reports")
    assert res.status_code == 200
    assert b"Test Candidate" in res.data


def test_api_report_pdf_download(auth_client, tmp_path, monkeypatch):
    monkeypatch.setattr("app.routes.reports.OUTPUT_FOLDER", tmp_path)
    rep_dir = tmp_path / "reports"
    rep_dir.mkdir(parents=True, exist_ok=True)

    sample_rep = {
        "candidate_name": "PDF Candidate",
        "job_title": "Developer",
        "combined_score": 90.0,
        "ranking_score": 85.0,
        "interview_score": 95.0,
        "hire_recommendation": "RECOMMEND",
        "overall_summary": "Excellent performance.",
        "key_strengths": ["Python", "FastAPI"],
        "key_gaps": [],
        "proctoring": {"status": "CLEAN", "browser_log": [], "webcam_log": []},
        "responses": [],
    }
    (rep_dir / "report_PDF_Candidate.json").write_text(json.dumps(sample_rep), encoding="utf-8")

    res = auth_client.get("/api/report-pdf/report_PDF_Candidate.json")
    assert res.status_code == 200
    assert res.mimetype == "application/pdf"
    assert b"%PDF" in res.data[:10]  # Valid PDF header


def test_api_report_pdf_not_found(auth_client, tmp_path, monkeypatch):
    monkeypatch.setattr("app.routes.reports.OUTPUT_FOLDER", tmp_path)
    rep_dir = tmp_path / "reports"
    rep_dir.mkdir(parents=True, exist_ok=True)

    res = auth_client.get("/api/report-pdf/non_existent.json")
    assert res.status_code == 404
    assert res.get_json()["error"] == "Report not found"


def test_hr_notification_lifecycle(auth_client, test_db):
    # Verify initially 0 notifications
    assert get_unread_notification_count() == 0

    # Create notification
    notif_id = create_hr_notification(
        notif_type="interview_completed",
        title="Interview Finished",
        message="John Doe has completed the Python Developer interview.",
        candidate_name="John Doe",
        job_title="Python Developer",
        link="/reports",
    )
    assert notif_id > 0
    assert get_unread_notification_count() == 1

    # Fetch notifications via API
    res = auth_client.get("/api/notifications")
    assert res.status_code == 200
    notifs = res.get_json()
    assert len(notifs) >= 1
    assert notifs[0]["candidate_name"] == "John Doe"

    # Mark as read
    res_read = auth_client.post(f"/api/notifications/{notif_id}/read")
    assert res_read.status_code == 200
    assert get_unread_notification_count() == 0

    # Add second notification and mark all as read
    create_hr_notification(
        notif_type="interview_completed",
        title="Second Notification",
        message="Second candidate finished.",
        candidate_name="Jane Doe",
        job_title="Data Scientist",
    )
    assert get_unread_notification_count() == 1

    res_all = auth_client.post("/api/notifications/read-all")
    assert res_all.status_code == 200
    assert get_unread_notification_count() == 0
