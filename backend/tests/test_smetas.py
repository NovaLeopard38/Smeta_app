def test_create_smeta(client, auth_headers):
    res = client.post(
        "/smetas",
        json={"name": "Test Smeta"},
        headers=auth_headers,
    )
    assert res.status_code == 200
    data = res.json()
    assert data["name"] == "Test Smeta"
    assert "id" in data


def test_list_smetas(client, auth_headers):
    client.post("/smetas", json={"name": "Listed Smeta"}, headers=auth_headers)
    res = client.get("/smetas", headers=auth_headers)
    assert res.status_code == 200
    names = [s["name"] for s in res.json()]
    assert "Listed Smeta" in names


def test_update_smeta(client, auth_headers):
    create_res = client.post("/smetas", json={"name": "Before Update"}, headers=auth_headers)
    smeta_id = create_res.json()["id"]
    res = client.patch(
        f"/smetas/{smeta_id}",
        json={"name": "After Update"},
        headers=auth_headers,
    )
    assert res.status_code == 200
    assert res.json()["name"] == "After Update"


def test_add_item_to_smeta(client, auth_headers):
    create_res = client.post("/smetas", json={"name": "Items Smeta"}, headers=auth_headers)
    smeta_id = create_res.json()["id"]
    res = client.post(
        f"/smetas/{smeta_id}/items",
        json={
            "name": "Camera IP",
            "unit": "pcs",
            "quantity": 2,
            "unit_price": 5000.0,
        },
        headers=auth_headers,
    )
    assert res.status_code == 200
    data = res.json()
    assert data["total"] > 0


def test_delete_smeta(client, auth_headers):
    create_res = client.post("/smetas", json={"name": "To Delete"}, headers=auth_headers)
    smeta_id = create_res.json()["id"]
    res = client.delete(f"/smetas/{smeta_id}", headers=auth_headers)
    assert res.status_code == 200
    assert res.json()["status"] == "ok"


def test_branch_smeta(client, auth_headers):
    create_res = client.post("/smetas", json={"name": "Original"}, headers=auth_headers)
    smeta_id = create_res.json()["id"]
    res = client.post(f"/smetas/{smeta_id}/branch", headers=auth_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["parent_id"] == smeta_id
