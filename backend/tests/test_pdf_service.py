import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from backend.services.pdf_service import build_report_html, CONFIDENCE_LABELS, DISCLAIMER_TEXT


def test_build_report_html_contains_client_name():
    html = build_report_html(
        case_data={"client_name": "Sharma Family"},
        profile={"domicile": "Singapore", "nationality": "Indian", "tax_residency": "Singapore", "objectives": '["wealth preservation"]'},
        recommendations=[],
        diagrams={},
    )
    assert "Sharma Family" in html
    assert "Singapore" in html


def test_build_report_html_includes_disclaimer():
    html = build_report_html(
        case_data={},
        profile={},
        recommendations=[],
        diagrams={},
    )
    assert "not legal or tax advice" in html.lower() or "not legal" in html.lower()


def test_build_report_html_includes_recommendation():
    recs = [{"structure_name": "Singapore Trust", "confidence_level": "high", "rationale": "Tax efficient", "sources": '["singapore_trust.txt"]'}]
    html = build_report_html(case_data={}, profile={}, recommendations=recs, diagrams={})
    assert "Singapore Trust" in html
    assert "Tax efficient" in html


def test_build_report_html_escapes_html_in_client_name():
    html = build_report_html(
        case_data={"client_name": "<script>alert('xss')</script>"},
        profile={},
        recommendations=[],
        diagrams={},
    )
    assert "<script>" not in html
    assert "&lt;script&gt;" in html or "alert" not in html


def test_confidence_labels_have_all_levels():
    assert "high" in CONFIDENCE_LABELS
    assert "specialist_review" in CONFIDENCE_LABELS
    assert "complex" in CONFIDENCE_LABELS


@pytest.mark.asyncio
async def test_generate_pdf_raises_on_nonzero_exit():
    from backend.services.pdf_service import generate_pdf

    mock_proc = AsyncMock()
    mock_proc.returncode = 1
    mock_proc.communicate.return_value = (b"", b"Puppeteer error")

    with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
        with pytest.raises((RuntimeError, Exception)):
            await generate_pdf("<html><body>test</body></html>")
