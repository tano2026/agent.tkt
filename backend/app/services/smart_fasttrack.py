"""FastTrack — Smart Agent Service

Dịch vụ hỗ trợ thủ tục sân bay Nội Bài (T2) — An Bình Air Services.
Data lấy từ bảng giá chính thức "BaoGia_DichVuSanBay_AnBinh" (Fast Track)
và "BẢNG GIÁ PC THƯƠNG GIA (7-2026)" (Phòng chờ thương gia toàn quốc).
Giá chưa bao gồm VAT. USD chỉ mang tính tham khảo (Fast Track only).
"""

from typing import Optional

# ---------------------------------------------------------------------------
# I. HỖ TRỢ THỦ TỤC — FAST TRACK (Nội Bài, T2)
# ---------------------------------------------------------------------------

_FASTTRACK_SERVICES = [
    {
        "id": "domestic_departure",
        "stt": 1,
        "terminal": "Ga Quốc Nội",
        "name": "Tiễn khách ưu tiên (Fast Track Departure)",
        "tier": "Fast Track",
        "features": [
            "Đón khách tại điểm đón trên sân bay",
            "Hỗ trợ check-in & gửi hành lý tại quầy",
            "Soi chiếu an ninh ưu tiên",
            "Hướng dẫn đến cửa ra tàu bay",
        ],
        "price": 450_000,
        "price_usd": 17,
    },
    {
        "id": "domestic_arrival",
        "stt": 2,
        "terminal": "Ga Quốc Nội",
        "name": "Đón khách ưu tiên (Fast Track Arrival)",
        "tier": "Fast Track",
        "features": [
            "Trưng biển đón tại băng chuyền hành lý",
            "Hỗ trợ lấy hành lý và tiễn ra xe",
        ],
        "price": 450_000,
        "price_usd": 17,
    },
    {
        "id": "intl_departure_standard",
        "stt": 3,
        "terminal": "Ga Quốc Tế",
        "name": "Tiễn khách tiêu chuẩn (Standard Departure)",
        "tier": "Standard",
        "features": [
            "Đón khách tại điểm đón trên sân bay",
            "Hỗ trợ check-in & gửi hành lý",
            "Hướng dẫn khu vực xuất cảnh",
        ],
        "price": 250_000,
        "price_usd": 9,
    },
    {
        "id": "intl_departure_fasttrack",
        "stt": 3,
        "terminal": "Ga Quốc Tế",
        "name": "Tiễn khách ưu tiên (Fast Track Departure)",
        "tier": "Fast Track",
        "features": [
            "Đón khách tại điểm đón trên sân bay",
            "Hỗ trợ check-in & gửi hành lý",
            "Soi chiếu an ninh ưu tiên",
            "Thủ tục xuất cảnh ưu tiên",
            "Hướng dẫn cửa ra máy bay",
        ],
        "price": 650_000,
        "price_usd": 25,
    },
    {
        "id": "intl_departure_vipb",
        "stt": 4,
        "terminal": "Ga Quốc Tế",
        "name": "Tiễn khách VIP B (VIP B Departure)",
        "tier": "VIP B",
        "features": [
            "Đón khách tại điểm đón trên sân bay",
            "Check-in tại quầy ưu tiên",
            "Thay mặt khách làm thủ tục xuất cảnh",
            "Soi chiếu an ninh ưu tiên",
            "Thủ tục xuất cảnh ưu tiên",
            "Hướng dẫn cửa ra máy bay",
        ],
        "price": 1_100_000,
        "price_usd": 42,
    },
    {
        "id": "intl_arrival_standard",
        "stt": 5,
        "terminal": "Ga Quốc Tế",
        "name": "Đón khách tiêu chuẩn (Standard Arrival)",
        "tier": "Standard",
        "features": [
            "Trưng biển đón tại khu vực nhập cảnh",
            "Hướng dẫn khu vực lấy visa (nếu cần)",
            "Hướng dẫn khách làm thủ tục nhập cảnh",
            "Hướng dẫn khu vực lấy hành lý",
        ],
        "price": 400_000,
        "price_usd": 15,
    },
    {
        "id": "intl_arrival_fasttrack",
        "stt": 5,
        "terminal": "Ga Quốc Tế",
        "name": "Đón khách ưu tiên (Fast Track Arrival)",
        "tier": "Fast Track",
        "features": [
            "Trưng biển đón tại khu vực nhập cảnh",
            "Hỗ trợ qua bục nhập cảnh ưu tiên",
            "Hướng dẫn khu vực lấy hành lý",
        ],
        "price": 550_000,
        "price_usd": 21,
    },
    {
        "id": "intl_arrival_vipb",
        "stt": 6,
        "terminal": "Ga Quốc Tế",
        "name": "Đón khách VIP B (VIP B Arrival)",
        "tier": "VIP B",
        "features": [
            "Trưng biển đón tại khu vực nhập cảnh",
            "Dẫn thẳng xuống khu vực lấy hành lý",
            "Thay mặt khách làm thủ tục nhập cảnh",
            "Hỗ trợ lấy hành lý và dẫn ra xe",
        ],
        "price": 1_100_000,
        "price_usd": 42,
    },
    {
        "id": "transit_intl_domestic",
        "stt": 7,
        "terminal": "Nối chuyến",
        "name": "Nối chuyến Quốc tế → Nội địa (Int'l → Domestic Transit)",
        "tier": "Transit",
        "features": [
            "Đón & nhập cảnh qua bục ưu tiên",
            "Hỗ trợ lấy hành lý, di chuyển sang ga nội địa",
            "Check-in chuyến bay tiếp nối",
            "Hướng dẫn soi chiếu & cửa ra tàu bay",
        ],
        "price": 1_000_000,
        "price_usd": 38,
    },
    {
        "id": "transit_domestic_intl",
        "stt": 8,
        "terminal": "Nối chuyến",
        "name": "Nối chuyến Nội địa → Quốc tế (Domestic → Int'l Transit)",
        "tier": "Transit",
        "features": [
            "Đón tại sảnh đến ga nội địa",
            "Di chuyển sang ga quốc tế",
            "Check-in & thủ tục xuất cảnh",
            "Hướng dẫn soi chiếu & cửa ra tàu bay",
        ],
        "price": 1_000_000,
        "price_usd": 38,
    },
]

_FASTTRACK_NOTE = "Trẻ sơ sinh < 2 tuổi: MIỄN PHÍ (tối đa 02 bé / 01 người lớn). Giá chưa bao gồm VAT."

# ---------------------------------------------------------------------------
# II. PHÒNG CHỜ THƯƠNG GIA (toàn quốc) — Bảng giá 7/2026
# ---------------------------------------------------------------------------
# companion_policy: "1" = Bông Sen VNA | "2" = Đối tác | "other" = SH Premium

_LOUNGE_SERVICES = [
    # --- Nhóm I: Vietnam Airlines Bông Sen ---
    {"name": "Phòng khách Bông Sen Quốc tế HAN", "group": "Bông Sen (VNA)", "airport": "Nội Bài",
     "code": "HAN", "terminal": "Quốc tế", "location": "Khu cách ly Quốc tế, Cảng HKQT Nội Bài",
     "adult_price": 935_000, "child_price": 690_000, "policy": "1"},
    {"name": "Phòng khách Bông Sen Quốc tế CXR", "group": "Bông Sen (VNA)", "airport": "Cam Ranh",
     "code": "CXR", "terminal": "Quốc tế", "location": "Khu vực cách ly Ga đi Quốc tế, Sân bay Quốc tế Cam Ranh",
     "adult_price": 785_000, "child_price": 580_000, "policy": "1"},
    {"name": "Phòng khách Bông Sen Nội địa SGN", "group": "Bông Sen (VNA)", "airport": "Tân Sơn Nhất",
     "code": "SGN", "terminal": "Quốc nội", "location": "Khu vực cách ly Ga T3 đi Quốc nội, Sân bay Quốc tế Tân Sơn Nhất",
     "adult_price": 610_000, "child_price": 430_000, "policy": "1"},
    {"name": "Phòng khách Bông Sen Nội địa HAN", "group": "Bông Sen (VNA)", "airport": "Nội Bài",
     "code": "HAN", "terminal": "Quốc nội", "location": "Khu cách ly Quốc nội, Cảng HKQT Nội Bài",
     "adult_price": 545_000, "child_price": 375_000, "policy": "1"},
    {"name": "Phòng khách Bông Sen UIH", "group": "Bông Sen (VNA)", "airport": "Phù Cát",
     "code": "UIH", "terminal": "Quốc nội", "location": "Khu vực cách ly Ga đi Quốc nội, Cảng hàng không Phù Cát",
     "adult_price": 380_000, "child_price": 260_000, "policy": "1"},

    # --- Nhóm II: SH Premium Lounge Quốc tế ---
    {"name": "SH Premium Lounge Ha Noi East (Cánh Đông)", "group": "SH Premium", "airport": "Nội Bài",
     "code": "HAN", "terminal": "Quốc tế", "location": "Khu cách ly Quốc tế, Cảng HKQT Nội Bài",
     "adult_price": 800_000, "child_price": 420_000, "policy": "other"},
    {"name": "SH Premium Lounge Ha Noi West (Cánh Tây)", "group": "SH Premium", "airport": "Nội Bài",
     "code": "HAN", "terminal": "Quốc tế", "location": "Khu cách ly Quốc tế, Cảng HKQT Nội Bài",
     "adult_price": 950_000, "child_price": 495_000, "policy": "other"},
    {"name": "SH Premium Lounge Cam Ranh", "group": "SH Premium", "airport": "Cam Ranh",
     "code": "CXR", "terminal": "Quốc tế", "location": "Khu cách ly Quốc tế, Cảng HKQT Cam Ranh",
     "adult_price": 800_000, "child_price": 420_000, "policy": "other"},

    # --- Nhóm III: SH Premium Lounge Quốc nội ---
    {"name": "SH Premium Lounge Ha Noi", "group": "SH Premium", "airport": "Nội Bài",
     "code": "HAN", "terminal": "Quốc nội", "location": "Khu cách ly Quốc nội, Cảng HKQT Nội Bài",
     "adult_price": 460_000, "child_price": 250_000, "policy": "other"},
    {"name": "SH Premium Lounge Cam Ranh", "group": "SH Premium", "airport": "Cam Ranh",
     "code": "CXR", "terminal": "Quốc nội", "location": "Khu cách ly Quốc nội, Cảng HKQT Cam Ranh",
     "adult_price": 450_000, "child_price": 220_000, "policy": "other"},
    {"name": "SH Premium Lounge Phu Quoc 1&2", "group": "SH Premium", "airport": "Phú Quốc",
     "code": "PQC", "terminal": "Quốc nội", "location": "Khu cách ly Quốc nội, Cảng HKQT Phú Quốc",
     "adult_price": 450_000, "child_price": 220_000, "policy": "other"},
    {"name": "SH Premium Lounge Con Dao", "group": "SH Premium", "airport": "Côn Đảo",
     "code": "VCS", "terminal": "Quốc nội", "location": "Khu cách ly, Cảng Côn Đảo",
     "adult_price": 450_000, "child_price": 220_000, "policy": "other"},
    {"name": "SH Premium Lounge Da Nang", "group": "SH Premium", "airport": "Đà Nẵng",
     "code": "DAD", "terminal": "Quốc nội", "location": "Khu cách ly Quốc nội, Cảng HKQT Đà Nẵng",
     "adult_price": 485_000, "child_price": 485_000, "policy": "danang",
     "note": "Thời gian sử dụng tối đa 2 giờ (khác các phòng chờ còn lại, không có giá trẻ em riêng)"},
    {"name": "SH Premium Lounge Tan Son Nhat", "group": "SH Premium", "airport": "Tân Sơn Nhất",
     "code": "SGN", "terminal": "Quốc nội", "location": "Khu cách ly Quốc nội, Nhà ga T3, Cảng HKQT Tân Sơn Nhất",
     "adult_price": 495_000, "child_price": 250_000, "policy": "other"},
    {"name": "SH Premium Lounge Lien Khuong", "group": "SH Premium", "airport": "Liên Khương (Đà Lạt)",
     "code": "DLI", "terminal": "Quốc nội", "location": "Khu cách ly Quốc nội, Cảng HKQT Liên Khương",
     "adult_price": 400_000, "child_price": 200_000, "policy": "other"},
    {"name": "SH Premium Lounge Phu Cat", "group": "SH Premium", "airport": "Phù Cát (Quy Nhơn)",
     "code": "UIH", "terminal": "Quốc nội", "location": "Khu cách ly Quốc nội, Cảng HKQT Phù Cát",
     "adult_price": 400_000, "child_price": 200_000, "policy": "other"},
    {"name": "SH Premium Lounge Cat Bi", "group": "SH Premium", "airport": "Cát Bi (Hải Phòng)",
     "code": "HPH", "terminal": "Quốc nội", "location": "Khu cách ly Quốc nội, Cảng HKQT Cát Bi",
     "adult_price": 400_000, "child_price": 200_000, "policy": "other"},
    {"name": "SH Premium Lounge Phu Bai", "group": "SH Premium", "airport": "Phú Bài (Huế)",
     "code": "HUI", "terminal": "Quốc nội", "location": "Khu cách ly Quốc nội, Cảng HKQT Phú Bài",
     "adult_price": 400_000, "child_price": 200_000, "policy": "other"},
    {"name": "SH Premium Lounge Vinh", "group": "SH Premium", "airport": "Vinh",
     "code": "VII", "terminal": "Quốc nội", "location": "Khu cách ly Quốc nội, Cảng HKQT Vinh",
     "adult_price": 400_000, "child_price": 200_000, "policy": "other"},
    {"name": "SH Premium Lounge Can Tho", "group": "SH Premium", "airport": "Cần Thơ",
     "code": "VCA", "terminal": "Quốc nội", "location": "Khu cách ly Quốc nội, Cảng HKQT Cần Thơ",
     "adult_price": 400_000, "child_price": 200_000, "policy": "other"},
    {"name": "SH Premium Lounge Buon Ma Thuot", "group": "SH Premium", "airport": "Buôn Ma Thuột",
     "code": "BMV", "terminal": "Quốc nội", "location": "Khu cách ly, Cảng HK Buôn Ma Thuột",
     "adult_price": 400_000, "child_price": 200_000, "policy": "other"},
    {"name": "SH Premium Lounge Dien Bien", "group": "SH Premium", "airport": "Điện Biên",
     "code": "DIN", "terminal": "Quốc nội", "location": "Khu cách ly Quốc nội, Cảng HK Điện Biên",
     "adult_price": 400_000, "child_price": 200_000, "policy": "other"},
    {"name": "SH Premium Lounge Pleiku", "group": "SH Premium", "airport": "Pleiku",
     "code": "PXU", "terminal": "Quốc nội", "location": "Khu cách ly, Cảng HK Pleiku",
     "adult_price": 400_000, "child_price": 220_000, "policy": "other"},
    {"name": "SH Premium Lounge Tuy Hoa", "group": "SH Premium", "airport": "Tuy Hòa",
     "code": "TBB", "terminal": "Quốc nội", "location": "Khu cách ly, Cảng HK Tuy Hòa",
     "adult_price": 400_000, "child_price": 200_000, "policy": "other"},
    {"name": "SH Premium Lounge Tho Xuan", "group": "SH Premium", "airport": "Thọ Xuân (Thanh Hóa)",
     "code": "THD", "terminal": "Quốc nội", "location": "Khu cách ly, Cảng HK Thọ Xuân",
     "adult_price": 400_000, "child_price": 200_000, "policy": "other"},
    {"name": "SH Premium Lounge Chu Lai", "group": "SH Premium", "airport": "Chu Lai (Quảng Nam)",
     "code": "VCL", "terminal": "Quốc nội", "location": "Khu cách ly Quốc nội, Cảng HK Chu Lai",
     "adult_price": 400_000, "child_price": 200_000, "policy": "other"},
    {"name": "SH Premium Lounge Dong Hoi", "group": "SH Premium", "airport": "Đồng Hới (Quảng Bình)",
     "code": "VDH", "terminal": "Quốc nội", "location": "Khu cách ly, Cảng HK Đồng Hới",
     "adult_price": 400_000, "child_price": 200_000, "policy": "other"},
    {"name": "SH Premium Lounge Ca Mau", "group": "SH Premium", "airport": "Cà Mau",
     "code": "CAH", "terminal": "Quốc nội", "location": "Khu cách ly Quốc nội, Cảng HK Cà Mau",
     "adult_price": 400_000, "child_price": 200_000, "policy": "other"},
    {"name": "SH Premium Lounge Rach Gia", "group": "SH Premium", "airport": "Rạch Giá (Kiên Giang)",
     "code": "VKG", "terminal": "Quốc nội", "location": "Khu cách ly Quốc nội, Cảng HK Rạch Giá",
     "adult_price": 400_000, "child_price": 200_000, "policy": "other"},

    # --- Nhóm IV: Phòng khách đối tác ---
    {"name": "Apricot Lounge", "group": "Đối tác", "airport": "Tân Sơn Nhất",
     "code": "SGN", "terminal": "Quốc tế", "location": "Khu cách ly Quốc tế, Cảng HKQT Tân Sơn Nhất",
     "adult_price": 1_000_000, "child_price": 525_000, "policy": "2"},
    {"name": "Jasmine Halah Lounge", "group": "Đối tác", "airport": "Tân Sơn Nhất",
     "code": "SGN", "terminal": "Quốc tế", "location": "Khu cách ly Quốc tế, Cảng HKQT Tân Sơn Nhất",
     "adult_price": 1_000_000, "child_price": 525_000, "policy": "2"},
    {"name": "Sun Coast Lounge", "group": "Đối tác", "airport": "Cam Ranh",
     "code": "CXR", "terminal": "Quốc tế", "location": "Khu cách ly Quốc tế, Cảng HKQT Cam Ranh",
     "adult_price": 830_000, "child_price": 440_000, "policy": "2"},
    {"name": "The Sens Leisure Lounge", "group": "Đối tác", "airport": "Phú Quốc",
     "code": "PQC", "terminal": "Quốc tế", "location": "Khu cách ly Quốc tế, Cảng HKQT Phú Quốc",
     "adult_price": 830_000, "child_price": 440_000, "policy": "2"},
    {"name": "Le Saigonnais Lounge", "group": "Đối tác", "airport": "Tân Sơn Nhất",
     "code": "SGN", "terminal": "Quốc nội", "location": "Khu cách ly Quốc nội, Cảng HKQT Tân Sơn Nhất",
     "adult_price": 515_000, "child_price": 260_000, "policy": "2"},
]

_LOUNGE_POLICY_TEXT = {
    "1": "Tối đa 1 trẻ dưới 2 tuổi đi cùng người lớn: MIỄN PHÍ. Trẻ ≥2 tuổi hoặc trẻ thứ 2+: áp giá người lớn.",
    "2": "Mỗi người lớn miễn phí tối đa 1 trẻ dưới 5 tuổi. Trẻ dưới 5 tuổi thứ 2+ và trẻ 5-12 tuổi: giá trẻ em. Trẻ >12 tuổi: giá người lớn.",
    "other": "Mỗi người lớn miễn phí tối đa 2 trẻ dưới 5 tuổi. Trẻ dưới 5 tuổi thứ 3+ và trẻ 5-12 tuổi: giá trẻ em. Trẻ >12 tuổi: giá người lớn.",
    "danang": "Không áp dụng giá trẻ em riêng — mọi khách đi kèm tính theo đơn giá chung.",
}

_LOUNGE_NOTE = (
    "Giá chưa bao gồm VAT. Thời gian sử dụng tối đa 03 giờ trước giờ khởi hành "
    "(riêng SH Premium Lounge Đà Nẵng: tối đa 02 giờ). "
    "Phụ thu thêm giờ: SH Premium Đà Nẵng — 2 giờ đầu +50%, từ giờ 3 +100%/giờ; "
    "các phòng chờ còn lại — mỗi block 3 giờ thêm +50% đơn giá/khách."
)

_AIRPORT_ALIASES = {
    "Nội Bài": ["nội bài", "noi bai", "han", "hà nội", "ha noi"],
    "Tân Sơn Nhất": ["tân sơn nhất", "tan son nhat", "sgn", "sài gòn", "sai gon", "tp.hcm", "hcm", "hồ chí minh"],
    "Cam Ranh": ["cam ranh", "cxr", "nha trang", "khánh hòa", "khanh hoa"],
    "Đà Nẵng": ["đà nẵng", "da nang", "dad"],
    "Phú Quốc": ["phú quốc", "phu quoc", "pqc"],
    "Côn Đảo": ["côn đảo", "con dao", "vcs"],
    "Cần Thơ": ["cần thơ", "can tho", "vca"],
    "Phù Cát": ["phù cát", "phu cat", "uih", "quy nhơn", "quy nhon"],
    "Liên Khương (Đà Lạt)": ["liên khương", "lien khuong", "dli", "đà lạt", "da lat"],
    "Cát Bi (Hải Phòng)": ["cát bi", "cat bi", "hph", "hải phòng", "hai phong"],
    "Phú Bài (Huế)": ["phú bài", "phu bai", "hui", "huế", "hue"],
    "Vinh": ["vinh", "vii"],
    "Buôn Ma Thuột": ["buôn ma thuột", "buon ma thuot", "bmv"],
    "Điện Biên": ["điện biên", "dien bien", "din"],
    "Pleiku": ["pleiku", "pxu"],
    "Tuy Hòa": ["tuy hòa", "tuy hoa", "tbb"],
    "Thọ Xuân (Thanh Hóa)": ["thọ xuân", "tho xuan", "thd", "thanh hóa", "thanh hoa"],
    "Chu Lai (Quảng Nam)": ["chu lai", "vcl", "quảng nam", "quang nam"],
    "Đồng Hới (Quảng Bình)": ["đồng hới", "dong hoi", "vdh", "quảng bình", "quang binh"],
    "Cà Mau": ["cà mau", "ca mau", "cah"],
    "Rạch Giá (Kiên Giang)": ["rạch giá", "rach gia", "vkg", "kiên giang", "kien giang"],
}


def _wants_lounge(text_lower: str) -> bool:
    return any(kw in text_lower for kw in ["phòng chờ", "phong cho", "lounge", "thương gia", "thuong gia"])


def _wants_transit(text_lower: str) -> bool:
    return any(kw in text_lower for kw in ["nối chuyến", "noi chuyen", "transit", "chuyển tiếp", "chuyen tiep"])


def _terminal_filter(text_lower: str) -> Optional[str]:
    if any(kw in text_lower for kw in ["quốc tế", "quoc te", "international", "intl"]):
        return "Ga Quốc Tế"
    if any(kw in text_lower for kw in ["quốc nội", "quoc noi", "nội địa", "noi dia", "domestic"]):
        return "Ga Quốc Nội"
    return None


def _direction_filter(text_lower: str) -> Optional[str]:
    if any(kw in text_lower for kw in ["tiễn", "tien khach", "đi", "khởi hành", "khoi hanh", "departure", "đi nước ngoài"]):
        return "departure"
    if any(kw in text_lower for kw in ["đón", "don khach", "về", "hạ cánh", "ha canh", "arrival"]):
        return "arrival"
    return None


def _tier_filter(text_lower: str) -> Optional[str]:
    if "vip b" in text_lower or "vip" in text_lower:
        return "VIP B"
    if "fast track" in text_lower or "fasttrack" in text_lower or "ưu tiên" in text_lower or "uu tien" in text_lower:
        return "Fast Track"
    if "tiêu chuẩn" in text_lower or "tieu chuan" in text_lower or "standard" in text_lower:
        return "Standard"
    return None


def _lounge_airport_filter(text_lower: str) -> Optional[str]:
    for canonical, aliases in _AIRPORT_ALIASES.items():
        if any(alias in text_lower for alias in aliases):
            return canonical
    return None


def _lounge_terminal_filter(text_lower: str) -> Optional[str]:
    if any(kw in text_lower for kw in ["quốc tế", "quoc te", "international", "intl"]):
        return "Quốc tế"
    if any(kw in text_lower for kw in ["quốc nội", "quoc noi", "nội địa", "noi dia", "domestic"]):
        return "Quốc nội"
    return None


def _format_fasttrack_row(svc: dict) -> str:
    lines = [f"**{svc['name']}** — {svc['terminal']}"]
    for f in svc["features"]:
        lines.append(f"  • {f}")
    lines.append(f"  💰 **{svc['price']:,.0f}₫/khách** (≈{svc['price_usd']} USD)")
    return "\n".join(lines)


def _format_lounge_row(lg: dict) -> str:
    line = (
        f"**{lg['name']}** — {lg['airport']} ({lg['terminal']})\n"
        f"  📍 {lg['location']}\n"
        f"  • Người lớn: **{lg['adult_price']:,.0f}₫**\n"
        f"  • Trẻ em: **{lg['child_price']:,.0f}₫**"
    )
    if lg.get("note"):
        line += f"\n  ⚠️ {lg['note']}"
    return line


def format_fasttrack_info(message: str = "") -> str:
    """Format Fast Track / Lounge info as HTML-friendly string, theo intent trong message."""
    text_lower = message.lower()

    # Lounge request
    if _wants_lounge(text_lower):
        airport = _lounge_airport_filter(text_lower)
        terminal = _lounge_terminal_filter(text_lower)

        matches = _LOUNGE_SERVICES
        if airport:
            matches = [lg for lg in matches if lg["airport"] == airport]
        if terminal:
            matches = [lg for lg in matches if lg["terminal"] == terminal]

        # Default (no filter): chỉ show Nội Bài — sân bay chính của An Bình
        header_note = ""
        if not airport and not terminal:
            matches = [lg for lg in _LOUNGE_SERVICES if lg["airport"] == "Nội Bài"]
            header_note = " (Nội Bài — mặc định. Hỏi tên sân bay khác để xem thêm, VD: 'phòng chờ Tân Sơn Nhất')"

        lines = [f"🛋️ **Phòng Chờ Thương Gia{header_note}**"]
        if not matches:
            lines.append("\nKhông tìm thấy phòng chờ phù hợp. Thử hỏi theo tên sân bay (VD: 'phòng chờ Đà Nẵng', 'phòng chờ Phú Quốc').")
            return "\n".join(lines)

        used_policies = set()
        for lg in matches:
            lines.append("")
            lines.append(_format_lounge_row(lg))
            used_policies.add(lg["policy"])

        lines.append("")
        lines.append(f"📌 {_LOUNGE_NOTE}")
        lines.append("\n**Chính sách trẻ em đi kèm:**")
        for p in used_policies:
            lines.append(f"  • {_LOUNGE_POLICY_TEXT[p]}")
        return "\n".join(lines)

    # Transit request
    if _wants_transit(text_lower):
        lines = ["🔄 **Dịch Vụ Nối Chuyến — Nội Bài**"]
        for svc in _FASTTRACK_SERVICES:
            if svc["terminal"] == "Nối chuyến":
                lines.append("")
                lines.append(_format_fasttrack_row(svc))
        lines.append("")
        lines.append(f"📌 {_FASTTRACK_NOTE}")
        return "\n".join(lines)

    terminal = _terminal_filter(text_lower)
    direction = _direction_filter(text_lower)
    tier = _tier_filter(text_lower)

    # Specific match requested
    if terminal or direction or tier:
        matches = []
        for svc in _FASTTRACK_SERVICES:
            if svc["terminal"] == "Nối chuyến":
                continue
            if terminal and svc["terminal"] != terminal:
                continue
            if direction == "departure" and "Tiễn" not in svc["name"] and "Departure" not in svc["name"]:
                continue
            if direction == "arrival" and "Đón" not in svc["name"] and "Arrival" not in svc["name"]:
                continue
            if tier and svc["tier"] != tier:
                continue
            matches.append(svc)

        if matches:
            lines = ["⚡ **Fast Track — Nội Bài (T2)**"]
            for svc in matches:
                lines.append("")
                lines.append(_format_fasttrack_row(svc))
            lines.append("")
            lines.append(f"📌 {_FASTTRACK_NOTE}")
            lines.append("💡 Gõ 'phòng chờ' để xem giá Business Lounge.")
            return "\n".join(lines)

    # Default: overview toàn bộ bảng giá
    lines = ["⚡ **Fast Track & Phòng Chờ — Sân Bay Nội Bài (T2)**"]
    lines.append("An Bình Air Services | Hotline: 0869.320.320\n")

    lines.append("**🏠 GA QUỐC NỘI**")
    for svc in _FASTTRACK_SERVICES:
        if svc["terminal"] == "Ga Quốc Nội":
            lines.append(f"  • {svc['name']}: **{svc['price']:,.0f}₫**/khách")

    lines.append("\n**🌐 GA QUỐC TẾ (TIỄN)**")
    for svc in _FASTTRACK_SERVICES:
        if svc["terminal"] == "Ga Quốc Tế" and ("Tiễn" in svc["name"] or "Departure" in svc["name"]):
            lines.append(f"  • {svc['name']}: **{svc['price']:,.0f}₫**/khách")

    lines.append("\n**🌐 GA QUỐC TẾ (ĐÓN)**")
    for svc in _FASTTRACK_SERVICES:
        if svc["terminal"] == "Ga Quốc Tế" and ("Đón" in svc["name"] or "Arrival" in svc["name"]):
            lines.append(f"  • {svc['name']}: **{svc['price']:,.0f}₫**/khách")

    lines.append("\n**🔄 NỐI CHUYẾN**")
    for svc in _FASTTRACK_SERVICES:
        if svc["terminal"] == "Nối chuyến":
            lines.append(f"  • {svc['name']}: **{svc['price']:,.0f}₫**/khách")

    lines.append("\n**🛋️ PHÒNG CHỜ THƯƠNG GIA (Nội Bài)**")
    for lg in _LOUNGE_SERVICES:
        if lg["airport"] == "Nội Bài":
            lines.append(f"  • {lg['name']} ({lg['terminal']}): **{lg['adult_price']:,.0f}₫** người lớn")
    lines.append("  💡 Có phòng chờ tại 20+ sân bay toàn quốc — hỏi 'phòng chờ [tên sân bay]' để xem.")

    lines.append(f"\n📌 {_FASTTRACK_NOTE}")
    lines.append("\n💡 Bạn cần dịch vụ nào? (VD: 'fast track quốc tế đi', 'đón VIP B', 'phòng chờ Đà Nẵng')")
    return "\n".join(lines)


def handle_fasttrack(message: str) -> str:
    """Main handler for Fast Track / Lounge queries."""
    return format_fasttrack_info(message)
