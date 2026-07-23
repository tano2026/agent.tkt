"""
Chat API — AI-powered chat với LLM làm trung tâm.

Luồng:
1. Gửi message lên LLM (kèm context của turn trước)
2. LLM quyết định: search_flight hoặc reply
3. Nếu search → gọi AGT → format → trả về
4. Nếu reply → trả về luôn
5. Multi-turn: inject flight results context + hỗ trợ round-trip
"""

from __future__ import annotations

import json
import logging
import threading
import re
from datetime import datetime, timedelta
from typing import Any, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services.llm_gateway import get_llm
from app.services.abtrip_client import get_client
from app.services.flight_formatter import format_flight_results
from app.services.mock_flights import generate_mock_result
from app.services.intent_parser import (
    parse_flight_search, _LOCATION_SLANG, classify_intent, classify_service, parse_passenger_details,
)
from app.services.smart_fasttrack import handle_fasttrack
from app.services.smart_esim import handle_esim
from app.services.smart_visa import handle_visa
from app.services.smart_passport import handle_passport
from app.services.rag_knowledge import get_rag
from app.services.conversation_memory import get_memory
from app.services.flight_watcher import get_flight_watcher

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["chat"])


class ChatRequest(BaseModel):
    message: str
    agent: str = "ticketing"
    session_id: str = ""
    model_config = {"extra": "ignore"}  # Accept extra fields gracefully


class ChatResponse(BaseModel):
    reply: str
    type: str = "text"
    data: Optional[dict[str, Any]] = None
    suggestions: list[str] = []


# ── Database-backed session store ─────────────────────────────────────

_session_cache = threading.local()


def _get_session(session_id: str) -> dict[str, Any]:
    """Get session from SQLite, cached per-thread for current request.

    Returns a mutable dict — no need to save() explicitly;
    _flush_session() persists it automatically at the end of the request.
    """
    if not session_id:
        return {}
    # Check thread-local cache first
    cache_key = f"s_{session_id}"
    if hasattr(_session_cache, cache_key):
        return getattr(_session_cache, cache_key)

    session = get_memory().get_session(session_id)
    setattr(_session_cache, cache_key, session)
    return session


def _flush_session(session_id: str) -> None:
    """Persist cached session back to SQLite and clear cache."""
    if not session_id:
        return
    cache_key = f"s_{session_id}"
    if hasattr(_session_cache, cache_key):
        session = getattr(_session_cache, cache_key)
        try:
            get_memory().save_session(session_id, session)
        except Exception as e:
            logger.warning("Failed to save session %s: %s", session_id[:8], e)
        delattr(_session_cache, cache_key)


# ── Airport codes for reverse lookup ─────────────────────────────────
_AIRPORT_NAMES = {
    "SGN": "TP.HCM", "HAN": "Hà Nội", "DAD": "Đà Nẵng",
    "CXR": "Nha Trang", "DLI": "Đà Lạt", "PQC": "Phú Quốc",
    "HUI": "Huế", "VCS": "Côn Đảo", "VDH": "Đồng Hới",
    "VII": "Vinh", "DIN": "Điện Biên",
    "HPH": "Hải Phòng", "UIH": "Quy Nhơn", "BMV": "Buôn Ma Thuột",
    "VCL": "Chu Lai",
}


@router.post("/chat")
async def chat(body: ChatRequest) -> ChatResponse:
    message = body.message.strip()
    agent = body.agent
    session_id = body.session_id

    if not message:
        raise HTTPException(status_code=400, detail="Message is required")

    logger.info("Chat [%s] %s: %s", session_id[:8], agent, message[:80])

    if agent == "ticketing":
        result = await _handle_ticketing(message, session_id)
        _flush_session(session_id)
        return result
    elif agent == "sim":
        result = await _handle_general(message, session_id, "sim")
        _flush_session(session_id)
        return result
    elif agent == "visa":
        result = await _handle_general(message, session_id, "visa")
        _flush_session(session_id)
        return result
    else:
        return ChatResponse(reply=f"Agent '{agent}' chưa được hỗ trợ.")


async def _handle_ticketing(message: str, session_id: str) -> ChatResponse:
    """Ticketing: gọi LLM → nếu LLM muốn tìm vé thì gọi AGT/mock."""
    session = _get_session(session_id)

    # ── STEP 0: SmartAgent Service Router (only if no pending action) ──
    pending_action = session.get("pending_action")
    
    # Check for flight selection command
    select_match = re.search(r"^(chọn|chon|dat|đặt)\s+(\d+|[a-zA-Z]{1,2}[0-9a-zA-Z]{1,5})", message, re.IGNORECASE)
    if select_match and session.get("last_structured_flights"):
        command = select_match.group(1).lower()
        value = select_match.group(2)
        
        if value.isdigit():
            return await _handle_flight_selection(message, session, session_id, "index", int(value))
        else:
            # If it's not a digit, assume it's a flight code like BL360
            return await _handle_flight_selection(message, session, session_id, "code", value)

    if not pending_action:
        service = classify_service(message)
        if service != "flight":
            return await _handle_smart_service(message, session_id, session, service)

    # ── STEP 1: Kiểm tra nếu đang trong trạng thái chờ hành động ─────────
    
    if pending_action == "awaiting_passenger_info":
        return await _handle_passenger_info_collection(message, session, session_id)
    
    if pending_action == "confirm_booking":
        msg_lower = message.lower().strip()
        if msg_lower in ("ok", "có", "co", "yes", "y", "đồng ý", "hoàn tất", "dat", "đặt"):
            session["pending_action"] = None
            session["history"].append({"role": "user", "content": message})
            return await _execute_booking(session, session_id)
        elif msg_lower in ("hủy", "huy", "no", "k", "không", "ko", "khong", "thôi", "thoi", "cancel"):
            session["pending_action"] = None
            session["passengers_to_book"] = []
            session["selected_flight"] = None
            session["history"].append({"role": "user", "content": message})
            session["history"].append({"role": "assistant", "content": "👍 Đã hủy đặt vé. Bạn cần tìm gì khác không?"})
            return ChatResponse(reply="👍 Đã hủy đặt vé. Bạn cần tìm gì khác không?", type="text")
        else:
            session["history"].append({"role": "user", "content": message})
            session["history"].append({"role": "assistant", "content": "Vui lòng gõ 'Đồng ý' hoặc 'OK' để xác nhận, hoặc 'Hủy' để bỏ qua."})
            return ChatResponse(reply="Vui lòng gõ 'Đồng ý' hoặc 'OK' để xác nhận, hoặc 'Hủy' để bỏ qua.", type="text", suggestions=["Đồng ý", "OK", "Hủy đặt vé"])

    if pending_action == "confirm_search":
        msg_lower = message.lower().strip()
        if msg_lower in ("ok", "có", "co", "yes", "y", "đồng ý", "tim", "tìm", "oke", "okay"):
            # User xác nhận → tiến hành search
            parsed = session.get("pending_data", {})
            session["pending_action"] = None
            session["pending_data"] = None
            return await _execute_flight_search(parsed, session, session_id, message)
        elif msg_lower in ("hủy", "huy", "no", "k", "không", "ko", "khong", "thôi", "thoi"):
            session["pending_action"] = None
            session["pending_data"] = None
            session["history"].append({"role": "user", "content": message})
            session["history"].append({"role": "assistant", "content": "👍 Không sao, bạn cần tìm gì thì nói tôi nhé!"})
            return ChatResponse(reply="👍 Không sao, bạn cần tìm gì thì nói tôi nhé!", type="text")
        else:
            session["history"].append({"role": "user", "content": message})
            session["history"].append({"role": "assistant", "content": "Tôi chưa hiểu ý bạn. Vui lòng gõ 'OK' hoặc 'Có' để xác nhận tìm kiếm, hoặc 'Đổi ngày' / 'Hủy' để thay đổi."})
            return ChatResponse(
                reply="Tôi chưa hiểu ý bạn. Vui lòng gõ 'OK' hoặc 'Có' để xác nhận tìm kiếm, hoặc 'Đổi ngày' / 'Hủy' để thay đổi.",
                type="text",
                suggestions=["OK", "Có", "Đổi ngày", "Hủy"],
            )

    # if pending_action == "awaiting_confirm": # Removed (handled by LLM function calling)
    #     # ... (original awaiting_confirm logic, now removed)
    #     pass # This block is effectively removed

    # ── STEP 1: Parse với intent parser local (nhanh, rẻ) ──────────
    parsed = parse_flight_search(message)
    intent_type = classify_intent(message)

    # ── STEP 2: Nếu thiếu thông tin → hỏi lại khách ────────────────
    # Removed (LLM will use collect_passenger_info or answer_question now)

    # ── STEP 3: Nếu đã đầy đủ → confirm trước khi search ──────────
    if parsed and intent_type == "search_flight" and "origin" in parsed and "destination" in parsed:
        session["pending_action"] = "confirm_search"
        session["pending_data"] = parsed

        origin_name = _reverse_location(parsed["origin"])
        dest_name = _reverse_location(parsed["destination"])
        date_str = parsed.get("date", "")
        try:
            d = datetime.strptime(date_str, "%d%m%Y")
            date_display = d.strftime("%d/%m/%Y")
        except (ValueError, TypeError):
            date_display = date_str

        adults = parsed.get("adults", 1)
        confirm_msg = (
            f"✈️ **Tìm vé: {origin_name} → {dest_name}**\n"
            f"📅 Ngày: {date_display}\n"
            f"👤 {adults} người{' lớn' if adults > 0 else ''}"
            f"{' + ' + str(parsed.get('children', 0)) + ' trẻ em' if parsed.get('children', 0) > 0 else ''}"
            f"{' + ' + str(parsed.get('infants', 0)) + ' em bé' if parsed.get('infants', 0) > 0 else ''}\n\n"
            f"✅ **Xác nhận tìm?** (gõ OK / Có)"
        )
        session["history"].append({"role": "assistant", "content": confirm_msg})
        return ChatResponse(
            reply=confirm_msg,
            type="confirm",
            data={"params": parsed},
            suggestions=["OK", "Có", "Đổi ngày", "Hủy"],
        )

    # ── STEP 4: Non-search intents — handle locally ─────────────────
    policy_responses = {
        "policy_baggage": (
            "🧳 **Hành lý máy bay — thông tin cơ bản**\n\n"
            "• **Hành lý xách tay:** 1 kiện ≤7kg, kích thước 56x36x23cm\n"
            "• **Hành lý ký gửi:** Tùy hãng:\n"
            "  • Vietnam Airlines: 20-32kg (Bao gồm vé)\n"
            "  • Vietjet: 0kg (mua thêm từ 7-32kg)\n"
            "  • Bamboo: 20kg (bao gồm vé Eco)\n"
            "  • Pacific: 0kg (mua thêm)\n\n"
            "💡 Bạn muốn biết cụ thể hãng nào không?"
        ),
        "policy_change": (
            "🔄 **Đổi vé — quy định chung**\n\n"
            "• Nội địa: đổi được trước giờ bay, phí tùy hạng vé\n"
            "• Quốc tế: tùy điều kiện vé, có thể mất phí 50-100%\n"
            "• **Vietjet:** Đổi online đến 3h trước giờ bay\n"
            "• **VNA:** Đổi được đến 1h trước, phí ~150-500K\n\n"
            "Bạn bay hãng nào? Mình check cụ thể cho!"
        ),
        "policy_cancel": (
            "❌ **Hủy vé — lưu ý**\n\n"
            "• Vé **không hoàn** (non-refund) là phổ biến nhất\n"
            "• Một số vé có thể hoàn lại 50-80% thuế phí\n"
            "• Hủy trước giờ bay: càng sớm càng tốt\n"
            "• Liên hệ mình để check điều kiện vé cụ thể nhé!"
        ),
        "policy_documents": (
            "📋 **Thủ tục sân bay — những thứ cần mang**\n\n"
            "• **CMND/CCCD** (bản gốc)\n"
            "• **Vé máy bay** (in sẵn hoặc bản mềm)\n"
            "• Trẻ em: giấy khai sinh (bản sao)\n"
            "• Bay quốc tế: Hộ chiếu + Visa (nếu cần)\n\n"
            "Check-in online trước 24h để chọn chỗ ngồi nhé!"
        ),
        "policy_general": (
            "📄 **Chính sách chung — cần biết**\n\n"
            "Tùy mỗi hãng và hạng vé. Bạn muốn check:\n"
            "• 🧳 **Hành lý** bao nhiêu kg?\n"
            "• 🔄 **Đổi vé** / hủy vé?\n"
            "• 📋 **Thủ tục** check-in / giấy tờ?"
        ),
    }

    if intent_type in policy_responses:
        reply = policy_responses[intent_type]
        session["history"].append({"role": "user", "content": message})
        session["history"].append({"role": "assistant", "content": reply})
        return ChatResponse(reply=reply, type="text")

    # ── STEP 5: Chưa parse được → gọi LLM ──────────────────────────
    logger.info("=== Splashing: calling LLM for session %s, msg='%s' ===", session_id, message[:60])

    # ── Check for follow-up commands (client-side quick actions) ─────
    cmd_result = _handle_followup_command(message, session)
    if cmd_result:
        session["history"].append({"role": "user", "content": message})
        session["history"].append({"role": "assistant", "content": cmd_result["reply"]})
        return ChatResponse(**cmd_result)

    session["history"].append({"role": "user", "content": message})

    # ── Inject last search context if available ─────────────────────
    context = _build_context(session, message)
    llm = get_llm()
    result = await llm.chat(
        message=message,
        history=session.get("history", []),
        agent="ticketing",
        context=context,
    )

    llm_type = result.get("type", "reply")

    if llm_type == "search":
        params = result.get("params", {})
        return await _execute_flight_search(params, session, session_id, message)

    else:
        # LLM trả lời trực tiếp
        reply = result.get("content", "Xin lỗi, tôi chưa hiểu ý bạn.")
        session["history"].append({"role": "assistant", "content": reply})
        return ChatResponse(reply=reply, type="text")



async def _handle_passenger_info_collection(message: str, session: dict, session_id: str) -> ChatResponse:
    """Xử lý luồng thu thập thông tin hành khách."""
    # Khởi tạo danh sách hành khách nếu chưa có
    if "passengers_to_book" not in session:
        session["passengers_to_book"] = []
        last_search_params = session.get("last_search", {}).get("params", {})
        num_adults = last_search_params.get("adults", 1)
        num_children = last_search_params.get("children", 0)
        num_infants = last_search_params.get("infants", 0)

        for _ in range(num_adults):
            session["passengers_to_book"].append({"pax_type": "adult", "info": {}})
        for _ in range(num_children):
            session["passengers_to_book"].append({"pax_type": "child", "info": {}})
        for _ in range(num_infants):
            session["passengers_to_book"].append({"pax_type": "infant", "info": {}})

        session["current_passenger_index"] = 0

    passengers = session["passengers_to_book"]
    current_idx = session["current_passenger_index"]

    if current_idx >= len(passengers):
        # Đã thu thập đủ thông tin tất cả hành khách, chuyển sang xác nhận
        session["pending_action"] = "confirm_booking"
        return await _confirm_booking(session, session_id)

    current_pax_entry = passengers[current_idx]
    current_pax_info = current_pax_entry["info"]
    pax_type = current_pax_entry["pax_type"]
    pax_type_display = "người lớn" if pax_type == "adult" else ("trẻ em" if pax_type == "child" else "em bé")

    # 1. --- Xử lý input trực tiếp từ người dùng (ảnh hoặc text) ---
    # Kiểm tra nếu message là URL ảnh (giả định)
    image_url_match = re.search(r"(http[s]?://\S+\.(?:png|jpg|jpeg|gif))", message, re.IGNORECASE)
    if image_url_match:
        image_url = image_url_match.group(0)
        # TODO: Integrate vision_analyze here. This requires direct tool calling from the agent,
        # not directly from the FastAPI backend. For now, we will skip image processing.
        # This part needs to be handled by the outer Hermes agent if it receives an image.
        reply_msg = "Tôi đã nhận được ảnh. Hiện tại tôi chưa thể tự động trích xuất thông tin từ ảnh Hộ chiếu/CCCD. Vui lòng gõ thông tin hoặc gửi lại theo cú pháp."
        session["history"].append({"role": "assistant", "content": reply_msg})
        return ChatResponse(reply=reply_msg, type="text")

    # Parse thông tin từ text người dùng nhập vào
    parsed_from_message = parse_passenger_details(message)
    current_pax_info.update(parsed_from_message)

    # 2. --- Gọi LLM để trích xuất thông tin từ tin nhắn hiện tại (và lịch sử) ---
    llm = get_llm()
    llm_context = f"Khách hàng đang cung cấp thông tin cho hành khách {current_idx + 1} ({pax_type}). Các thông tin đã có: {json.dumps(current_pax_info, ensure_ascii=False)}. Thu thập các thông tin còn thiếu: họ tên, ngày sinh (DDMMYYYY), giới tính (Nam/Nữ), số điện thoại, email."
    llm_result = await llm.chat(
        message=message,
        history=session.get("history", []),
        agent="ticketing",
        context=llm_context,
    )

    if llm_result and llm_result.get("type") == "collect_pax":
        collected_info_from_llm = llm_result.get("params", {})
        current_pax_info.update(collected_info_from_llm)

    # 3. --- Kiểm tra và hỏi thông tin còn thiếu ---
    # Nếu các trường này không có, tự động điền "phòng vé"
    current_pax_info.setdefault("full_name", "phòng vé")
    current_pax_info.setdefault("date_of_birth", "01011990") # Một ngày sinh mặc định
    current_pax_info.setdefault("gender", "Nam") # Giới tính mặc định
    current_pax_info.setdefault("email", "phongve@abtrip.vn") # Email mặc định

    missing_fields = []
    # Chỉ số điện thoại là bắt buộc phải hỏi khách
    if current_idx == 0 and not current_pax_info.get("phone_number"):
        missing_fields.append("Số điện thoại")

    if missing_fields:
        pax_type_display = "người lớn" if pax_type == "adult" else ("trẻ em" if pax_type == "child" else "em bé")
        reply_msg = f"Vui lòng cho tôi biết {', '.join(missing_fields).lower()} của hành khách {current_idx + 1} ({pax_type_display}).\n\n💡 Bạn có thể nhập theo cú pháp: `0987654321`"
        suggestions = []
        if "Số điện thoại" in missing_fields:
            suggestions.append("0987654321")

        session["history"].append({"role": "assistant", "content": reply_msg})
        return ChatResponse(
            reply=reply_msg,
            type="clarify_pax_info",
            data={"missing_fields": missing_fields, "pax_index": current_idx, "pax_type": pax_type},
            suggestions=suggestions,
        )
    else:
        # Đã đủ thông tin cho hành khách hiện tại, chuyển sang hành khách tiếp theo
        session["current_passenger_index"] += 1
        # Lưu thông tin liên hệ đầu tiên làm mặc định nếu các hành khách sau thiếu
        if current_idx == 0:
            session["contact_info"] = {
                "phone_number": current_pax_info.get("phone_number"),
                "email": current_pax_info.get("email"),
            }
        else:
            # Gợi ý dùng thông tin liên hệ của người đầu tiên nếu còn thiếu
            if not current_pax_info.get("phone_number") and session["contact_info"].get("phone_number"):
                current_pax_info["phone_number"] = session["contact_info"]["phone_number"]
            if not current_pax_info.get("email") and session["contact_info"].get("email"):
                current_pax_info["email"] = session["contact_info"]["email"]

        reply_msg = f"✅ Đã có đủ thông tin cho hành khách {current_idx + 1} ({pax_type_display})."
        session["history"].append({"role": "assistant", "content": reply_msg})
        # Gọi lại chính hàm này để xử lý hành khách tiếp theo hoặc chuyển sang xác nhận
        return await _handle_passenger_info_collection("", session, session_id) # Empty message to re-trigger flow

async def _confirm_booking(session: dict, session_id: str) -> ChatResponse:
    """Hiển thị tổng hợp thông tin và yêu cầu xác nhận đặt vé."""
    selected_flight = session.get("selected_flight", {})
    passengers = session.get("passengers_to_book", [])

    if not selected_flight or not passengers:
        session["pending_action"] = None
        return ChatResponse(reply="⚠️ Có lỗi xảy ra, không tìm thấy thông tin chuyến bay hoặc hành khách để đặt vé. Vui lòng thử lại.", type="text")

    summary_msg = f"**✈️ XÁC NHẬN ĐẶT VÉ ABTRIP**\n\n**Chuyến bay:**\n*   {selected_flight['code']} của {selected_flight['airline_name']}\n*   Thời gian: {selected_flight['depart']} → {selected_flight['arrive']}\n*   Giá vé: **{selected_flight['price_str']}**\n\n**Thông tin hành khách:**\n"
    for i, pax_entry in enumerate(passengers):
        pax_info = pax_entry["info"]
        summary_msg += f"*   **Hành khách {i+1} ({pax_entry['pax_type'].capitalize()}):** {pax_info.get('full_name')}, NS: {pax_info.get('date_of_birth')}, GT: {pax_info.get('gender')}\n"
        if pax_info.get("phone_number") or pax_info.get("email"):
            summary_msg += f"    SĐT: {pax_info.get('phone_number', 'N/A')}, Email: {pax_info.get('email', 'N/A')}\n"

    total_price = selected_flight['price_raw'] * len(passengers) # Simplified for now
    summary_msg += f"\n**Tổng tiền dự kiến:** **{total_price:,.0f}₫**\n\n✅ **Xác nhận đặt vé?** (Gõ 'Đồng ý' hoặc 'OK' để hoàn tất)"

    session["history"].append({"role": "assistant", "content": summary_msg})
    return ChatResponse(
        reply=summary_msg,
        type="confirm_booking",
        data={"flight": selected_flight, "passengers": passengers},
        suggestions=["Đồng ý", "OK", "Hủy đặt vé", "Sửa thông tin"],
    )

async def _execute_booking(session: dict, session_id: str) -> ChatResponse:
    """Thực hiện gọi API đặt vé và xuất vé."""
    selected_flight = session.get("selected_flight", {})
    passengers_to_book = session.get("passengers_to_book", [])

    if not selected_flight or not passengers_to_book:
        session["pending_action"] = None
        return ChatResponse(reply="⚠️ Không đủ thông tin để đặt vé. Vui lòng thử lại quy trình từ đầu.", type="text")

    # Gọi API BookFlight và IssueTicket từ abtrip_client.py
    client = get_client()
    try:
        # Bước 1: BookFlight
        book_response = await client.book_flight(
            session_info=selected_flight.get("session_info"), # Cần đảm bảo session_info có sẵn từ bước chọn chuyến bay
            flight_option_id=selected_flight.get("flight_option_id"),
            fare_option_id=selected_flight.get("fare_option_id"),
            airline_option_id=selected_flight.get("airline_option_id"),
            passengers=passengers_to_book # Cần format lại passengers cho đúng với API
        )

        if not book_response or not book_response.get("Success"):
            error_msg = book_response.get("Message", "Lỗi đặt chỗ không xác định.")
            return ChatResponse(reply=f"❌ Đặt chỗ không thành công: {error_msg}. Vui lòng thử lại hoặc liên hệ hỗ trợ.", type="text")

        pnr_code = book_response.get("PNR", "")
        # Bước 2: IssueTicket
        issue_response = await client.issue_ticket(
            session_info=selected_flight.get("session_info"),
            pnr_code=pnr_code,
            payment_type="DEFAULT" # Tạm thời dùng DEFAULT, có thể mở rộng sau
        )

        if not issue_response or not issue_response.get("Success"):
            error_msg = issue_response.get("Message", "Lỗi xuất vé không xác định.")
            return ChatResponse(reply=f"❌ Xuất vé không thành công: {error_msg}. Vui lòng liên hệ hỗ trợ với mã đặt chỗ: {pnr_code}.", type="text")

        reply_msg = (
            f"✅ **ĐẶT VÉ VÀ XUẤT VÉ THÀNH CÔNG!**\n\n"
            f"Mã đặt chỗ (PNR): **{pnr_code}**\n"
            f"Bạn sẽ nhận được email xác nhận vé điện tử trong ít phút tới.\n\n"
            f"Chúc bạn có một chuyến đi vui vẻ!"
        )
        session["pending_action"] = None
        session["passengers_to_book"] = [] # Clear passenger info
        session["selected_flight"] = None # Clear selected flight
        session["history"].append({"role": "assistant", "content": reply_msg})
        return ChatResponse(reply=reply_msg, type="booking_success", data={"pnr": pnr_code})

    except Exception as e:
        logger.error("Lỗi khi thực hiện đặt/xuất vé: %s", e)
        session["pending_action"] = None
        return ChatResponse(reply="❌ Có lỗi xảy ra trong quá trình đặt/xuất vé. Vui lòng thử lại sau hoặc liên hệ hỗ trợ.", type="text")


# ── Execute flight search (shared between confirm + LLM paths) ─────

async def _execute_flight_search(
    params: dict,
    session: dict,
    session_id: str,
    original_message: str,
) -> ChatResponse:
    """Execute actual flight search and return formatted results."""
    origin = params.get("origin", "").upper()
    destination = params.get("destination", "").upper()
    date = params.get("date", "")
    adults = params.get("adults", 1)
    children = params.get("children", 0)
    infants = params.get("infants", 0)

    # ── Round-trip detection ────────────────────────────────────
    is_return = params.get("is_return", False)
    if is_return and session.get("last_search"):
        last_params = session["last_search"].get("params", {})
        if not origin and last_params.get("destination"):
            origin = last_params["destination"]
        if not destination and last_params.get("origin"):
            destination = last_params["origin"]
        params["origin"] = origin
        params["destination"] = destination
        if not date and last_params.get("date"):
            try:
                d = datetime.strptime(last_params["date"], "%d%m%Y")
                return_date = d + timedelta(days=3)
                date = return_date.strftime("%d%m%Y")
                params["date"] = date
            except ValueError:
                pass

    if not origin or not destination:
        reply = "✈️ Bạn vui lòng cho tôi biết điểm đi, điểm đến và ngày bay nhé!"
    else:
        logger.info("Searching flights: %s→%s %s (adults=%s, chd=%s, inf=%s)",
                    origin, destination, date, adults, children, infants)

        api_result = await _search_flights(params)
        if api_result.get("Success", False):
            reply, flights_data = format_flight_results(api_result, params, return_data=True)
            session["last_search"] = {
                "params": params,
                "summary": _summarize_results(api_result, params),
                "raw": api_result,
            }
            session["last_raw_flights"] = api_result.get("ListGroup", [])
            session["last_structured_flights"] = flights_data # Store the processed flights data
            session["last_results_count"] = len(flights_data)
        else:
            reply = f"❌ Lỗi tra cứu: {api_result.get('Message', 'Không rõ lỗi')}"
            flights_data = None
            session["last_search"] = None
            session["last_raw_flights"] = None
            session["last_structured_flights"] = None

    session["history"].append({"role": "assistant", "content": reply})
    suggestions = _get_suggestions(session)

    data = {"params": params, "last_search": session.get("last_search")}
    if "last_structured_flights" in session:
        data["flights"] = session["last_structured_flights"]

    return ChatResponse(
        reply=reply,
        type="flight_results",
        data=data,
        suggestions=suggestions,
    )


async def _handle_flight_selection(
    message: str,
    session: dict,
    session_id: str, # Thêm session_id vào đây
    selection_type: Literal["index", "code"],
    selection_value: str | int,
) -> ChatResponse:
    """Handle flight selection by index or flight code."""
    last_structured_flights = session.get("last_structured_flights")
    if not last_structured_flights:
        return ChatResponse(
            reply="⚠️ Chưa có kết quả chuyến bay nào để chọn. Bạn vui lòng tìm kiếm trước nhé!",
            type="text",
            suggestions=["Tìm chuyến bay"]
        )

    selected_flight = None
    if selection_type == "index":
        try:
            idx = int(selection_value)
            selected_flight = next((f for f in last_structured_flights if f["index"] == idx), None)
        except ValueError:
            pass
    elif selection_type == "code":
        code = str(selection_value).upper()
        selected_flight = next((f for f in last_structured_flights if f["code"].upper() == code), None)

    if not selected_flight:
        return ChatResponse(
            reply=f"⚠️ Không tìm thấy chuyến bay #{selection_value}. Vui lòng kiểm tra lại số thứ tự hoặc mã chuyến.",
            type="text",
            suggestions=["Xem lại chuyến bay", "Tìm chuyến bay khác"]
        )

    _AIRLINE_NAMES = {
        "VN": "Vietnam Airlines", "VJ": "Vietjet Air", "QH": "Bamboo Airways",
        "BL": "Pacific Airlines", "VU": "Vietravel Airlines",
    }
    airline_name = _AIRLINE_NAMES.get(selected_flight["airline"], selected_flight["airline"])
    reply = (
        f"✅ Bạn đã chọn chuyến bay **{selected_flight['code']}** của hãng **{airline_name}**\n"
        f"   Thời gian: {selected_flight['depart']} → {selected_flight['arrive']}\n"
        f"   Giá vé: **{selected_flight['price_str']}**\n"
        f"   Tổng cộng {selected_flight['seats']} ghế trống."
    )
    # Store selected flight details for later booking steps
    selected_flight["airline_name"] = airline_name # Add airline_name to selected_flight
    session["selected_flight"] = selected_flight

    # Chuyển sang trạng thái thu thập thông tin hành khách
    session["pending_action"] = "awaiting_passenger_info"
    return await _handle_passenger_info_collection("", session, session_id)

async def _confirm_booking(session: dict, session_id: str) -> ChatResponse:
    """Hiển thị tổng hợp thông tin và yêu cầu xác nhận đặt vé."""
    selected_flight = session.get("selected_flight", {})
    passengers = session.get("passengers_to_book", [])
    return ChatResponse(
        reply=reply + "\n\n💡 Vui lòng cung cấp thông tin hành khách để tiếp tục đặt vé.",
        type="text",
        suggestions=["Đặt vé ngay", "Hỏi về hành lý"]
    )


async def _handle_smart_service(message: str, session_id: str, session: dict, service: str) -> ChatResponse:
    """Route to the correct SmartAgent service handler."""
    session_id_short = session_id[:8] if session_id else "?"
    logger.info("SmartAgent service [%s]: %s — msg='%s'", session_id_short, service, message[:60])

    if service == "fasttrack":
        reply = handle_fasttrack(message)
        response_type = "text"
        suggestions = ["Fast Track Nội Bài", "Fast Track Tân Sơn Nhất", "Fast Track Đà Nẵng", "Giá"]
    elif service == "esim":
        reply = handle_esim(message)
        response_type = "text"
        suggestions = ["eSIM Châu Á", "eSIM Châu Âu", "eSIM Toàn cầu", "Giá"]
    elif service == "visa":
        reply = handle_visa(message)
        response_type = "text"
        suggestions = ["Visa Nhật Bản", "Visa Hàn Quốc", "Visa Schengen", "Visa Mỹ"]
    elif service == "passport":
        reply = handle_passport(message)
        response_type = "text"
        suggestions = ["Làm hộ chiếu", "Hộ chiếu cấp nhanh", "Chi phí", "Liên hệ"]
    else:
        reply = f"Dịch vụ '{service}' chưa được hỗ trợ."
        response_type = "text"
        suggestions = []

    session["history"].append({"role": "user", "content": message})
    session["history"].append({"role": "assistant", "content": reply})
    return ChatResponse(reply=reply, type=response_type, suggestions=suggestions)


async def _handle_general(message: str, session_id: str, agent: str) -> ChatResponse:
    """SIM & Visa: gọi LLM thuần chat."""
    session = _get_session(session_id)
    session["history"].append({"role": "user", "content": message})

    llm = get_llm()
    result = await llm.chat(
        message=message,
        history=session.get("history", []),
        agent=agent,
    )
    reply = result.get("content", "Xin lỗi, tôi chưa hiểu ý bạn.")

    session["history"].append({"role": "assistant", "content": reply})
    return ChatResponse(reply=reply, type="text")


# ── Build context for LLM ──────────────────────────────────────────

def _build_context(session: dict, message: str) -> str | None:
    """Build context string from RAG + last search results for the LLM."""
    parts = []

    # ── RAG knowledge context ──────────────────────────────────
    try:
        rag = get_rag()
        rag_ctx = rag.format_context(message, n_results=2)
        if rag_ctx:
            parts.append(rag_ctx)
    except Exception as e:
        logger.warning("RAG context error: %s", e)

    # ── Last search context ─────────────────────────────────────
    last = session.get("last_search")
    if last:
        params = last.get("params", {})
        summary = last.get("summary", "")
        if summary:
            origin_name = _AIRPORT_NAMES.get(params.get("origin", ""), params.get("origin", ""))
            dest_name = _AIRPORT_NAMES.get(params.get("destination", ""), params.get("destination", ""))
            parts.append(
                f"[KẾT QUẢ TÌM KIẾM TRƯỚC ĐÓ]\n"
                f"Tuyến: {origin_name} → {dest_name}\n"
                f"Ngày: {params.get('date', '?')}\n"
                f"Số hành khách: {params.get('adults', 1)} người lớn, "
                f"{params.get('children', 0)} trẻ em, {params.get('infants', 0)} em bé\n"
                f"Kết quả:\n{summary}\n"
                f"[HẾT KẾT QUẢ]"
            )

    if not parts:
        return None

    ctx = "\n\n".join(parts)
    ctx += f"\n\nNgười dùng nói: {message}"
    return ctx


def _summarize_results(api_result: dict, params: dict) -> str:
    """Create a brief summary of flight results for context injection."""
    groups = api_result.get("ListGroup", [])
    if not groups:
        return "Không có chuyến bay nào."

    lines = []
    cheapest = float("inf")
    cheapest_flight = ""

    for grp in groups:
        options = grp.get("ListAirOption", [])
        for opt in options:
            airline = opt.get("Airline", "?")
            flight_code = f"{airline}{opt.get('FlightNumber', '?')}"
            depart = opt.get("DepartTime", "?")[:5]
            arrive = opt.get("ArriveTime", "?")[:5]
            price_str = opt.get("PriceFmt") or opt.get("Price")
            try:
                price = float(opt.get("Price", 0) or 0)
            except (ValueError, TypeError):
                price = 0
            if price and price < cheapest:
                cheapest = price
                cheapest_flight = flight_code

            lines.append(f"  {flight_code}: {depart}→{arrive} {price_str}₫")

    total = params.get("adults", 1) + params.get("children", 0) + params.get("infants", 0)
    summary = f"{len(lines)} chuyến bay tìm thấy.\n"
    summary += "\n".join(lines[:8])  # top 8 to save tokens
    if len(lines) > 8:
        summary += f"\n  ... và {len(lines) - 8} chuyến khác"
    if cheapest < float("inf"):
        summary += f"\n💰 Rẻ nhất: {cheapest_flight} ({cheapest:,.0f}₫/vé)"
    summary += f"\n👥 {total} khách"
    return summary


# ── Follow-up commands ─────────────────────────────────────────────

_FOLLOWUP_PATTERNS = {
    "rẻ nhất": "cheapest",
    "re nhat": "cheapest",
    "sớm nhất": "earliest",
    "som nhat": "earliest",
    "nhanh nhất": "fastest",
    "nhanh nhat": "fastest",
    "bay thẳng": "direct",
    "bay thang": "direct",
    "các chuyến": "show_all",
    "xem tất cả": "show_all",
    "xem tat ca": "show_all",
    "xem lịch khác": "other_date",
    "lich khac": "other_date",
    "giá": "sort_price",
    "sắp xếp": "sort_price",
}


def _handle_followup_command(message: str, session: dict) -> dict | None:
    """Handle quick follow-up commands without going to LLM."""
    last = session.get("last_search")
    logger.info("=== FOLLOWUP: has_last=%s, msg='%s' ===",
                last is not None,
                message[:60])
    if not last:
        return None

    msg_lower = message.lower().strip()

    # Map message to action
    action = None
    for pattern, act in _FOLLOWUP_PATTERNS.items():
        if pattern in msg_lower:
            action = act
            break

    if not action:
        return None

    params = last.get("params", {})
    raw = last.get("raw", {})
    groups = raw.get("ListGroup", [])

    if action in ("cheapest", "earliest", "fastest", "direct", "show_all", "sort_price"):
        if not groups:
            return None

        all_options = []
        seen_prices = set()
        for grp in groups:
            for opt in grp.get("ListAirOption", []):
                price = opt.get("Price") or opt.get("TotalPrice") or 0
                try:
                    price_f = float(price)
                except (ValueError, TypeError):
                    price_f = 0
                # Airline & FlightNumber can be nested in ListFlightOption[*].ListFlight[*]
                airline = opt.get("Airline", "") or ""
                flight_num = opt.get("FlightNumber", "") or ""
                if not airline or not flight_num:
                    # Try nested structure (AGT format)
                    for fo in opt.get("ListFlightOption", []):
                        for fl in fo.get("ListFlight", []):
                            airline = fl.get("Airline", "") or airline
                            flight_num = fl.get("FlightNumber", "") or flight_num
                            if airline and flight_num:
                                break
                        if airline and flight_num:
                            break
                key = f"{airline}{flight_num}"
                if key and key not in seen_prices:
                    seen_prices.add(key)
                    all_options.append({**opt, "_price": price_f, "_airline": airline, "_flight_num": flight_num})

        if action == "cheapest":
            all_options.sort(key=lambda x: x["_price"])
            filtered = all_options[:1]
            label = "💸 Chuyến rẻ nhất"
        elif action == "earliest":
            all_options.sort(key=lambda x: x.get("DepartTime", "99:99"))
            filtered = all_options[:1]
            label = "🌅 Chuyến sớm nhất"
        elif action == "fastest":
            all_options.sort(key=lambda x: (
                int(x.get("DepartTime", "0000")[:2]) * 60 +
                int(x.get("DepartTime", "0000")[3:5]) -
                int(x.get("ArriveTime", "0000")[:2]) * 60 -
                int(x.get("ArriveTime", "0000")[3:5])
            ))
            filtered = all_options[:1]
            label = "🚀 Chuyến nhanh nhất"
        elif action == "direct":
            filtered = [o for o in all_options if o.get("StopNum", "0") == "0"]
            if not filtered:
                return None
            label = "✈️ Chuyến bay thẳng"
        elif action == "show_all":
            filtered = all_options
            label = "📋 Tất cả chuyến bay"
        elif action == "sort_price":
            all_options.sort(key=lambda x: x["_price"])
            filtered = all_options
            label = "💰 Sắp xếp theo giá"

        if not filtered:
            return None

        # Format filtered results
        lines = [f"### {label}"]
        for opt in filtered:
            airline = opt.get("_airline") or opt.get("Airline", "?")
            flight_num = opt.get("_flight_num") or opt.get("FlightNumber", "?")
            flight = f"{airline}{flight_num}"
            # Get DepartTime/ArriveTime from nested structure if not at top level
            depart = opt.get("DepartTime", "")
            arrive = opt.get("ArriveTime", "")
            if not depart or not arrive:
                for fo in opt.get("ListFlightOption", []):
                    for fl in fo.get("ListFlight", []):
                        full_depart = fl.get("DepartDate", "")
                        full_arrive = fl.get("ArriveDate", "")
                        if full_depart:
                            depart = full_depart.split()[-1] if " " in full_depart else full_depart
                        if full_arrive:
                            arrive = full_arrive.split()[-1] if " " in full_arrive else full_arrive
                        if depart and arrive:
                            break
                    if depart and arrive:
                        break
            depart = (depart or "??")[:5]
            arrive = (arrive or "??")[:5]
            price_fmt = opt.get("PriceFmt", f"{opt.get('_price', 0):,.0f}₫")
            stop = "" if opt.get("StopNum", "0") == "0" else f" ({opt['StopNum']} stop)"
            lines.append(f"  {flight}  {depart}→{arrive}  **{price_fmt}**{stop}")

        if action in ("cheapest", "earliest", "fastest", "direct"):
            lines.append(f"\n👥 {params.get('adults', 1)} người lớn")
            p = filtered[0].get("_price", 0) * params.get("adults", 1)
            lines.append(f"💰 Tổng: **{p:,.0f}₫**")
            lines.append("\n👉 Gõ 'đặt' + mã chuyến để đặt (VD: 'đặt BLBL175')")
        else:
            lines.append(f"\n{len(filtered)} chuyến")

        suggestions = ["Chuyến rẻ nhất", "Chuyến sớm nhất", "Đổi ngày bay", "Tìm tuyến khác"]

        return {
            "reply": "\n".join(lines),
            "type": "flight_results",
            "data": {"params": params, "filtered": True},
            "suggestions": suggestions,
        }

    return None


def _get_suggestions(session: dict) -> list[str]:
    """Get contextual suggestions based on current search state."""
    last = session.get("last_search")
    logger.info("=== GET_SUGGESTIONS: last=%s, last_keys=%s", last is not None, list(last.keys()) if last else "N/A")
    import traceback as _tb
    if not last:
        return ["Chuyến rẻ nhất", "Chuyến bay thẳng", "Chuyến sớm nhất", "Xem lịch khác"]

    params = last.get("params", {})
    suggestions = ["Chuyến rẻ nhất", "Chuyến bay thẳng", "Chuyến sớm nhất"]

    # Add round-trip suggestion if we have a route
    origin = params.get("origin", "")
    destination = params.get("destination", "")
    if origin and destination:
        dest_name = _AIRPORT_NAMES.get(destination, destination)
        suggestions.append(f"Về {dest_name}")
        suggestions.append("Đổi ngày bay")

    return suggestions[:4]  # keep max 4


# ── Search flights ─────────────────────────────────────────────────

async def _search_flights(params: dict) -> dict:
    """Gọi AGT API tìm chuyến bay. Nếu fail → mock data."""
    origin = params.get("origin", "").upper()
    dest = params.get("destination", "").upper()
    date = params.get("date", "")
    adults = params.get("adults", 1)
    children = params.get("children", 0)
    infants = params.get("infants", 0)

    # Try real AGT API first
    try:
        client = get_client()
        routes = [{
            "Leg": 0,
            "StartPoint": origin,
            "EndPoint": dest,
            "DepartDate": date,
        }]
        result = await client.search_flight(
            system="",
            adt=adults,
            chd=children,
            inf=infants,
            routes=routes,
        )
        # Only use real result if it has actual flight data with prices
        if result.get("Success") and result.get("ListGroup"):
            has_real_data = False
            for grp in result["ListGroup"]:
                for opt in grp.get("ListAirOption", []):
                    price = opt.get("Price") or opt.get("TotalPrice")
                    if price and float(price) > 0:
                        has_real_data = True
                        break
                if has_real_data:
                    break
            if has_real_data:
                return result
            logger.warning("AGT returned %d groups but all prices are null/0 — falling back to mock",
                           len(result["ListGroup"]))
    except Exception as e:
        logger.warning(f"AGT API failed, using mock: {e}")

    # Fallback to mock
    logger.info(f"Using mock data for {origin}→{dest} on {date}")
    return generate_mock_result(
        origin=origin,
        destination=dest,
        date=date,
        adults=adults,
        children=children,
        infants=infants,
    )


def _reverse_location(code: str) -> str:
    """Get human-friendly location name from IATA code."""
    names = {
        "SGN": "TP.HCM", "HAN": "Hà Nội", "DAD": "Đà Nẵng",
        "CXR": "Nha Trang", "DLI": "Đà Lạt", "PQC": "Phú Quốc",
        "HUI": "Huế", "VCS": "Côn Đảo", "VDH": "Đồng Hới",
        "VII": "Vinh", "DIN": "Điện Biên", "HPH": "Hải Phòng",
        "VDO": "Vân Đồn", "UIH": "Quy Nhơn", "TBB": "Tuy Hòa",
        "PXU": "Pleiku", "BMV": "Buôn Ma Thuột", "VCA": "Cần Thơ",
        "VKG": "Rạch Giá", "VCL": "Chu Lai",
    }
    return names.get(code, code)
