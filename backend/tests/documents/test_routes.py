from uuid import uuid4

from conftest import create_user_and_get_headers


async def test_create_document(client, auth_headers):
    resp = await client.post(
        "/api/documents/",
        json={"title": "My Doc"},
        headers=auth_headers,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["title"] == "My Doc"
    assert data["status"] == "draft"
    assert data["version"] == 1


async def test_list_documents(client, auth_headers):
    await client.post("/api/documents/", json={"title": "Doc 1"}, headers=auth_headers)
    await client.post("/api/documents/", json={"title": "Doc 2"}, headers=auth_headers)
    resp = await client.get("/api/documents/", headers=auth_headers)
    assert resp.status_code == 200
    assert len(resp.json()) == 2


async def test_get_document(client, auth_headers):
    create_resp = await client.post(
        "/api/documents/", json={"title": "My Doc"}, headers=auth_headers
    )
    doc_id = create_resp.json()["id"]
    resp = await client.get(f"/api/documents/{doc_id}", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["title"] == "My Doc"


async def test_get_document_not_found(client, auth_headers):
    resp = await client.get(f"/api/documents/{uuid4()}", headers=auth_headers)
    assert resp.status_code == 404


async def test_update_document(client, auth_headers):
    create_resp = await client.post(
        "/api/documents/", json={"title": "Old"}, headers=auth_headers
    )
    doc_id = create_resp.json()["id"]
    resp = await client.patch(
        f"/api/documents/{doc_id}",
        json={"title": "New", "expected_version": 1},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["title"] == "New"
    assert resp.json()["version"] == 2


async def test_update_document_conflict(client, auth_headers):
    create_resp = await client.post(
        "/api/documents/", json={"title": "Doc"}, headers=auth_headers
    )
    doc_id = create_resp.json()["id"]
    await client.patch(
        f"/api/documents/{doc_id}",
        json={"title": "V2", "expected_version": 1},
        headers=auth_headers,
    )
    resp = await client.patch(
        f"/api/documents/{doc_id}",
        json={"title": "Stale", "expected_version": 1},
        headers=auth_headers,
    )
    assert resp.status_code == 409


async def test_delete_document(client, auth_headers):
    create_resp = await client.post(
        "/api/documents/", json={"title": "To Delete"}, headers=auth_headers
    )
    doc_id = create_resp.json()["id"]
    resp = await client.delete(f"/api/documents/{doc_id}", headers=auth_headers)
    assert resp.status_code == 204

    resp = await client.get(f"/api/documents/{doc_id}", headers=auth_headers)
    assert resp.status_code == 404


async def test_delete_document_wrong_owner(client, auth_headers):
    create_resp = await client.post(
        "/api/documents/", json={"title": "My Doc"}, headers=auth_headers
    )
    doc_id = create_resp.json()["id"]

    other_headers = await create_user_and_get_headers(client, suffix="2")
    resp = await client.delete(f"/api/documents/{doc_id}", headers=other_headers)
    assert resp.status_code == 403


async def test_documents_require_auth(client):
    resp = await client.get("/api/documents/")
    assert resp.status_code in (401, 403)
