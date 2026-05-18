"""Tests for materials CRUD."""
import pytest


def test_create_material(client, auth_headers):
    """Test creating a material."""
    resp = client.post("/materials", json={
        "name": "Камера IP тестовая",
        "unit": "шт",
        "price": 5000.0,
        "source": "Тест",
        "characteristics": "2 Мп, PoE",
        "item_type": "equipment",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "Камера IP тестовая"
    assert data["price"] == 5000.0


def test_get_materials(client, auth_headers):
    """Test listing materials."""
    # Create one first
    client.post("/materials", json={
        "name": "Тестовый материал для списка",
        "unit": "м",
        "price": 100.0,
        "source": "Тест",
    })
    resp = client.get("/materials", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert data["total"] >= 1


def test_search_materials(client, auth_headers):
    """Test material search."""
    client.post("/materials", json={
        "name": "Уникальный кабель UTP для поиска",
        "unit": "м",
        "price": 25.0,
        "source": "Тест",
    })
    resp = client.get("/materials?q=уникальный+кабель", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 1
    assert "уникальный" in data["items"][0]["name"].lower()
