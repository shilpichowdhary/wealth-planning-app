import pytest
from backend.services.auth_service import AuthService, verify_password, hash_password

def test_password_hash_and_verify():
    pw = "SecurePass123!"
    hashed = hash_password(pw)
    assert hashed != pw
    assert verify_password(pw, hashed)
    assert not verify_password("wrong", hashed)

def test_create_access_token():
    token = AuthService.create_access_token({"sub": "user-id-123"})
    assert isinstance(token, str)
    payload = AuthService.decode_token(token)
    assert payload["sub"] == "user-id-123"

@pytest.mark.asyncio
async def test_create_advisor_user(async_client, auth_headers):
    # The auth_headers fixture already creates an advisor user and logs in.
    # Verify the token works by calling POST /auth/token with the same credentials.
    resp = await async_client.post(
        "/auth/token",
        data={"username": "advisor@test.com", "password": "TestPass123!"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
