"""Vietnamese font support for ReportLab PDF generation.

Font resolution order:
1. Bundled DejaVu Serif fonts (legal_chatbot/fonts/) — works everywhere including Vercel
2. Windows system fonts (C:/Windows/Fonts/) — local dev on Windows
3. Linux system fonts (/usr/share/fonts/) — Linux servers
"""

from pathlib import Path
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

_fonts_registered = False

# Directory containing bundled fonts (DejaVu Serif)
_BUNDLED_FONTS_DIR = Path(__file__).resolve().parent.parent / "fonts"

# Font search paths: (registered_name, list_of_candidate_paths)
# First found path wins for each name.
_FONT_CANDIDATES = {
    "Vietnamese": [
        _BUNDLED_FONTS_DIR / "DejaVuSerif.ttf",
        Path("C:/Windows/Fonts/times.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf"),
        Path("/usr/share/fonts/dejavu-serif/DejaVuSerif.ttf"),
        Path("/usr/share/fonts/dejavu/DejaVuSerif.ttf"),
        Path("/usr/share/fonts/truetype/liberation/LiberationSerif-Regular.ttf"),
    ],
    "Vietnamese-Bold": [
        _BUNDLED_FONTS_DIR / "DejaVuSerif-Bold.ttf",
        Path("C:/Windows/Fonts/timesbd.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf"),
        Path("/usr/share/fonts/dejavu-serif/DejaVuSerif-Bold.ttf"),
        Path("/usr/share/fonts/dejavu/DejaVuSerif-Bold.ttf"),
        Path("/usr/share/fonts/truetype/liberation/LiberationSerif-Bold.ttf"),
    ],
    "Vietnamese-Italic": [
        _BUNDLED_FONTS_DIR / "DejaVuSerif-Italic.ttf",
        Path("C:/Windows/Fonts/timesi.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSerif-Italic.ttf"),
        Path("/usr/share/fonts/dejavu-serif/DejaVuSerif-Italic.ttf"),
        Path("/usr/share/fonts/dejavu/DejaVuSerif-Italic.ttf"),
        Path("/usr/share/fonts/truetype/liberation/LiberationSerif-Italic.ttf"),
    ],
}

# Actual registered names (set during registration)
_registered_names = {"normal": None, "bold": None, "italic": None}


def register_vietnamese_fonts() -> bool:
    """Register Vietnamese-compatible fonts with ReportLab."""
    global _fonts_registered

    if _fonts_registered:
        return True

    for style_key, candidates in _FONT_CANDIDATES.items():
        for path in candidates:
            if path.exists():
                try:
                    pdfmetrics.registerFont(TTFont(style_key, str(path)))
                    # Map style_key to role
                    if "Bold" in style_key:
                        _registered_names["bold"] = style_key
                    elif "Italic" in style_key:
                        _registered_names["italic"] = style_key
                    else:
                        _registered_names["normal"] = style_key
                    break  # found a font for this style
                except Exception as e:
                    print(f"Warning: Could not register font {style_key} from {path}: {e}")

    normal = _registered_names["normal"]
    bold = _registered_names["bold"]
    italic = _registered_names["italic"]

    if normal:
        pdfmetrics.registerFontFamily(
            normal,
            normal=normal,
            bold=bold or normal,
            italic=italic or normal,
            boldItalic=bold or normal,
        )
        _fonts_registered = True
        return True

    print("Warning: No Vietnamese fonts found. PDF may not display Vietnamese correctly.")
    return False


def get_font_name(bold: bool = False, italic: bool = False) -> str:
    """Get the appropriate registered font name."""
    register_vietnamese_fonts()

    normal = _registered_names["normal"] or "Helvetica"
    bold_name = _registered_names["bold"] or normal
    italic_name = _registered_names["italic"] or normal

    if bold:
        return bold_name
    if italic:
        return italic_name
    return normal
