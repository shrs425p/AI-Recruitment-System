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
    dashboard_routes.register_dashboard_routes(app)

    response = app.test_client().post("/api/open-output-folder")

    assert response.status_code == 200
    assert response.get_json()["success"] is True
    assert launched == [dashboard_routes.OUTPUT_FOLDER]
