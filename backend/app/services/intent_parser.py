"""
Intent Parser V3 — Aviation-specific NLP with slang/dialect support.

Parse câu hỏi tiếng Việt tự nhiên về vé máy bay thành structured intent.
Không gọi LLM cho câu đơn giản — dùng rule-based cho tốc độ.
Có hỗ trợ tiếng địa phương, viết tắt, tiếng lóng phòng vé.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta
from typing import Any, Optional

from app.services.aviation_db import resolve_location, resolve_airline, get_policy

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# SLANG & VIẾT TẮT TIẾNG VIỆT — phòng vé, dân du lịch, khách hàng
# ---------------------------------------------------------------------------

# Từ điển viết tắt / tiếng lóng → IATA code
_LOCATION_SLANG: dict[str, str] = {
    # Miền Bắc
    "hà nội": "HAN", "hn": "HAN", "han": "HAN",
    "nội bài": "HAN", "noi bai": "HAN",
    "hải phòng": "HPH", "hph": "HPH", "cát bi": "HPH",
    "quảng ninh": "VDO", "vân đồn": "VDO",
    "vinh": "VII", "vii": "VII", "nghệ an": "VII",
    "thanh hóa": "THD", "thọ xuân": "THD",
    "điện biên": "DIN", "dien bien": "DIN",
    # Miền Trung
    "đà nẵng": "DAD", "dn": "DAD", "dad": "DAD", "da nang": "DAD", "dng": "DAD",
    "huế": "HUI", "hue": "HUI", "hui": "HUI", "phú bài": "HUI",
    "nha trang": "CXR", "nt": "CXR", "cxr": "CXR", "cam ranh": "CXR",
    "quy nhơn": "UIH", "uih": "UIH", "phù cát": "UIH",
    "tuy hòa": "TBB", "tbb": "TBB", "phú yên": "TBB",
    "pleiku": "PXU", "pxu": "PXU", "gia lai": "PXU",
    "buôn ma thuột": "BMV", "bmv": "BMV", "bmt": "BMV", "dak lak": "BMV",
    "đồng hới": "VDH", "vdh": "VDH", "quảng bình": "VDH",
    "chu lai": "VCL", "vcl": "VCL", "quảng nam": "VCL",
    "đà lạt": "DLI", "dli": "DLI", "da lat": "DLI", "liên khương": "DLI",
    # Miền Nam
    "sài gòn": "SGN", "sg": "SGN", "hcm": "SGN", "sgn": "SGN",
    "saigon": "SGN", "tphcm": "SGN", "tp.hcm": "SGN",
    "tân sơn nhất": "SGN", "tan son nhat": "SGN",
    "phú quốc": "PQC", "pq": "PQC", "pqc": "PQC", "phu quoc": "PQC",
    "cần thơ": "VCA", "vca": "VCA", "can tho": "VCA",
    "côn đảo": "VCS", "vcs": "VCS", "con dao": "VCS",
    "rạch giá": "VKG", "vkg": "VKG", "rach gia": "VKG",
    # Quốc tế
    "bangkok": "BKK", "bkk": "BKK", "krung thep": "BKK",
    "singapore": "SIN", "sin": "SIN",
    "tokyo": "NRT", "nrt": "NRT", "narita": "NRT",
    "seoul": "ICN", "icn": "ICN", "incheon": "ICN",
    "đài bắc": "TPE", "tpe": "TPE", "dai bac": "TPE", "đài loan": "TPE",
    "hong kong": "HKG", "hkg": "HKG",
    "bangkok": "BKK", "bkk": "BKK",
}

# Từ điển hãng — viết tắt + tên lóng
_AIRLINE_SLANG: dict[str, str] = {
    "vna": "VN", "vietnam airlines": "VN",
    "vietjet": "VJ", "vj": "VJ",
    "bamboo": "QH", "qh": "QH", "bamboo airways": "QH",
    "vietravel": "VU", "vu": "VU", "vietravel airlines": "VU",
    "sun": "9G", "9g": "9G", "sun phuquoc": "9G",
    "pacific": "BL", "bl": "BL", "pacific airlines": "BL",
}

# ---------------------------------------------------------------------------
# INTENT KEYWORDS — mở rộng với tiếng lóng
# ---------------------------------------------------------------------------

_INTENT_FLIGHT_SEARCH = [
    # Chuẩn
    "vé", "tìm", "chuyến", "bay", "máy bay", "giá vé", "giá",
    "sg", "hn", "hcm", "sgn", "han", "sài gòn", "hà nội",
    "đà nẵng", "nha trang", "phú quốc", "đi", "từ",
    # Tiếng lóng / viết tắt
    "vé bay", "kiếm vé", "có vé", "còn vé", "check vé",
    "giá bao nhiêu", "bao nhiêu tiền", "tiền vé", "giá vé đi",
    "cho tôi xin giá", "báo giá", "báo vé",
    "kiếm chuyến", "có chuyến", "chuyến nào",
    "hàng", "có hàng", "kiểm tra hàng", "còn hàng",
    "từ...đi", "từ...ra", "từ...vào",
    "sg đi hn", "hn đi sg", "sgn han", "han sgn",
    "từ sg", "từ hn",
]

_INTENT_BOOKING = [
    "đặt", "book", "mua vé", "lấy vé", "chốt vé",
    "giữ chỗ", "cọc vé", "đặt cọc",
    "đặt chỗ", "đặt dùm", "book dùm",
    "xuất vé", "ra vé", "lấy booking",
    "đặt vé", "mua dùm",
]

_INTENT_RETRIEVE = [
    "tra cứu", "mã đặt", "booking code", "check booking",
    "kiểm tra vé", "xem vé", "mã vé", "mã pnr", "pnr",
    "tra vé", "soát vé", "xem booking",
]

_INTENT_BAGGAGE = [
    "hành lý", "xách tay", "ký gửi", "bao nhiêu kg",
    "vali", "hành lý ký gửi", "hành lý xách tay",
    "mang được", "được mang", "mang lên máy bay",
    "hành lý bao nhiêu", "kg", "kí",
]

_INTENT_CHANGE = [
    "đổi vé", "đổi ngày", "đổi tên", "change",
    "dời vé", "dời ngày", "dời chuyến",
    "đổi chuyến", "thay đổi vé",
]

_INTENT_CANCEL = [
    "hủy", "hoàn", "hủy vé", "cancel",
    "hủy chỗ", "hủy booking", "bỏ vé",
    "hoàn tiền", "hoàn vé", "lấy lại tiền",
]

_INTENT_DOCUMENTS = [
    "giấy tờ", "cần gì", "thủ tục", "check-in",
    "cần mang", "xuất trình", "làm thủ tục",
    "checkin", "online checkin", "làm checkin",
]

_INTENT_POLICY = [
    "chính sách", "quy định", "điều kiện",
    "thể lệ", "luật", "điều khoản",
]

_INTENT_FARE_RULE = [
    "điều kiện vé", "fare rule", "quy định giá",
    "điều kiện giá", "fare basis", "hạng vé",
]

# ---------------------------------------------------------------------------
# Date parsing utilities
# ---------------------------------------------------------------------------

TODAY = datetime.now().date()

VIETNAMESE_MONTHS = {
    "tháng 1": 1, "tháng một": 1, "tháng giêng": 1,
    "tháng 2": 2, "tháng hai": 2,
    "tháng 3": 3, "tháng ba": 3,
    "tháng 4": 4, "tháng tư": 4,
    "tháng 5": 5, "tháng năm": 5,
    "tháng 6": 6, "tháng sáu": 6,
    "tháng 7": 7, "tháng bảy": 7,
    "tháng 8": 8, "tháng tám": 8,
    "tháng 9": 9, "tháng chín": 9,
    "tháng 10": 10, "tháng mười": 10,
    "tháng 11": 11, "tháng mười một": 11,
    "tháng 12": 12, "tháng mười hai": 12,
}


def parse_relative_date(text: str) -> str | None:
    """Parse relative date expressions → DDMMYYYY."""
    text = text.lower().strip()

    # "ngày mai" / "mai" / "sáng mai" / "chiều mai"
    if re.search(r'\b(mai|ngày\s*mai|sáng\s*mai|chiều\s*mai|tối\s*mai)\b', text):
        return (TODAY + timedelta(days=1)).strftime("%d%m%Y")

    # "ngày kia" / "kia" / "hôm kia"
    if re.search(r'\b(ngày\s*kia|kia|hôm\s*kia)\b', text):
        return (TODAY + timedelta(days=2)).strftime("%d%m%Y")

    # "cuối tuần" = next Saturday
    if "cuối tuần" in text or "cuoi tuan" in text:
        days_ahead = 5 - TODAY.weekday()  # Saturday = 5
        if days_ahead <= 0:
            days_ahead += 7
        return (TODAY + timedelta(days=days_ahead)).strftime("%d%m%Y")

    # "tuần sau" = +7 days
    if "tuần sau" in text or "tuan sau" in text:
        return (TODAY + timedelta(days=7)).strftime("%d%m%Y")

    # "tháng sau" = +1 month
    if "tháng sau" in text or "thang sau" in text:
        next_month = TODAY.month + 1
        year = TODAY.year
        if next_month > 12:
            next_month = 1
            year += 1
        return datetime(year, next_month, 1).strftime("%d%m%Y")

    # "hôm nay" / "hôm ni" / "bữa nay" = today
    if "hôm nay" in text or "hom nay" in text or "bữa nay" in text or "hôm ni" in text:
        return TODAY.strftime("%d%m%Y")

    return None


def parse_date(text: str) -> str | None:
    """Parse date from text → DDMMYYYY."""
    text = text.strip()

    # Try relative first
    rel = parse_relative_date(text)
    if rel:
        return rel

    # DD/MM or DD/MM/YYYY or DD-MM or DD-MM-YYYY
    match = re.search(r'(\d{1,2})\s*[/\-]\s*(\d{1,2})(?:\s*[/\-]\s*(\d{2,4}))?', text)
    if match:
        day, month = int(match.group(1)), int(match.group(2))
        year_str = match.group(3)
        year = int(year_str) if year_str else TODAY.year
        if year < 100:
            year += 2000
        try:
            return datetime(year, month, day).strftime("%d%m%Y")
        except ValueError:
            pass

    # DD tháng MM [năm YYYY] — "20 tháng 7" or "20 tháng 7 năm 2026"
    match = re.search(r'(\d{1,2})\s*tháng\s*(\d{1,2})(?:\s*năm\s*(\d{2,4}))?', text)
    if match:
        day, month = int(match.group(1)), int(match.group(2))
        year_str = match.group(3)
        year = int(year_str) if year_str else TODAY.year
        if year < 100:
            year += 2000
        try:
            return datetime(year, month, day).strftime("%d%m%Y")
        except ValueError:
            pass

    # MMM DD — "July 20", "Jul 20", "july 20"
    match = re.search(r'(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\s*\.?\s*(\d{1,2})(?:st|nd|rd|th)?', text.lower())
    if match:
        month_map = {
            "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
            "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
        }
        month_abbr = match.group(1)[:3]  # "july"[:3] = "jul"
        month = month_map.get(month_abbr)
        if month is None:
            return None
        day = int(match.group(2))
        year = TODAY.year
        try:
            return datetime(year, month, day).strftime("%d%m%Y")
        except ValueError:
            pass

    return None


# ---------------------------------------------------------------------------
# Passenger parsing
# ---------------------------------------------------------------------------

def parse_passengers(text: str) -> dict:
    """Parse number of passengers from text. Supports slang."""
    result = {"adults": 1, "children": 0, "infants": 0}
    text_lower = text.lower()

    # "2 người", "2 khách", "2 vé", "2 người lớn", "2 pax"
    match = re.search(r'(\d+)\s*(người|khách|vé|pax|người\s*lớn|nguoi|khach)', text_lower)
    if match:
        result["adults"] = int(match.group(1))

    # "1 trẻ em", "2 trẻ", "1 trẻ nhỏ"
    match = re.search(r'(\d+)\s*(trẻ\s*em|trẻ|trẻ\s*nhỏ|bé|tre\s*em|tre|be)', text_lower)
    if match:
        result["children"] = int(match.group(1))

    # "1 em bé", "2 em", "1 infant"
    match = re.search(r'(\d+)\s*(em\s*bé|em\s*nhỏ|infant|sơ\s*sinh|baby)', text_lower)
    if match:
        result["infants"] = int(match.group(1))

    return result


# ---------------------------------------------------------------------------
# Intent classification
# ---------------------------------------------------------------------------

def classify_intent(text: str) -> str:
    """Classify the intent of the user message."""
    text_lower = text.lower()

    # Policy questions — check specific first
    if any(kw in text_lower for kw in _INTENT_BAGGAGE):
        return "policy_baggage"
    if any(kw in text_lower for kw in _INTENT_CHANGE):
        return "policy_change"
    if any(kw in text_lower for kw in _INTENT_CANCEL):
        return "policy_cancel"
    if any(kw in text_lower for kw in _INTENT_DOCUMENTS):
        return "policy_documents"
    if any(kw in text_lower for kw in _INTENT_POLICY):
        return "policy_general"

    # Fare rule
    if any(kw in text_lower for kw in _INTENT_FARE_RULE):
        return "fare_rule"

    # Retrieve booking
    if any(kw in text_lower for kw in _INTENT_RETRIEVE):
        return "retrieve_booking"

    # Booking intent
    if any(kw in text_lower for kw in _INTENT_BOOKING):
        return "book_flight"

    # SmartAgent Services
    if any(kw in text_lower for kw in ["fast track", "fasttrack", "ưu tiên", "uu tien", "vip"]):
        if any(kw in text_lower for kw in ["nội bài", "noi bai"]):
            return "service_fasttrack"
        return "service_fasttrack"

    if any(kw in text_lower for kw in ["esim", "e-sim", "sim", "4g", "5g", "internet", "data", "wifi"]):
        return "service_esim"

    if any(kw in text_lower for kw in ["visa", "thị thực", "thi thuc", "xin visa"]):
        return "service_visa"

    if any(kw in text_lower for kw in ["hộ chiếu", "ho chieu", "passport", "cấp hộ chiếu"]):
        return "service_passport"

    # Default to flight search
    return "search_flight"


def classify_service(message: str) -> str:
    """Xác định service từ message. Trả về: flight, fasttrack, esim, visa, passport"""
    msg = message.strip().lower()

    if any(kw in msg for kw in ["fast track", "fasttrack", "ưu tiên", "uu tien", "vip"]):
        return "fasttrack"
    if any(kw in msg for kw in ["esim", "e-sim", "sim du lịch", "sim di động", "4g", "5g", "internet", "data", "wifi"]):
        return "esim"
    if any(kw in msg for kw in ["visa", "thị thực", "thi thuc", "xin visa"]):
        return "visa"
    if any(kw in msg for kw in ["hộ chiếu", "ho chieu", "passport"]):
        return "passport"
    if any(kw in msg for kw in ["vé máy bay", "vé", "bay", "tìm vé", "flight"]):
        return "flight"

    return "flight"

    # Check if text contains known airport codes or slang
    for slang, code in _LOCATION_SLANG.items():
        if slang in text_lower:
            return "search_flight"

    # Airline info
    if any(kw in text_lower for kw in _AIRLINE_SLANG):
        return "airline_info"

    # Default
    return "greeting"


# ---------------------------------------------------------------------------
# Flight search parsing
# ---------------------------------------------------------------------------

def _find_locations(text_lower: str) -> list[tuple[str, str]]:
    """Find all location mentions with position, de-duplicate overlapping.
    Returns sorted list of (position, name, code)."""
    matches = []
    for name, code in _LOCATION_SLANG.items():
        # Use word boundary matching to avoid partial matches
        for m in re.finditer(r'\b' + re.escape(name) + r'\b', text_lower):
            matches.append((m.start(), m.end(), name, code))

    if not matches:
        return []

    # Sort by position
    matches.sort(key=lambda x: x[0])

    # De-duplicate overlapping (keep longest) AND remove same-code duplicates
    filtered = []
    matched_codes = set()
    for m in matches:
        code = m[3]
        if code in matched_codes:
            # Same code already found — skip unless this position pair is different
            # Check if the first match position pair is different
            continue

        if not filtered:
            filtered.append(m)
            matched_codes.add(code)
        else:
            prev = filtered[-1]
            # If overlapping, keep the longer one
            if m[0] < prev[1]:
                if (m[1] - m[0]) > (prev[1] - prev[0]):
                    # m is longer, replace prev — update matched set
                    matched_codes.discard(prev[3])
                    filtered[-1] = m
                    matched_codes.add(code)
                # otherwise keep prev
            else:
                filtered.append(m)
                matched_codes.add(code)

    return [(m[3], m[2]) for m in filtered]  # (code, name)


def parse_flight_search(text: str) -> dict | None:
    """
    Parse câu tìm vé → tham số search.
    Trả về None nếu không tìm thấy route.

    Hỗ trợ:
    - "từ SGN đi HAN ngày mai 2 người"
    - "SGN HAN 20/7"
    - "có vé SG đi HN cuối tuần này 1 người"
    - "kiếm chuyến từ Hà Nội vào SG ngày kia"
    - "có hàng SG-HN không?" (tiếng lóng phòng vé)
    """
    text_lower = text.lower()
    params: dict[str, Any] = {}

    # Find locations
    location_matches = _find_locations(text_lower)

    if len(location_matches) >= 2:
        params["origin"] = location_matches[0][0]
        params["destination"] = location_matches[1][0]
    elif len(location_matches) == 1:
        code = location_matches[0][0]
        # Check direction words before the location
        idx = text_lower.find(location_matches[0][1])
        before = text_lower[max(0, idx - 30):idx]

        # Từ khóa chỉ điểm đến
        dest_kw = ["đi", "đến", "vào", "qua", "ra", "về", "di", "den", "vao", "qua"]

        # Từ khóa chỉ điểm đi
        origin_kw = ["từ", "tu", "ở", "tại", "o", "tai"]

        # Detect: "đi HAN", "vào SG", "ra HN" → HAN/SG/HN là destination
        if any(kw in before for kw in dest_kw):
            params["destination"] = code
        elif any(kw in before for kw in origin_kw):
            params["origin"] = code
        else:
            params["origin"] = code

    # Parse date
    date = parse_date(text)
    if date:
        params["date"] = date

    # Parse passengers
    passengers = parse_passengers(text)
    params.update(passengers)

    # Parse cabin class
    if any(kw in text_lower for kw in ["thương gia", "business", "hạng nhất", "first", "hạng sang"]):
        params["cabin_class"] = "business"
    else:
        params["cabin_class"] = "economy"

    # Round-trip detection
    if any(kw in text_lower for kw in ["khứ hồi", "vé về", "bay về", "vé khứ hồi", "2 chiều", "cả đi lẫn về"]):
        params["is_return"] = True

    if "origin" in params and "destination" in params:
        return params

    # Partial match — still return what we have (for clarify flow)
    if "origin" in params or "destination" in params:
        return params

    return None


def parse_booking_intent(text: str) -> dict | None:
    """
    Parse booking intent — rút thông tin đặt vé.
    """
    text_lower = text.lower()
    params: dict[str, Any] = {}

    # Tìm flight code
    match = re.search(r'\b([A-Z0-9]{2,3}\s*\d{3,4})\b', text)
    if match:
        params["flight_code"] = match.group(1).replace(" ", "")

    # Tìm thông tin người đặt nếu có
    # Name pattern: "tên [Name]" or "Nguyễn Văn A"
    # Phone pattern: 0\d{9,10}
    match = re.search(r'(0\d{9,10})', text)
    if match:
        params["phone"] = match.group(1)

    return params if params else None


def check_missing_info(parsed: dict) -> list[str]:
    """Check what info is missing for a flight search. Returns list of missing fields."""
    missing = []
    if "origin" not in parsed or not parsed.get("origin"):
        missing.append("điểm đi")
    if "destination" not in parsed or not parsed.get("destination"):
        missing.append("điểm đến")
    if "date" not in parsed or not parsed.get("date"):
        missing.append("ngày bay")
    return missing


def generate_clarify_question(missing: list[str], parsed: dict) -> str | None:
    """Generate a natural question to ask the customer for missing info."""
    if not missing:
        return None

    origin = parsed.get("origin", "")
    dest = parsed.get("destination", "")
    date = parsed.get("date", "")
    adults = parsed.get("adults", 1)

    # Map codes to Vietnamese airport names
    _AIRPORT_VIET = {
        "SGN": "TP.HCM", "HAN": "Hà Nội", "DAD": "Đà Nẵng",
        "CXR": "Nha Trang", "DLI": "Đà Lạt", "PQC": "Phú Quốc",
        "HUI": "Huế", "VCS": "Côn Đảo", "VDH": "Đồng Hới",
        "VII": "Vinh", "DIN": "Điện Biên", "HPH": "Hải Phòng",
        "VDO": "Vân Đồn", "UIH": "Quy Nhơn", "TBB": "Tuy Hòa",
        "PXU": "Pleiku", "BMV": "Buôn Ma Thuột", "VCA": "Cần Thơ",
        "VKG": "Rạch Giá", "VCL": "Chu Lai",
    }
    origin_name = _AIRPORT_VIET.get(origin, origin) if origin else ""
    dest_name = _AIRPORT_VIET.get(dest, dest) if dest else ""

    if not origin and not dest:
        return "✈️ Bạn muốn bay từ đâu đi đâu vậy ạ?"
    if origin and not dest:
        return f"✈️ Từ {origin_name}, bạn muốn bay đi đâu ạ?"
    if dest and not origin:
        return f"✈️ Bạn muốn bay từ đâu đến {dest_name} ạ?"
    if origin and dest and not date:
        return f"✈️ Từ {origin_name} → {dest_name}, bạn bay ngày nào ạ?"
    if origin and dest and date:
        # All info available — just confirm rather than ask
        try:
            d = datetime.strptime(date, "%d%m%Y")
            date_display = d.strftime("%d/%m/%Y")
        except ValueError:
            date_display = date
        return None  # All set

    return "✈️ Bạn vui lòng cho biết điểm đi, điểm đến và ngày bay nhé!"
