from flask import Flask

from app.routes.health import register_health_routes


def test_health_endpoint_reports_ok():
    app = Flask(__name__)
    register_health_routes(app)

    response = app.test_client().get("/api/health")

    assert response.status_code == 200
    data = response.get_json()
    assert data["success"] is True
    assert data["database"] == "ok"
