"""
Date and airport extraction utilities for the LLM gateway fallback.

No external dependencies — pure Python.
"""

from __future__ import annotations

import re
from datetime import date, timedelta
from typing import Optional

# ---------------------------------------------------------------------------
# Airport name → code mapping
# ---------------------------------------------------------------------------

AIRPORT_MAP: dict[str, str] = {
    "hà nội": "HAN", "ha noi": "HAN", "noi bai": "HAN",
    "sài gòn": "SGN", "saigon": "SGN", "hồ chí minh": "SGN",
    "ho chi minh": "SGN", "hcmc": "SGN", "tân sơn nhất": "SGN",
    "đà nẵng": "DAD", "da nang": "DAD", "danang": "DAD",
    "nha trang": "CXR", "cam ranh": "CXR",
    "vinh": "VII",
    "huế": "HUI", "hue": "HUI", "phú bài": "HUI",
    "phú quốc": "PQC", "phu quoc": "PQC",
    "đà lạt": "DLI", "da lat": "DLI", "liên khương": "DLI",
    "cần thơ": "VCA", "can tho": "VCA",
    "hải phòng": "HPH", "hai phong": "HPH", "cát bi": "HPH",
    "quảng ninh": "VDO", "vân đồn": "VDO",
    "thanh hoá": "THD", "thanh hóa": "THD", "thanh hoa": "THD", "thọ xuân": "THD",
    "đồng hới": "VDH", "dong hoi": "VDH",
    "quy nhơn": "UIH", "quy nhon": "UIH", "phù cát": "UIH",
    "buôn ma thuột": "BMV", "buon ma thuot": "BMV", "tây nguyên": "BMV",
    "rạch giá": "VKG", "rach gia": "VKG",
    "cà mau": "CAH", "ca mau": "CAH",
    "côn đảo": "VCS", "con dao": "VCS",
    "tuy hoà": "TBB", "tuy hòa": "TBB", "tuy hoa": "TBB", "đông tác": "TBB",
}

# Airport codes (uppercase 3-letter) for direct code matching
AIRPORT_CODES: set[str] = {
    "HAN", "SGN", "DAD", "CXR", "VII", "HUI", "PQC",
    "DLI", "VCA", "HPH", "VDO", "THD", "VDH", "UIH",
    "BMV", "VKG", "CAH", "VCS", "TBB",
}

# Common words that follow "từ" / "đi" / "ở" but are NOT airports
STOP_WORDS: set[str] = {"ngày", "tháng", "năm", "mai", "kia", "nay", "mùng", "vào", "lúc", "giờ", "phút", "tìm", "vé", "cho", "với", "bạn", "mình", "tôi", "ơi", "nhé"}


def extract_airports_from_text(text: str) -> dict[str, str]:
    """
    Extract origin and destination airports from natural language.

    Patterns handled:
    - "từ Hà Nội đi Sài Gòn"
    - "Hanoi to Saigon"
    - "HAN → SGN"
    - "đi từ Hà Nội đến Sài Gòn"
    """
    result: dict[str, str] = {}
    lower = text.lower()

    # Try code-based direct match first (uppercase 3-letter codes)
    codes = re.findall(r"\b[A-Z]{3}\b", text)
    for code in codes:
        if code in AIRPORT_CODES:
            if "origin" not in result:
                result["origin"] = code
            elif "destination" not in result and code != result["origin"]:
                result["destination"] = code

    # Try Vietnamese patterns: từ X (đi|đến|tới|về) Y
    # Pattern: từ <place> [đi|đến|tới|về|ra|vào] <place>
    patterns = [
        (r"(?:từ|tu|from)\s+([\w\s]+?)\s+(?:đi|den|to|đến|tới|toi|về|ve|ra|vào|vao)\s+([\w\s]+)", True),
        (r"(?:đi|den|to)\s+([\w\s]+?)\s+(?:từ|tu|from)\s+([\w\s]+)", False),
    ]

    for pattern, forward in patterns:
        match = re.search(pattern, lower)
        if match:
            origin_raw = match.group(1 if forward else 2).strip()
            dest_raw = match.group(2 if forward else 1).strip()

            # Try to match each raw term against airport map
            for name, code in sorted(AIRPORT_MAP.items(), key=lambda x: -len(x[0])):
                if name in origin_raw and "origin" not in result:
                    result["origin"] = code
                if name in dest_raw and "destination" not in result:
                    result["destination"] = code

    return result


def extract_date_from_text(text: str) -> str:
    """Extract a date from natural language, return DDMMYYYY string."""
    lower = text.lower()
    today = date.today()

    # Relative dates
    if any(w in lower for w in ["hôm nay", "hom nay", "hnay", "today"]):
        return today.strftime("%d%m%Y")
    if any(w in lower for w in ["ngày mai", "ngay mai", "mai", "tomorrow"]):
        return (today + timedelta(days=1)).strftime("%d%m%Y")
    if any(w in lower for w in ["ngày kia", "ngay kia", "kia"]):
        return (today + timedelta(days=2)).strftime("%d%m%Y")

    # Explicit date patterns
    # DD/MM/YYYY or DD-MM-YYYY or DD.MM.YYYY
    m = re.search(r"(\d{1,2})\s*[/\-\.]\s*(\d{1,2})\s*[/\-\.]\s*(\d{4})", text)
    if m:
        d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
        return f"{d:02d}{mo:02d}{y}"

    # DD/MM or DD-MM (assume current year)
    m = re.search(r"(\d{1,2})\s*[/\-\.]\s*(\d{1,2})(?:\s*[/\-\.]\s*(\d{4}))?", text)
    if m:
        d, mo = int(m.group(1)), int(m.group(2))
        y = int(m.group(3)) if m.group(3) else today.year
        if y < 100:
            y += 2000
        return f"{d:02d}{mo:02d}{y}"

    # "mùng X/Y" or "ngày X/Y"
    m = re.search(r"(?:mùng|ngày|ngay)\s+(\d{1,2})\s*[/\-]\s*(\d{1,2})", lower)
    if m:
        d, mo = int(m.group(1)), int(m.group(2))
        y = today.year
        return f"{d:02d}{mo:02d}{y}"

    # Already DDMMYYYY 8-digit
    m = re.search(r"\b(\d{8})\b", text)
    if m:
        return m.group(1)

    # Fallback: today
    return today.strftime("%d%m%Y")
