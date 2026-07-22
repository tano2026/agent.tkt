"""Visa — Smart Agent Service

Cung cấp thông tin dịch vụ visa du lịch.
"""

from typing import Optional

_VISA_TYPES = {
    "thailand": {
        "name": "Visa Thái Lan",
        "types": "Miễn visa 30 ngày (VN passport)",
        "processing": "Không cần xin trước",
        "fee": "Miễn phí",
        "note": "Cần passport còn hạn ≥6 tháng",
    },
    "china": {
        "name": "Visa Trung Quốc",
        "types": "Du lịch (L), Thương mại (M), Thăm thân (Q2)",
        "processing": "5-7 ngày làm việc",
        "fee": "1,200,000₫ - 2,500,000₫",
        "note": "Cần dịch thuật công chứng giấy tờ",
    },
    "japan": {
        "name": "Visa Nhật Bản",
        "types": "Du lịch (tối đa 15 ngày, single/multi entry)",
        "processing": "5-7 ngày làm việc",
        "fee": "1,500,000₫ - 3,000,000₫",
        "note": "Cần sao kê tài khoản ngân hàng 3 tháng",
    },
    "korea": {
        "name": "Visa Hàn Quốc",
        "types": "Du lịch (C-3-9, single/multi)",
        "processing": "7-10 ngày làm việc",
        "fee": "1,000,000₫ - 2,500,000₫",
        "note": "Có thể xin visa 5 năm nếu đã từng đi Hàn/Mỹ/Nhật/Âu",
    },
    "schengen": {
        "name": "Visa Schengen (Châu Âu)",
        "types": "Du lịch, Thương mại (tối đa 90 ngày)",
        "processing": "10-15 ngày làm việc",
        "fee": "4,500,000₫ (bao gồm lệ phí + dịch vụ)",
        "note": "Cần bảo hiểm du lịch, lịch trình bay, xác nhận khách sạn",
    },
    "uk": {
        "name": "Visa Anh (UK)",
        "types": "Du lịch (Standard Visitor, tối đa 6 tháng)",
        "processing": "10-15 ngày làm việc",
        "fee": "5,000,000₫ - 7,000,000₫",
        "note": "Cần dịch thuật + chứng minh tài chính",
    },
    "usa": {
        "name": "Visa Mỹ (USA)",
        "types": "Du lịch/Thương mại (B1/B2)",
        "processing": "2-4 tuần (sau phỏng vấn)",
        "fee": "6,500,000₫ (lệ phí DS-160 + phí dịch vụ)",
        "note": "Cần phỏng vấn trực tiếp tại Đại sứ quán, cần đặt lịch sớm",
    },
    "australia": {
        "name": "Visa Úc",
        "types": "Du lịch (Visitor Visa 600, eVisitor)",
        "processing": "7-14 ngày làm việc",
        "fee": "3,500,000₫ - 5,000,000₫",
        "note": "Xin online, cần scan passport + giấy tờ",
    },
}


def _get_visa_key(text: str) -> Optional[str]:
    text_lower = text.lower()
    mapping = {
        "thái lan": "thailand",
        "thailand": "thailand",
        "trung quốc": "china",
        "trung quoc": "china",
        "china": "china",
        "nhật bản": "japan",
        "nhat ban": "japan",
        "japan": "japan",
        "hàn quốc": "korea",
        "han quoc": "korea",
        "korea": "korea",
        "schengen": "schengen",
        "châu âu": "schengen",
        "chau au": "schengen",
        "anh": "uk",
        "uk": "uk",
        "mỹ": "usa",
        "my": "usa",
        "usa": "usa",
        "úc": "australia",
        "uc": "australia",
        "australia": "australia",
    }
    for keyword, key in mapping.items():
        if keyword in text_lower:
            return key
    return None


def format_visa_info(country_key: Optional[str] = None) -> str:
    if country_key and country_key in _VISA_TYPES:
        v = _VISA_TYPES[country_key]
        return (
            f"🛂 **{v['name']}**\n"
            f"• Loại: {v['types']}\n"
            f"• Xử lý: {v['processing']}\n"
            f"• Phí: {v['fee']}\n"
            f"📌 *{v['note']}*\n\n"
            f"📞 Liên hệ 0869.320.320 để được tư vấn chi tiết!"
        )

    lines = ["🛂 **Dịch vụ Visa — Hỗ trợ xin visa toàn cầu**"]
    lines.append("Tư vấn + xử lý hồ sơ, tỷ lệ đậu cao.\n")
    for k, v in _VISA_TYPES.items():
        lines.append(f"• **{v['name']}** — {v['types'][:40]} | {v['fee']}")
    lines.append("\n💡 Bạn muốn xem thông tin nước nào?")
    lines.append("(Thái Lan, Trung Quốc, Nhật, Hàn, Schengen, UK, Mỹ, Úc)")
    return "\n".join(lines)


def handle_visa(message: str) -> str:
    country_key = _get_visa_key(message)
    return format_visa_info(country_key)
