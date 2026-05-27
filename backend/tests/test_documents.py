import os
import pytest


async def _create_case(async_client, auth_headers) -> str:
    r = await async_client.post(
        "/cases/", json={"client_name": "Doc Test Client"}, headers=auth_headers
    )
    assert r.status_code == 201, r.text
    return r.json()["case_id"]


@pytest.mark.asyncio
async def test_upload_rejects_exe_renamed_as_pdf(async_client, auth_headers, tmp_path, monkeypatch):
    """A Windows PE binary renamed `evil.pdf` must be rejected with 415, and
    nothing should land in the uploads directory."""
    # PE/COFF magic bytes — python-magic will identify this as application/x-dosexec.
    fake_exe = b"MZ" + b"\x00" * 64 + b"This program cannot be run in DOS mode.\x00"

    # Redirect uploads_path to tmp_path so we don't pollute the real ./uploads/.
    from backend.config import settings
    monkeypatch.setattr(settings, "uploads_path", str(tmp_path))

    case_id = await _create_case(async_client, auth_headers)
    upload_dir = os.path.join(str(tmp_path), "cases", case_id)
    files_before = set(os.listdir(upload_dir)) if os.path.isdir(upload_dir) else set()

    r = await async_client.post(
        f"/documents/{case_id}/upload",
        files={"file": ("evil.pdf", fake_exe, "application/pdf")},
        headers=auth_headers,
    )
    assert r.status_code == 415, r.text

    files_after = set(os.listdir(upload_dir)) if os.path.isdir(upload_dir) else set()
    assert files_after == files_before, "Rejected upload must not persist on disk"


@pytest.mark.asyncio
async def test_upload_accepts_real_pdf(async_client, auth_headers, tmp_path, monkeypatch):
    """Sanity check the happy path still works after the reorder."""
    pdf_bytes = b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF\n"
    from backend.config import settings
    monkeypatch.setattr(settings, "uploads_path", str(tmp_path))

    case_id = await _create_case(async_client, auth_headers)
    r = await async_client.post(
        f"/documents/{case_id}/upload",
        files={"file": ("ok.pdf", pdf_bytes, "application/pdf")},
        headers=auth_headers,
    )
    # 201 expected; the embedding pipeline may fail on the truncated PDF but
    # validation + disk write should succeed (chunk_count may be 0).
    assert r.status_code == 201, r.text
