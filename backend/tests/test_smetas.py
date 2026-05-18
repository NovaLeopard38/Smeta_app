"""Tests for smeta CRUD."""
import pytest


def test_create_smeta(client, auth_headers):
    """Test creating a smeta."""
    resp = client.post("/smetas", json={
        "name": "Тестовая смета",
    }, headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "Тестовая смета"
    assert data["total"] == 0


def test_list_smetas(client, auth_headers):
    """Test listing smetas."""
    client.post("/smetas", json={"name": "Для списка"}, headers=auth_headers)
    resp = client.get("/smetas", headers=auth_headers)
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)
    assert len(resp.json()) >= 1


def test_add_item_to_smeta(client, auth_headers):
    """Test adding an item to a smeta."""
    smeta = client.post("/smetas", json={"name": "С позициями"}, headers=auth_headers).json()
    resp = client.post(f"/smetas/{smeta['id']}/items", json={
        "name": "Камера тестовая",
        "section": "Оборудование",
        "unit": "шт",
        "quantity": 4,
        "unit_price": 3000,
    }, headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["items"]) >= 1
    assert data["total"] > 0


def test_delete_smeta(client, auth_headers):
    """Test deleting a smeta."""
    smeta = client.post("/smetas", json={"name": "Для удаления"}, headers=auth_headers).json()
    resp = client.delete(f"/smetas/{smeta['id']}", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_branch_smeta(client, auth_headers):
    """Test branching a smeta."""
    smeta = client.post("/smetas", json={"name": "Оригинал"}, headers=auth_headers).json()
    resp = client.post(f"/smetas/{smeta['id']}/branch", headers=auth_headers)
    assert resp.status_code == 200
    branch = resp.json()
    assert "вариант" in branch["name"]
    assert branch["parent_id"] == smeta["id"]
