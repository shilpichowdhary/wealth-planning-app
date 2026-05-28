"""Fernet helpers for app-layer encryption.

The master key is loaded once from KV (or local fallback in dev) and held in
memory. Each Fernet round uses a random IV, so the same plaintext produces
different ciphertext each time.

decrypt() is tolerant: if the input is NOT a valid Fernet token, it's returned
unchanged. This allows the Phase 3 cutover migration to run against a DB where
some rows are still plaintext and others are already ciphertext, without
breaking either path.
"""
import logging
from functools import lru_cache
from cryptography.fernet import Fernet, InvalidToken
from backend.services.azure_kv import get_fernet_master_key

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def _cipher() -> Fernet:
    return Fernet(get_fernet_master_key())


def encrypt(plaintext: str | None) -> str | None:
    if plaintext is None:
        return None
    return _cipher().encrypt(str(plaintext).encode()).decode()


def decrypt(ciphertext: str | None) -> str | None:
    """Decrypt a Fernet token. Returns the input unchanged if it isn't a valid token —
    this tolerates plaintext rows during the Phase 3 cutover migration."""
    if ciphertext is None:
        return None
    try:
        return _cipher().decrypt(ciphertext.encode()).decode()
    except (InvalidToken, ValueError, TypeError):
        return ciphertext


def reset_cipher_cache() -> None:
    """Test helper — clear the cipher cache so key changes take effect."""
    _cipher.cache_clear()
