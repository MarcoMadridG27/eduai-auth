from fastapi.testclient import TestClient
from app.main import app


client = TestClient(app)


def test_register_and_login():
    email = "testuser@example.com"
    password = "strongpassword"
    # cleanup DB not implemented; run tests on a fresh DB
    resp = client.post("/register", json={"email": email, "password": password, "full_name": "Test User"})
    assert resp.status_code in (200, 201)
    data = resp.json()
    assert data["email"] == email

    # login
    resp = client.post("/login", data={"username": email, "password": password})
    assert resp.status_code == 200
    token = resp.json().get("access_token")
    assert token
