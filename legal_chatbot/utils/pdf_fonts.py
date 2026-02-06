"""Vietnamese font support for ReportLab PDF generation"""

import os
from pathlib import Path
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# Font registration status
_fonts_registered = False

# Vietnamese-compatible fonts to try (in order of preference)
VIETNAMESE_FONTS = [
    # Windows fonts with Vietnamese support
    ("Times-Vietnamese", "C:/Windows/Fonts/times.ttf"),
    ("Times-Vietnamese-Bold", "C:/Windows/Fonts/timesbd.ttf"),
    ("Times-Vietnamese-Italic", "C:/Windows/Fonts/timesi.ttf"),
    ("Arial-Vietnamese", "C:/Windows/Fonts/arial.ttf"),
    ("Arial-Vietnamese-Bold", "C:/Windows/Fonts/arialbd.ttf"),
    ("Tahoma-Vietnamese", "C:/Windows/Fonts/tahoma.ttf"),
    ("Tahoma-Vietnamese-Bold", "C:/Windows/Fonts/tahomabd.ttf"),
]

# Fallback font name
DEFAULT_FONT = "Times-Vietnamese"
DEFAULT_FONT_BOLD = "Times-Vietnamese-Bold"
DEFAULT_FONT_ITALIC = "Times-Vietnamese-Italic"


def register_vietnamese_fonts():
    """Register Vietnamese-compatible fonts with ReportLab"""
    global _fonts_registered

    if _fonts_registered:
        return True

    registered = []

    for font_name, font_path in VIETNAMESE_FONTS:
        if os.path.exists(font_path):
            try:
                pdfmetrics.registerFont(TTFont(font_name, font_path))
                registered.append(font_name)
            except Exception as e:
                print(f"Warning: Could not register font {font_name}: {e}")

    if registered:
        _fonts_registered = True
        return True

    print("Warning: No Vietnamese fonts found. PDF may not display Vietnamese correctly.")
    return False


def get_font_name(bold: bool = False, italic: bool = False) -> str:
    """Get the appropriate font name based on style"""
    register_vietnamese_fonts()

    if bold and italic:
        return DEFAULT_FONT_BOLD  # No bold-italic, use bold
    elif bold:
        return DEFAULT_FONT_BOLD
    elif italic:
        return DEFAULT_FONT_ITALIC
    else:
        return DEFAULT_FONT


def is_font_available(font_name: str) -> bool:
    """Check if a font is registered"""
    register_vietnamese_fonts()
    try:
        pdfmetrics.getFont(font_name)
        return True
    except KeyError:
        return False
