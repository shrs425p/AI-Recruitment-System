from app import create_app
from app.auth import generate_jwt


def test_api_404_returns_json():
    app = create_app()
    client = app.test_client()

    with app.app_context():
        token = generate_jwt(user_id=1, username="admin", role="admin")
    with client.session_transaction() as sess:
        sess["logged_in"] = True
        sess["jwt_token"] = token

    response = client.get("/api/nonexistent-route")
    assert response.status_code == 404
    assert response.is_json
    data = response.get_json()
    assert "error" in data


def test_web_404_returns_response():
    app = create_app()
    client = app.test_client()

    with app.app_context():
        token = generate_jwt(user_id=1, username="admin", role="admin")
    with client.session_transaction() as sess:
        sess["logged_in"] = True
        sess["jwt_token"] = token


    response = client.get("/nonexistent-page")
    assert response.status_code == 404

