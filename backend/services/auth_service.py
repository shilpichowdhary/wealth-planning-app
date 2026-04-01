from datetime import datetime, timedelta
import time
import logging
import bcrypt
from jose import jwt, JWTError, jwk
from jose.utils import base64url_decode
import httpx
from backend.config import settings

logger = logging.getLogger(__name__)


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))

ACCESS_TOKEN_EXPIRE_HOURS = 8

# Azure JWKS cache
_jwks_cache: dict | None = None
_jwks_cache_time: float = 0
JWKS_CACHE_SECONDS = 86400  # 24 hours


async def fetch_azure_jwks() -> dict:
    """Fetch Azure AD public keys (JWKS), cached for 24 hours."""
    global _jwks_cache, _jwks_cache_time
    if _jwks_cache and (time.time() - _jwks_cache_time) < JWKS_CACHE_SECONDS:
        return _jwks_cache
    async with httpx.AsyncClient() as client:
        resp = await client.get(settings.azure_jwks_uri)
        resp.raise_for_status()
        _jwks_cache = resp.json()
        _jwks_cache_time = time.time()
        return _jwks_cache


def validate_azure_id_token(id_token: str) -> dict:
    """Validate an Azure AD ID token and return its claims.

    Fetches the matching public key from the cached JWKS,
    then verifies the RS256 signature, audience, issuer, and expiry.
    """
    import asyncio
    loop = asyncio.get_event_loop()
    jwks = loop.run_until_complete(fetch_azure_jwks())
    return _validate_token_with_jwks(id_token, jwks)


async def validate_azure_id_token_async(id_token: str) -> dict:
    """Async version of Azure ID token validation."""
    jwks_data = await fetch_azure_jwks()
    return _validate_token_with_jwks(id_token, jwks_data)


def _validate_token_with_jwks(id_token: str, jwks_data: dict) -> dict:
    """Validate token against JWKS keys."""
    # Get the key ID from the token header
    header = jwt.get_unverified_header(id_token)
    kid = header.get("kid")
    if not kid:
        raise ValueError("Token header missing kid")

    # Find the matching key
    rsa_key = None
    for key in jwks_data.get("keys", []):
        if key.get("kid") == kid:
            rsa_key = key
            break

    if not rsa_key:
        raise ValueError("Matching signing key not found in Azure JWKS")

    # Decode and validate
    claims = jwt.decode(
        id_token,
        rsa_key,
        algorithms=["RS256"],
        audience=settings.azure_client_id,
        issuer=settings.azure_issuer,
    )
    return claims


class AuthService:
    @staticmethod
    def create_access_token(data: dict) -> str:
        payload = data.copy()
        payload["exp"] = datetime.utcnow() + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)
        return jwt.encode(payload, settings.secret_key, algorithm="HS256")

    @staticmethod
    def decode_token(token: str) -> dict:
        try:
            return jwt.decode(token, settings.secret_key, algorithms=["HS256"])
        except JWTError:
            raise ValueError("Invalid token")
