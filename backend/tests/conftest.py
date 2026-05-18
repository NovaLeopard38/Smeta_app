"""Pytest fixtures for Smeta backend tests."""
import os
import sys
import pytest

# Ensure backend is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("AUTH_SECRET", "test-secret-key-for-tests")
os.environ.setdefault("ADMIN_EMAIL", "test-admin@test.com")
os.environ.setdefault("ADMIN_PASSWORD", "testpass123")
os.environ.setdefault("DATABASE_URL", "sqlite:///./test_smeta.db")


@pytest.fixture(scope="session")
def app():
    """Create FastAPI test app."""
    from app import app as _app
    return _app


@pytest.fixture
def client(app):
    """Create test client."""
    from fastapi.testclient import TestClient
    return TestClient(app)


@pytest.fixture
def admin_token(client):
    """Login as admin and return token."""
    resp = client.post("/auth/login", json={
        "email": os.environ["ADMIN_EMAIL"],
        "password": os.environ["ADMIN_PASSWORD"],
    })
    if resp.status_code == 200:
        return resp.json()["access_token"]
    # Register if first time
    resp = client.post("/auth/register", json={
        "email": "testuser@test.com",
        "password": "testpass123",
    })
    return resp.json().get("access_token", "")


@pytest.fixture
def auth_headers(admin_token):
    """Return authorization headers."""
    return {"Authorization": f"Bearer {admin_token}"}
