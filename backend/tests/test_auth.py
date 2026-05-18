"""Tests for authentication endpoints."""
import pytest


def test_root(client):
    """Test root endpoint returns 200."""
    resp = client.get("/")
    assert resp.status_code == 200
    assert "смет" in resp.json()["message"].lower() or "работает" in resp.json()["message"]


def test_register_new_user(client):
    """Test user registration."""
    resp = client.post("/auth/register", json={
        "email": "newuser@example.com",
        "password": "password123",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert data["user"]["email"] == "newuser@example.com"
    assert data["user"]["is_admin"] is False


def test_register_duplicate_user(client):
    """Test that registering duplicate email fails."""
    client.post("/auth/register", json={
        "email": "dupe@example.com",
        "password": "password123",
    })
    resp = client.post("/auth/register", json={
        "email": "dupe@example.com",
        "password": "another_password",
    })
    assert resp.status_code == 409


def test_login_wrong_password(client):
    """Test login with wrong password."""
    client.post("/auth/register", json={
        "email": "logintest@example.com",
        "password": "correct_password",
    })
    resp = client.post("/auth/login", json={
        "email": "logintest@example.com",
        "password": "wrong_password",
    })
    assert resp.status_code == 401


def test_login_correct_password(client):
    """Test login with correct password."""
    client.post("/auth/register", json={
        "email": "loginok@example.com",
        "password": "my_password",
    })
    resp = client.post("/auth/login", json={
        "email": "loginok@example.com",
        "password": "my_password",
    })
    assert resp.status_code == 200
    assert "access_token" in resp.json()


def test_me_unauthorized(client):
    """Test /auth/me without token."""
    resp = client.get("/auth/me")
    assert resp.status_code == 401


def test_me_with_token(client):
    """Test /auth/me with valid token."""
    reg = client.post("/auth/register", json={
        "email": "metest@example.com",
        "password": "password123",
    })
    token = reg.json()["access_token"]
    resp = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["email"] == "metest@example.com"
