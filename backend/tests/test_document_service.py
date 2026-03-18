import pytest
from backend.services.document_service import extract_text, validate_mime_type


def test_extract_text_from_txt(tmp_path):
    f = tmp_path / "test.txt"
    f.write_text("This is a test document about Singapore trusts.")
    text = extract_text(str(f), "txt")
    assert "Singapore" in text


def test_validate_mime_rejects_exe(tmp_path):
    f = tmp_path / "bad.exe"
    f.write_bytes(b"MZ\x00\x00")
    with pytest.raises(ValueError, match="Invalid file type"):
        validate_mime_type(str(f))


def test_validate_mime_accepts_pdf(tmp_path):
    # PDF magic bytes
    f = tmp_path / "doc.pdf"
    f.write_bytes(b"%PDF-1.4\n%%EOF")
    # Should not raise (or raise only because it's a malformed PDF, not MIME error)
    try:
        validate_mime_type(str(f))
    except ValueError as e:
        assert "Invalid file type" not in str(e)
