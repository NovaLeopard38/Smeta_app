import uuid


def test_register_returns_token(client):
    email = f"reg_{uuid.uuid4().hex[:8]}@test.com"
    res = client.post("/auth/register", json={"email": email, "password": "testpass123"})
    assert res.status_code == 200
    data = res.json()
    assert "access_token" in data
    assert data["access_token"]


def test_register_duplicate_email(client):
    email = f"dup_{uuid.uuid4().hex[:8]}@test.com"
    res1 = client.post("/auth/register", json={"email": email, "password": "testpass123"})
    assert res1.status_code == 200
    res2 = client.post("/auth/register", json={"email": email, "password": "testpass123"})
    assert res2.status_code == 409


def test_login_correct_credentials(client):
    email = f"login_{uuid.uuid4().hex[:8]}@test.com"
    client.post("/auth/register", json={"email": email, "password": "mypassword1"})
    res = client.post("/auth/login", json={"email": email, "password": "mypassword1"})
    assert res.status_code == 200
    assert "access_token" in res.json()


def test_login_wrong_password(client):
    email = f"wrong_{uuid.uuid4().hex[:8]}@test.com"
    client.post("/auth/register", json={"email": email, "password": "correct1"})
    res = client.post("/auth/login", json={"email": email, "password": "incorrect"})
    assert res.status_code == 401


def test_me_without_token(client):
    res = client.get("/auth/me")
    assert res.status_code == 401


def test_me_with_valid_token(client):
    email = f"me_{uuid.uuid4().hex[:8]}@test.com"
    reg = client.post("/auth/register", json={"email": email, "password": "testpass123"})
    token = reg.json()["access_token"]
    res = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    assert res.json()["email"] == email
