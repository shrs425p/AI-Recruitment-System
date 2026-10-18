"""
test_resume.py - test suite for resume parsing, PDF extraction,
Microsoft Word (.docx) extraction, upload validation whitelisting, and file security.
"""

from __future__ import annotations

import io
from pathlib import Path

import pytest
from flask.testing import FlaskClient

import app.routes.upload as upload_mod
from src.pdf_to_txt import extract_direct_text, extract_docx_text, process_file


class TestDocumentTextExtraction:
    """Tests raw text extraction from PDF and Word (.docx) document formats."""

    def test_docx_extract_valid_file(self, temp_dir: Path, sample_docx_bytes: bytes):
        docx_path = temp_dir / "sample_resume.docx"
        docx_path.write_bytes(sample_docx_bytes)

        text = extract_docx_text(str(docx_path))
        assert "Jane Doe" in text
        assert "Senior Software Engineer" in text
        assert "Python" in text
        assert "Kubernetes" in text

    def test_docx_extract_nonexistent_file_returns_empty_or_fails_gracefully(self):
        text = extract_docx_text("nonexistent_path_to_resume.docx")
        assert text == ""

    def test_docx_extract_corrupted_file_handles_gracefully(self, temp_dir: Path):
        bad_docx = temp_dir / "corrupted.docx"
        bad_docx.write_bytes(b"PK\x03\x04corrupted_zip_payload_not_a_valid_docx")

        text = extract_docx_text(str(bad_docx))
        assert isinstance(text, str)
        assert text == ""

    def test_process_file_pipeline_extracts_docx(self, temp_dir: Path, sample_docx_bytes: bytes):
        docx_path = temp_dir / "candidate_test.docx"
        docx_path.write_bytes(sample_docx_bytes)
        out_dir = temp_dir / "txt_out"
        out_dir.mkdir(parents=True, exist_ok=True)

        success = process_file(docx_path, out_dir)
        assert success is True
        txt_file = out_dir / f"{docx_path.stem}.txt"
        assert txt_file.exists()
        content = txt_file.read_text(encoding="utf-8")
        assert "Jane Doe" in content

    def test_pdf_extract_corrupted_file_handles_gracefully(self, temp_dir: Path):
        bad_pdf = temp_dir / "broken.pdf"
        bad_pdf.write_bytes(b"not_a_valid_pdf_file_header")

        text = extract_direct_text(str(bad_pdf))
        assert text == ""


class TestResumeUploadSecurityAndWhitelisting:
    """Tests resume upload endpoints, file format whitelisting, and duplicate handling."""

    def test_upload_accepts_pdf_and_docx(
        self,
        auth_client: FlaskClient,
        temp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
        sample_docx_bytes: bytes,
        sample_pdf_bytes: bytes,
    ):
        resumes_dir = temp_dir / "resumes"
        resumes_dir.mkdir(parents=True, exist_ok=True)
        monkeypatch.setattr(upload_mod, "RESUMES_FOLDER", resumes_dir)

        response = auth_client.post(
            "/api/upload",
            data={
                "resumes": [
                    (io.BytesIO(sample_pdf_bytes), "alice_resume.pdf"),
                    (io.BytesIO(sample_docx_bytes), "bob_resume.docx"),
                ]
            },
            content_type="multipart/form-data",
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data["count"] == 2
        assert "alice_resume.pdf" in data["saved"]
        assert "bob_resume.docx" in data["saved"]
        assert len(data.get("rejected", [])) == 0

    def test_upload_strictly_rejects_unapproved_extensions(
        self, auth_client: FlaskClient, temp_dir: Path, monkeypatch: pytest.MonkeyPatch
    ):
        resumes_dir = temp_dir / "resumes"
        resumes_dir.mkdir(parents=True, exist_ok=True)
        monkeypatch.setattr(upload_mod, "RESUMES_FOLDER", resumes_dir)

        response = auth_client.post(
            "/api/upload",
            data={
                "resumes": [
                    (io.BytesIO(b"malicious script"), "payload.exe"),
                    (io.BytesIO(b"malicious shell"), "script.sh"),
                    (io.BytesIO(b"archive"), "resumes.zip"),
                ]
            },
            content_type="multipart/form-data",
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data["count"] == 0
        assert len(data["rejected"]) == 3

    def test_upload_preserves_existing_files_and_renames_duplicates(
        self, auth_client: FlaskClient, temp_dir: Path, monkeypatch: pytest.MonkeyPatch, sample_pdf_bytes: bytes
    ):
        resumes_dir = temp_dir / "resumes"
        resumes_dir.mkdir(parents=True, exist_ok=True)
        (resumes_dir / "resume.pdf").write_bytes(b"existing original")
        monkeypatch.setattr(upload_mod, "RESUMES_FOLDER", resumes_dir)

        response = auth_client.post(
            "/api/upload",
            data={"resumes": [(io.BytesIO(sample_pdf_bytes), "resume.pdf")]},
            content_type="multipart/form-data",
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data["count"] == 1
        assert data["saved"] == ["resume_1.pdf"]
        assert (resumes_dir / "resume.pdf").read_bytes() == b"existing original"
        assert (resumes_dir / "resume_1.pdf").exists()

    def test_view_resume_requires_hr_auth(self, client: FlaskClient):
        response = client.get("/api/view-resume/test.pdf")
        assert response.status_code in (401, 302, 403)

    def test_view_resume_nonexistent_returns_404(
        self, auth_client: FlaskClient, temp_dir: Path, monkeypatch: pytest.MonkeyPatch
    ):
        resumes_dir = temp_dir / "resumes"
        resumes_dir.mkdir(parents=True, exist_ok=True)
        monkeypatch.setattr(upload_mod, "RESUMES_FOLDER", resumes_dir)

        response = auth_client.get("/api/view-resume/nonexistent_file.pdf")
        assert response.status_code == 404
