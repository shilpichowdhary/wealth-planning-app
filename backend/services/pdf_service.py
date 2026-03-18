import asyncio
import json
import logging
import os
import tempfile
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

# Project root is 2 levels up from this file (backend/services/pdf_service.py -> backend/ -> project_root/)
PROJECT_ROOT = str(Path(__file__).resolve().parent.parent.parent)

CONFIDENCE_LABELS = {
    "high": "🟢 High confidence",
    "specialist_review": "🟡 Review with specialist",
    "complex": "🔴 Jurisdiction-specific complexity — verify with local counsel",
}

DISCLAIMER_TEXT = (
    "This report was generated with AI assistance. It is not legal or tax advice. "
    "All recommendations should be verified with qualified legal and tax counsel in the relevant jurisdictions. "
    "Confidence levels indicate the degree of coverage in the knowledge base, not legal certainty."
)


def build_report_html(case_data: dict, profile: dict, recommendations: list[dict], diagrams: dict) -> str:
    recs_html = ""
    for r in recommendations:
        sources = r.get("sources", [])
        if isinstance(sources, str):
            try:
                sources = json.loads(sources)
            except (json.JSONDecodeError, ValueError):
                sources = []
        sources_html = "".join(f'<li class="source">{s}</li>' for s in (sources or []))
        confidence = r.get("confidence_level", "high")
        # Handle enum values
        if hasattr(confidence, 'value'):
            confidence = confidence.value
        label = CONFIDENCE_LABELS.get(str(confidence), str(confidence))
        structure_name = r.get("structure_name", "")
        rationale = r.get("rationale", "")
        recs_html += f"""
        <div class="rec-card">
          <h3>{structure_name}</h3>
          <div class="confidence">{label}</div>
          <p>{rationale}</p>
          <ul class="sources">{sources_html}</ul>
        </div>"""

    objectives_raw = profile.get("objectives", "[]") or "[]"
    try:
        objectives_list = json.loads(objectives_raw) if isinstance(objectives_raw, str) else objectives_raw
    except (json.JSONDecodeError, ValueError):
        objectives_list = []
    objectives_str = ", ".join(objectives_list) if objectives_list else "N/A"

    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<style>
  body {{ font-family: 'Georgia', serif; color: #1e293b; margin: 0; padding: 0; }}
  .cover {{ background: #0f172a; color: white; padding: 80px 60px; min-height: 100vh; display: flex; flex-direction: column; justify-content: center; }}
  .cover h1 {{ font-size: 36px; margin-bottom: 12px; }}
  .cover .subtitle {{ font-size: 16px; color: #94a3b8; }}
  .cover .disclaimer {{ margin-top: 40px; font-size: 12px; color: #64748b; border-top: 1px solid #1e3a5f; padding-top: 16px; }}
  .page {{ padding: 60px; page-break-before: always; }}
  h2 {{ font-size: 24px; color: #0f172a; border-bottom: 2px solid #e2e8f0; padding-bottom: 8px; }}
  .rec-card {{ border: 1px solid #e2e8f0; border-radius: 8px; padding: 24px; margin-bottom: 24px; }}
  .rec-card h3 {{ margin: 0 0 8px 0; font-size: 18px; }}
  .confidence {{ font-size: 13px; margin-bottom: 12px; }}
  .sources {{ font-size: 12px; color: #64748b; padding-left: 20px; }}
  .source {{ margin-bottom: 4px; }}
  .disclaimer-page {{ background: #f8fafc; padding: 60px; font-size: 12px; color: #64748b; page-break-before: always; }}
</style>
</head>
<body>
<div class="cover">
  <h1>Wealth Planning Advisory</h1>
  <div class="subtitle">{case_data.get('client_name', 'Confidential Client')}</div>
  <div class="subtitle">Prepared: {datetime.utcnow().strftime('%d %B %Y')}</div>
  <div class="disclaimer">Confidential. Prepared for the addressee only.</div>
</div>

<div class="page">
  <h2>Client Profile</h2>
  <p><strong>Domicile:</strong> {profile.get('domicile', 'N/A')}</p>
  <p><strong>Tax Residency:</strong> {profile.get('tax_residency', 'N/A')}</p>
  <p><strong>Nationality:</strong> {profile.get('nationality', 'N/A')}</p>
  <p><strong>Objectives:</strong> {objectives_str}</p>
</div>

<div class="page">
  <h2>Recommendations</h2>
  {recs_html}
</div>

<div class="disclaimer-page">
  <h2 style="color:#1e293b">Disclaimer</h2>
  <p>{DISCLAIMER_TEXT}</p>
</div>
</body></html>"""


async def generate_pdf(html: str) -> bytes:
    """Render HTML to PDF using Puppeteer via Node subprocess.

    IMPORTANT: node is invoked with cwd=PROJECT_ROOT so that require('puppeteer')
    resolves correctly from frontend/node_modules/.
    """
    html_path = None
    pdf_path = None
    js_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".html", delete=False, mode="w") as f:
            f.write(html)
            html_path = f.name
        pdf_path = html_path.replace(".html", ".pdf")

        script = f"""
const puppeteer = require('./frontend/node_modules/puppeteer');
(async () => {{
  const browser = await puppeteer.launch({{args: ['--no-sandbox', '--disable-setuid-sandbox']}});
  const page = await browser.newPage();
  await page.goto('file://{html_path}', {{waitUntil: 'networkidle0'}});
  await page.pdf({{
    path: '{pdf_path}',
    format: 'A4',
    printBackground: true,
    margin: {{top: '0', bottom: '0', left: '0', right: '0'}}
  }});
  await browser.close();
}})().catch(e => {{ console.error(e); process.exit(1); }});
"""
        with tempfile.NamedTemporaryFile(suffix=".js", delete=False, mode="w") as js_file:
            js_file.write(script)
            js_path = js_file.name

        proc = await asyncio.create_subprocess_exec(
            "node", js_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=PROJECT_ROOT,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=30)
        if proc.returncode != 0:
            logger.error("Puppeteer failed (code %d): %s", proc.returncode, stderr.decode())
            raise RuntimeError(f"PDF generation failed: {stderr.decode()[:200]}")

        with open(pdf_path, "rb") as f:
            return f.read()
    finally:
        for p in [html_path, pdf_path, js_path]:
            if p:
                try:
                    os.unlink(p)
                except OSError:
                    pass
