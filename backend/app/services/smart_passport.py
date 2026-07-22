"""Passport — Smart Agent Service

Cung cấp thông tin dịch vụ làm hộ chiếu.
"""

from typing import Optional


def format_passport_info(detail: Optional[str] = None) -> str:
    """Format passport service info."""
    base = (
        "📄 **Hộ chiếu — Dịch vụ làm hộ chiếu**\n\n"
        "**Hộ chiếu phổ thông (passport xanh):**\n"
        "• Lần đầu: 200,000₫ (12 trang) / 400,000₫ (24 trang)\n"
        "• Cấp lại: 400,000₫ - 500,000₫\n"
        "• Thời gian: 5-7 ngày làm việc\n"
        "• Hạn: 10 năm\n\n"
        "**Hộ chiếu cấp nhanh (dịch vụ):**\n"
        "• Trong 1-3 ngày: 1,500,000₫ - 2,000,000₫\n"
        "• Bao gồm: chụp ảnh, hướng dẫn, nộp hồ sơ, nhận hộ\n\n"
        "**Lưu ý:**\n"
        "• Cần CCCD gốc + ảnh thẻ 4x6 (nền trắng)\n"
        "• Trẻ em <14 tuổi: cần giấy khai sinh + CCCD cha/mẹ\n"
        "• Passport cũ nếu có\n\n"
        "📞 Gọi 0869.320.320 để đặt lịch làm hộ chiếu nhanh!"
    )
    return base


def handle_passport(message: str) -> str:
    """Main handler for passport queries."""
    return format_passport_info()
