"""FastTrack — Smart Agent Service

Dịch vụ Fast Track Nội Bài + các sân bay khác.
Cung cấp thông tin gói VIP, giá, quy trình.
"""

from typing import Optional

_SERVICES = {
    "noi_bai": {
        "name": "Fast Track Nội Bài (HAN)",
        "description": "Dịch vụ ưu tiên tại sân bay Nội Bài — Hành trình riêng, làm thủ tục nhanh",
        "features": [
            "Nhân viên đón tận cửa ga quốc nội/quốc tế",
            "Làm thủ tục check-in tại quầy riêng (VIP)",
            "Ưu tiên soi chiếu an ninh (Fast Track)",
            "Hỗ trợ hành lý ký gửi",
            "Xe điện đưa ra tận chân máy bay (tùy gói)",
            "Phòng chờ VIP Lounge trước giờ bay",
        ],
        "price": {
            "retail": 650_000,
            "agent": 450_000,
        },
        "hours": "24/7 — nhân viên trực sẵn tại T2 Nội Bài",
        "note": "Nhận booking tối thiểu 30 phút trước giờ bay",
    },
    "tan_son_nhat": {
        "name": "Fast Track Tân Sơn Nhất (SGN)",
        "description": "Dịch vụ ưu tiên tại sân bay Tân Sơn Nhất",
        "features": [
            "Nhân viên đón tại ga quốc nội/quốc tế",
            "Check-in quầy riêng",
            "Làn ưu tiên an ninh",
            "Phòng chờ VIP Lounge (tùy gói)",
        ],
        "price": {
            "retail": 550_000,
            "agent": 380_000,
        },
        "hours": "06:00 - 23:00",
    },
    "da_nang": {
        "name": "Fast Track Đà Nẵng (DAD)",
        "description": "Dịch vụ ưu tiên tại sân bay Đà Nẵng",
        "features": [
            "Đón tại ga đến/quốc tế",
            "Check-in nhanh",
            "Làn ưu tiên an ninh",
            "Xe đưa ra máy bay",
        ],
        "price": {
            "retail": 450_000,
            "agent": 320_000,
        },
        "hours": "06:00 - 22:00",
    },
    "international": {
        "name": "Fast Track Quốc Tế",
        "description": "Dịch vụ ưu tiên tại các sân bay quốc tế (đối tác)",
        "features": [
            "Áp dụng tại 40+ sân bay trên thế giới",
            "Hỗ trợ transit nhanh",
            "Phòng chờ VIP",
        ],
        "price": {
            "retail": 800_000,
            "agent": 600_000,
        },
        "note": "Giá tham khảo, tùy sân bay",
    },
}


def _get_airport_key(text: str) -> Optional[str]:
    """Map user input to airport key."""
    text_lower = text.lower()
    mapping = {
        "nội bài": "noi_bai",
        "noi bai": "noi_bai",
        "han": "noi_bai",
        "hà nội": "noi_bai",
        "ha noi": "noi_bai",
        "tân sơn nhất": "tan_son_nhat",
        "tan son nhat": "tan_son_nhat",
        "sgn": "tan_son_nhat",
        "tp.hcm": "tan_son_nhat",
        "hcm": "tan_son_nhat",
        "sài gòn": "tan_son_nhat",
        "saigon": "tan_son_nhat",
        "đà nẵng": "da_nang",
        "da nang": "da_nang",
        "dad": "da_nang",
        "quốc tế": "international",
        "quoc te": "international",
    }
    for keyword, key in mapping.items():
        if keyword in text_lower:
            return key
    return None


def format_fasttrack_info(airport_key: Optional[str] = None) -> str:
    """Format Fast Track service info as HTML-friendly string."""
    if airport_key and airport_key in _SERVICES:
        svc = _SERVICES[airport_key]
        lines = [
            f"⚡ **{svc['name']}**",
            svc["description"],
            "",
            "**Quyền lợi:**",
        ]
        for f in svc["features"]:
            lines.append(f"  • {f}")
        lines.append(f"\n⏰ {svc['hours']}")
        lines.append(f"\n💰 **Giá:**")
        lines.append(f"  • Khách lẻ: **{svc['price']['retail']:,.0f}₫**")
        lines.append(f"  • Đại lý: **{svc['price']['agent']:,.0f}₫**")
        if svc.get("note"):
            lines.append(f"\n📌 *{svc['note']}*")
        return "\n".join(lines)

    # Nếu không xác định sân bay, hiển thị tất cả
    lines = ["⚡ **Fast Track — Dịch vụ ưu tiên sân bay**"]
    lines.append("Giúp bạn qua nhanh các thủ tục, tiết kiệm thời gian!\n")
    for key, svc in _SERVICES.items():
        lines.append(f"• **{svc['name']}**")
        lines.append(f"  {svc['description'][:60]}...")
        lines.append(f"  💰 Từ **{svc['price']['retail']:,.0f}₫**")
    lines.append("\n💡 Bạn muốn biết thông tin sân bay nào?")
    return "\n".join(lines)


def handle_fasttrack(message: str) -> str:
    """Main handler for Fast Track queries."""
    airport_key = _get_airport_key(message)
    return format_fasttrack_info(airport_key)
