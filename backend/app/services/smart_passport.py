"""Passport / CCCD — Smart Agent Service

Dịch vụ hỗ trợ làm hộ chiếu, CCCD, các thủ tục liên quan (thiếu mộc, xử phạt
hành chính, hồ sơ em bé, in ngang, v.v).

Data: GIÁ CTV NGÀY 22/06/2026 — CHƯA GỒM PHÍ NHÀ NƯỚC (+50K).

⚠️ QUAN TRỌNG — đọc trước khi sửa data này:
- Giá hộ chiếu lên xuống THẤT THƯỜNG — phải check lại với cán bộ trước khi
  báo khách, không dùng số cứng trong file này để chốt giá cuối.
- Hồ sơ thiếu mộc: khách hỏi trường hợp cụ thể → tự lên hồ sơ thêm 100K.
- Thủ tục (nộp tỉnh nào, cơ quan nào, mẫu đơn, cách khai) PHỤ THUỘC từng
  trường hợp khách, KHÔNG nhất quán — phải hỏi cán bộ xử lý theo case,
  bot chỉ báo giá tham khảo + hướng dẫn liên hệ, không tự bốc thủ tục.
- "Ibox" = cần hỏi riêng qua chat/Zalo, giá không cố định / theo tỉnh đặc biệt.
"""

from __future__ import annotations

from typing import Optional

_PRICE_DATE = "22/06/2026"

_DISCLAIMER = (
    "\n\n⚠️ *Giá CTV cập nhật {date}, CHƯA gồm phí Nhà nước (+50K).* "
    "Giá hộ chiếu/CCCD thay đổi thất thường — nhân viên sẽ xác nhận lại giá "
    "chính xác theo hồ sơ cụ thể của bạn trước khi chốt.\n"
    "📞 Liên hệ 0869.320.320 để được tư vấn đúng trường hợp (nộp tỉnh nào, "
    "cơ quan nào, mẫu đơn ra sao) — mỗi hồ sơ có thủ tục khác nhau, không "
    "áp dụng chung một cách."
).format(date=_PRICE_DATE)

_MIEN_BAC_PROVINCES = [
    "hà nội", "ha noi", "ninh bình", "ninh binh", "hưng yên", "hung yen",
    "tuyên quang", "tuyen quang", "hải phòng", "hai phong",
]
_MIEN_NAM_PROVINCES = [
    "an giang", "tây ninh", "tay ninh", "khánh hòa", "khanh hoa",
    "lâm đồng", "lam dong", "đắk lắk", "dak lak", "đồng nai", "dong nai",
    "vĩnh long", "vinh long", "hồ chí minh", "ho chi minh", "hcm", "tphcm",
    "sài gòn", "sai gon", "bình dương", "binh duong", "vũng tàu", "vung tau",
]


# ---------------------------------------------------------------------------
# Menu tổng — khi không xác định được case cụ thể
# ---------------------------------------------------------------------------

def _menu() -> str:
    return (
        "📄 **Dịch vụ Hộ chiếu / CCCD — An Bình**\n\n"
        "Bạn đang cần loại nào, cho tôi biết cụ thể hơn để báo giá đúng:\n\n"
        "1️⃣ Hộ chiếu còn hạn — cấp đổi (Miền Bắc / Miền Nam)\n"
        "2️⃣ Hồ sơ thiếu mộc\n"
        "3️⃣ Hồ sơ em bé (trẻ em)\n"
        "4️⃣ Nộp Cục HCM (hồ sơ lỗi / không nhận lần đầu)\n"
        "5️⃣ In ngang hộ chiếu (đã có dữ liệu, chỉ in lại)\n"
        "6️⃣ CCCD lăn tay (Hà Nội / Miền Nam)\n"
        "7️⃣ Giấy phạt / hồ sơ xử phạt hành chính\n"
        "8️⃣ Dịch vụ khác: check thiếu mộc, duyệt nhanh, bị chú, giấy xác nhận...\n\n"
        "Nói rõ: hộ chiếu hay CCCD, ở tỉnh nào, hồ sơ có vướng gì không "
        "(thiếu mộc, tạm trú khác khẩu, hồ sơ trẻ em...) để tôi báo đúng gói."
        + _DISCLAIMER
    )


# ---------------------------------------------------------------------------
# 1. Giấy phạt / xử phạt hành chính
# ---------------------------------------------------------------------------

def _format_xu_phat() -> str:
    return (
        "📄 **Giấy phạt & Hồ sơ xử phạt hành chính**\n\n"
        "• Giấy phạt Campuchia: 10.000K (3-5 ngày)\n"
        "• Hồ sơ có quyết định xử phạt hành chính:\n"
        "  – Làm nhanh 3-5 ngày: 2.850K\n"
        "  – Làm thường 12-16 ngày: 1.800K\n"
        "• Đi Cam/Lào/Trung về còn hộ chiếu: Ibox hỏi giá riêng"
        + _DISCLAIMER
    )


# ---------------------------------------------------------------------------
# 2. Thiếu mộc
# ---------------------------------------------------------------------------

def _format_thieu_moc() -> str:
    return (
        "📄 **Hồ sơ thiếu mộc**\n\n"
        "⚠️ Hồ sơ thiếu mộc cần biết cụ thể tình huống của bạn trước — "
        "tự lên hồ sơ thiếu mộc sẽ cộng thêm 100K.\n\n"
        "• Thiếu mộc trên 1 năm, có CMND/CCCD khẩu Miền Bắc, không trình diện: "
        "9.000K (8-9 ngày)\n"
        "  – Khẩu Miền Nam: Ibox hỏi giá riêng\n"
        "• Thiếu mộc không có giấy tờ chứng minh, không trình diện: "
        "24.500K (8-9 ngày)\n"
        "• Thiếu mộc sổ thông hành toàn quốc: có mốc 1 ngày / 3 ngày / "
        "3-4 ngày / 10 ngày — giá theo từng mốc, cho tôi biết bạn cần mốc "
        "nào để báo chính xác\n\n"
        "Cho tôi biết: hồ sơ thiếu mộc bao lâu rồi, có giấy tờ chứng minh "
        "khẩu không, có trình diện được không — để tư vấn đúng."
        + _DISCLAIMER
    )


# ---------------------------------------------------------------------------
# 3. Hồ sơ em bé
# ---------------------------------------------------------------------------

def _format_em_be() -> str:
    return (
        "📄 **Hộ chiếu trẻ em**\n\n"
        "• Tự xác minh: nộp An Giang, cộng +100K\n"
        "• Bao xác minh (chỉ nhận bé đã nhập khẩu, lên hồ sơ trước 10h sáng "
        "được tính ngày) — **giá cố định, không giảm**:\n\n"
        "✅ *Dính tạm trú và khác khẩu:*\n"
        "  – 3 ngày: 3.000K\n"
        "  – 4 ngày: 2.850K\n"
        "  – 5 ngày: 2.350K\n"
        "  – 6 ngày: 2.050K\n"
        "  – 10-12 ngày: 1.950K (hỏi trước để hướng dẫn nộp)\n\n"
        "✅ *Không dính tạm trú* (khác khẩu chịu chờ thêm 1-2 ngày: +300K):\n"
        "  – 3 ngày: 2.200K\n"
        "  – 4 ngày: 1.850K\n"
        "  – 5 ngày: 1.650K\n"
        "  – 6 ngày: 1.450K\n"
        "  – 10-12 ngày: 1.250K (hỏi trước để hướng dẫn nộp)"
        + _DISCLAIMER
    )


# ---------------------------------------------------------------------------
# 4. Nộp Cục HCM
# ---------------------------------------------------------------------------

def _format_nop_cuc_hcm() -> str:
    return (
        "📄 **Nộp Cục HCM**\n\n"
        "⚠️ Cục HCM không nhận lần đầu, hồ sơ không trùng hình/thiếu dấu — "
        "lỗi thường tới ngày in mới báo và bắt buộc trình diện, không huỷ "
        "được, nhận tới 22h đêm. Cân nhắc kỹ nếu hồ sơ có khả năng mất "
        "lịch buổi đêm.\n\n"
        "Giá cố định, không giảm:\n"
        "  – 1 ngày: 2.100K\n"
        "  – 3 ngày: 1.550K\n"
        "  – 4 ngày: 1.200K\n"
        "  – 5 ngày: 850K\n"
        "  – 6 ngày: 700K"
        + _DISCLAIMER
    )


# ---------------------------------------------------------------------------
# 5. Hộ chiếu còn hạn — cấp đổi (Miền Nam / Miền Bắc)
# ---------------------------------------------------------------------------

def _format_con_han_nam() -> str:
    return (
        "📄 **Hộ chiếu còn hạn — cấp đổi, Miền Nam**\n\n"
        "  – 1 ngày: 2.250K (An Giang lên sớm & trình diện trước 5h chiều, "
        "Tây Ninh lên trước 8h tối)\n"
        "  – 3 ngày: 1.650K\n"
        "  – 4 ngày: 1.300K\n"
        "  – 5 ngày: 1.100K\n"
        "  – 6 ngày: 900K"
        + _DISCLAIMER
    )


def _format_con_han_bac() -> str:
    return (
        "📄 **Hộ chiếu còn hạn — cấp đổi, Miền Bắc**\n\n"
        "  – 1 ngày: 1.800K\n"
        "  – 3 ngày: 1.650K\n"
        "  – 10 ngày: 550K\n"
        "  ⚠️ Không trùng ảnh, phải lên lại: áp phí 0đ\n\n"
        "**Tỉnh riêng:**\n"
        "  – Hà Nội (3 ngày): 1.750K\n"
        "  – Ninh Bình: 1.750K\n"
        "  – Hưng Yên (1-3 ngày, cùng khẩu): 1.750K\n"
        "  – Tuyên Quang (1-3 ngày): 1.850K\n"
        "  – Hải Phòng (5-6 ngày): 2.200K\n\n"
        "Nhiều tỉnh khác cũng bốc được nhưng giá cao — cần Ibox hỏi riêng."
        + _DISCLAIMER
    )


# ---------------------------------------------------------------------------
# 6. In ngang hộ chiếu
# ---------------------------------------------------------------------------

def _format_in_ngang() -> str:
    return (
        "📄 **In ngang hộ chiếu** (đã có dữ liệu, chỉ cần in lại)\n\n"
        "**Miền Bắc:**\n"
        "  – In đúng hẹn (ảnh không can thiệp khâu lấy): 1.000K\n"
        "  – Lấy đúng hẹn tại Cục Hà Nội: 850K\n\n"
        "**Miền Nam:**\n"
        "  – Nhận nhanh: Tây Ninh, Khánh Hòa, Lâm Đồng, Đắk Lắk, Đồng Nai, "
        "Vĩnh Long — giá theo gói, hỏi riêng\n"
        "  – Các tỉnh khác: 2.000K (5-6 ngày, bốc tại HCM — cần có dữ liệu "
        "mới in được)\n\n"
        "**In ngang phòng HCM (mã 899):**\n"
        "Hồ sơ thường tính theo ngày trình diện; hồ sơ lỗi hình/lỗi khác "
        "tính từ ngày gửi hồ sơ.\n"
        "Đẩy bưu trong hồ sơ + vận đơn đi luôn trong ngày:\n"
        "  – 3 ngày: 2.000K\n"
        "  – 4 ngày: 1.700K\n"
        "  – 5 ngày: 1.300K\n"
        "  – 6 ngày: 1.100K"
        + _DISCLAIMER
    )


# ---------------------------------------------------------------------------
# 7. CCCD
# ---------------------------------------------------------------------------

def _format_cccd_ha_noi() -> str:
    return (
        "📄 **CCCD lăn tay — Hà Nội**\n\n"
        "  – Gói nhanh 1 ngày (nay làm mai trả, miễn tạm trú, nhận toàn "
        "quốc): 1.700K\n"
        "  – Gói 3-4 ngày (miễn tạm trú, nhận toàn quốc): 1.400K"
        + _DISCLAIMER
    )


def _format_cccd_mien_nam() -> str:
    return (
        "📄 **CCCD — Miền Nam**\n\n"
        "  – Khẩu tỉnh, làm combo tại HCM: 2.950K (1 ngày tạm trú + 2-3 "
        "ngày ra CCCD)\n"
        "  – Khẩu tỉnh, làm combo tại HCM: 2.350K (3-5 ngày tạm trú + 2-3 "
        "ngày ra CCCD)\n"
        "  – Khẩu SG (TP.HCM + Bình Dương + Vũng Tàu) hoặc đã có tạm trú "
        "SG: 1.650K (3-4 ngày)"
        + _DISCLAIMER
    )


# ---------------------------------------------------------------------------
# 8. Dịch vụ khác
# ---------------------------------------------------------------------------

def _format_dich_vu_khac() -> str:
    return (
        "📄 **Dịch vụ khác**\n\n"
        "  – Check thiếu mộc, check số lần cấp hộ chiếu, check cấm xuất "
        "cảnh: 700K\n"
        "  – Duyệt nhanh hồ sơ Cục HCM (không cần gửi hộ chiếu cũ về): "
        "500K\n"
        "  – Giấy xác nhận hộ chiếu: 900K (tự lên hồ sơ +100K)\n"
        "  – Bị chú số hộ chiếu: 900K (Miền Nam) — Miền Bắc: Ibox hỏi riêng\n"
        "  – Bị chú nơi sinh: 900K\n"
        "  – Bị giam giữ/thu hồi hộ chiếu ở cửa khẩu, sân bay (còn biên "
        "bản): trường hợp đặc biệt, liên hệ trực tiếp để tư vấn"
        + _DISCLAIMER
    )


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

def handle_passport(message: str) -> str:
    """Main handler for passport / CCCD queries — route theo case cụ thể."""
    msg = message.strip().lower()

    # Em bé / trẻ em — check trước vì có thể lẫn với các case khác
    if any(kw in msg for kw in ["em bé", "em be", "trẻ em", "tre em", "bé", "be sinh"]):
        return _format_em_be()

    # Giấy phạt / xử phạt hành chính / đi Cam-Lào-Trung
    if any(kw in msg for kw in [
        "giấy phạt", "giay phat", "xử phạt hành chính", "xu phat hanh chinh",
        "phạt campuchia", "phat campuchia", "đi cam", "đi lào", "đi trung",
    ]):
        return _format_xu_phat()

    # Dịch vụ phụ (check trước "thiếu mộc" vì "check thiếu mộc" là dịch vụ
    # check 700K, không phải làm lại hồ sơ thiếu mộc)
    if any(kw in msg for kw in [
        "duyệt nhanh", "duyet nhanh", "giấy xác nhận", "giay xac nhan",
        "bị chú", "bi chu", "cấm xuất cảnh", "cam xuat canh",
        "giam giữ", "giam giu", "thu hồi hộ chiếu", "thu hoi ho chieu",
        "check thiếu mộc", "check thieu moc", "check số lần", "check so lan",
        "check cấm", "check cam",
    ]):
        return _format_dich_vu_khac()

    # Thiếu mộc (lên hồ sơ mới)
    if any(kw in msg for kw in ["thiếu mộc", "thieu moc"]):
        return _format_thieu_moc()

    # Nộp Cục HCM
    if any(kw in msg for kw in ["nộp cục hcm", "nop cuc hcm", "cục hcm", "cuc hcm"]):
        return _format_nop_cuc_hcm()

    # In ngang
    if any(kw in msg for kw in ["in ngang"]):
        return _format_in_ngang()

    # CCCD — phân theo vùng
    if any(kw in msg for kw in ["cccd", "lăn tay", "lan tay", "căn cước"]):
        if any(p in msg for p in _MIEN_NAM_PROVINCES) or "miền nam" in msg or "mien nam" in msg:
            return _format_cccd_mien_nam()
        if any(p in msg for p in _MIEN_BAC_PROVINCES) or "miền bắc" in msg or "mien bac" in msg or "hà nội" in msg or "ha noi" in msg:
            return _format_cccd_ha_noi()
        return (
            _format_cccd_ha_noi()
            + "\n\n---\n\n"
            + _format_cccd_mien_nam()
        )

    # Hộ chiếu còn hạn — cấp đổi, phân theo vùng.
    # Chỉ trigger khi có tín hiệu rõ "còn hạn"/"cấp đổi", HOẶC khi câu có
    # "hộ chiếu"/"passport" ĐI KÈM tên tỉnh cụ thể — không trigger cho câu
    # nói trống "hộ chiếu" (câu đó phải rơi về menu để hỏi rõ loại trước).
    has_region = (
        any(p in msg for p in _MIEN_NAM_PROVINCES) or "miền nam" in msg or "mien nam" in msg
        or any(p in msg for p in _MIEN_BAC_PROVINCES) or "miền bắc" in msg or "mien bac" in msg
    )
    mentions_passport = any(kw in msg for kw in ["hộ chiếu", "ho chieu", "passport"])
    if "còn hạn" in msg or "con han" in msg or "cấp đổi" in msg or "cap doi" in msg or (mentions_passport and has_region):
        if any(p in msg for p in _MIEN_NAM_PROVINCES) or "miền nam" in msg or "mien nam" in msg:
            return _format_con_han_nam()
        if any(p in msg for p in _MIEN_BAC_PROVINCES) or "miền bắc" in msg or "mien bac" in msg:
            return _format_con_han_bac()
        # Không rõ vùng — hỏi lại
        return (
            "📄 **Hộ chiếu còn hạn — cấp đổi**\n\n"
            "Bạn ở Miền Bắc hay Miền Nam, và ở tỉnh nào? Giá và thời gian "
            "khác nhau theo tỉnh, cho tôi biết để báo đúng."
            + _DISCLAIMER
        )

    return _menu()
