"""Azure Key Vault client wrapped to be safe for local dev.

When the production env vars are set (KEY_VAULT_URL), the master Fernet key
is fetched from KV via the VM's system-assigned Managed Identity.

When KEY_VAULT_URL is unset, falls back to LOCAL_FERNET_KEY env var — but only
if ALLOW_LOCAL_FERNET_KEY=true. That gate exists so production cannot
accidentally start with a local key just because KV happens to be unreachable.
"""
import logging
import os
from functools import lru_cache

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def get_fernet_master_key() -> bytes:
    vault_url = os.environ.get("KEY_VAULT_URL")
    if vault_url:
        from azure.identity import DefaultAzureCredential
        from azure.keyvault.secrets import SecretClient
        credential = DefaultAzureCredential()
        client = SecretClient(vault_url=vault_url, credential=credential)
        secret = client.get_secret("wealth-planning-fernet-master-v1")
        logger.info("Fernet master key loaded from Key Vault")
        return secret.value.encode()

    if os.environ.get("ALLOW_LOCAL_FERNET_KEY") == "true":
        key = os.environ.get("LOCAL_FERNET_KEY")
        if not key:
            raise RuntimeError(
                "ALLOW_LOCAL_FERNET_KEY=true but LOCAL_FERNET_KEY is empty. "
                "Set both, or remove the allow-local flag to require KEY_VAULT_URL."
            )
        logger.warning("Using LOCAL_FERNET_KEY — DEVELOPMENT ONLY")
        return key.encode()

    raise RuntimeError(
        "Encryption is not configured. Set KEY_VAULT_URL (production) or "
        "ALLOW_LOCAL_FERNET_KEY=true + LOCAL_FERNET_KEY (development)."
    )


def reset_key_cache() -> None:
    """Test helper — clear the lru_cache so env-var changes take effect."""
    get_fernet_master_key.cache_clear()
