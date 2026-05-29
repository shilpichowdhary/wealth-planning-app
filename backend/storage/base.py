"""Storage abstraction for user content (uploads + generated reports).

Keys are always POSIX-style, slash-separated, and namespaced by their first
segment: ``uploads/...`` or ``reports/...``. This keeps a single key space that
maps cleanly onto either the local filesystem or an Azure Blob container (where
the key is simply the blob name).

Backends must provide :meth:`as_local_path` because several consumers require a
real path on disk: python-magic, PyMuPDF, python-docx, and LibreOffice/soffice.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import BinaryIO


class Storage(ABC):
    @abstractmethod
    def save_bytes(self, key: str, data: bytes, *, content_type: str | None = None) -> None:
        ...

    @abstractmethod
    def open(self, key: str) -> BinaryIO:
        """Return a readable binary stream for the object."""
        ...

    @abstractmethod
    def exists(self, key: str) -> bool:
        ...

    @abstractmethod
    def delete(self, key: str) -> None:
        """Delete the object. No error if it does not exist."""
        ...

    @abstractmethod
    def as_local_path(self, key: str):
        """Context manager yielding a real local :class:`Path` for the object.

        Local backend yields the file itself (zero-copy); cloud backends yield a
        temporary copy that is removed on exit.
        """
        ...

    def response(self, key: str, *, media_type: str, download_name: str):
        """FastAPI response that serves the object as a download.

        Default implementation streams via :meth:`open`; backends may override
        with a more efficient path.
        """
        from fastapi.responses import StreamingResponse

        return StreamingResponse(
            self.open(key),
            media_type=media_type,
            headers={"Content-Disposition": f'attachment; filename="{download_name}"'},
        )
