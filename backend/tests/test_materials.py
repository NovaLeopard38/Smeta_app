def test_create_material(client):
    res = client.post(
        "/materials",
        json={
            "name": "IP Camera DS-2CD2143",
            "unit": "pcs",
            "price": 12500.0,
            "source": "Hikvision",
            "characteristics": "4MP, IR 30m",
            "item_type": "equipment",
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert "id" in data
    assert data["name"] == "IP Camera DS-2CD2143"


def test_get_materials(client):
    # Ensure at least one material exists
    client.post(
        "/materials",
        json={"name": "Cable UTP Cat5e", "unit": "m", "price": 25.0, "source": "local", "characteristics": "", "item_type": "equipment"},
    )
    res = client.get("/materials")
    assert res.status_code == 200
    data = res.json()
    assert "items" in data
    assert "total" in data
    assert data["total"] > 0


def test_search_materials(client):
    client.post(
        "/materials",
        json={"name": "SearchableXYZ Widget", "unit": "pcs", "price": 100.0, "source": "", "characteristics": "", "item_type": "equipment"},
    )
    res = client.get("/materials", params={"q": "SearchableXYZ"})
    assert res.status_code == 200
    data = res.json()
    assert data["total"] >= 1
    names = [item["name"] for item in data["items"]]
    assert any("SearchableXYZ" in n for n in names)


def test_update_material(client, admin_headers):
    create_res = client.post(
        "/materials",
        json={"name": "Update Target", "unit": "pcs", "price": 500.0, "source": "", "characteristics": "", "item_type": "equipment"},
    )
    mat_id = create_res.json()["id"]
    res = client.patch(
        f"/materials/{mat_id}",
        json={"price": 777.0},
        headers=admin_headers,
    )
    assert res.status_code == 200
    assert res.json()["price"] == 777.0


def test_delete_material(client, admin_headers):
    create_res = client.post(
        "/materials",
        json={"name": "Delete Target", "unit": "pcs", "price": 100.0, "source": "", "characteristics": "", "item_type": "equipment"},
    )
    mat_id = create_res.json()["id"]
    res = client.delete(f"/materials/{mat_id}", headers=admin_headers)
    assert res.status_code == 200
    assert res.json()["status"] == "ok"
    assert res.json()["deleted"] == mat_id
