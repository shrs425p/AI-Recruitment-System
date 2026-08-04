import app.routes.ranking as ranking_routes
import app.routes.upload as upload_routes
from app import create_app
from app.database import (
    delete_job_template,
    get_all_job_templates,
    init_db,
    save_job_template,
)
from src.email_sender import send_interview_email


def test_job_template_db_crud(tmp_path, monkeypatch):
    test_db = tmp_path / "test_templates.db"
    monkeypatch.setattr("app.database.DB_PATH", test_db)
    init_db()

    template_id = save_job_template("Python Engineer", "Must know Python, Flask, and SQL.")
    assert isinstance(template_id, int)

    templates = get_all_job_templates()
    assert len(templates) == 1
    assert templates[0]["title"] == "Python Engineer"
    assert "Flask" in templates[0]["jd_text"]

    delete_job_template(template_id)
    assert len(get_all_job_templates()) == 0


def test_job_template_api_endpoints(tmp_path, monkeypatch):
    test_db = tmp_path / "test_api_templates.db"
    monkeypatch.setattr("app.database.DB_PATH", test_db)
    init_db()

    app = create_app()
    ranking_routes.register_ranking_routes(app)
    client = app.test_client()

    # POST create template
    resp = client.post(
        "/api/job-templates",
        json={"title": "Data Analyst", "jd_text": "SQL, Python, PowerBI"},
    )
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["success"] is True
    template_id = data["id"]

    # GET templates list
    resp_get = client.get("/api/job-templates")
    assert resp_get.status_code == 200
    assert len(resp_get.get_json()) == 1

    # DELETE template
    resp_del = client.delete(f"/api/job-templates/{template_id}")
    assert resp_del.status_code == 200


def test_view_resume_security(tmp_path, monkeypatch):
    resumes_dir = tmp_path / "resumes"
    resumes_dir.mkdir()
    (resumes_dir / "sample.pdf").write_text("dummy pdf content", encoding="utf-8")

    monkeypatch.setattr(upload_routes, "RESUMES_FOLDER", resumes_dir)

    app = create_app()
    upload_routes.register_upload_routes(app)
    client = app.test_client()

    # Valid request
    valid_resp = client.get("/api/view-resume/sample.pdf")
    assert valid_resp.status_code == 200

    # Nonexistent request
    missing_resp = client.get("/api/view-resume/missing.pdf")
    assert missing_resp.status_code == 404


def test_email_template_customization(monkeypatch):
    import config
    monkeypatch.setattr(config, "EMAIL_TEMPLATE_SUBJECT", "Role: {job_title} - {candidate_name}")
    monkeypatch.setattr(config, "EMAIL_TEMPLATE_BODY", "Hello {candidate_name}, welcome to {company}.")

    # Mock smtplib
    class DummySMTP:
        def __init__(self, host, port, timeout=10):
            pass
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def starttls(self):
            pass
        def login(self, u, p):
            pass
        def send_message(self, msg):
            assert "Role: Engineer - Jane Doe" in msg["Subject"]

    monkeypatch.setattr("smtplib.SMTP", DummySMTP)

    success, err = send_interview_email(
        smtp_host="localhost",
        smtp_port=587,
        smtp_email="hr@example.com",
        smtp_password="pass",
        recipient_email="jane@example.com",
        candidate_name="Jane Doe",
        job_title="Engineer",
        interview_slot="2026-08-10 10:00",
        hr_name="HR Manager",
        company="Acme Corp",
    )
    assert success is True


def test_save_config_creates_parent_directories():
    import config
    import main
    main._save_config(config)
    assert (main.APP_DATA_DIR / "config.py").exists()
