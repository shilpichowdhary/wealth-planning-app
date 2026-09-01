"""Embed TrueType fonts into a generated .pptx.

python-pptx names fonts by typeface only; it does not embed the font files.
On a machine that lacks Frank Ruhl Libre / Public Sans, PowerPoint silently
substitutes Calibri/Times and the deck renders off-brand — violating brand
rule #1 (Frank Ruhl Libre Light for titles, Public Sans for body). The LC
skill explicitly calls for embedding the fonts; this module does that as a
post-processing pass on the saved .pptx.

It injects the OOXML that PowerPoint's "Embed fonts in the file" feature
produces:
  • font binaries as  ppt/fonts/fontN.fntdata
  • a Default content-type for the `fntdata` extension
  • `font` relationships from the presentation part
  • `<p:embeddedFontLst>` in presentation.xml + `embedTrueTypeFonts="1"`

Best-effort: any failure is logged and swallowed so deck generation still
succeeds (just without embedded fonts).
"""
from __future__ import annotations

import logging
import shutil
import zipfile
from pathlib import Path
from tempfile import NamedTemporaryFile

logger = logging.getLogger(__name__)

_NS_CT = "http://schemas.openxmlformats.org/package/2006/content-types"
_NS_REL = "http://schemas.openxmlformats.org/package/2006/relationships"
_NS_P = "http://schemas.openxmlformats.org/presentationml/2006/main"
_NS_R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
_REL_FONT = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/font"

SKILL_FONT_DIR = (
    Path(__file__).resolve().parent.parent
    / "skills" / "lighthouse-canton-ppt" / "assets" / "fonts"
)

# typeface name -> {slot: filename}. Slots: regular / bold / italic / boldItalic.
# The families ship as variable fonts; we embed the variable file in the
# regular (and italic) slot, which viewers render at the default instance.
DEFAULT_FONTS: dict[str, dict[str, str]] = {
    "Public Sans": {
        "regular": "PublicSans-VariableFont_wght.ttf",
        "italic": "PublicSans-Italic-VariableFont_wght.ttf",
    },
    "Frank Ruhl Libre": {
        "regular": "FrankRuhlLibre-VariableFont_wght.ttf",
    },
}


def _resolve_fonts() -> list[tuple[str, dict[str, Path]]]:
    resolved: list[tuple[str, dict[str, Path]]] = []
    for typeface, slots in DEFAULT_FONTS.items():
        slot_paths: dict[str, Path] = {}
        for slot, fname in slots.items():
            p = SKILL_FONT_DIR / fname
            if p.exists():
                slot_paths[slot] = p
        if slot_paths:
            resolved.append((typeface, slot_paths))
    return resolved


def embed_fonts(pptx_path: Path, fonts: list[tuple[str, dict[str, Path]]] | None = None) -> bool:
    """Embed `fonts` into the .pptx at `pptx_path` in place.

    Returns True if fonts were embedded, False otherwise (missing files, or a
    failure — in which case the original file is left untouched).
    """
    fonts = fonts if fonts is not None else _resolve_fonts()
    if not fonts:
        logger.warning("No brand font files found under %s; skipping embed", SKILL_FONT_DIR)
        return False

    try:
        with zipfile.ZipFile(pptx_path, "r") as zin:
            names = set(zin.namelist())
            # Idempotency guard: if this package was already embedded, do not
            # add a second <p:embeddedFontLst> / duplicate font parts.
            if "<p:embeddedFontLst>" in zin.read("ppt/presentation.xml").decode("utf-8"):
                logger.info("Fonts already embedded in %s; skipping", pptx_path.name)
                return True
            content_types = zin.read("[Content_Types].xml").decode("utf-8")
            presentation = zin.read("ppt/presentation.xml").decode("utf-8")
            pres_rels = zin.read("ppt/_rels/presentation.xml.rels").decode("utf-8")
            other = {n: zin.read(n) for n in names
                     if n not in ("[Content_Types].xml", "ppt/presentation.xml",
                                  "ppt/_rels/presentation.xml.rels")}

        # Build the font parts + the XML fragments that reference them.
        font_parts: dict[str, bytes] = {}
        rels_fragments: list[str] = []
        embedded_font_elems: list[str] = []
        rid_seq = _next_rel_id(pres_rels)
        font_seq = 1
        for typeface, slot_paths in fonts:
            slot_elems: list[str] = []
            for slot, path in slot_paths.items():
                part_name = f"ppt/fonts/font{font_seq}.fntdata"
                font_seq += 1
                font_parts[part_name] = path.read_bytes()
                rid = f"rIdFont{rid_seq}"
                rid_seq += 1
                rels_fragments.append(
                    f'<Relationship Id="{rid}" Type="{_REL_FONT}" '
                    f'Target="fonts/{Path(part_name).name}"/>'
                )
                slot_elems.append(f'<p:{slot} r:id="{rid}"/>')
            embedded_font_elems.append(
                f'<p:embeddedFont><p:font typeface="{_xml_escape(typeface)}"/>'
                + "".join(slot_elems)
                + "</p:embeddedFont>"
            )

        content_types = _patch_content_types(content_types)
        presentation = _patch_presentation(presentation, embedded_font_elems)
        pres_rels = _patch_rels(pres_rels, rels_fragments)

        tmp = NamedTemporaryFile(delete=False, suffix=".pptx", dir=str(pptx_path.parent))
        tmp.close()
        with zipfile.ZipFile(tmp.name, "w", zipfile.ZIP_DEFLATED) as zout:
            zout.writestr("[Content_Types].xml", content_types)
            zout.writestr("ppt/presentation.xml", presentation)
            zout.writestr("ppt/_rels/presentation.xml.rels", pres_rels)
            for name, data in other.items():
                zout.writestr(name, data)
            for name, data in font_parts.items():
                zout.writestr(name, data)
        shutil.move(tmp.name, pptx_path)
        logger.info("Embedded %d brand font family/families into %s",
                    len(fonts), pptx_path.name)
        return True
    except Exception as e:  # noqa: BLE001 — embedding is best-effort
        logger.warning("Font embedding failed for %s: %s", pptx_path, e, exc_info=True)
        return False


def _xml_escape(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def _next_rel_id(pres_rels: str) -> int:
    """Return an integer suffix that won't collide with existing rIdN ids."""
    import re
    nums = [int(m) for m in re.findall(r'Id="rId(\d+)"', pres_rels)]
    return (max(nums) + 1) if nums else 1


def _patch_content_types(xml: str) -> str:
    if 'Extension="fntdata"' in xml:
        return xml
    default = '<Default Extension="fntdata" ContentType="application/x-fontdata"/>'
    return xml.replace("</Types>", default + "</Types>", 1)


def _patch_rels(xml: str, fragments: list[str]) -> str:
    return xml.replace("</Relationships>", "".join(fragments) + "</Relationships>", 1)


def _patch_presentation(xml: str, embedded_font_elems: list[str]) -> str:
    # 1. Ensure embedTrueTypeFonts="1" on the root <p:presentation ...> tag.
    import re
    if "embedTrueTypeFonts" not in xml:
        xml = re.sub(
            r"(<p:presentation\b[^>]*?)(\s*>)",
            r'\1 embedTrueTypeFonts="1"\2',
            xml,
            count=1,
        )
    # 2. Insert <p:embeddedFontLst> in schema order: after <p:notesSz .../>,
    #    which is where it belongs (before p:defaultTextStyle / p:extLst).
    lst = "<p:embeddedFontLst>" + "".join(embedded_font_elems) + "</p:embeddedFontLst>"
    m = re.search(r"<p:notesSz\b[^>]*/>", xml)
    if m:
        idx = m.end()
        return xml[:idx] + lst + xml[idx:]
    # Fallback: place before defaultTextStyle, else before closing tag.
    if "<p:defaultTextStyle" in xml:
        return xml.replace("<p:defaultTextStyle", lst + "<p:defaultTextStyle", 1)
    return xml.replace("</p:presentation>", lst + "</p:presentation>", 1)
