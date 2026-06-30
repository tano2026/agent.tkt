"""
Chat API — Natural language booking chat for all 3 agents.

POST /api/chat
  { agent: "ticketing"|"sim"|"visa", message: string, session_id?: string }
  → { type: "text"|"tool_call"|"error"|"booking_result", content, sessions }
"""

from __future__ import annotations

import json
import logging
import uuid
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services.abtrip_client import get_client as get_abtrip_client
from app.services.llm_gateway import get_llm

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["chat"])

# ─── In-memory session store ──────────────────────────────────────────────────
# TODO: Replace with Redis/DB in production
_sessions: dict[str, list[dict[str, str]]] = {}

# ─── Models ───────────────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    agent: str = Field("ticketing", description="ticketing | sim | visa")
    message: str = Field(..., min_length=1, max_length=2000)
    session_id: str | None = None

class ChatResponse(BaseModel):
    type: str = Field(..., description="text | tool_call | error | booking_result")
    content: str | dict[str, Any] = Field(...)
    session_id: str
    suggestions: list[str] = []


# ─── Agent-specific system prompt extensions ─────────────────────────────────

AGENT_SYSTEM_EXTENSIONS = {
    "ticketing": """
Bạn là chuyên gia vé máy bay. Nhiệm vụ:
- Tìm chuyến bay, tư vấn chính sách hãng
- Hỗ trợ đặt vé, check giá, so sánh
- Nếu cần tìm chuyến bay → trả JSON tool_call
- Nếu hỏi chính sách → trả lời ngay từ kiến thức của bạn
""",
    "sim": """
Bạn là chuyên gia tư vấn SIM du lịch & eSIM. Nhiệm vụ:
- Tư vấn gói SIM/eSIM cho từng quốc gia
- Giải thích dung lượng, thời hạn, giá cả
- Hỗ trợ đặt mua eSIM

LƯU Ý: Tính năng SIM đang phát triển. Bạn có thể tư vấn cơ bản dựa trên kiến thức của bạn.
""",
    "visa": """
Bạn là chuyên gia tư vấn Visa & Hộ chiếu. Nhiệm vụ:
- Tư vấn thủ tục xin visa các nước
- Liệt kê hồ sơ cần chuẩn bị
- Giải thích thời gian xử lý, lệ phí
- Nếu khách muốn làm thủ tục → chuyển thông tin sang nhân viên xử lý

LƯU Ý: Bạn CHỈ tư vấn thông tin. Khi khách muốn đặt dịch vụ, báo sẽ kết nối nhân viên.
""",
}

SUGGESTIONS = {
    "ticketing": [
        "Tìm vé HN SG ngày mai",
        "Chính sách hành lý VietJet",
        "Vé rẻ nhất Đà Nẵng cuối tuần",
        "Đổi vé máy bay có mất phí không?",
    ],
    "sim": [
        "eSIM Thái Lan bao nhiêu?",
        "SIM du lịch Nhật Bản",
        "eSIM có cần đổi sim không?",
    ],
    "visa": [
        "Visa du lịch Nhật cần gì?",
        "Thủ tục xin visa Hàn Quốc",
        "Hộ chiếu hết hạn làm lại bao lâu?",
    ],
}


# ─── Routes ───────────────────────────────────────────────────────────────────

@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """Handle chat message for any agent."""
    agent = request.agent if request.agent in ("ticketing", "sim", "visa") else "ticketing"
    session_id = request.session_id or str(uuid.uuid4())

    # Get or create session history
    if session_id not in _sessions:
        _sessions[session_id] = []
    history = _sessions[session_id]

    # Get LLM response
    llm = get_llm()
    system = AGENT_SYSTEM_EXTENSIONS.get(agent, "") + "\n" + llm.SYSTEM_PROMPT if hasattr(llm, 'SYSTEM_PROMPT') else AGENT_SYSTEM_EXTENSIONS.get(agent, "")

    # Import aviation data for system prompt (for ticketing)
    from app.services.aviation_db import get_airport_dict_for_prompt, get_airline_dict_for_prompt
    full_system = system.replace("{airport_info}", get_airport_dict_for_prompt()).replace("{airline_info}", get_airline_dict_for_prompt())

    response = await llm.chat(
        message=request.message,
        history=history,
        system_override=full_system,
    )

    # Handle tool calls
    if response["type"] == "tool_call":
        tool_name = response["content"]["tool"]
        tool_args = response["content"]["args"]

        if tool_name == "search_flight":
            result = await _execute_search_flight(tool_args)
            if result.get("success"):
                # Feed result back to LLM for formatting
                formatted = await _format_flight_results(result, tool_args)
                # Save assistant message
                history.append({"role": "user", "content": request.message})
                history.append({"role": "assistant", "content": formatted})

                return ChatResponse(
                    type="text",
                    content=formatted,
                    session_id=session_id,
                    suggestions=["Đặt chuyến này", "Xem chuyến khác", "So sánh giá"],
                )
            else:
                error_msg = f"Xin lỗi, không tìm thấy chuyến bay phù hợp: {result.get('error', 'Lỗi hệ thống')}"
                history.append({"role": "user", "content": request.message})
                history.append({"role": "assistant", "content": error_msg})
                return ChatResponse(
                    type="text",
                    content=error_msg,
                    session_id=session_id,
                    suggestions=["Thử lại với ngày khác", "Gọi hỗ trợ"],
                )

        # Unknown tool
        text_response = f"Tôi chưa hỗ trợ chức năng '{tool_name}' này. Bạn có thể hỏi tìm vé hoặc chính sách hãng nhé."
        history.append({"role": "user", "content": request.message})
        history.append({"role": "assistant", "content": text_response})
        return ChatResponse(type="text", content=text_response, session_id=session_id, suggestions=SUGGESTIONS[agent])

    # Text response
    if response["type"] == "error":
        return ChatResponse(type="error", content=response["content"], session_id=session_id, suggestions=SUGGESTIONS[agent])

    content = response["content"]
    history.append({"role": "user", "content": request.message})
    history.append({"role": "assistant", "content": content})

    return ChatResponse(
        type="text",
        content=content,
        session_id=session_id,
        suggestions=SUGGESTIONS[agent],
    )


@router.get("/api/chat/history/{session_id}")
async def get_history(session_id: str):
    """Get chat history for a session."""
    history = _sessions.get(session_id, [])
    return {"session_id": session_id, "messages": history[-50:]}


# ─── Tool executors ────────────────────────────────────────────────────────────

async def _execute_search_flight(args: dict[str, Any]) -> dict[str, Any]:
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


async def _format_flight_results(result: dict[str, Any], args: dict[str, Any]) -> str:
    """Format flight search results into a nice text response."""
    routes = result.get("data", {}).get("ListRoute", [])
    if not routes:
        return "Xin lỗi, không tìm thấy chuyến bay phù hợp với yêu cầu của bạn."

    route = routes[0]
    start_point = route.get("StartPoint", "???")
    end_point = route.get("EndPoint", "???")
    depart_date = route.get("DepartDate", "???")

    flights = route.get("ListFlight", [])
    if not flights:
        return f"Xin lỗi, không có chuyến bay nào từ {start_point} đến {end_point} ngày {depart_date}."

    lines = [f"✈️ {start_point} → {end_point} | {depart_date}\n"]

    # Parse and sort by price
    parsed = []
    for f in flights:
        items = f.get("ListItem", []) or f.get("ListAirItem", []) or []
        if items:
            item = items[0]
            price = float(item.get("TotalPrice", 0) or item.get("Price", 0))
            currency = item.get("Currency", "VND")
            airline = f.get("Airline", "??")
            flight_code = f.get("FlightNumber", "") or f.get("FlightCode", "")
            depart_time = f.get("StartTime", "??")
            arrive_time = f.get("EndTime", "??")
            duration = f.get("Duration", "") or f.get("FlightTime", "")
            parsed.append({
                "airline": airline,
                "flight": f"{airline}{flight_code}",
                "depart": depart_time,
                "arrive": arrive_time,
                "duration": duration,
                "price": price,
                "currency": currency,
            })

    if not parsed:
        return f"✈️ {start_point} → {end_point} | {depart_date}\nCó chuyến bay nhưng chưa có giá. Vui lòng thử lại."

    parsed.sort(key=lambda x: x["price"])

    # Find best options
    cheapest = min(parsed, key=lambda x: x["price"]) if parsed else None
    fastest = min(parsed, key=lambda x: x.get("duration", "999")) if parsed and any(p.get("duration") for p in parsed) else None

    for p in parsed:
        tags = []
        if p == cheapest:
            tags.append("⭐ Rẻ nhất")
        if p == fastest and p != cheapest:
            tags.append("🚀 Nhanh nhất")
        if float(p["depart"][:2]) >= 19:
            tags.append("💥 Bay đêm")

        tag_str = "  " + "  ".join(tags) if tags else ""
        price_str = f"{p['price']:,.0f}₫/khách" if p["currency"] == "VND" else f"{p['price']:,.0f}{p['currency']}/khách"
        duration_str = f" ({p['duration']})" if p.get("duration") else ""

        lines.append(f"{p['flight']}  {p['depart']}→{p['arrive']}{duration_str}  {price_str}{tag_str}")

    # Summary
    adt = args.get("adt", 1)
    total_min = cheapest["price"] * adt if cheapest else 0
    total_max = parsed[-1]["price"] * adt if parsed else 0

    if total_min == total_max:
        lines.append(f"\n💰 Tổng {adt} người: {total_min:,.0f}₫")
    else:
        lines.append(f"\n💰 Tổng {adt} người: {total_min:,.0f}₫ - {total_max:,.0f}₫")

    lines.append("\nBạn muốn đặt chuyến nào? 👇")

    return "\n".join(lines)


@router.get("/api/agents")
async def list_agents():
    """List available agents."""
    return {
        "agents": [
            {
                "id": "ticketing",
                "name": "Vé máy bay",
                "icon": "✈️",
                "description": "Tìm & đặt vé máy bay nội địa/quốc tế",
                "gradient": "from-blue-600 to-blue-800",
            },
            {
                "id": "sim",
                "name": "SIM du lịch",
                "icon": "📱",
                "description": "eSIM & SIM quốc tế giá tốt",
                "gradient": "from-emerald-600 to-emerald-800",
            },
            {
                "id": "visa",
                "name": "Visa & Hộ chiếu",
                "icon": "🛂",
                "description": "Tư vấn visa, hộ chiếu các nước",
                "gradient": "from-violet-600 to-violet-800",
            },
        ]
    }
