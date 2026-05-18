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
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient


@pytest.fixture(scope="session", autouse=True)
def set_env():
    """Ensure env vars are set for the entire test session."""
    os.environ["AUTH_SECRET"] = "test-secret"
    os.environ["ADMIN_EMAIL"] = "admin@test.com"
    os.environ["ADMIN_PASSWORD"] = "testpass123"
    os.environ["DATABASE_URL"] = "sqlite:///./test_smeta.db"


@pytest.fixture(scope="session")
def test_engine():
    """Create test engine and tables once for the session."""
    engine = create_engine("sqlite:///./test_smeta.db", connect_args={"check_same_thread": False})
    from models import Base
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)
    engine.dispose()
    if os.path.exists("./test_smeta.db"):
        os.remove("./test_smeta.db")


@pytest.fixture
def db_session(test_engine):
    """Per-test session with transaction rollback for isolation."""
    connection = test_engine.connect()
    transaction = connection.begin()
    TestingSessionLocal = sessionmaker(bind=connection)
    session = TestingSessionLocal()
    yield session
    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
def client(db_session):
    """TestClient with overridden DB dependency."""
    from app import app
    from database import get_db

    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def auth_headers(client):
    """Register a unique user and return auth headers."""
    import uuid
    email = f"test_{uuid.uuid4().hex[:8]}@test.com"
    res = client.post("/auth/register", json={"email": email, "password": "testpass123"})
    assert res.status_code == 200, f"Registration failed: {res.text}"
    token = res.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def admin_headers(client):
    """Login as admin and return auth headers."""
    res = client.post("/auth/login", json={"email": "admin@test.com", "password": "testpass123"})
    assert res.status_code == 200, f"Admin login failed: {res.text}"
    token = res.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
