"""Regenerate the Wealth Planning favicon set.

Per the LC brand contract (gotcha #19): app/icon.svg, app/icon.png,
app/apple-icon.png must all show the same crimson square + white serif
glyph as the sidebar brand-mark. For Wealth Planning that letter is "W".

Run from the project root with:
    venv\\Scripts\\python.exe frontend\\scripts\\regen_favicons.py
"""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

CRIMSON = (229, 0, 37)
WHITE = (255, 255, 255)
LETTER = "W"
FONT_PATH = r"C:\Windows\Fonts\FrankRuhlLibre-VariableFont_wght.ttf"

OUT_DIR = Path(__file__).resolve().parents[1] / "app"


def render(size: int) -> Image.Image:
    img = Image.new("RGBA", (size, size), CRIMSON)
    draw = ImageDraw.Draw(img)
    # 0.62 keeps a "W" visually balanced inside the square; "W" is wider
    # than "L" / "P" so we don't push to 0.78.
    font = ImageFont.truetype(FONT_PATH, int(size * 0.62))
    bbox = draw.textbbox((0, 0), LETTER, font=font)
    w = bbox[2] - bbox[0]
    h = bbox[3] - bbox[1]
    draw.text(
        ((size - w) / 2 - bbox[0], (size - h) / 2 - bbox[1]),
        LETTER,
        font=font,
        fill=WHITE,
    )
    return img


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    # Tab favicon (Next.js picks this up as /icon).
    render(32).save(OUT_DIR / "icon.png", "PNG")

    # Apple touch icon (180x180 is the iOS standard).
    render(180).save(OUT_DIR / "apple-icon.png", "PNG")

    # Crisp SVG for modern browsers — referenced first in <head> via
    # Next's metadata pipeline (app/icon.svg). Use the Frank Ruhl serif
    # font-family so the rendering matches the raster files even when
    # the user agent doesn't have Frank Ruhl installed (Georgia is the
    # closest classical-serif fallback).
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32" '
        'width="32" height="32">\n'
        '  <rect width="32" height="32" fill="#E50025"/>\n'
        '  <text x="16" y="23.5" text-anchor="middle" '
        'font-family="\'Frank Ruhl Libre\', Georgia, serif" '
        'font-size="22" font-weight="500" letter-spacing="-0.02em" '
        'fill="#FFFFFF">W</text>\n'
        "</svg>\n"
    )
    (OUT_DIR / "icon.svg").write_text(svg, encoding="utf-8")

    print(f"Wrote favicons to {OUT_DIR}")


if __name__ == "__main__":
    main()
