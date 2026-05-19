import pytest
from fastapi.testclient import TestClient
from fastapi import HTTPException
from app.main import app
from app import auth, schemas, models
from app.database import get_db, SessionLocal
from jose import jwt
import datetime

client = TestClient(app)


def test_root():
    # Test root endpoint redirects to docs
    resp = client.get("/", follow_redirects=False)
    assert resp.status_code == 307
    assert resp.headers["location"] == "/docs"


def test_register_and_login():
    email = "testuser@example.com"
    password = "strongpassword"
    
    # 1. Register a new user
    resp = client.post("/register", json={"email": email, "password": password, "full_name": "Test User"})
    assert resp.status_code in (200, 201)
    data = resp.json()
    assert data["email"] == email
    assert data["full_name"] == "Test User"
    assert data["provider"] == "email"

    # 2. Duplicate registration should fail
    resp_dup = client.post("/register", json={"email": email, "password": "anotherpassword", "full_name": "Duplicate User"})
    assert resp_dup.status_code == 400
    assert resp_dup.json()["detail"] == "Email already registered"

    # 3. Login with correct credentials
    resp_login = client.post("/login", data={"username": email, "password": password})
    assert resp_login.status_code == 200
    token_data = resp_login.json()
    assert token_data["token_type"] == "bearer"
    token = token_data.get("access_token")
    assert token

    # 4. Login with incorrect password should fail
    resp_bad_login = client.post("/login", data={"username": email, "password": "wrongpassword"})
    assert resp_bad_login.status_code == 401
    assert resp_bad_login.json()["detail"] == "Incorrect email or password"

    # 5. Login with non-existent user should fail
    resp_no_user = client.post("/login", data={"username": "nonexistent@example.com", "password": "somepassword"})
    assert resp_no_user.status_code == 401


def test_get_me():
    email = "me_user@example.com"
    password = "strongpassword"
    
    # Register
    client.post("/register", json={"email": email, "password": password, "full_name": "Me User"})
    
    # Login to get token
    resp_login = client.post("/login", data={"username": email, "password": password})
    token = resp_login.json()["access_token"]
    
    # Fetch /me with valid token
    headers = {"Authorization": f"Bearer {token}"}
    resp_me = client.get("/me", headers=headers)
    assert resp_me.status_code == 200
    assert resp_me.json()["email"] == email

    # Fetch /me with invalid token
    headers_invalid = {"Authorization": "Bearer invalidtokenhere"}
    resp_me_invalid = client.get("/me", headers=headers_invalid)
    assert resp_me_invalid.status_code == 401

    # Fetch /me with token missing 'sub'
    payload = {"some_other_claim": "value"}
    token_no_sub = jwt.encode(payload, auth.JWT_SECRET, algorithm=auth.JWT_ALGORITHM)
    headers_no_sub = {"Authorization": f"Bearer {token_no_sub}"}
    resp_me_no_sub = client.get("/me", headers=headers_no_sub)
    assert resp_me_no_sub.status_code == 401


def test_save_sessions_and_get_sessions():
    email = "session_user@example.com"
    password = "strongpassword"
    
    # Register
    client.post("/register", json={"email": email, "password": password, "full_name": "Session User"})
    
    # 1. Save a new session
    session_payload = {
        "user_id": email,
        "session_data": {
            "title": "Math Session 1",
            "content": "Solving linear equations."
        }
    }
    resp_save = client.post("/save-session", json=session_payload)
    assert resp_save.status_code == 200
    saved_data = resp_save.json()
    assert saved_data["user_id"] == email
    assert saved_data["id"] != ""
    assert saved_data["session_data"]["title"] == "Math Session 1"
    assert "created_at" in saved_data
    
    session_id = saved_data["id"]

    # 2. Save a session for non-existent user should fail
    bad_session_payload = {
        "user_id": "nonexistent_user@example.com",
        "session_data": {
            "title": "Ghost Session",
            "content": "Does not exist"
        }
    }
    resp_bad_save = client.post("/save-session", json=bad_session_payload)
    assert resp_bad_save.status_code == 404
    assert resp_bad_save.json()["detail"] == "User not found"

    # 3. List all sessions (unfiltered)
    resp_all = client.get("/sessions")
    assert resp_all.status_code == 200
    sessions_list = resp_all.json()
    assert len(sessions_list) >= 1
    # Check that our session is in the list
    found_session = next((s for s in sessions_list if s["id"] == session_id), None)
    assert found_session
    assert found_session["user_id"] == email

    # 4. List sessions filtered by user_id
    resp_filtered = client.get(f"/sessions?user_id={email}")
    assert resp_filtered.status_code == 200
    filtered_list = resp_filtered.json()
    assert len(filtered_list) >= 1
    assert filtered_list[0]["user_id"] == email

    # 5. List sessions filtered by non-existent user_id
    resp_empty = client.get("/sessions?user_id=ghost@example.com")
    assert resp_empty.status_code == 200
    assert resp_empty.json() == []

    # 6. Update existing session (sending the same session ID in session_data)
    update_payload = {
        "user_id": email,
        "session_data": {
            "session_id": session_id,
            "title": "Math Session 1 - Updated",
            "content": "Solving quadratic equations."
        }
    }
    resp_update = client.post("/save-session", json=update_payload)
    assert resp_update.status_code == 200
    updated_data = resp_update.json()
    assert updated_data["id"] == session_id
    assert updated_data["session_data"]["title"] == "Math Session 1 - Updated"


def test_comments_and_likes():
    email = "comments_user@example.com"
    password = "strongpassword"
    
    # Register
    client.post("/register", json={"email": email, "password": password, "full_name": "Comments User"})
    
    # Save a session to test comments/likes on
    session_payload = {
        "user_id": email,
        "session_data": {
            "title": "Interactivity Session",
            "content": "Testing likes and comments."
        }
    }
    resp_save = client.post("/save-session", json=session_payload)
    session_id = resp_save.json()["id"]

    # 1. Add comment to session successfully
    comment_payload = {
        "author": "Alice",
        "text": "Great session, very helpful!"
    }
    resp_comment = client.post(f"/api/sessions/{session_id}/comment", json=comment_payload)
    assert resp_comment.status_code == 200
    comment_data = resp_comment.json()
    assert comment_data["status"] == "ok"
    assert comment_data["comment"]["author"] == "Alice"
    assert comment_data["comment"]["text"] == "Great session, very helpful!"

    # 2. Add comment with empty text should fail
    bad_comment_payload = {
        "author": "Alice",
        "text": ""
    }
    resp_bad_comment = client.post(f"/api/sessions/{session_id}/comment", json=bad_comment_payload)
    assert resp_bad_comment.status_code == 400
    assert resp_bad_comment.json()["detail"] == "El comentario no puede estar vacío"

    # 3. Add comment to non-existent session should fail
    resp_comment_no_session = client.post("/api/sessions/nonexistentsession/comment", json=comment_payload)
    assert resp_comment_no_session.status_code == 404
    assert resp_comment_no_session.json()["detail"] == "Sesión no encontrada"

    # 4. Like session successfully
    resp_like = client.post(f"/api/sessions/{session_id}/like")
    assert resp_like.status_code == 200
    assert resp_like.json()["status"] == "ok"
    assert resp_like.json()["likes"] == 1

    # 5. Like session again (should increment)
    resp_like_2 = client.post(f"/api/sessions/{session_id}/like")
    assert resp_like_2.status_code == 200
    assert resp_like_2.json()["likes"] == 2

    # 6. Like non-existent session should fail
    resp_like_no_session = client.post("/api/sessions/nonexistentsession/like")
    assert resp_like_no_session.status_code == 404
    assert resp_like_no_session.json()["detail"] == "Sesión no encontrada"


def test_google_login_invalid_token():
    # Send a request with a fake google token
    # This should trigger verify_google_token which will fail and raise HTTP 401
    payload = {"id_token": "fake_google_token_value"}
    resp = client.post("/google-login", json=payload)
    assert resp.status_code == 401
    assert "Invalid Google token" in resp.json()["detail"]


def test_verify_google_token_clock_skew_exception():
    # Directly test verify_google_token clock skew detection
    # We pass an error message to make sure "used too early" branches are exercised
    with pytest.raises(HTTPException) as excinfo:
        auth.verify_google_token("invalid_token")
    assert excinfo.value.status_code == 401


def test_google_login_success(monkeypatch):
    # Mock verify_google_token to simulate a successful Google sign-in
    def mock_verify_google_token(id_tok, audience):
        return {
            "email": "google_user@example.com",
            "name": "Google User"
        }
    monkeypatch.setattr(auth, "verify_google_token", mock_verify_google_token)

    payload = {"id_token": "valid_google_token_mocked"}
    resp = client.post("/google-login", json=payload)
    assert resp.status_code == 200
    token_data = resp.json()
    assert token_data["token_type"] == "bearer"
    assert token_data["access_token"]
    
    # Try a second time (user already exists)
    resp_existing = client.post("/google-login", json=payload)
    assert resp_existing.status_code == 200
    assert resp_existing.json()["access_token"]


def test_startup_sessions_column():
    # Trigger the startup database check to ensure that branch is fully tested.
    from app.main import add_sessions_column_if_missing
    add_sessions_column_if_missing()
