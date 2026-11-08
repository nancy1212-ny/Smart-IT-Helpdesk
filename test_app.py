from app import app


def test_home_page():
    app.config["TESTING"] = True

    client = app.test_client()

    response = client.get("/")

    assert response.status_code == 200


def test_dashboard_requires_login():
    app.config["TESTING"] = True

    client = app.test_client()

    response = client.get("/dashboard")

    assert response.status_code == 302


def test_login_page_loads():
    app.config["TESTING"] = True

    client = app.test_client()

    response = client.get("/")

    assert b"Login" in response.data