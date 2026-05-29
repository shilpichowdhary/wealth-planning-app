"""Azure Blob Storage backend.

The storage key is used directly as the blob name within a single container
(``settings.azure_blob_container``). Works against a real Storage account or the
Azurite emulator (both via a standard connection string).
"""
from __future__ import annotations

import io
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import BinaryIO, Iterator

from backend.config import settings
from backend.storage.base import Storage


class AzureBlobStorage(Storage):
    def __init__(self) -> None:
        from azure.storage.blob import BlobServiceClient

        if not settings.azure_storage_connection_string:
            raise RuntimeError("AZURE_STORAGE_CONNECTION_STRING is required for storage_backend=azure")
        self._svc = BlobServiceClient.from_connection_string(settings.azure_storage_connection_string)
        self._container = settings.azure_blob_container
        # Idempotently ensure the container exists.
        try:
            self._svc.create_container(self._container)
        except Exception:
            pass

    def _blob(self, key: str):
        return self._svc.get_blob_client(container=self._container, blob=key)

    def save_bytes(self, key: str, data: bytes, *, content_type: str | None = None) -> None:
        from azure.storage.blob import ContentSettings

        cs = ContentSettings(content_type=content_type) if content_type else None
        self._blob(key).upload_blob(data, overwrite=True, content_settings=cs)

    def open(self, key: str) -> BinaryIO:
        buf = io.BytesIO()
        self._blob(key).download_blob().readinto(buf)
        buf.seek(0)
        return buf

    def exists(self, key: str) -> bool:
        return self._blob(key).exists()

    def delete(self, key: str) -> None:
        try:
            self._blob(key).delete_blob()
        except Exception:
            pass

    @contextmanager
    def as_local_path(self, key: str) -> Iterator[Path]:
        tmp = tempfile.NamedTemporaryFile(suffix=Path(key).suffix, delete=False)
        try:
            self._blob(key).download_blob().readinto(tmp)
            tmp.close()
            yield Path(tmp.name)
        finally:
            try:
                Path(tmp.name).unlink()
            except OSError:
                pass

    def response(self, key: str, *, media_type: str, download_name: str):
        from fastapi.responses import StreamingResponse

        downloader = self._blob(key).download_blob()
        return StreamingResponse(
            downloader.chunks(),
            media_type=media_type,
            headers={"Content-Disposition": f'attachment; filename="{download_name}"'},
        )
