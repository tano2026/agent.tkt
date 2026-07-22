"""eSIM — Smart Agent Service

Cung cấp thông tin eSIM du lịch quốc tế.
"""

from typing import Optional

_PLANS = [
    {
        "name": "eSIM Châu Á",
        "coverage": "15 nước: Thái Lan, Singapore, Malaysia, Indonesia, Philippines, Hàn Quốc, Nhật Bản, Đài Loan, Hồng Kông, Trung Quốc, Ấn Độ, v.v.",
        "data": "3GB/ngày",
        "duration": "5-30 ngày",
        "price": 99_000,
        "price_note": "từ 99K/5 ngày",
    },
    {
        "name": "eSIM Châu Âu",
        "coverage": "33 nước: Pháp, Đức, Ý, Tây Ban Nha, Anh, Thụy Sĩ, Hà Lan, v.v.",
        "data": "2GB/ngày",
        "duration": "7-30 ngày",
        "price": 159_000,
        "price_note": "từ 159K/7 ngày",
    },
    {
        "name": "eSIM Châu Mỹ",
        "coverage": "Mỹ, Canada, Mexico, Brazil, v.v.",
        "data": "2GB/ngày",
        "duration": "7-30 ngày",
        "price": 199_000,
        "price_note": "từ 199K/7 ngày",
    },
    {
        "name": "eSIM Toàn cầu",
        "coverage": "100+ quốc gia",
        "data": "1GB/ngày",
        "duration": "7-30 ngày",
        "price": 299_000,
        "price_note": "từ 299K/7 ngày",
    },
    {
        "name": "eSIM Việt Nam (du khách nước ngoài)",
        "coverage": "Việt Nam",
        "data": "5GB/ngày",
        "duration": "7-30 ngày",
        "price": 129_000,
        "price_note": "từ 129K/7 ngày",
    },
]


def format_esim_info(region: Optional[str] = None) -> str:
    """Format eSIM plans as HTML-friendly string."""
    if region:
        region_lower = region.lower()
        filtered = [p for p in _PLANS if region_lower in p["name"].lower() or region_lower in p["coverage"].lower()]
        if filtered:
            plan = filtered[0]
            return (
                f"📶 **{plan['name']}**\n"
                f"• Vùng phủ: {plan['coverage']}\n"
                f"• Data: {plan['data']}\n"
                f"• Thời hạn: {plan['duration']}\n"
                f"💰 **{plan['price_note']}**\n\n"
                f"✅ Cài đặt tự động trong 5 phút, hỗ trợ eSIM-compatible devices.\n"
                f"💡 Gõ 'danh sách eSIM' để xem tất cả gói."
            )

    lines = ["📶 **eSIM Du Lịch — Internet không biên giới**"]
    lines.append("Data 4G/5G tốc độ cao, lắp đặt trong 5 phút, không cần SIM vật lý!\n")
    for p in _PLANS:
        lines.append(f"• **{p['name']}**")
        lines.append(f"  🌍 {p['coverage'][:60]}")
        lines.append(f"  💰 {p['price_note']}")
    lines.append("\n💡 Bạn muốn xem chi tiết khu vực nào?")
    lines.append("(Châu Á, Châu Âu, Châu Mỹ, Toàn cầu)")
    return "\n".join(lines)


def handle_esim(message: str) -> str:
    """Main handler for eSIM queries."""
    regions = ["châu á", "châu âu", "châu mỹ", "toàn cầu", "việt nam", "asia", "europe", "america", "global", "vietnam"]
    message_lower = message.lower()
    region = None
    for r in regions:
        if r in message_lower:
            region = r
            break
    return format_esim_info(region)
