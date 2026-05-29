"""Pluggable content storage (local filesystem or Azure Blob).

Select the backend via ``settings.storage_backend`` ("local" | "azure").
Call sites use the singleton returned by :func:`get_storage`.
"""
from __future__ import annotations

from functools import lru_cache

from backend.config import settings
from backend.storage.base import Storage


@lru_cache(maxsize=1)
def get_storage() -> Storage:
    if settings.storage_backend == "azure":
        from backend.storage.azure import AzureBlobStorage

        return AzureBlobStorage()
    from backend.storage.local import LocalStorage

    return LocalStorage()


__all__ = ["Storage", "get_storage"]
