"""
Chat API v2 — Premium LLM Bot with multi-turn booking flow.

State machine:
  idle → search_results → collecting_passengers → awaiting_confirmation → booking_result

Features:
- Proper OpenAI-compatible function calling
- Redis session persistence (with in-memory fallback)
- Multi-turn passenger info collection
- Dynamic suggestions based on context
- Structured error recovery
"""

from __future__ import annotations

import json
import logging
import traceback as tb_mod
from datetime import datetime
from typing import Any

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.models.chat import (
    TOOL_BOOK_FLIGHT,
    TOOL_SEARCH_FLIGHT,
)
from app.models.chat import LLMResponse as LLMResponseModel
from app.services.abtrip_client import get_client as get_abtrip_client
from app.services.llm_gateway import get_llm
from app.services.session_service import get_session_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["chat"])

# ─── Request / Response Models ───────────────────────────────────────────────

class ChatRequest(BaseModel):
    agent: str = Field("ticketing", description="ticketing | sim | visa")
    message: str = Field(..., min_length=1, max_length=2000)
    session_id: str | None = None


class ChatResponse(BaseModel):
    type: str = Field(..., description="text | tool_call | error | booking_result")
    content: str | dict[str, Any]
    session_id: str
    suggestions: list[str] = Field(default_factory=list)
    step: str = "idle"
    booking_code: str | None = None


class HistoryResponse(BaseModel):
    session_id: str
    messages: list[dict[str, Any]] = Field(default_factory=list)


# ─── Agent Config ────────────────────────────────────────────────────────────

AGENT_META = {
    "ticketing": {
        "name": "Vé máy bay",
        "icon": "✈️",
        "suggestions": [
            "Tìm vé HN SG ngày mai",
            "Chính sách hành lý VietJet",
            "Vé rẻ nhất Đà Nẵng cuối tuần",
            "Đổi vé máy bay có mất phí không?",
        ],
    },
    "sim": {
        "name": "SIM du lịch",
        "icon": "📱",
        "suggestions": [
            "eSIM Thái Lan bao nhiêu?",
            "SIM du lịch Nhật Bản",
            "eSIM có cần đổi sim không?",
        ],
    },
    "visa": {
        "name": "Visa & Hộ chiếu",
        "icon": "🛂",
        "suggestions": [
            "Visa du lịch Nhật cần gì?",
            "Thủ tục xin visa Hàn Quốc",
            "Hộ chiếu hết hạn làm lại bao lâu?",
        ],
    },
}


# ─── Helper: Build system prompt ─────────────────────────────────────────────

def _build_system_prompt(agent: str) -> str:
    """Build the full system prompt with agent-specific instructions."""
    from app.services.aviation_db import (
        get_airline_dict_for_prompt,
        get_airport_dict_for_prompt,
    )
    from app.services.llm_gateway import SYSTEM_PROMPT as BASE_PROMPT

    agent_extensions = {
        "ticketing": "",
        "sim": """
## LƯU Ý CHO AGENT SIM:
- Bạn là chuyên gia SIM du lịch & eSIM
- Tư vấn gói SIM/eSIM cho từng quốc gia
- Giải thích dung lượng, thời hạn, giá cả
- Hỗ trợ đặt mua eSIM
- Tính năng SIM đang phát triển, tư vấn cơ bản dựa trên kiến thức
""",
        "visa": """
## LƯU Ý CHO AGENT VISA:
- Bạn là chuyên gia tư vấn Visa & Hộ chiếu
- Tư vấn thủ tục xin visa các nước
- Liệt kê hồ sơ cần chuẩn bị
- Giải thích thời gian xử lý, lệ phí
- Bạn CHỈ tư vấn thông tin, không đặt dịch vụ
""",
    }

    today = datetime.now().strftime("%d/%m/%Y")
    base = BASE_PROMPT.format(
        airport_info=get_airport_dict_for_prompt(),
        airline_info=get_airline_dict_for_prompt(),
        today=today,
    )
    return base + agent_extensions.get(agent, "")


# ─── Helper: Dynamic suggestions ─────────────────────────────────────────────

def _get_suggestions(agent: str, step: str, search_data: dict | None = None) -> list[str]:
    """Get context-aware suggestions based on current state."""
    base = AGENT_META.get(agent, AGENT_META["ticketing"])["suggestions"]

    if step == "search_results" and search_data:
        return [
            "Chọn chuyến rẻ nhất",
            "Xem chuyến khác",
            "So sánh giá các chuyến",
        ]
    elif step == "collecting_passengers":
        return [
            "Cung cấp thông tin hành khách",
            "Tôi chưa có sẵn thông tin",
            "Hủy và tìm lại",
        ]
    elif step == "awaiting_confirmation":
        return [
            "Xác nhận đặt vé",
            "Sửa thông tin hành khách",
            "Hủy đặt vé",
        ]
    elif step == "booking_result":
        return [
            "Tra cứu vé khác",
            "Kiểm tra trạng thái vé",
            "Gọi hỗ trợ",
        ]

    return base


# ─── Helper: Validate passenger info ─────────────────────────────────────────

def _validate_passenger(p: dict[str, Any]) -> list[str]:
    """Validate passenger info, return list of missing/incorrect fields."""
    errors = []
    if not p.get("lastName") or not p.get("firstName"):
        errors.append("Thiếu họ tên hành khách")
    if not p.get("gender"):
        errors.append("Thiếu giới tính (Nam/Nữ)")
    if not p.get("birthDate") or len(str(p.get("birthDate", ""))) != 8:
        errors.append("Thiếu ngày sinh (DDMMYYYY)")
    # Validate date format
    bd = str(p.get("birthDate", ""))
    if bd and len(bd) == 8:
        try:
            datetime.strptime(bd, "%d%m%Y")
        except ValueError:
            errors.append("Ngày sinh không hợp lệ (cần DDMMYYYY)")
    return errors


# ─── Helper: Format flight search results ────────────────────────────────────

def _format_flight_results(data: dict[str, Any], args: dict[str, Any]) -> str:
    """Format flight search results into user-friendly text."""
    routes = data.get("data", {}).get("ListRoute", []) if data.get("data") else data.get("ListRoute", [])
    if not routes:
        return "Xin lỗi, không tìm thấy chuyến bay phù hợp với yêu cầu của bạn."

    route = routes[0]
    start = route.get("StartPoint", "???")
    end = route.get("EndPoint", "???")
    depart = route.get("DepartDate", "???")

    flights = route.get("ListFlight", [])
    if not flights:
        return f"✈️ **{start} → {end}** | {depart}\nKhông có chuyến bay nào."

    parsed = _parse_flights(flights)
    if not parsed:
        return f"✈️ **{start} → {end}** | {depart}\nCó chuyến bay nhưng chưa có giá. Vui lòng thử lại."

    lines = [f"✈️ **{start} → {end}** | {depart}\n"]

    cheapest = parsed[0]
    fastest = min(parsed, key=lambda x: x.get("duration", "999")) if any(p.get("duration") for p in parsed) else None

    for i, p in enumerate(parsed):
        tags = []
        if p == cheapest:
            tags.append("⭐ Rẻ nhất")
        if fastest and p == fastest and p != cheapest:
            tags.append("🚀 Nhanh nhất")
        hour = int(p["depart"][:2]) if p["depart"][:2].isdigit() else 0
        if hour >= 19:
            tags.append("💥 Bay đêm")
        tag_str = "  " + "  ".join(tags) if tags else ""
        price_str = (
            f"{p['price']:,.0f}₫/khách"
            if p["currency"] == "VND"
            else f"{p['price']:,.0f}{p['currency']}/khách"
        )
        dur_str = f" ({p['duration']})" if p.get("duration") else ""
        lines.append(f"{i+1}. {p['flight']}  {p['depart']}→{p['arrive']}{dur_str}  {price_str}{tag_str}")

    adt = args.get("adt", 1)
    total_min = cheapest["price"] * adt
    total_max = parsed[-1]["price"] * adt
    if total_min == total_max:
        lines.append(f"\n💰 Tổng {adt} người: {total_min:,.0f}₫")
    else:
        lines.append(f"\n💰 Tổng {adt} người: {total_min:,.0f}₫ - {total_max:,.0f}₫")
    lines.append("\nGõ số thứ tự chuyến bay bạn muốn đặt 👇")
    return "\n".join(lines)


def _parse_flights(flights: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Parse raw AGT flight list into simplified structured array for frontend cards."""
    parsed = []
    for f in flights:
        items = f.get("ListItem", []) or f.get("ListAirItem", []) or []
        for item in items:
            price = float(item.get("TotalPrice", 0) or item.get("Price", 0))
            currency = item.get("Currency", "VND")
            airline = f.get("Airline", "??")
            flight_code = f.get("FlightNumber", "") or f.get("FlightCode", "")
            depart_time = f.get("StartTime", "??")
            arrive_time = f.get("EndTime", "??")
            duration = f.get("Duration", "") or f.get("FlightTime", "")
            session = f.get("Session", "") or item.get("Session", "")
            parsed.append({
                "airline": airline,
                "flight": f"{airline}{flight_code}",
                "depart": depart_time,
                "arrive": arrive_time,
                "duration": duration,
                "price": price,
                "currency": currency,
                "session": session,
                "AirlineCode": airline,
                "FlightNumber": flight_code,
                "DepartTime": depart_time,
                "ArrivalTime": arrive_time,
                "AdultFare": price,
                "AvailableSeats": int(f.get("AvailSeat", 0) or f.get("SeatRemain", "0")),
            })
    parsed.sort(key=lambda x: x["price"])
    return parsed


# ─── Routes ──────────────────────────────────────────────────────────────────

@router.post("/chat")
async def chat(request: ChatRequest):
    """Handle chat message with multi-turn state machine."""
    try:
        agent = request.agent if request.agent in ("ticketing", "sim", "visa") else "ticketing"
        sessions = get_session_service()

        # Get or create session
        if request.session_id:
            session_data = await sessions.get_session(request.session_id)
            if not session_data:
                session_id = await sessions.create_session(agent, request.session_id)
                # Use the requested session_id
                session_data = await sessions.get_session(session_id)
            else:
                session_id = request.session_id
        else:
            session_id = await sessions.create_session(agent)
            session_data = {"agent": agent, "messages": [], "step": "idle", "search_results": [], "booking_draft": {}}

        if session_data is None:
            session_data = {
                "agent": agent,
                "messages": [],
                "step": "idle",
                "search_results": [],
                "booking_draft": {},
            }

        step = session_data.get("step", "idle")
        history = session_data.get("messages", [])
        search_results = session_data.get("search_results", [])

        # ── PROCESS MESSAGE BASED ON STATE ────────────────────────────

        # State: search_results — user might be picking a flight number
        if step == "search_results" and search_results:
            latest = search_results[-1]
            formatted = latest.get("formatted", "")
            raw = latest.get("raw_data", {})

            # Check if user is selecting a flight by number
            selection = _detect_flight_selection(request.message, raw)
            if selection is not None:
                # User selected a flight — start collecting passenger info
                selected_flight = selection
                draft = {
                    "selected_route": selected_flight,
                    "passengers": [],
                    "contact": {},
                    "step": "collecting_passengers",
                    "error_message": "",
                }
                await sessions.save_booking_draft(session_id, draft)
                await sessions.update_step(session_id, "collecting_passengers")

                # Save messages
                await sessions.add_message(session_id, "user", request.message)
                response_text = _build_passenger_prompt(selected_flight)
                await sessions.add_message(session_id, "assistant", response_text)

                return ChatResponse(
                    type="text",
                    content=response_text,
                    session_id=session_id,
                    suggestions=_get_suggestions(agent, "collecting_passengers"),
                    step="collecting_passengers",
                )

        # State: collecting_passengers — collect passenger details
        if step == "collecting_passengers":
            result = await _handle_passenger_collection(session_id, request.message)
            if result["type"] == "need_more_info":
                await sessions.add_message(session_id, "user", request.message)
                await sessions.add_message(session_id, "assistant", result["content"])
                return ChatResponse(
                    type="text",
                    content=result["content"],
                    session_id=session_id,
                    suggestions=_get_suggestions(agent, "collecting_passengers"),
                    step="collecting_passengers",
                )
            elif result["type"] == "ready_to_confirm":
                # All passenger info gathered — show confirmation
                await sessions.update_step(session_id, "awaiting_confirmation")
                await sessions.add_message(session_id, "user", request.message)
                await sessions.add_message(session_id, "assistant", result["content"])
                return ChatResponse(
                    type="text",
                    content=result["content"],
                    session_id=session_id,
                    suggestions=_get_suggestions(agent, "awaiting_confirmation"),
                    step="awaiting_confirmation",
                )
            elif result["type"] == "cancelled":
                await sessions.update_step(session_id, "idle")
                await sessions.add_message(session_id, "user", request.message)
                await sessions.add_message(session_id, "assistant", result["content"])
                return ChatResponse(
                    type="text",
                    content=result["content"],
                    session_id=session_id,
                    suggestions=_get_suggestions(agent, "idle"),
                    step="idle",
                )

        # State: awaiting_confirmation — user confirms or cancels booking
        if step == "awaiting_confirmation":
            if _is_confirmation(request.message):
                # Execute booking!
                draft = await sessions.get_booking_draft(session_id)
                await sessions.update_step(session_id, "booking_in_progress")
                await sessions.add_message(session_id, "user", request.message)
                booking_result = await _execute_booking(draft)
                await sessions.update_step(session_id, "booking_result")
                await sessions.add_message(session_id, "assistant", booking_result["content"])

                # Reset draft
                await sessions.save_booking_draft(session_id, {
                    "selected_route": {}, "passengers": [], "contact": {}, "step": "idle", "error_message": "",
                })

                return ChatResponse(
                    type="booking_result",
                    content=booking_result["content"],
                    session_id=session_id,
                    suggestions=_get_suggestions(agent, "booking_result"),
                    step="booking_result",
                    **({"booking_code": booking_result.get("booking_code")} if booking_result.get("booking_code") else {}),
                )
            elif _is_cancellation(request.message):
                await sessions.update_step(session_id, "idle")
                await sessions.add_message(session_id, "user", request.message)
                msg = "Đã hủy đặt vé. Bạn cần tìm chuyến bay khác không? 👇"
                await sessions.add_message(session_id, "assistant", msg)
                return ChatResponse(
                    type="text",
                    content=msg,
                    session_id=session_id,
                    suggestions=_get_suggestions(agent, "idle"),
                    step="idle",
                )

        # ── DEFAULT: Send to LLM for processing ──────────────────────

        # Build system prompt
        system = _build_system_prompt(agent)

        # Get LLM response
        llm = get_llm()
        llm_response = await llm.chat(
            message=request.message,
            history=history,
            system_override=system,
        )

        await sessions.add_message(session_id, "user", request.message)

        # Handle tool calls
        if llm_response.type == "tool_call":
            tool_name = llm_response.tool_name
            tool_args = llm_response.tool_args
            logger.info("Tool call: %s with args=%s", tool_name, tool_args)

            if tool_name == TOOL_SEARCH_FLIGHT:
                result = await _execute_search(tool_args)
                if result.get("success"):
                    formatted = _format_flight_results(result, tool_args)
                    # Save search results to session
                    await sessions.save_search_results(session_id, result, formatted)
                    await sessions.add_message(session_id, "assistant", formatted)

                    return ChatResponse(
                        type="text",
                        content=formatted,
                        session_id=session_id,
                        suggestions=_get_suggestions(agent, "search_results"),
                        step="search_results",
                    )
                else:
                    error_msg = f"Xin lỗi, không tìm thấy chuyến bay phù hợp: {result.get('error', 'Lỗi hệ thống')}"
                    await sessions.add_message(session_id, "assistant", error_msg)
                    return ChatResponse(
                        type="text",
                        content=error_msg,
                        session_id=session_id,
                        suggestions=_get_suggestions(agent, step),
                        step=step,
                    )

            elif tool_name == TOOL_BOOK_FLIGHT:
                # LLM wants to book — but we need to transition to passenger collection
                # If passenger info is already in args, validate and show confirmation
                passengers = tool_args.get("passengers", [])
                if passengers and all(_validate_passenger(p) == [] for p in passengers):
                    # All info present — show confirmation
                    draft = {
                        "selected_route": tool_args,
                        "passengers": passengers,
                        "contact": tool_args.get("contact", {}),
                        "step": "awaiting_confirmation",
                        "error_message": "",
                    }
                    await sessions.save_booking_draft(session_id, draft)
                    await sessions.update_step(session_id, "awaiting_confirmation")
                    msg = _build_confirmation_text(draft)
                    await sessions.add_message(session_id, "assistant", msg)
                    return ChatResponse(
                        type="text",
                        content=msg,
                        session_id=session_id,
                        suggestions=_get_suggestions(agent, "awaiting_confirmation"),
                        step="awaiting_confirmation",
                    )
                else:
                    # Need to collect passenger info
                    draft = {
                        "selected_route": tool_args,
                        "passengers": passengers or [],
                        "contact": tool_args.get("contact", {}),
                        "step": "collecting_passengers",
                        "error_message": "",
                    }
                    await sessions.save_booking_draft(session_id, draft)
                    await sessions.update_step(session_id, "collecting_passengers")
                    msg = _build_passenger_prompt(tool_args)
                    await sessions.add_message(session_id, "assistant", msg)
                    return ChatResponse(
                        type="text",
                        content=msg,
                        session_id=session_id,
                        suggestions=_get_suggestions(agent, "collecting_passengers"),
                        step="collecting_passengers",
                    )

            # Unknown tool
            msg = f"Tôi chưa hỗ trợ chức năng '{tool_name}' này. Bạn có thể hỏi tìm vé hoặc chính sách hãng nhé."
            await sessions.add_message(session_id, "assistant", msg)
            return ChatResponse(
                type="text",
                content=msg,
                session_id=session_id,
                suggestions=_get_suggestions(agent, step),
                step=step,
            )

        # Text response from LLM
        if llm_response.type == "error":
            await sessions.add_message(session_id, "assistant", llm_response.content)
            return ChatResponse(
                type="error",
                content=str(llm_response.content),
                session_id=session_id,
                suggestions=_get_suggestions(agent, step),
                step=step,
            )

        content = str(llm_response.content)
        await sessions.add_message(session_id, "assistant", content)
        return ChatResponse(
            type="text",
            content=content,
            session_id=session_id,
            suggestions=_get_suggestions(agent, step),
            step=step,
        )

    except Exception as exc:
        tb = tb_mod.format_exc()
        logger.error("Chat error: %s\n%s", exc, tb)
        try:
            await sessions.add_message(
                request.session_id or "",
                "assistant",
                "Xin lỗi, hệ thống đang gặp lỗi. Vui lòng thử lại.",
            )
        except Exception:
            pass
        return ChatResponse(
            type="error",
            content="Xin lỗi, hệ thống đang gặp lỗi. Vui lòng thử lại.",
            session_id=request.session_id or "",
            suggestions=[],
            step="idle",
        )


@router.get("/chat/history/{session_id}")
async def get_history(session_id: str):
    """Get chat history for a session."""
    sessions = get_session_service()
    messages = await sessions.get_messages(session_id, limit=50)
    return HistoryResponse(session_id=session_id, messages=messages)


@router.get("/agents")
async def list_agents():
    """List available agents with metadata."""
    return {
        "agents": [
            {
                "id": k,
                "name": v["name"],
                "icon": v["icon"],
                "description": v["suggestions"][0] if v["suggestions"] else "",
                "gradient": {
                    "ticketing": "from-blue-600 to-blue-800",
                    "sim": "from-emerald-600 to-emerald-800",
                    "visa": "from-violet-600 to-violet-800",
                }.get(k, "from-gray-600 to-gray-800"),
            }
            for k, v in AGENT_META.items()
        ]
    }


# ─── State Helpers ───────────────────────────────────────────────────────────

def _detect_flight_selection(message: str, search_data: dict[str, Any]) -> dict[str, Any] | None:
    """
    Detect if user is selecting a flight by number or airline+flight code.
    Returns the selected flight data dict, or None.
    """
    msg = message.strip().lower()

    # Check for cancellation keywords
    if any(kw in msg for kw in ["hủy", "cancel", "thôi", "không", "khác", "tìm lại"]):
        return None

    # Try to extract a number (flight index)
    import re
    num_match = re.search(r'\b(\d+)\b', msg)
    if num_match:
        idx = int(num_match.group(1)) - 1  # 0-indexed
        routes = search_data.get("data", {}).get("ListRoute", [])
        if routes:
            flights = routes[0].get("ListFlight", [])
            if 0 <= idx < len(flights):
                flight = flights[idx]
                items = flight.get("ListItem", []) or flight.get("ListAirItem", []) or []
                if items:
                    item = items[0]
                    return {
                        "session": flight.get("Session", "") or item.get("Session", ""),
                        "airline": flight.get("Airline", ""),
                        "flightNumber": flight.get("FlightNumber", "") or flight.get("FlightCode", ""),
                        "startPoint": routes[0].get("StartPoint", ""),
                        "endPoint": routes[0].get("EndPoint", ""),
                        "departDate": routes[0].get("DepartDate", ""),
                        "departTime": flight.get("StartTime", ""),
                        "arriveTime": flight.get("EndTime", ""),
                        "fareClass": item.get("FareClass", ""),
                        "price": float(item.get("TotalPrice", 0) or item.get("Price", 0)),
                        "currency": item.get("Currency", "VND"),
                        "leg": 0,
                        "ListBaggage": flight.get("ListBaggage", []),
                        "ListAirportFee": flight.get("ListAirportFee", []),
                    }

    # Try to match airline+flight number pattern (VN230, VJ151, etc.)
    flight_match = re.search(r'\b([A-Za-z]{2,3})\s*(\d{2,4})\b', msg)
    if flight_match:
        airline = flight_match.group(1).upper()
        flight_num = flight_match.group(2)
        routes = search_data.get("data", {}).get("ListRoute", [])
        if routes:
            flights = routes[0].get("ListFlight", [])
            for flight in flights:
                code = (flight.get("FlightNumber", "") or flight.get("FlightCode", "")).strip()
                fl_airline = flight.get("Airline", "").strip()
                if fl_airline == airline and code == flight_num:
                    items = flight.get("ListItem", []) or flight.get("ListAirItem", []) or []
                    if items:
                        item = items[0]
                        return {
                            "session": flight.get("Session", "") or item.get("Session", ""),
                            "airline": airline,
                            "flightNumber": flight_num,
                            "startPoint": routes[0].get("StartPoint", ""),
                            "endPoint": routes[0].get("EndPoint", ""),
                            "departDate": routes[0].get("DepartDate", ""),
                            "departTime": flight.get("StartTime", ""),
                            "arriveTime": flight.get("EndTime", ""),
                            "fareClass": item.get("FareClass", ""),
                            "price": float(item.get("TotalPrice", 0) or item.get("Price", 0)),
                            "currency": item.get("Currency", "VND"),
                            "leg": 0,
                            "ListBaggage": flight.get("ListBaggage", []),
                            "ListAirportFee": flight.get("ListAirportFee", []),
                        }

    return None


def _is_confirmation(message: str) -> bool:
    """Detect if user is confirming the booking."""
    msg = message.strip().lower()
    confirm_words = [
        "xác nhận", "đồng ý", "đặt", "ok", "oki", "okay",
        "yes", "yeah", "yep", "chuẩn", "đúng r", "đúng rồi",
        "làm", "tiến hành", "book", "đi",
    ]
    return any(kw in msg for kw in confirm_words)


def _is_cancellation(message: str) -> bool:
    """Detect if user wants to cancel the booking process."""
    msg = message.strip().lower()
    cancel_words = ["hủy", "cancel", "thôi", "không đặt", "bỏ qua", "quay lại", "tìm lại"]
    return any(kw in msg for kw in cancel_words)


def _build_passenger_prompt(flight: dict[str, Any]) -> str:
    """Generate prompt asking for passenger information."""
    route = f"{flight.get('startPoint', '???')} → {flight.get('endPoint', '???')}"
    flight_str = f"{flight.get('airline', '')}{flight.get('flightNumber', '')}"
    date_str = flight.get("departDate", "")
    if len(date_str) == 8:
        date_str = f"{date_str[:2]}/{date_str[2:4]}/{date_str[4:]}"
    price = flight.get("price", 0)
    price_str = f"{price:,.0f}₫" if flight.get("currency", "VND") == "VND" else f"{price:,.0f}"

    return (
        f"✈️ **{route}** | {flight_str} | {date_str} | {price_str}/khách\n\n"
        "Vui lòng cung cấp thông tin hành khách:\n\n"
        "**Mỗi hành khách cần:**\n"
        "1. Họ và tên đầy đủ (VD: Nguyễn Văn A)\n"
        "2. Giới tính (Nam/Nữ)\n"
        "3. Ngày sinh (DD/MM/YYYY)\n"
        "4. Số hộ chiếu (nếu có)\n\n"
        "Bạn có thể gửi theo format:\n"
        "`Nguyễn Văn A, Nam, 15/08/1990, AB123456`\n\n"
        "Hoặc đơn giản là gửi từng thông tin một, tôi sẽ hỏi dần 👇"
    )


def _build_confirmation_text(draft: dict[str, Any]) -> str:
    """Build booking confirmation summary."""
    route = draft.get("selected_route", {})
    passengers = draft.get("passengers", [])
    contact = draft.get("contact", {})

    route_str = f"{route.get('startPoint', '???')} → {route.get('endPoint', '???')}"
    flight_str = f"{route.get('airline', '')}{route.get('flightNumber', '')}"
    date_str = route.get("departDate", "")
    if len(date_str) == 8:
        date_str = f"{date_str[:2]}/{date_str[2:4]}/{date_str[4:]}"

    price = route.get("price", 0)
    price_str = f"{price:,.0f}₫" if route.get("currency", "VND") == "VND" else f"{price:,.0f}"
    total = price * len(passengers)

    lines = [
        "📋 **XÁC NHẬN ĐẶT VÉ**",
        "",
        f"✈️ {route_str}",
        f"   Chuyến bay: {flight_str}",
        f"   Ngày: {date_str}",
        f"   Giờ: {route.get('departTime', '???')} → {route.get('arriveTime', '???')}",
        f"   Giá: {price_str}/khách",
        "",
        f"**Hành khách ({len(passengers)} người):**",
    ]

    for i, p in enumerate(passengers, 1):
        name = f"{p.get('title', '')} {p.get('lastName', '')} {p.get('firstName', '')}".strip()
        gender = "Nam" if p.get("gender", "").lower() == "male" else "Nữ" if p.get("gender", "").lower() == "female" else p.get("gender", "")
        dob = str(p.get("birthDate", ""))
        if len(dob) == 8:
            dob = f"{dob[:2]}/{dob[2:4]}/{dob[4:]}"
        lines.append(f"   {i}. {name} | {gender} | {dob}")

    if contact.get("phone"):
        lines.append(f"\n📞 Liên hệ: {contact.get('fullName', '')} - {contact.get('phone', '')}")

    lines.append(f"\n💰 **Tổng tiền: {total:,.0f}₫**")
    lines.append("\nGõ **OK** hoặc **Xác nhận** để đặt vé, hoặc **Hủy** để hủy 👇")

    return "\n".join(lines)


async def _handle_passenger_collection(session_id: str, message: str) -> dict[str, Any]:
    """
    Process passenger info message.
    Returns:
      - type="need_more_info": still collecting, ask for more
      - type="ready_to_confirm": all info gathered, show confirmation
      - type="cancelled": user cancelled booking process
    """
    sessions = get_session_service()
    draft = await sessions.get_booking_draft(session_id)

    if _is_cancellation(message):
        return {"type": "cancelled", "content": "Đã hủy quy trình đặt vé. Bạn cần tìm chuyến bay khác không? 👇"}

    passengers = draft.get("passengers", [])
    selected_route = draft.get("selected_route", {})

    # Try to parse passenger info from the message
    import re

    # Check if user provided structured passenger info
    # Format: "Nguyễn Văn A, Nam, 15/08/1990, AB123456" or similar

    # Try multiple passenger format
    lines = message.strip().split("\n")
    new_passengers = []

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # Try format: "Name, Gender, DOB, Passport" (comma separated)
        parts = [p.strip() for p in line.split(",")]
        if len(parts) >= 2:
            # Parse name (first part)
            full_name = parts[0].strip()
            # Split into last/first (Vietnamese convention: last is first in list)
            name_parts = full_name.split()
            last_name = name_parts[0] if name_parts else ""
            first_name = " ".join(name_parts[1:]) if len(name_parts) > 1 else full_name

            gender_raw = parts[1].strip().lower()
            gender = "Male" if gender_raw in ("nam", "male", "m") else "Female"

            # Parse DOB
            dob = ""
            if len(parts) >= 3:
                dob_raw = parts[2].strip()
                # Try various date formats
                date_match = re.match(r'(\d{1,2})[/\-](\d{1,2})[/\-](\d{4})', dob_raw)
                if date_match:
                    d, m, y = date_match.groups()
                    dob = f"{d.zfill(2)}{m.zfill(2)}{y}"
                elif re.match(r'\d{8}', dob_raw):
                    dob = dob_raw

            passport = parts[3].strip() if len(parts) >= 4 else ""

            title = "Mr" if gender == "Male" else "Ms"
            pas_type = "adult"

            new_passengers.append({
                "type": pas_type,
                "title": title,
                "lastName": last_name,
                "firstName": first_name,
                "gender": gender,
                "birthDate": dob,
                "passport": passport,
                "passportExpDate": "",
                "nationality": "VN",
            })

    if new_passengers:
        # Replace passengers with parsed data
        draft["passengers"] = new_passengers
        await sessions.save_booking_draft(session_id, draft)

        # Validate
        errors = []
        for p in new_passengers:
            errors.extend(_validate_passenger(p))

        if errors:
            return {
                "type": "need_more_info",
                "content": f"Có một số thông tin cần bổ sung:\n" + "\n".join(f"- {e}" for e in errors) + "\n\nVui lòng gửi bổ sung nhé 👇",
            }

        # All good — show confirmation
        return {"type": "ready_to_confirm", "content": _build_confirmation_text(draft)}

    # No structured data found — LLM can handle this
    # Send back to LLM for natural language processing
    return {"type": "need_more_info", "content": "Tôi chưa nhận được thông tin rõ ràng. Bạn vui lòng cung cấp: Họ tên, Giới tính, Ngày sinh (VD: Nguyễn Văn A, Nam, 15/08/1990) 👇"}


# ─── Tool Executors ──────────────────────────────────────────────────────────

async def _execute_search(args: dict[str, Any]) -> dict[str, Any]:
    """Execute flight search through AGT API."""
    try:
        client = get_abtrip_client()
        routes = args.get("routes", [])
        adt = args.get("adt", 1)
        chd = args.get("chd", 0)
        inf = args.get("inf", 0)
        system = args.get("system", "1")

        if not routes:
            return {"success": False, "error": "Thiếu thông tin hành trình"}

        result = await client.search_flight(
            system=system,
            adt=adt,
            chd=chd,
            inf=inf,
            routes=routes,
        )

        if result.get("Success") and result.get("ListRoute"):
            return {"success": True, "data": result}
        else:
            error_msg = result.get("Message", "Không có chuyến bay phù hợp")
            return {"success": False, "error": error_msg}

    except Exception as e:
        logger.exception("Search flight failed: %s", e)
        return {"success": False, "error": "Lỗi kết nối hệ thống. Vui lòng thử lại."}


async def _execute_booking(draft: dict[str, Any]) -> dict[str, Any]:
    """Execute BookFlight through AGT API."""
    try:
        client = get_abtrip_client()
        route = draft.get("selected_route", {})
        passengers = draft.get("passengers", [])
        contact = draft.get("contact", {})

        if not route or not passengers:
            return {"type": "error", "content": "Thiếu thông tin đặt vé hoặc hành khách."}

        # Build AGT booking request
        agt_passengers = []
        for p in passengers:
            # AGT expects FullName = LastName + " " + FirstName
            full_name = f"{p.get('lastName', '')} {p.get('firstName', '')}".strip()
            ptype = 0 if p.get("type", "adult") == "adult" else (1 if p.get("type") == "child" else 2)
            agt_passengers.append({
                "FullName": full_name,
                "FirstName": p.get("firstName", ""),
                "LastName": p.get("lastName", ""),
                "Birthday": p.get("birthDate", ""),
                "Gender": p.get("gender", "Male"),
                "PassengerType": ptype,
                "Passport": p.get("passport", ""),
                "PassportExpDate": p.get("passportExpDate", ""),
                "Nationality": p.get("nationality", "VN"),
            })

        # Build air_options list from route data — each route is one air option
        air_options = [
            {
                "Session": route.get("session", ""),
                "Airline": route.get("airline", ""),
                "FlightNumber": route.get("flightNumber", ""),
                "StartPoint": route.get("startPoint", ""),
                "EndPoint": route.get("endPoint", ""),
                "DepartDate": route.get("departDate", ""),
                "DepartTime": route.get("departTime", ""),
                "ArriveTime": route.get("arriveTime", ""),
                "FareClass": route.get("fareClass", ""),
                "Price": route.get("price", 0),
                "Currency": route.get("currency", "VND"),
            }
        ]

        # Determine system from route or default to "1" (domestic)
        system = route.get("system", "1")

        # Build guest contact from draft contact info
        guest_contact = {
            "FullName": contact.get("fullName", ""),
            "Phone": contact.get("phone", ""),
            "Email": contact.get("email", ""),
            "Address": contact.get("address", ""),
        }

        booking_result = await client.book_flight(
            forced=False,
            system=system,
            guest_contact=guest_contact,
            agent_contact=None,
            passengers=agt_passengers,
            air_options=air_options,
            option="",
            payment=None,
        )

        if booking_result.get("Success") or booking_result.get("BookingCode"):
            booking_code = booking_result.get("BookingCode", "") or booking_result.get("OrderCode", "")
            return {
                "type": "booking_result",
                "content": (
                    f"✅ **ĐẶT VÉ THÀNH CÔNG!**\n\n"
                    f"Mã đặt chỗ: **{booking_code}**\n"
                    f"Vui lòng giữ mã này để tra cứu sau.\n\n"
                    f"Tiếp theo tôi có thể:\n"
                    f"> - Tra cứu trạng thái vé\n"
                    f"> - Đặt thêm chuyến khác\n"
                    f"> - Gọi hỗ trợ"
                ),
                "booking_code": booking_code,
            }
        else:
            error_msg = booking_result.get("Message", "Đặt vé thất bại, vui lòng thử lại.")
            return {
                "type": "error",
                "content": f"❌ **ĐẶT VÉ THẤT BẠI**\n\n{error_msg}\n\nVui lòng thử lại hoặc gọi hỗ trợ.",
            }

    except Exception as e:
        logger.exception("Booking failed: %s", e)
        return {
            "type": "error",
            "content": "❌ Lỗi hệ thống khi đặt vé. Vui lòng thử lại sau.",
        }


# ─── SSE Streaming Endpoint ───────────────────────────────────────────────────


class StreamRequest(BaseModel):
    agent: str = Field("ticketing", description="ticketing | sim | visa")
    message: str = Field(..., min_length=1, max_length=2000)
    session_id: str | None = None


@router.post("/chat/stream")
async def chat_stream(request: StreamRequest):
    """SSE streaming endpoint for real-time token-by-token LLM response.

    Returns a Server-Sent Events stream where each event is either:
      - type: token — a text token from the LLM
      - type: tool_call — LLM wants to call a tool (includes tool_name + tool_args)
      - type: done — stream finished, includes full response
      - type: error — something went wrong
    """
    async def event_generator():
        try:
            agent = request.agent if request.agent in ("ticketing", "sim", "visa") else "ticketing"
            sessions = get_session_service()

            # Get or create session
            session_id = request.session_id or await sessions.create_session(agent)
            history = await sessions.get_messages(session_id, limit=20)

            # Get LLM response
            llm = get_llm()
            llm_response = await llm.chat(
                message=request.message,
                history=history,
            )

            await sessions.add_message(session_id, "user", request.message)

            # Handle tool calls
            if llm_response.type == "tool_call":
                tool_name = llm_response.tool_name
                tool_args = llm_response.tool_args

                # Send tool call event
                yield f"data: {json.dumps({'type': 'tool_call', 'tool_name': tool_name, 'tool_args': tool_args})}\n\n"

                if tool_name == TOOL_SEARCH_FLIGHT:
                    result = await _execute_search(tool_args)
                    if result.get("success"):
                        formatted = _format_flight_results(result, tool_args)
                        await sessions.save_search_results(session_id, result, formatted)
                        await sessions.add_message(session_id, "assistant", formatted)
                        # Extract structured flight data for frontend cards
                        routes = result.get("data", {}).get("ListRoute", []) or result.get("ListRoute", [])
                        flights_data = _parse_flights(routes[0].get("ListFlight", [])) if routes else []
                        yield f"data: {json.dumps({'type': 'done', 'content': formatted, 'data': flights_data, 'session_id': session_id, 'step': 'search_results'})}\n\n"
                    else:
                        error_msg = f"Xin lỗi, không tìm thấy chuyến bay: {result.get('error', 'Lỗi hệ thống')}"
                        await sessions.add_message(session_id, "assistant", error_msg)
                        yield f"data: {json.dumps({'type': 'done', 'content': error_msg, 'session_id': session_id, 'step': 'idle'})}\n\n"

                elif tool_name == TOOL_BOOK_FLIGHT:
                    passengers = tool_args.get("passengers", [])
                    if passengers and all(_validate_passenger(p) == [] for p in passengers):
                        draft = {
                            "selected_route": tool_args,
                            "passengers": passengers,
                            "contact": tool_args.get("contact", {}),
                            "step": "awaiting_confirmation",
                            "error_message": "",
                        }
                        await sessions.save_booking_draft(session_id, draft)
                        await sessions.update_step(session_id, "awaiting_confirmation")
                        msg = _build_confirmation_text(draft)
                        await sessions.add_message(session_id, "assistant", msg)
                        yield f"data: {json.dumps({'type': 'done', 'content': msg, 'session_id': session_id, 'step': 'awaiting_confirmation'})}\n\n"
                    else:
                        draft = {
                            "selected_route": tool_args,
                            "passengers": passengers or [],
                            "contact": tool_args.get("contact", {}),
                            "step": "collecting_passengers",
                            "error_message": "",
                        }
                        await sessions.save_booking_draft(session_id, draft)
                        await sessions.update_step(session_id, "collecting_passengers")
                        msg = _build_passenger_prompt(tool_args)
                        await sessions.add_message(session_id, "assistant", msg)
                        passenger_count = tool_args.get("adt", 1) + tool_args.get("chd", 0)
                        yield f"data: {json.dumps({'type': 'done', 'content': msg, 'data': {'passenger_count': passenger_count}, 'session_id': session_id, 'step': 'collecting_passengers'})}\n\n"

                else:
                    yield f"data: {json.dumps({'type': 'done', 'content': f'Tool {tool_name} chưa hỗ trợ', 'session_id': session_id})}\n\n"

            elif llm_response.type == "text":
                content = str(llm_response.content)
                await sessions.add_message(session_id, "assistant", content)
                yield f"data: {json.dumps({'type': 'done', 'content': content, 'session_id': session_id, 'step': 'idle'})}\n\n"

            elif llm_response.type == "error":
                yield f"data: {json.dumps({'type': 'error', 'content': str(llm_response.content), 'session_id': session_id})}\n\n"

        except Exception as exc:
            tb_mod.print_exc()
            yield f"data: {json.dumps({'type': 'error', 'content': 'Lỗi hệ thống, vui lòng thử lại.'})}\n\n"
        finally:
            yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
