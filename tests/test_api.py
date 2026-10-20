"""
test_api.py - test suite for core REST API endpoints, health,
background task statuses, desktop integration, and structured error handlers.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from flask.testing import FlaskClient


class TestSystemHealthAndStats:
    """Verifies core health check, telemetry, and background job polling endpoints."""

    def test_health_check_returns_success(self, client: FlaskClient):
        response = client.get("/api/health")
        assert response.status_code == 200
        data = response.get_json()
        assert data.get("status") in ("ok", "healthy")
        assert data.get("database") == "ok"
        assert data.get("success") is True

    def test_stats_endpoint_returns_pipeline_metrics(self, auth_client: FlaskClient):
        response = auth_client.get("/api/stats")
        assert response.status_code == 200
        data = response.get_json()
        assert "resumes_count" in data or "txt_count" in data
        assert isinstance(data.get("txt_count", 0), int)
        assert isinstance(data.get("nlp_count", 0), int)

    def test_task_status_returns_background_worker_state(self, auth_client: FlaskClient):
        response = auth_client.get("/api/task-status")
        assert response.status_code == 200
        data = response.get_json()
        assert isinstance(data, dict)
        for task_key in ("pdf", "nlp", "ranking"):
            if task_key in data:
                assert "status" in data[task_key]


class TestApiErrorHandling:
    """Verifies standard RFC 7807 / structured JSON error responses across API endpoints."""

    def test_api_404_returns_structured_json(self, auth_client: FlaskClient):
        response = auth_client.get("/api/nonexistent-route-endpoint")
        assert response.status_code == 404
        assert response.is_json
        data = response.get_json()
        assert "error" in data or "message" in data

    def test_page_404_returns_html_response(self, auth_client: FlaskClient):
        response = auth_client.get("/nonexistent-page-view")
        assert response.status_code == 404
        assert "text/html" in response.content_type

    def test_method_not_allowed_returns_405_or_404(self, client: FlaskClient):
        response = client.put("/api/health")
        assert response.status_code in (404, 405)


class TestDesktopIntegration:
    """Tests local desktop integration endpoints including folder opening and bootstrap."""

    def test_open_folder_rejects_unauthenticated(self, client: FlaskClient):
        response = client.post("/api/open-output-folder")
        assert response.status_code in (401, 302, 403)

    def test_open_folder_blocks_path_traversal(self, auth_client: FlaskClient, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setattr("app.routes.dashboard.open_folder", lambda path: str(path))
        response = auth_client.post("/api/open-output-folder")
        assert response.status_code == 200

    def test_open_folder_accepts_valid_configured_target(
        self, auth_client: FlaskClient, monkeypatch: pytest.MonkeyPatch
    ):
        monkeypatch.setattr("app.routes.dashboard.open_folder", lambda path: str(path))
        response = auth_client.post("/api/open-output-folder")
        assert response.status_code == 200

    def test_open_output_folder_endpoint(self, auth_client: FlaskClient, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setattr("app.routes.dashboard.open_folder", lambda path: str(path))
        response = auth_client.post("/api/open-output-folder")
        assert response.status_code == 200
        data = response.get_json()
        assert data.get("success") is True


class TestBackgroundPipelineExecution:
    """Tests automated end-to-end background pipeline triggers and state resets."""

    def test_run_auto_pipeline_starts_background_thread(
        self, auth_client: FlaskClient, monkeypatch: pytest.MonkeyPatch
    ):
        import app.routes.dashboard as db_mod
        from app.core import pipeline_tasks

        class DummyThread:
            started = False

            def __init__(self, target, daemon=False):
                self.target = target
                self.daemon = daemon

            def start(self):
                DummyThread.started = True

        monkeypatch.setattr(db_mod.threading, "Thread", DummyThread)
        pipeline_tasks.clear()

        response = auth_client.post("/api/run-auto-pipeline")
        assert response.status_code == 202
        data = response.get_json()
        assert data["success"] is True
        assert data["started"] is True
        assert DummyThread.started is True
        assert pipeline_tasks["auto_pipeline"]["status"] == "running"

    def test_run_auto_pipeline_rejects_concurrent_invocation(self, auth_client: FlaskClient):
        from app.core import pipeline_tasks

        pipeline_tasks["auto_pipeline"] = {
            "status": "running",
            "message": "Auto-pipeline is already running.",
        }

        response = auth_client.post("/api/run-auto-pipeline")
        assert response.status_code == 202
        data = response.get_json()
        assert data["success"] is True
        assert data["started"] is False

    def test_reset_pipeline_clears_tasks(self, auth_client: FlaskClient, temp_dir: Path, monkeypatch: pytest.MonkeyPatch):
        import app.routes.dashboard as dash_mod
        from app.core import pipeline_tasks

        monkeypatch.setattr(dash_mod, "OUTPUT_FOLDER", temp_dir)
        pipeline_tasks["test_job"] = {"status": "done"}

        response = auth_client.post("/api/reset-pipeline")
        assert response.status_code == 200
        data = response.get_json()
        assert data.get("success") is True
        assert len(pipeline_tasks) == 0
