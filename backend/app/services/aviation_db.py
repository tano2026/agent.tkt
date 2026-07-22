"""
Aviation Domain Database — Kiến thức hàng không Việt Nam.

Cung cấp lookup nhanh:
- Mã sân bay ↔ tên/địa danh
- Mã hãng bay ↔ tên hãng
- Địa danh địa phương → mã sân bay
"""

from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Airport Database — mapping code ↔ thông tin
# ---------------------------------------------------------------------------

AIRPORTS: dict[str, dict] = {
    "HAN": {"name": "Nội Bài", "city": "Hà Nội", "region": "Bắc Bộ"},
    "SGN": {"name": "Tân Sơn Nhất", "city": "Hồ Chí Minh", "region": "Nam Bộ"},
    "DAD": {"name": "Đà Nẵng", "city": "Đà Nẵng", "region": "Trung Bộ"},
    "CXR": {"name": "Cam Ranh", "city": "Nha Trang", "region": "Trung Bộ"},
    "HUI": {"name": "Phú Bài", "city": "Huế", "region": "Trung Bộ"},
    "PQC": {"name": "Phú Quốc", "city": "Phú Quốc", "region": "Nam Bộ"},
    "HPH": {"name": "Cát Bi", "city": "Hải Phòng", "region": "Bắc Bộ"},
    "VCA": {"name": "Trà Nóc", "city": "Cần Thơ", "region": "Nam Bộ"},
    "VII": {"name": "Vinh", "city": "Vinh", "region": "Bắc Trung Bộ"},
    "TBB": {"name": "Đông Tác", "city": "Tuy Hòa", "region": "Trung Bộ"},
    "DLI": {"name": "Liên Khương", "city": "Đà Lạt", "region": "Tây Nguyên"},
    "PXU": {"name": "Pleiku", "city": "Pleiku", "region": "Tây Nguyên"},
    "UIH": {"name": "Phù Cát", "city": "Quy Nhơn", "region": "Trung Bộ"},
    "VCL": {"name": "Chu Lai", "city": "Tam Kỳ", "region": "Trung Bộ"},
    "BMV": {"name": "Buôn Ma Thuột", "city": "Buôn Ma Thuột", "region": "Tây Nguyên"},
    "CAH": {"name": "Cà Mau", "city": "Cà Mau", "region": "Nam Bộ"},
    "VCS": {"name": "Côn Đảo", "city": "Côn Đảo", "region": "Nam Bộ"},
    "DIN": {"name": "Điện Biên", "city": "Điện Biên", "region": "Tây Bắc"},
    # International
    "BKK": {"name": "Suvarnabhumi", "city": "Bangkok", "region": "Quốc tế"},
    "DMK": {"name": "Don Mueang", "city": "Bangkok", "region": "Quốc tế"},
    "NRT": {"name": "Narita", "city": "Tokyo", "region": "Quốc tế"},
    "KIX": {"name": "Kansai", "city": "Osaka", "region": "Quốc tế"},
    "ICN": {"name": "Incheon", "city": "Seoul", "region": "Quốc tế"},
    "SIN": {"name": "Changi", "city": "Singapore", "region": "Quốc tế"},
    "KUL": {"name": "Kuala Lumpur", "city": "Kuala Lumpur", "region": "Quốc tế"},
    "PEK": {"name": "Beijing Capital", "city": "Bắc Kinh", "region": "Quốc tế"},
    "PVG": {"name": "Pudong", "city": "Thượng Hải", "region": "Quốc tế"},
    "CDG": {"name": "Charles de Gaulle", "city": "Paris", "region": "Quốc tế"},
    "SFO": {"name": "San Francisco", "city": "San Francisco", "region": "Quốc tế"},
}

# ---------------------------------------------------------------------------
# Địa danh → mã sân bay (alias mapping)
# ---------------------------------------------------------------------------

LOCATION_ALIASES: dict[str, str] = {
    # Hà Nội / Miền Bắc
    "hà nội": "HAN", "hn": "HAN", "hanoi": "HAN", "hà nôi": "HAN",
    "hải phòng": "HPH", "hải phong": "HPH", "hp": "HPH", "haiphong": "HPH",
    "vinh": "VII",
    "điện biên": "DIN", "dien bien": "DIN",
    # Miền Trung
    "đà nẵng": "DAD", "dn": "DAD", "da nang": "DAD", "đà nẳng": "DAD", "đn": "DAD",
    "huế": "HUI", "hue": "HUI",
    "nha trang": "CXR", "nt": "CXR", "nha trang": "CXR", "nhatrang": "CXR",
    "tuy hòa": "TBB", "tuy hoa": "TBB",
    "quy nhơn": "UIH", "quy nhon": "UIH", "qn": "UIH",
    "tam kỳ": "VCL", "tam ky": "VCL",
    # Miền Nam
    "sài gòn": "SGN", "sg": "SGN", "hồ chí minh": "SGN", "hcm": "SGN",
    "saigon": "SGN", "saì gòn": "SGN", "sai gon": "SGN", "tp hcm": "SGN",
    "cần thơ": "VCA", "can tho": "VCA", "ct": "VCA",
    "cà mau": "CAH", "ca mau": "CAH",
    "côn đảo": "VCS", "con dao": "VCS", "condao": "VCS",
    # Tây Nguyên
    "đà lạt": "DLI", "da lat": "DLI", "dalat": "DLI", "đà lạt": "DLI",
    "pleiku": "PXU",
    "buôn ma thuột": "BMV", "buon ma thuot": "BMV", "bmt": "BMV",
    # Đảo
    "phú quốc": "PQC", "phu quoc": "PQC", "pq": "PQC",
    # Quốc tế
    "bangkok": "BKK", "băng cốc": "BKK", "bang coc": "BKK",
    "tokyo": "NRT",
    "seoul": "ICN",
    "singapore": "SIN",
    "kuala lumpur": "KUL",
    "bắc kinh": "PEK",
    "thượng hải": "PVG",
    "paris": "CDG",
    "san francisco": "SFO",
}

# ---------------------------------------------------------------------------
# Airline Database
# ---------------------------------------------------------------------------

AIRLINES: dict[str, dict] = {
    "VN": {"name": "Vietnam Airlines", "short": "VNA", "type": "full-service"},
    "VJ": {"name": "VietJet Air", "short": "VietJet", "type": "low-cost"},
    "QH": {"name": "Bamboo Airways", "short": "Bamboo", "type": "full-service"},
    "BL": {"name": "Pacific Airlines", "short": "Pacific", "type": "low-cost"},
    "VU": {"name": "Vietravel Airlines", "short": "Vietravel", "type": "full-service"},
    "SQ": {"name": "Singapore Airlines", "short": "SIA", "type": "full-service"},
    "TG": {"name": "Thai Airways", "short": "Thai", "type": "full-service"},
    "KE": {"name": "Korean Air", "short": "Korean", "type": "full-service"},
    "JL": {"name": "Japan Airlines", "short": "JAL", "type": "full-service"},
    "CX": {"name": "Cathay Pacific", "short": "Cathay", "type": "full-service"},
    "EK": {"name": "Emirates", "short": "Emirates", "type": "full-service"},
}

AIRLINE_ALIASES: dict[str, str] = {
    "vietnam airlines": "VN", "vna": "VN", "hàng không": "VN",
    "vietjet": "VJ", "viet jet": "VJ", "vj": "VJ",
    "bamboo": "QH", "bamboo airways": "QH",
    "pacific": "BL", "pacific airlines": "BL",
    "vietravel": "VU", "vietravel airlines": "VU",
}


# ---------------------------------------------------------------------------
# Chính sách hãng (tổng quan)
# ---------------------------------------------------------------------------

POLICIES: dict[str, dict] = {
    "hành lý": {
        "VN": "Hành lý xách tay 1 kiện 10kg. Hành lý ký gửi: Economy 20-23kg, Business 32kg.",
        "VJ": "Hành lý xách tay 1 kiện 7kg. Hành lý ký gửi mua thêm theo gói (15-40kg).",
        "QH": "Hành lý xách tay 1 kiện 10kg. Hành lý ký gửi 20-32kg tùy hạng vé.",
        "chung": "Hành lý mua thêm tại sân bay thường đắt hơn mua online 30-50%.",
    },
    "đổi vé": {
        "VN": "Đổi tên: không được. Đổi ngày: mất phí 200.000-500.000đ + chênh lệch giá.",
        "VJ": "Đổi tên: 100.000-300.000đ. Đổi ngày: mất phí + chênh lệch giá.",
        "QH": "Đổi tên: không được. Đổi ngày: mất phí 0-300.000đ + chênh lệch.",
        "chung": "Vé rẻ (Economy Smart/Eco) thường không được đổi. Vé thường có phí đổi.",
    },
    "hủy vé": {
        "VN": "Hủy trước 24h: mất 30-50% giá vé. Hủy sau 24h: mất 70-100%.",
        "VJ": "Hủy trước 3h: mất 50-70%. Hủy sau: mất 100%. Vé rẻ không hoàn.",
        "QH": "Hủy trước 24h: mất 30%. Hủy sau: mất 70-100%.",
        "chung": "Vé khuyến mãi thường không hoàn tiền khi hủy.",
    },
    "giấy tờ": {
        "nội địa": "Người lớn: CMND/CCCD còn hạn. Trẻ em dưới 14t: giấy khai sinh hoặc hộ chiếu. Trẻ sơ sinh: giấy khai sinh.",
        "quốc tế": "Hộ chiếu còn hạn 6 tháng. Visa (nếu cần). Giấy tờ trẻ em: hộ chiếu riêng hoặc kèm cha/mẹ.",
    },
}


def resolve_location(text: str) -> str | None:
    """Tra cứu địa danh → mã sân bay."""
    key = text.lower().strip()
    return LOCATION_ALIASES.get(key)


def resolve_airline(text: str) -> str | None:
    """Tra cứu tên hãng → mã hãng."""
    key = text.lower().strip()
    return AIRLINE_ALIASES.get(key)


def get_airport_info(code: str) -> dict | None:
    """Lấy thông tin sân bay."""
    return AIRPORTS.get(code.upper())


def get_all_airports() -> dict:
    """Lấy tất cả sân bay."""
    return dict(AIRPORTS)


def get_policy(topic: str, airline: str = "") -> str:
    """Lấy thông tin chính sách."""
    topic = topic.lower()
    if topic in POLICIES:
        policy_data = POLICIES[topic]
        result = []
        if airline and airline in policy_data:
            result.append(f"✈️ **{airline}**: {policy_data[airline]}")
        elif airline:
            result.append(f"**{airline}**: Không có thông tin chi tiết.")
        if "chung" in policy_data:
            result.append(f"📌 *Lưu ý chung*: {policy_data['chung']}")
        return "\n\n".join(result) if result else "Không có thông tin cho chủ đề này."
    else:
        # Check sub-topics like "nội địa", "quốc tế"
        return POLICIES.get("giấy tờ", {}).get(topic, "Không có thông tin.")
