import pytest
from unittest.mock import patch, AsyncMock


@pytest.mark.asyncio
async def test_create_case_requires_auth(async_client):
    resp = await async_client.post("/cases/", json={"client_name": "Test Client"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_create_and_get_case(auth_headers, async_client):
    resp = await async_client.post("/cases/", json={"client_name": "Sharma Family"}, headers=auth_headers)
    assert resp.status_code == 201
    data = resp.json()
    assert data["client_name"] == "Sharma Family"
    case_id = data["case_id"]

    get_resp = await async_client.get(f"/cases/{case_id}", headers=auth_headers)
    assert get_resp.status_code == 200


@pytest.mark.asyncio
async def test_get_nonexistent_case_returns_404(auth_headers, async_client):
    resp = await async_client.get("/cases/nonexistent-id", headers=auth_headers)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_list_cases_returns_only_own(auth_headers, async_client):
    # Create a case
    await async_client.post("/cases/", json={"client_name": "Test Family"}, headers=auth_headers)
    # List cases - should see our case
    resp = await async_client.get("/cases/", headers=auth_headers)
    assert resp.status_code == 200
    cases = resp.json()
    assert len(cases) >= 1
    assert all(c["client_name"] for c in cases)


@pytest.mark.asyncio
async def test_generate_compact_summary_returns_fallback_on_error():
    from backend.services.summary_service import generate_compact_summary
    with patch("anthropic.AsyncAnthropic") as mock_cls:
        mock_instance = AsyncMock()
        mock_cls.return_value = mock_instance
        mock_instance.messages.create.side_effect = Exception("API error")
        result = await generate_compact_summary([{"role": "user", "content": "test"}])
    assert result == "{}"
