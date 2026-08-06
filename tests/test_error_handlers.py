from app import create_app


def test_api_404_returns_json():
    app = create_app()
    client = app.test_client()

    # Inject authenticated session so auth guard does not intercept before 404
    with client.session_transaction() as sess:
        sess["logged_in"] = True

    response = client.get("/api/nonexistent-route")
    assert response.status_code == 404
    assert response.is_json
    data = response.get_json()
    assert "error" in data
    assert data["code"] == 404


def test_web_404_returns_response():
    app = create_app()
    client = app.test_client()

    # Inject authenticated session so auth guard does not intercept before 404
    with client.session_transaction() as sess:
        sess["logged_in"] = True

    response = client.get("/nonexistent-page")
    assert response.status_code == 404
    assert b"404" in response.data or b"not found" in response.data.lower()
