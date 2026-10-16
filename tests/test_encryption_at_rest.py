import io

import fitz

from app import create_app
from app.database import (
    get_all_candidates,
    get_candidate_by_name,
    get_connection,
    init_db,
    log_email,
    upsert_candidate,
)
from app.routes import upload as upload_routes
from src.pdf_to_txt import extract_direct_text, process_file
from src.security import decrypt_bytes, decrypt_secret, encrypt_bytes


def test_database_email_pii_encryption_at_rest(tmp_path, monkeypatch):
    test_db = tmp_path / "test_enc.db"
    monkeypatch.setattr("app.database.DB_PATH", test_db)
    init_db()

    from app.database import create_run
    run_id = create_run("ranking")
    cand_name = "Jane Doe"
    cand_email = "jane.doe@example.com"

    cid = upsert_candidate(run_id=run_id, name=cand_name, email=cand_email, score=85)
    assert cid > 0

    # 1. Verify in raw SQLite that email is stored encrypted with ENC: prefix
    conn = get_connection()
    try:
        raw_row = conn.execute("SELECT email FROM candidates WHERE id=?", (cid,)).fetchone()
        assert raw_row is not None
        raw_email = raw_row["email"]
        assert raw_email.startswith("ENC:")
        assert raw_email != cand_email
        assert decrypt_secret(raw_email) == cand_email
    finally:
        conn.close()

    # 2. Verify get_candidate_by_name returns decrypted plaintext
    cand = get_candidate_by_name(cand_name, run_id=run_id)
    assert cand is not None
    assert cand["email"] == cand_email

    # 3. Verify get_all_candidates returns decrypted plaintext
    all_cands = get_all_candidates(run_id=run_id)
    assert len(all_cands) == 1
    assert all_cands[0]["email"] == cand_email

    # 4. Verify log_email encrypts recipient at rest
    log_email(run_id=run_id, schedule_id=None, recipient=cand_email, subject="Invitation")
    conn = get_connection()
    try:
        raw_log = conn.execute("SELECT recipient FROM email_log WHERE run_id=?", (run_id,)).fetchone()
        assert raw_log is not None
        assert raw_log["recipient"].startswith("ENC:")
        assert decrypt_secret(raw_log["recipient"]) == cand_email
    finally:
        conn.close()


def test_resume_upload_and_view_encryption(tmp_path, monkeypatch):
    resumes_dir = tmp_path / "resumes"
    resumes_dir.mkdir()
    monkeypatch.setattr(upload_routes, "RESUMES_FOLDER", resumes_dir)

    app = create_app()
    client = app.test_client()

    with client.session_transaction() as sess:
        sess["logged_in"] = True
        sess["desktop_session"] = True
        sess["_csrf_token"] = "enc-test-csrf"
    client.environ_base["HTTP_X_CSRF_TOKEN"] = "enc-test-csrf"

    pdf_payload = b"%PDF-1.4 sample encrypted resume payload"
    resp = client.post(
        "/api/upload",
        data={"resumes": [(io.BytesIO(pdf_payload), "jane_resume.pdf")]},
        content_type="multipart/form-data",
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert "jane_resume.pdf" in data["saved"]

    saved_file = resumes_dir / "jane_resume.pdf"
    assert saved_file.exists()
    disk_bytes = saved_file.read_bytes()
    assert disk_bytes.startswith(b"ARS_ENC:")
    assert disk_bytes != pdf_payload
    assert decrypt_bytes(disk_bytes) == pdf_payload

    # View resume via HR endpoint
    view_resp = client.get("/api/view-resume/jane_resume.pdf")
    assert view_resp.status_code == 200
    assert view_resp.data == pdf_payload


def test_pdf_processing_with_encrypted_files(tmp_path):
    # Create a real PDF with fitz
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Jane Doe - Python Developer with 5 years experience in machine learning.")
    pdf_bytes = doc.tobytes()
    doc.close()

    # Encrypt the PDF bytes and write to disk
    enc_pdf = tmp_path / "jane_encrypted.pdf"
    enc_pdf.write_bytes(encrypt_bytes(pdf_bytes))

    # Test extract_direct_text on encrypted file path
    extracted = extract_direct_text(str(enc_pdf))
    assert "Jane Doe" in extracted
    assert "Python Developer" in extracted

    # Test process_file converts encrypted PDF to text
    out_dir = tmp_path / "txt_output"
    success = process_file(enc_pdf, out_dir)
    assert success is True
    out_txt = out_dir / "jane_encrypted.txt"
    assert out_txt.exists()
    content = out_txt.read_text(encoding="utf-8")
    assert "Jane Doe" in content
