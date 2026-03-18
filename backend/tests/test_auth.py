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
