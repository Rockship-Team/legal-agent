"""Vietnamese text processing utilities"""

import re
import unicodedata
from typing import Optional


def normalize_vietnamese(text: str) -> str:
    """
    Normalize Vietnamese text using NFD normalization.
    This ensures consistent handling of diacritics.
    """
    return unicodedata.normalize('NFD', text)


def clean_text(text: str) -> str:
    """Clean text by removing extra whitespace and normalizing"""
    # Remove extra whitespace
    text = re.sub(r'\s+', ' ', text)
    # Strip leading/trailing whitespace
    text = text.strip()
    return text


def extract_article_number(text: str) -> Optional[int]:
    """
    Extract article number from Vietnamese legal text.
    Matches patterns like "Điều 1", "Điều 123", "Dieu 45"
    """
    patterns = [
        r'Điều\s+(\d+)',
        r'ĐIỀU\s+(\d+)',
        r'Dieu\s+(\d+)',
        r'DIEU\s+(\d+)',
    ]

    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return int(match.group(1))

    return None


def extract_all_article_references(text: str) -> list[tuple[int, str]]:
    """
    Extract all article references from text.
    Returns list of (article_number, full_match) tuples.
    """
    pattern = r'(Điều|ĐIỀU|Dieu|DIEU)\s+(\d+)'
    matches = re.findall(pattern, text, re.IGNORECASE)

    results = []
    for prefix, num in matches:
        results.append((int(num), f"{prefix} {num}"))

    return results


def normalize_for_embedding(text: str) -> str:
    """NFC normalize for PhoBERT-based embedding models.

    CRITICAL: PhoBERT was trained on NFC text.
    Using NFD decomposes diacritics into combining marks,
    producing completely different token sequences.

    Rules:
    - NFC normalize (NOT NFD)
    - Collapse whitespace
    - Do NOT lowercase
    - Do NOT remove diacritics
    - Do NOT remove stop words
    """
    text = unicodedata.normalize("NFC", text)
    text = " ".join(text.split())
    return text.strip()


def normalize_category_name(text: str) -> str:
    """Normalize a string into a consistent category name (snake_case, no diacritics).

    Examples:
        "vay tiền"    → "vay_tien"
        "Vay Tiền"    → "vay_tien"
        "vaytien"     → "vay_tien"  (word boundary detection)
        "lao_dong"    → "lao_dong"
        "  Mua Bán "  → "mua_ban"
        "hợp đồng"   → "hop_dong"
    """
    # Step 1: NFC normalize, strip, lowercase
    text = unicodedata.normalize("NFC", text).strip().lower()
    # Step 2: Remove diacritics (vay tiền → vay tien)
    text = remove_diacritics(text)
    # Step 3: Replace any non-alphanumeric with underscore
    text = re.sub(r'[^a-z0-9]+', '_', text)
    # Step 4: Try to split concatenated words using a known word list
    # Common Vietnamese legal words (without diacritics)
    _WORDS = [
        "mua", "ban", "thue", "cho", "vay", "muon",
        "dat", "nha", "xe", "may", "oto", "phong",
        "lao", "dong", "dich", "vu", "dau", "tu",
        "dan", "su", "hinh", "thuong", "mai",
        "hop", "uy", "quyen", "bao", "hiem",
        "tien", "tai", "san", "kinh", "doanh",
    ]
    parts = text.split("_")
    expanded = []
    for part in parts:
        if not part:
            continue
        # If part is already a known word or very short, keep it
        if part in _WORDS or len(part) <= 3:
            expanded.append(part)
            continue
        # Try greedy left-to-right split into known words
        remaining = part
        split_parts = []
        while remaining:
            matched = False
            # Try longest match first
            for length in range(min(len(remaining), 6), 1, -1):
                candidate = remaining[:length]
                if candidate in _WORDS:
                    split_parts.append(candidate)
                    remaining = remaining[length:]
                    matched = True
                    break
            if not matched:
                # No known word found, keep the rest as-is
                split_parts.append(remaining)
                break
        expanded.extend(split_parts)
    result = "_".join(expanded)
    # Step 5: Clean up consecutive underscores
    result = re.sub(r'_+', '_', result).strip('_')
    return result or "other"


def edit_distance(a: str, b: str) -> int:
    """Levenshtein edit distance between two strings."""
    if len(a) < len(b):
        return edit_distance(b, a)
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a):
        curr = [i + 1]
        for j, cb in enumerate(b):
            cost = 0 if ca == cb else 1
            curr.append(min(curr[j] + 1, prev[j + 1] + 1, prev[j] + cost))
        prev = curr
    return prev[-1]


def remove_diacritics(text: str) -> str:
    """
    Remove Vietnamese diacritics from text for comparison.
    Converts "hợp đồng" -> "hop dong", "xem trước" -> "xem truoc"
    """
    # Vietnamese character mapping
    diacritics_map = {
        'à': 'a', 'á': 'a', 'ả': 'a', 'ã': 'a', 'ạ': 'a',
        'ă': 'a', 'ằ': 'a', 'ắ': 'a', 'ẳ': 'a', 'ẵ': 'a', 'ặ': 'a',
        'â': 'a', 'ầ': 'a', 'ấ': 'a', 'ẩ': 'a', 'ẫ': 'a', 'ậ': 'a',
        'đ': 'd',
        'è': 'e', 'é': 'e', 'ẻ': 'e', 'ẽ': 'e', 'ẹ': 'e',
        'ê': 'e', 'ề': 'e', 'ế': 'e', 'ể': 'e', 'ễ': 'e', 'ệ': 'e',
        'ì': 'i', 'í': 'i', 'ỉ': 'i', 'ĩ': 'i', 'ị': 'i',
        'ò': 'o', 'ó': 'o', 'ỏ': 'o', 'õ': 'o', 'ọ': 'o',
        'ô': 'o', 'ồ': 'o', 'ố': 'o', 'ổ': 'o', 'ỗ': 'o', 'ộ': 'o',
        'ơ': 'o', 'ờ': 'o', 'ớ': 'o', 'ở': 'o', 'ỡ': 'o', 'ợ': 'o',
        'ù': 'u', 'ú': 'u', 'ủ': 'u', 'ũ': 'u', 'ụ': 'u',
        'ư': 'u', 'ừ': 'u', 'ứ': 'u', 'ử': 'u', 'ữ': 'u', 'ự': 'u',
        'ỳ': 'y', 'ý': 'y', 'ỷ': 'y', 'ỹ': 'y', 'ỵ': 'y',
        # Uppercase
        'À': 'A', 'Á': 'A', 'Ả': 'A', 'Ã': 'A', 'Ạ': 'A',
        'Ă': 'A', 'Ằ': 'A', 'Ắ': 'A', 'Ẳ': 'A', 'Ẵ': 'A', 'Ặ': 'A',
        'Â': 'A', 'Ầ': 'A', 'Ấ': 'A', 'Ẩ': 'A', 'Ẫ': 'A', 'Ậ': 'A',
        'Đ': 'D',
        'È': 'E', 'É': 'E', 'Ẻ': 'E', 'Ẽ': 'E', 'Ẹ': 'E',
        'Ê': 'E', 'Ề': 'E', 'Ế': 'E', 'Ể': 'E', 'Ễ': 'E', 'Ệ': 'E',
        'Ì': 'I', 'Í': 'I', 'Ỉ': 'I', 'Ĩ': 'I', 'Ị': 'I',
        'Ò': 'O', 'Ó': 'O', 'Ỏ': 'O', 'Õ': 'O', 'Ọ': 'O',
        'Ô': 'O', 'Ồ': 'O', 'Ố': 'O', 'Ổ': 'O', 'Ỗ': 'O', 'Ộ': 'O',
        'Ơ': 'O', 'Ờ': 'O', 'Ớ': 'O', 'Ở': 'O', 'Ỡ': 'O', 'Ợ': 'O',
        'Ù': 'U', 'Ú': 'U', 'Ủ': 'U', 'Ũ': 'U', 'Ụ': 'U',
        'Ư': 'U', 'Ừ': 'U', 'Ứ': 'U', 'Ử': 'U', 'Ữ': 'U', 'Ự': 'U',
        'Ỳ': 'Y', 'Ý': 'Y', 'Ỷ': 'Y', 'Ỹ': 'Y', 'Ỵ': 'Y',
    }

    result = []
    for char in text:
        result.append(diacritics_map.get(char, char))
    return ''.join(result)
