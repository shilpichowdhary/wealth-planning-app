import pytest
from httpx import AsyncClient, ASGITransport
from backend.main import app
from backend.database import create_tables

@pytest.mark.asyncio
async def test_create_case_requires_auth():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/cases/", json={"client_name": "Test Client"})
    assert resp.status_code == 401

@pytest.mark.asyncio
async def test_create_and_get_case(auth_headers, async_client):
    resp = await async_client.post("/cases/", json={"client_name": "Sharma Family"}, headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["client_name"] == "Sharma Family"
    case_id = data["case_id"]

    get_resp = await async_client.get(f"/cases/{case_id}", headers=auth_headers)
    assert get_resp.status_code == 200
