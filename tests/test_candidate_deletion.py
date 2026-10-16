import logging

import app.routes.dashboard as dashboard_routes
from app import create_app
from app.database import (
    create_interview_token,
    create_run,
    get_candidate_by_name,
    get_connection,
    init_db,
    log_email,
    save_schedule,
    upsert_candidate,
)


def _auth_client():
    app = create_app()
    client = app.test_client()
    with client.session_transaction() as sess:
        sess["logged_in"] = True
        sess["desktop_session"] = True
        sess["_csrf_token"] = "csrf-token-del-test"
    client.environ_base["HTTP_X_CSRF_TOKEN"] = "csrf-token-del-test"
    return client


def test_delete_candidate_endpoint_requires_auth():
    app = create_app()
    client = app.test_client()
    res = client.delete("/api/candidate/1")
    assert res.status_code == 401


def test_delete_candidate_endpoint_requires_csrf():
    app = create_app()
    client = app.test_client()
    with client.session_transaction() as sess:
        sess["logged_in"] = True
        sess["desktop_session"] = True
        sess["_csrf_token"] = "token-xyz"
    # No X-CSRF-Token passed
    res = client.delete("/api/candidate/1")
    assert res.status_code == 403


def test_delete_candidate_nonexistent_returns_404():
    client = _auth_client()
    res = client.delete("/api/candidate/999999")
    assert res.status_code == 404
    data = res.get_json()
    assert "not found" in data["error"].lower()


def test_delete_candidate_purges_db_and_disk_assets(tmp_path, monkeypatch, caplog):
    test_db = tmp_path / "test_deletion.db"
    monkeypatch.setattr("app.database.DB_PATH", test_db)
    init_db()

    resumes_dir = tmp_path / "resumes"
    output_dir = tmp_path / "output"
    resumes_dir.mkdir(parents=True)
    (output_dir / "txt").mkdir(parents=True)
    (output_dir / "nlp").mkdir(parents=True)
    (output_dir / "interviews").mkdir(parents=True)
    (output_dir / "reports").mkdir(parents=True)
    (output_dir / "ranking").mkdir(parents=True)

    monkeypatch.setattr("app.core.RESUMES_FOLDER", resumes_dir)
    monkeypatch.setattr("app.core.OUTPUT_FOLDER", output_dir)
    monkeypatch.setattr(dashboard_routes, "RESUMES_FOLDER", resumes_dir)
    monkeypatch.setattr(dashboard_routes, "OUTPUT_FOLDER", output_dir)

    cand_name = "Alex Johnson"
    cand_email = "alex.johnson@example.com"
    source_file = "alex_johnson_cv.pdf"

    # Seed DB records
    run_id = create_run("test_run")
    cand_id = upsert_candidate(run_id, cand_name, email=cand_email, source_file=source_file, score=88.5)
    sched_ids = save_schedule(run_id, [{"candidate_name": cand_name, "score": 88.5}], "Software Engineer")
    log_email(run_id, sched_ids[0], cand_email, "Interview Invitation")
    create_interview_token("token_del_test_123", cand_name, source_file, "Software Engineer")

    # Seed Disk files
    f_resume = resumes_dir / source_file
    f_resume.write_text("Dummy resume binary data")
    f_txt = output_dir / "txt" / "alex_johnson_cv.txt"
    f_txt.write_text("Extracted resume text")
    f_nlp = output_dir / "nlp" / "alex_johnson_cv_nlp.json"
    f_nlp.write_text('{"skills": ["Python"]}')
    f_int = output_dir / "interviews" / "interview_Alex_Johnson_1700000000.json"
    f_int.write_text('{"candidate_name": "Alex Johnson"}')
    f_rep_json = output_dir / "reports" / "report_Alex_Johnson_1700000000.json"
    f_rep_json.write_text('{"candidate_name": "Alex Johnson"}')
    f_rep_pdf = output_dir / "reports" / "report_Alex_Johnson_1700000000.pdf"
    f_rep_pdf.write_text("PDF report binary")

    # Verify everything exists before deletion
    assert get_candidate_by_name(cand_name) is not None
    assert f_resume.exists()
    assert f_txt.exists()
    assert f_nlp.exists()
    assert f_int.exists()
    assert f_rep_json.exists()
    assert f_rep_pdf.exists()

    client = _auth_client()
    with caplog.at_level(logging.INFO):
        res = client.delete(f"/api/candidate/{cand_id}")

    assert res.status_code == 200
    assert res.get_json()["success"] is True

    # Verify DB records deleted
    conn = get_connection()
    try:
        assert conn.execute("SELECT COUNT(*) FROM candidates WHERE id=?", (cand_id,)).fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM schedules WHERE candidate_name=?", (cand_name,)).fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM email_log WHERE recipient=?", (cand_email,)).fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM interview_tokens WHERE candidate_name=?", (cand_name,)).fetchone()[0] == 0
    finally:
        conn.close()

    # Verify all disk files permanently removed
    assert not f_resume.exists()
    assert not f_txt.exists()
    assert not f_nlp.exists()
    assert not f_int.exists()
    assert not f_rep_json.exists()
    assert not f_rep_pdf.exists()

    # Verify logging does not store candidate PII (name, email)
    log_texts = [r.message for r in caplog.records if f"Candidate ID {cand_id}" in r.message]
    assert len(log_texts) > 0
    for msg in log_texts:
        assert cand_name not in msg
        assert cand_email not in msg
