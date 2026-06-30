"""
Aviation Database — Vietnamese domain knowledge for the Ticketing Bot.

Contains:
- Airport codes (IATA → name, city, aliases)
- City/region aliases (Vietnamese local names → airport code)
- Airline codes (IATA → name, policies)
- Vietnamese date/time parsers
"""

# ─── AIRPORTS ───────────────────────────────────────────────────────────────
# Each entry: IATA → {name, city, vietnam (bool), searchable_names (list)}

AIRPORTS: dict[str, dict] = {
    # ── Vietnam ──────────────────────────────────────────────────────────
    "HAN": {"name": "Nội Bài", "city": "Hà Nội", "vietnam": True,
            "aliases": ["hà nội", "hanoi", "hn", "nội bài", "noi bai", "thủ đô", "ha noi"]},
    "SGN": {"name": "Tân Sơn Nhất", "city": "Hồ Chí Minh", "vietnam": True,
            "aliases": ["hồ chí minh", "tphcm", "hcm", "sg", "sài gòn", "saigon", "saigòn",
                        "sai gon", "tân sơn nhất", "tan son nhat", "sì gòn",
                        "thành phố hồ chí minh", "tp hcm"]},
    "DAD": {"name": "Đà Nẵng", "city": "Đà Nẵng", "vietnam": True,
            "aliases": ["đà nẵng", "da nang", "dn", "đà nẵng city"]},
    "CXR": {"name": "Cam Ranh", "city": "Nha Trang", "vietnam": True,
            "aliases": ["nha trang", "cam ranh", "nt", "nha trang city"]},
    "PQC": {"name": "Phú Quốc", "city": "Phú Quốc", "vietnam": True,
            "aliases": ["phú quốc", "phu quoc", "pq", "đảo ngọc", "dao ngoc"]},
    "HUI": {"name": "Phú Bài", "city": "Huế", "vietnam": True,
            "aliases": ["huế", "hue", "phú bài", "phu bai"]},
    "HPH": {"name": "Cát Bi", "city": "Hải Phòng", "vietnam": True,
            "aliases": ["hải phòng", "hai phong", "hp", "cát bi", "cat bi"]},
    "VCA": {"name": "Trà Nóc", "city": "Cần Thơ", "vietnam": True,
            "aliases": ["cần thơ", "can tho", "ct", "trà nóc", "tra noc", "tây đô"]},
    "VII": {"name": "Vinh", "city": "Vinh", "vietnam": True,
            "aliases": ["vinh", "nghệ an", "nghe an", "na"]},
    "TBB": {"name": "Đông Tác", "city": "Tuy Hòa", "vietnam": True,
            "aliases": ["tuy hòa", "tuy hoa", "phú yên", "phu yen"]},
    "DLI": {"name": "Liên Khương", "city": "Đà Lạt", "vietnam": True,
            "aliases": ["đà lạt", "da lat", "dalat", "liên khương", "lien khuong"]},
    "VKG": {"name": "Rạch Giá", "city": "Rạch Giá", "vietnam": True,
            "aliases": ["rạch giá", "rach gia", "kiên giang", "kien giang"]},
    "CAH": {"name": "Cà Mau", "city": "Cà Mau", "vietnam": True,
            "aliases": ["cà mau", "ca mau"]},
    "VCS": {"name": "Côn Đảo", "city": "Côn Đảo", "vietnam": True,
            "aliases": ["côn đảo", "con dao", "côn sơn", "con son"]},
    "VDH": {"name": "Đồng Hới", "city": "Đồng Hới", "vietnam": True,
            "aliases": ["đồng hới", "dong hoi", "quảng bình", "quang binh"]},
    "PHA": {"name": "Đồng Tác", "city": "Phan Rang", "vietnam": True,
            "aliases": ["phan rang", "ninh thuận", "ninh thuan"]},

    # ── International (common from Vietnam) ───────────────────────────────
    "BKK": {"name": "Suvarnabhumi", "city": "Bangkok", "vietnam": False,
            "aliases": ["bangkok", "bkk", "thái lan", "thailand"]},
    "DMK": {"name": "Don Mueang", "city": "Bangkok", "vietnam": False,
            "aliases": ["bangkok don mueang", "dmk"]},
    "NRT": {"name": "Narita", "city": "Tokyo", "vietnam": False,
            "aliases": ["tokyo narita", "narita", "nhật bản", "nhat ban"]},
    "KIX": {"name": "Kansai", "city": "Osaka", "vietnam": False,
            "aliases": ["osaka", "kansai", "kix"]},
    "ICN": {"name": "Incheon", "city": "Seoul", "vietnam": False,
            "aliases": ["seoul", "incheon", "hàn quốc", "han quoc", "soul"]},
    "SIN": {"name": "Changi", "city": "Singapore", "vietnam": False,
            "aliases": ["singapore", "sin", "xinh ga po"]},
    "KUL": {"name": "Kuala Lumpur", "city": "Kuala Lumpur", "vietnam": False,
            "aliases": ["kuala lumpur", "malaysia", "kl"]},
    "PEK": {"name": "Beijing Capital", "city": "Beijing", "vietnam": False,
            "aliases": ["bắc kinh", "bac kinh", "beijing", "pek", "trung quốc"]},
    "PVG": {"name": "Pudong", "city": "Shanghai", "vietnam": False,
            "aliases": ["thượng hải", "thuong hai", "shanghai", "pvg"]},
    "CDG": {"name": "Charles de Gaulle", "city": "Paris", "vietnam": False,
            "aliases": ["paris", "pháp", "phap", "cdg"]},
    "SFO": {"name": "San Francisco", "city": "San Francisco", "vietnam": False,
            "aliases": ["san francisco", "sf", "mỹ", "my", "usa", "california"]},
    "LAX": {"name": "Los Angeles", "city": "Los Angeles", "vietnam": False,
            "aliases": ["los angeles", "la", "mỹ", "my"]},
    "SYD": {"name": "Sydney", "city": "Sydney", "vietnam": False,
            "aliases": ["sydney", "úc", "uc", "australia"]},
    "SGN_BKK": {"name": "SGN→BKK", "city": "SGN→BKK", "vietnam": False},  # Compound
}

# ─── AIRLINES ────────────────────────────────────────────────────────────────

AIRLINES: dict[str, dict] = {
    "VN": {"name": "Vietnam Airlines", "full_name": "Vietnam Airlines (Hãng hàng không Quốc gia Việt Nam)",
           "code": "VN", "vietnam": True, "iata": "VN", "icao": "HVN",
           "policy": {
               "baggage": {"checked": "20-32kg tùy hạng vé", "carry_on": "1 kiện 7-10kg"},
               "change_fee": "200.000-500.000đ tùy hạng, chênh lệch giá vé",
               "cancel": "Phí 30-70% giá vé tùy hạng",
               "checkin": "Mở 24h, đóng 40 phút trước giờ bay (nội địa), 50 phút (quốc tế)",
               "meal": "Có suất ăn theo hạng vé",
           }},
    "VJ": {"name": "VietJet Air", "full_name": "VietJet Air (Hàng không giá rẻ Thế hệ mới)",
           "code": "VJ", "vietnam": True, "iata": "VJ", "icao": "VJC",
           "policy": {
               "baggage": {"checked": "Mua thêm (15-40kg)", "carry_on": "1 kiện 7kg"},
               "change_fee": "150.000-300.000đ + chênh lệch, có thể đổi tên",
               "cancel": "Phí 50-100% tùy hạng vé",
               "checkin": "Mở 24h, đóng 40 phút trước giờ bay",
               "meal": "Có mua thêm với giá 30.000-70.000đ/suất",
           }},
    "QH": {"name": "Bamboo Airways", "full_name": "Bamboo Airways (Hàng không Tre Việt)",
           "code": "QH", "vietnam": True, "iata": "QH", "icao": "BAV",
           "policy": {
               "baggage": {"checked": "20-32kg tùy hạng", "carry_on": "1 kiện 7kg"},
               "change_fee": "0-400.000đ tùy hạng",
               "cancel": "Phí 20-80% tùy hạng",
               "checkin": "Mở 24h, đóng 40 phút trước giờ bay",
               "meal": "Có bao gồm hoặc mua thêm tùy hạng",
           }},
    "BL": {"name": "Pacific Airlines", "full_name": "Pacific Airlines",
           "code": "BL", "vietnam": True, "iata": "BL", "icao": "PIC",
           "policy": {
               "baggage": {"checked": "Mua thêm", "carry_on": "1 kiện 7kg"},
               "change_fee": "200.000đ + chênh lệch",
               "cancel": "Phí 50-100%",
               "checkin": "Mở 24h, đóng 40 phút",
               "meal": "Mua thêm",
           }},
    "VU": {"name": "Vietravel Airlines", "full_name": "Vietravel Airlines",
           "code": "VU", "vietnam": True, "iata": "VU", "icao": "VTL",
           "policy": {
               "baggage": {"checked": "20kg", "carry_on": "1 kiện 7kg"},
               "change_fee": "Liên hệ hãng",
               "cancel": "Liên hệ hãng",
               "checkin": "Mở 24h trước",
               "meal": "Tùy chọn",
           }},
}

# ─── VIETNAMESE CITY → AIRPORT MAPPING ───────────────────────────────────────

def lookup_airport(text: str) -> str | None:
    """Look up airport IATA code from any search text (name, alias, city)."""
    text_clean = text.strip().lower()
    for code, info in AIRPORTS.items():
        if code == text_clean or code.lower() == text_clean:
            return code
        for alias in info.get("aliases", []):
            if alias == text_clean or text_clean in [alias, f"{alias} bay", f"ra {alias}"]:
                return code
    # Fuzzy: check if the text contains any alias
    for code, info in AIRPORTS.items():
        for alias in info.get("aliases", []):
            if alias in text_clean or text_clean in alias:
                return code
    return None


def normalize_person_count(text: str) -> int:
    """Parse Vietnamese number words to integers."""
    mapping = {
        "một": 1, "hai": 2, "ba": 3, "bốn": 4, "năm": 5,
        "sáu": 6, "bảy": 7, "tám": 8, "chín": 9, "mười": 10,
        "1": 1, "2": 2, "3": 3, "4": 4, "5": 5,
        "6": 6, "7": 7, "8": 8, "9": 9, "10": 10,
    }
    text_clean = text.strip().lower()
    if text_clean in mapping:
        return mapping[text_clean]

    import re
    nums = re.findall(r'\d+', text)
    if nums:
        return int(nums[0])
    return 1  # default


def get_airport_info(code: str) -> dict | None:
    """Get airport details by IATA code."""
    if code in AIRPORTS:
        return {"code": code, **AIRPORTS[code]}
    return None


def get_airline_info(code: str) -> dict | None:
    """Get airline details by IATA code."""
    upper_code = code.upper()
    if upper_code in AIRLINES:
        return AIRLINES[upper_code]
    # Try full name match
    for airline_code, info in AIRLINES.items():
        if code.lower() in info["name"].lower():
            return info
    return None


def list_all_airports() -> list[dict]:
    """List all airports for LLM context."""
    result = []
    for code, info in sorted(AIRPORTS.items()):
        result.append({
            "code": code,
            "name": info["name"],
            "city": info["city"],
            "vietnam": info["vietnam"]
        })
    return result


def list_all_airlines() -> list[dict]:
    """List all airlines with basic info."""
    result = []
    for code, info in sorted(AIRLINES.items()):
        result.append({
            "code": code,
            "name": info["name"],
            "full_name": info.get("full_name", ""),
            "vietnam": info["vietnam"],
            "baggage_policy": info["policy"]["baggage"]["checked"]
        })
    return result


# ─── HELPER: airport/city lookup for LLM prompt injection ─────────────────────

def get_airport_dict_for_prompt() -> str:
    """Returns a formatted airport list for use in LLM system prompts."""
    lines = ["Địa danh → Mã sân bay (IATA):"]
    for code, info in sorted(AIRPORTS.items()):
        aliases = ", ".join(info["aliases"][:5])
        lines.append(f"  • {info['city']} ({info['name']}): {code} — gợi ý: {aliases}")
    return "\n".join(lines)


def get_airline_dict_for_prompt() -> str:
    """Returns a formatted airline list for LLM prompts."""
    lines = ["Hãng bay Việt Nam:"]
    for code, info in sorted(AIRLINES.items()):
        if info["vietnam"]:
            lines.append(f"  • {info['full_name']} — mã: {code}")
    lines.append("\nHãng bay quốc tế thường gặp:")
    intl = {code: info for code, info in AIRLINES.items() if not info["vietnam"]}
    if intl:
        for code, info in sorted(intl.items()):
            lines.append(f"  • {info['name']} — mã: {code}")
    return "\n".join(lines)
