"""Unit tests for the local storage backend (default)."""
from pathlib import Path

import pytest

from backend.config import settings
from backend.storage.local import LocalStorage


@pytest.fixture
def local(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "uploads_path", str(tmp_path / "uploads"))
    monkeypatch.setattr(settings, "reports_path", str(tmp_path / "reports"))
    return LocalStorage(), tmp_path


def test_uploads_namespace_roundtrip(local):
    s, tmp_path = local
    key = "uploads/cases/c1/file.txt"
    s.save_bytes(key, b"data", content_type="text/plain")
    assert s.exists(key)
    with s.as_local_path(key) as p:
        assert Path(p).read_bytes() == b"data"
    assert s.open(key).read() == b"data"
    # namespace maps under the configured uploads_path
    assert (tmp_path / "uploads" / "cases" / "c1" / "file.txt").exists()
    s.delete(key)
    assert not s.exists(key)


def test_reports_namespace_maps_to_reports_path(local):
    s, tmp_path = local
    s.save_bytes("reports/c1/deck-v1.pptx", b"pptx")
    assert (tmp_path / "reports" / "c1" / "deck-v1.pptx").exists()


def test_unknown_namespace_rejected(local):
    s, _ = local
    with pytest.raises(ValueError):
        s.save_bytes("bogus/x.txt", b"")
