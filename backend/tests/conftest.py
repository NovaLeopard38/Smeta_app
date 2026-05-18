import os
import sys

# Set test environment BEFORE any app imports
os.environ["AUTH_SECRET"] = "test-secret"
os.environ["ADMIN_EMAIL"] = "admin@test.com"
os.environ["ADMIN_PASSWORD"] = "testpass123"
os.environ["DATABASE_URL"] = "sqlite:///./test_smeta.db"

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="session", autouse=True)
def cleanup_test_db():
    """Remove test DB before and after test session."""
    db_path = "./test_smeta.db"
    if os.path.exists(db_path):
        os.remove(db_path)
    yield
    if os.path.exists(db_path):
        os.remove(db_path)


@pytest.fixture
def client():
    from app import app
    with TestClient(app) as c:
        yield c


@pytest.fixture
def auth_headers(client):
    """Register a unique user and return auth headers."""
    import uuid
    email = f"testuser_{uuid.uuid4().hex[:8]}@test.com"
    res = client.post("/auth/register", json={"email": email, "password": "testpass123"})
    assert res.status_code == 200
    token = res.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def admin_headers(client):
    """Login as admin and return auth headers."""
    res = client.post("/auth/login", json={"email": "admin@test.com", "password": "testpass123"})
    assert res.status_code == 200
    token = res.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
