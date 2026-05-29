"""Local filesystem storage backend (default).

Preserves the historical on-disk layout so existing deployments are unchanged:
``uploads/...`` maps under ``settings.uploads_path`` and ``reports/...`` under
``settings.reports_path``.
"""
from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path, PurePosixPath
from typing import BinaryIO, Iterator

from backend.config import settings
from backend.storage.base import Storage

_NAMESPACES = {"uploads": "uploads_path", "reports": "reports_path"}


class LocalStorage(Storage):
    def _abs(self, key: str) -> Path:
        # Backward-compat: legacy rows persisted absolute OS paths, not keys.
        legacy = Path(key)
        if legacy.is_absolute():
            return legacy
        parts = PurePosixPath(key).parts
        if len(parts) < 2 or parts[0] not in _NAMESPACES:
            raise ValueError(f"storage key must be namespaced (uploads/… or reports/…): {key!r}")
        root = getattr(settings, _NAMESPACES[parts[0]])
        return Path(root).resolve().joinpath(*parts[1:])

    def save_bytes(self, key: str, data: bytes, *, content_type: str | None = None) -> None:
        p = self._abs(key)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)

    def open(self, key: str) -> BinaryIO:
        return self._abs(key).open("rb")

    def exists(self, key: str) -> bool:
        return self._abs(key).exists()

    def delete(self, key: str) -> None:
        p = self._abs(key)
        if p.exists():
            p.unlink()

    @contextmanager
    def as_local_path(self, key: str) -> Iterator[Path]:
        yield self._abs(key)  # already a real file — zero copy

    def response(self, key: str, *, media_type: str, download_name: str):
        from fastapi.responses import FileResponse

        return FileResponse(str(self._abs(key)), media_type=media_type, filename=download_name)
