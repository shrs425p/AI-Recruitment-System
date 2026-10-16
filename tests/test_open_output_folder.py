from flask import Flask

import app.routes.dashboard as dashboard_routes


def test_open_output_folder_uses_folder_opener(monkeypatch):
    launched = []

    monkeypatch.setattr(
        dashboard_routes,
        "open_folder",
        lambda folder: launched.append(folder) or str(folder.resolve()),
    )

    app = Flask(__name__)
    app.secret_key = "test-secret"
    dashboard_routes.register_dashboard_routes(app)

    with app.test_client() as client:
        with client.session_transaction() as sess:
            sess["logged_in"] = True
            sess["desktop_session"] = True
        response = client.post("/api/open-output-folder")

    assert response.status_code == 200
    assert response.get_json()["success"] is True
    assert launched == [dashboard_routes.OUTPUT_FOLDER]
