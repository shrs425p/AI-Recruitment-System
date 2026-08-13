from flask import Flask

import app.routes.dashboard as dashboard_routes
import config
from app.core import pipeline_tasks


class DummyThread:
    started = False

    def __init__(self, target, daemon=False):
        self.target = target
        self.daemon = daemon

    def start(self):
        DummyThread.started = True


def test_auto_pipeline_starts_background_job(monkeypatch):
    monkeypatch.setattr(config, "LOGIN_ENABLED", False, raising=False)
    monkeypatch.setattr(dashboard_routes.threading, "Thread", DummyThread)
    pipeline_tasks.clear()
    DummyThread.started = False

    app = Flask(__name__)
    app.secret_key = "mock_test_key_for_flask"
    dashboard_routes.register_dashboard_routes(app)

    from app.auth import generate_jwt
    with app.app_context():
        token = generate_jwt(1, "admin", "admin")

    client = app.test_client()
    with client.session_transaction() as sess:
        sess["logged_in"] = True
        sess["jwt_token"] = token


    response = client.post("/api/run-auto-pipeline")

    assert response.status_code == 202

    data = response.get_json()
    assert data["success"] is True
    assert data["started"] is True
    assert DummyThread.started is True
    assert pipeline_tasks["auto_pipeline"]["status"] == "running"
