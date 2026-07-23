"""
Premium LLM Gateway — function calling + structured output + streaming.

Architecture:
1. Primary: OpenAI-compatible (9Router/OmniRoute) with tool/function calling
2. Fallback: Google Gemini with function calling API
3. Last resort: text-based JSON extraction (backward compat)

Each provider uses proper function calling so the LLM never hallucinates JSON.
"""

from __future__ import annotations

import json
import logging
import os
import re
from datetime import datetime
from typing import Any, AsyncGenerator

import httpx

from app.models.chat import (
    AVAILABLE_TOOLS,
    LLMResponse,
    TOOL_BOOK_FLIGHT,
    TOOL_SEARCH_FLIGHT,
)

logger = logging.getLogger(__name__)

# ─── SYSTEM PROMPT ────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """Bạn là chuyên gia tư vấn vé máy bay cho ABTrip — hệ thống đặt vé của người Việt.

## KIẾN THỨC SÂN BAY & HÃNG BAY
{airport_info}

{airline_info}

## LUẬT XỬ LÝ

1. **HIỂU TIẾNG VIỆT TỰ NHIÊN:**
   - Hôm nay là: {today}
   - "SG" = SGN (Sài Gòn), "HN" = HAN (Hà Nội), "DN" = DAD (Đà Nẵng)
   - "ngày mai" = ngày hôm sau, "ngày kia" = 2 ngày sau
   - "cuối tuần" = Thứ 7 hoặc Chủ nhật gần nhất
   - "tuần sau" = tuần tiếp theo
   - "sáng" = 6:00-11:59, "trưa" = 12:00-13:59, "chiều" = 14:00-17:59, "tối" = 18:00-23:59
   - "2 vé", "2 người", "2 khách" = 2 người lớn
   - "có em bé" = thêm 1 em bé (dưới 2 tuổi)

2. **LUỒNG XỬ LÝ:**
   - KHI CẦN TÌM VÉ → DÙNG TOOL `search_flight`
   - KHI KHÁCH CHỌN VÉ VÀ CUNG CẤP THÔNG TIN → DÙNG TOOL `book_flight`
   - KHI TRẢ LỜI CHÍNH SÁCH / GIẢI ĐÁP → TRẢ LỜI TEXT TRỰC TIẾP

3. **ĐỊNH DẠNG NGÀY:** luôn dùng DDMMYYYY (không dấu gạch).

4. **ĐỊNH DẠNG TRẢ LỜI (khi show kết quả):**
   ```
   ✈️ HAN → SGN | 01/07/2026
   
   VN230  07:30→09:45  1.250.000₫/khách  ⭐ Rẻ nhất
   VJ151  08:15→10:20  1.390.000₫/khách
   VN232  14:00→16:10  1.450.000₫/khách  🚀 Nhanh nhất
   VJ153  19:30→21:35  1.190.000₫/khách  💥 Bay đêm
   
   Tổng 2 người: 2.380.000₫ - 2.900.000₫
   
   Bạn muốn đặt chuyến nào? 👇
   ```
   - Luôn highlight option tốt nhất: Rẻ nhất, Nhanh nhất, Khuyến mãi
   - Giá luôn ghi đơn vị: /khách hoặc /người
   - Thời gian bay tính luôn (VD: 2h15)
   - Nếu có nhiều chuyến → gợi ý chọn lọc

5. **KHI NGƯỜI DÙNG HỎI CHÍNH SÁCH:**
   Tra cứu và trả lời trực tiếp, ví dụ:
   - "Bay VietJet có được mang bao nhiêu kg?" → Trả lời policy của VJ
   - "Đổi vé Vietnam Airlines mất bao nhiêu?" → Trả lời change_fee của VN
   - "Hủy vé Bamboo có mất tiền không?" → Trả lời cancel policy

6. **KHI KHÔNG HIỂU:** Hỏi lại lịch sự, gợi ý các lựa chọn.

7. **GIỌNG NÓI:** Thân thiện, chuyên nghiệp, tự nhiên như nhân viên phòng vé.
   - Xưng "tôi" gọi khách "bạn/anh/chị"
   - Nói ngắn gọn, đi thẳng vào vấn đề
   - Khi cần xác nhận: hỏi nhanh 1 câu, không dài dòng
"""


class LLMGateway:
    """Premium LLM Gateway with function calling support."""

    def __init__(self):
        self._gemini_api_key = os.getenv("GEMINI_API_KEY", "")
        self._openai_base_url = os.getenv("OPENAI_BASE_URL", "")
        self._openai_api_key = os.getenv("OPENAI_API_KEY", "")
        self._preferred_provider = self._detect_provider()
        self._http_client = httpx.AsyncClient(timeout=60.0)

    def _detect_provider(self) -> str:
        """Auto-detect best provider: Gemini > OpenAI-compatible."""
        if self._gemini_api_key:
            return "gemini"
        if self._openai_base_url:
            return "openai"
        return "gemini"  # Default: try Gemini (no key = free tier?)

    async def chat(
        self,
        message: str,
        history: list[dict[str, str]] | None = None,
        system_override: str | None = None,
    ) -> LLMResponse:
        """
        Send a chat message with function calling support and RAG context.

        Automatically enriches the system prompt with RAG-retrieved knowledge
        unless system_override is explicitly provided.

        Returns structured LLMResponse with:
        - type="text": just reply
        - type="tool_call": execute the named tool with args
        - type="error": something went wrong
        """
        try:
            # ── RAG enrichment ────────────────────────────────────────
            if system_override is None:
                rag_context = self._query_rag(message)
                if rag_context:
                    base_prompt = self._build_system_prompt()
                    system_override = f"{base_prompt}\n\n---\n{rag_context}"
            # ──────────────────────────────────────────────────────────

            if self._preferred_provider == "openai":
                return await self._chat_openai(message, history, system_override)
            return await self._chat_gemini(message, history, system_override)
        except Exception as e:
            logger.error("LLM primary failed: %s", e)
            # Try fallback
            try:
                if self._preferred_provider == "openai":
                    return await self._chat_gemini(message, history, system_override)
                return await self._chat_openai(message, history, system_override)
            except Exception as e2:
                logger.error("LLM fallback also failed: %s", e2)
                return LLMResponse(
                    type="error",
                    content="Xin lỗi, hiện tại hệ thống AI đang gặp sự cố. Vui lòng thử lại sau ít phút.",
                )

    # ── OpenAI-Compatible Provider (9Router / OmniRoute) ────────────────

    async def _chat_openai(
        self,
        message: str,
        history: list[dict[str, str]] | None = None,
        system_override: str | None = None,
    ) -> LLMResponse:
        """Call OpenAI-compatible endpoint with proper function calling."""
        from app.services.aviation_db import (
            get_airline_dict_for_prompt,
            get_airport_dict_for_prompt,
        )

        system = system_override or self._build_system_prompt()
        messages = [{"role": "system", "content": system}]

        if history:
            for msg in history[-15:]:  # Keep last 15 for context window
                role = "assistant" if msg.get("role") == "assistant" else "user"
                messages.append({"role": role, "content": msg.get("content", "")})

        messages.append({"role": "user", "content": message})

        tools = [t.model_dump(exclude_none=True) for t in AVAILABLE_TOOLS]

        payload = {
            "model": "oc/deepseek-v4-flash-free",  # DeepSeek via 9Router/OmniRoute
            "messages": messages,
            "tools": tools,
            "tool_choice": "auto",
            "temperature": 0.3,
            "max_tokens": 2048,
            "stream": False,  # Force JSON response (OmniRoute defaults to SSE)
        }

        resp = await self._http_client.post(
            f"{self._openai_base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {self._openai_api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
        )
        resp.raise_for_status()
        data = resp.json()

        return self._parse_openai_response(data)

    def _parse_openai_response(self, data: dict[str, Any]) -> LLMResponse:
        """Parse OpenAI-compatible response, handling function calls."""
        choice = data.get("choices", [{}])[0]
        message = choice.get("message", {})
        content = message.get("content", "")
        tool_calls = message.get("tool_calls")

        # Check for tool/function calls first
        if tool_calls:
            for tc in tool_calls:
                func = tc.get("function", {})
                name = func.get("name", "")
                try:
                    args = json.loads(func.get("arguments", "{}"))
                except json.JSONDecodeError:
                    args = {}

                if name in (TOOL_SEARCH_FLIGHT, TOOL_BOOK_FLIGHT):
                    logger.info("Tool call: %s with args=%s", name, args)
                    return LLMResponse(
                        type="tool_call",
                        content={"tool": name, "args": args},
                        tool_name=name,
                        tool_args=args,
                    )

        # If there's content text, return it
        if content and content.strip():
            return LLMResponse(type="text", content=content.strip())

        # Fallback: try to find embedded JSON tool call in content
        return self._parse_text_fallback(content or "")

    # ── Gemini Provider ────────────────────────────────────────────────

    async def _chat_gemini(
        self,
        message: str,
        history: list[dict[str, str]] | None = None,
        system_override: str | None = None,
    ) -> LLMResponse:
        """Call Google Gemini API with function calling."""
        if not self._gemini_api_key:
            raise ValueError("Gemini API key not configured")

        from app.services.aviation_db import (
            get_airline_dict_for_prompt,
            get_airport_dict_for_prompt,
        )

        system = system_override or self._build_system_prompt()

        # Build Gemini content array
        contents = []
        if history:
            for msg in history[-10:]:
                role = "model" if msg.get("role") == "assistant" else "user"
                contents.append({"role": role, "parts": [{"text": msg.get("content", "")}]})
        contents.append({"role": "user", "parts": [{"text": message}]})

        # Convert tools to Gemini function declarations
        function_declarations = []
        for tool in AVAILABLE_TOOLS:
            func = tool.function
            function_declarations.append({
                "name": func["name"],
                "description": func.get("description", ""),
                "parameters": func.get("parameters", {}),
            })

        payload = {
            "contents": contents,
            "systemInstruction": {"parts": [{"text": system}]},
            "tools": [{"functionDeclarations": function_declarations}],
            "generationConfig": {
                "temperature": 0.3,
                "maxOutputTokens": 2048,
                "topP": 0.95,
            },
        }

        url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"

        resp = await self._http_client.post(
            url,
            headers={
                "Authorization": f"Bearer {self._gemini_api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
        )
        resp.raise_for_status()
        data = resp.json()

        return self._parse_gemini_response(data)

    def _parse_gemini_response(self, data: dict[str, Any]) -> LLMResponse:
        """Parse Gemini response, handling function calls."""
        candidates = data.get("candidates", [])
        if not candidates:
            return LLMResponse(type="text", content="Xin lỗi, không nhận được phản hồi từ AI.")

        parts = candidates[0].get("content", {}).get("parts", [])

        text = ""
        for part in parts:
            if "text" in part:
                text += part["text"]
            elif "functionCall" in part:
                fc = part["functionCall"]
                name = fc.get("name", "")
                args = fc.get("args", {})
                logger.info("Gemini function call: %s with args=%s", name, args)
                if name in (TOOL_SEARCH_FLIGHT, TOOL_BOOK_FLIGHT):
                    return LLMResponse(
                        type="tool_call",
                        content={"tool": name, "args": args},
                        tool_name=name,
                        tool_args=args,
                    )

        if text.strip():
            # Check for embedded JSON in text
            return self._parse_text_fallback(text.strip())

        return LLMResponse(type="text", content=text.strip())

    # ── Text fallback parser (for models without function calling) ──────

    def _parse_text_fallback(self, text: str) -> LLMResponse:
        """
        Extract tool calls from plain text.
        Used as last resort when function calling API doesn't trigger.
        """
        text = text.strip()
        if not text:
            return LLMResponse(type="text", content="")

        # Try JSON code fence block
        json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', text, re.DOTALL)
        if json_match:
            try:
                parsed = json.loads(json_match.group(1))
                if isinstance(parsed, dict) and "tool" in parsed:
                    return LLMResponse(
                        type="tool_call",
                        content={"tool": parsed["tool"], "args": parsed.get("args", {})},
                        tool_name=parsed["tool"],
                        tool_args=parsed.get("args", {}),
                    )
            except json.JSONDecodeError:
                pass

        # Try bare JSON
        try:
            parsed = json.loads(text)
            if isinstance(parsed, dict) and "tool" in parsed:
                return LLMResponse(
                    type="tool_call",
                    content={"tool": parsed["tool"], "args": parsed.get("args", {})},
                    tool_name=parsed["tool"],
                    tool_args=parsed.get("args", {}),
                )
        except json.JSONDecodeError:
            pass

        # Try embedded {"tool": ...} pattern
        tool_match = re.search(
            r'(\{"tool":\s*"[^"]+"\s*,\s*"args":\s*\{.*?\}\s*\})',
            text, re.DOTALL
        )
        if tool_match:
            try:
                parsed = json.loads(tool_match.group(1))
                if isinstance(parsed, dict) and "tool" in parsed:
                    return LLMResponse(
                        type="tool_call",
                        content={"tool": parsed["tool"], "args": parsed.get("args", {})},
                        tool_name=parsed["tool"],
                        tool_args=parsed.get("args", {}),
                    )
            except json.JSONDecodeError:
                pass

        return LLMResponse(type="text", content=text)

    # ── Helpers ─────────────────────────────────────────────────────────

    def _build_system_prompt(self) -> str:
        """Build system prompt with live aviation data."""
        try:
            from app.services.aviation_db import (
                get_airline_dict_for_prompt,
                get_airport_dict_for_prompt,
            )
            today = datetime.now().strftime("%d/%m/%Y")
            return SYSTEM_PROMPT.format(
                airport_info=get_airport_dict_for_prompt(),
                airline_info=get_airline_dict_for_prompt(),
                today=today,
            )
        except Exception:
            # Fallback if aviation_db not available
            return SYSTEM_PROMPT.format(
                airport_info="",
                airline_info="",
                today=datetime.now().strftime("%d/%m/%Y"),
            )

    def _query_rag(self, message: str) -> str:
        """Query RAG service for relevant aviation knowledge."""
        try:
            from app.services.rag_service import get_rag_service

            svc = get_rag_service()
            if svc and hasattr(svc, "format_context"):
                return svc.format_context(message, top_k=4)
        except Exception:
            logger.debug("RAG query failed (non-critical):", exc_info=True)
        return ""

    async def close(self):
        await self._http_client.aclose()


# ═══════════════════════════════════════════════════════════════════════════
# Smart Agent specific functions: parse_intent, chat_response, extract_flight_info
# ═══════════════════════════════════════════════════════════════════════════

_SMART_SYSTEM_PROMPT = """Bạn là Smart Agent của ABTrip — trợ lý AI cho phòng vé máy bay.
Phân loại yêu cầu của khách hàng và hỗ trợ tư vấn.

Hôm nay là: {today}

CÁC DỊCH VỤ:
1. Vé máy bay (flight) — tìm vé, đặt vé nội địa & quốc tế
2. Fast Track (fasttrack) — dịch vụ ưu tiên sân bay Nội Bài
3. eSIM (esim) — eSIM du lịch toàn cầu
4. Visa (visa) — tư vấn visa, hộ chiếu
5. Khác (other) — các yêu cầu khác
"""


async def parse_intent(user_message: str) -> str:
    """
    Phân loại ý định người dùng: flight | fasttrack | esim | visa | other.

    Sử dụng LLM để phân tích câu hỏi tự nhiên và trả về intent tương ứng.
    """
    logger.info("parse_intent: %s", user_message[:80])
    try:
        gateway = get_llm()
        today = datetime.now().strftime("%d/%m/%Y")
        system = _SMART_SYSTEM_PROMPT.format(today=today)

        # Simple keyword-based pre-check for speed
        msg_lower = user_message.lower()
        keywords_visa = ["visa", "hộ chiếu", "passport", "xuất cảnh", "nhập cảnh", "schengen", "thị thực"]
        keywords_fasttrack = ["fast track", "fasttrack", "ưu tiên", "vip", "lounge", "phòng chờ", "nhanh"]
        keywords_esim = ["esim", "sim", "data", "4g", "5g", "internet", "wifi"]
        keywords_flight = ["vé", "bay", "máy bay", "chuyến", "giá vé", "đặt vé", "hành trình",
                          "sân bay", "khứ hồi", "một chiều", "tuyến bay"]

        score = {"visa": 0, "fasttrack": 0, "esim": 0, "flight": 0}

        for kw in keywords_visa:
            if kw in msg_lower:
                score["visa"] += 1
        for kw in keywords_fasttrack:
            if kw in msg_lower:
                score["fasttrack"] += 1
        for kw in keywords_esim:
            if kw in msg_lower:
                score["esim"] += 1
        for kw in keywords_flight:
            if kw in msg_lower:
                score["flight"] += 1

        # If keyword scoring is confident, return immediately
        max_score = max(score.values())
        if max_score >= 2:
            best = [k for k, v in score.items() if v == max_score]
            if len(best) == 1:
                logger.info("parse_intent: keyword match -> %s (score=%d)", best[0], max_score)
                return best[0]

        # Fallback: use LLM to classify
        prompt = f"""{system}

Phân loại câu sau thuộc dịch vụ nào (chỉ trả về MỘT từ: flight, fasttrack, esim, visa, other):

Câu: "{user_message}"

Phân loại:"""
        try:
            resp = await gateway._chat_openai(prompt, history=None, system_override=system)
            if resp.type == "text":
                text = resp.content.strip().lower()
                for intent in ["flight", "fasttrack", "esim", "visa", "other"]:
                    if intent in text:
                        return intent
        except Exception:
            pass

        # Ultimate fallback based on max score
        if max_score > 0:
            best = max(score, key=score.get)
            return best
        return "other"
    except Exception as e:
        logger.error("parse_intent error: %s", e)
        return "other"


async def chat_response(user_message: str, context: dict | None = None) -> str:
    """
    Trả lời tự nhiên dựa trên user_message và context (lịch sử, tenant info, etc.)
    Sử dụng LLM để sinh câu trả lời thân thiện, chuyên nghiệp.
    """
    logger.info("chat_response: %s", user_message[:80])
    try:
        gateway = get_llm()
        today = datetime.now().strftime("%d/%m/%Y")

        # Build context string
        ctx_str = ""
        if context:
            if context.get("tenant_name"):
                ctx_str += f"CTV: {context['tenant_name']}\n"
            if context.get("tier"):
                ctx_str += f"Gói: {context['tier']}\n"
            if context.get("intent"):
                ctx_str += f"Dịch vụ: {context['intent']}\n"
            if context.get("flight_info"):
                ctx_str += f"Thông tin chuyến bay: {context['flight_info']}\n"
            if context.get("history"):
                ctx_str += f"Lịch sử hội thoại:\n"
                for msg in context["history"][-6:]:
                    role = "Khách" if msg.get("role") == "user" else "Agent"
                    ctx_str += f"  {role}: {msg.get('content', '')[:200]}\n"

        system = f"""Bạn là trợ lý AI của ABTrip Smart Agent — phòng vé máy bay thông minh.

Hôm nay là: {today}

QUY TẮC:
1. Trả lời tự nhiên, thân thiện bằng tiếng Việt như nhân viên phòng vé chuyên nghiệp
2. Xưng "tôi" gọi khách "bạn/anh/chị"
3. Ngắn gọn, đi thẳng vào vấn đề
4. Nếu cần tra vé — hướng dẫn khách dùng ô tìm kiếm
5. Nếu hỏi về dịch vụ — tư vấn nhiệt tình
6. Nếu không biết — hẹn gọi lại hoặc chuyển tổng đài

Thông tin ngữ cảnh:
{ctx_str or "Chưa có thông tin cụ thể."}
"""

        resp = await gateway.chat(user_message, history=None, system_override=system)
        if resp.type == "text":
            return resp.content
        return "Rất tiếc, tôi chưa thể xử lý yêu cầu này ngay. Bạn vui lòng để lại thông tin, tôi sẽ chuyển cho bộ phận hỗ trợ."
    except Exception as e:
        logger.error("chat_response error: %s", e)
        return "Xin lỗi, hệ thống đang gặp sự cố. Vui lòng thử lại sau ít phút hoặc gọi hotline 1900 1234."


def extract_flight_info(text: str) -> dict:
    """
    Trích xuất thông tin chuyến bay từ text: ngày, tháng, tuyến bay.
    Trả về dict với các keys: from_airport, to_airport, depart_date, return_date (optional).

    Parse các dạng tiếng Việt tự nhiên:
    - "Hà Nội đi Sài Gòn ngày 25/07"
    - "vé SG HN tuần sau"
    - "từ Đà Nẵng ra Hà Nội ngày mai"
    - "HAN-SGN 01/08/2026"
    """
    logger.info("extract_flight_info: %s", text[:120])

    # Airport mapping
    airports = {
        "hà nội": "HAN", "ha noi": "HAN", "hanoi": "HAN", "hn": "HAN", "han": "HAN",
        "sài gòn": "SGN", "sg": "SGN", "saigon": "SGN", "sai gon": "SGN", "tphcm": "SGN", "hồ chí minh": "SGN", "ho chi minh": "SGN", "sgn": "SGN",
        "đà nẵng": "DAD", "da nang": "DAD", "danang": "DAD", "dn": "DAD", "dad": "DAD",
        "nha trang": "CXR", "nha trang": "CXR", "cxr": "CXR",
        "phú quốc": "PQC", "phu quoc": "PQC", "pqc": "PQC",
        "cần thơ": "VCA", "can tho": "VCA", "vca": "VCA",
        "hải phòng": "HPH", "hai phong": "HPH", "hph": "HPH",
        "vinh": "VII", "vii": "VII",
        "huế": "HUI", "hue": "HUI", "hui": "HUI",
        "đà lạt": "DLI", "da lat": "DLI", "dli": "DLI",
        "pleiku": "PXU", "pxu": "PXU",
        "côn đảo": "VCS", "con dao": "VCS", "vcs": "VCS",
        "thanh hóa": "THD", "thanh hoa": "THD", "thd": "THD",
        "quy nhơn": "UIH", "quy nhon": "UIH", "uih": "UIH",
        "tuy hòa": "TBB", "tuy hoa": "TBB", "tbb": "TBB",
    }

    result = {
        "from_airport": None,
        "to_airport": None,
        "depart_date": None,
        "return_date": None,
        "pax_count": 1,
    }

    msg_lower = text.lower()

    # Extract IATA codes directly (e.g. HAN-SGN, HAN→SGN, HAN SGN)
    iata_pattern = re.findall(r'\b([A-Z]{3})\s*[-→>]\s*([A-Z]{3})\b', text.upper())
    if iata_pattern:
        result["from_airport"] = iata_pattern[0][0]
        result["to_airport"] = iata_pattern[0][1]

    # If no IATA codes, try airport names
    if not result["from_airport"] or not result["to_airport"]:
        found_airports = []
        for name, code in sorted(airports.items(), key=lambda x: -len(x[0])):
            if name in msg_lower and code not in found_airports:
                found_airports.append(code)

        # Detect direction words
        direction_words = ["đi", "ra", "vào", "lên", "xuống", "về", "tới", "đến", "-", "→", ">", "qua"]
        # Try prepositions: "từ X đi/ra/vào Y", "X - Y", "X đi Y"
        from_pattern = re.search(r'(?:từ|ở)\s+([\w\s]+?)\s+(?:đi|ra|vào|lên|xuống|về|tới|đến|qua)\s+([\w\s]+)', msg_lower)
        if from_pattern:
            from_text = from_pattern.group(1).strip()
            to_text = from_pattern.group(2).strip()
            from_code = None
            to_code = None
            # Find airport codes from matched text
            for name, code in sorted(airports.items(), key=lambda x: -len(x[0])):
                if name in from_text:
                    from_code = code
                if name in to_text:
                    to_code = code
            if from_code and to_code:
                result["from_airport"] = from_code
                result["to_airport"] = to_code

        # Fallback to simple positional
        if not result["from_airport"] and len(found_airports) >= 2:
            # Find direction words to order
            for word in ["đi", "ra", "vào", "lên", "xuống", "về", "tới", "đến"]:
                if word in msg_lower:
                    parts = re.split(r'\b' + word + r'\b', msg_lower, maxsplit=1)
                    if len(parts) == 2:
                        # First airport is likely from, second is to
                        # Check which part each airport code belongs to
                        part_airports = [[], []]
                        for name, code in sorted(airports.items(), key=lambda x: -len(x[0])):
                            if name in parts[0] and code not in part_airports[0] + part_airports[1]:
                                part_airports[0].append(code)
                            if name in parts[1] and code not in part_airports[0] + part_airports[1]:
                                part_airports[1].append(code)
                        if part_airports[0] and part_airports[1]:
                            result["from_airport"] = part_airports[0][0]
                            result["to_airport"] = part_airports[1][0]
                            break

        # Last fallback: just use first 2 found
        if not result["from_airport"] and len(found_airports) >= 2:
            result["from_airport"] = found_airports[0]
            result["to_airport"] = found_airports[1]

    # Extract dates
    today = datetime.now()
    current_year = today.year

    # Pattern: DD/MM/YYYY or DD-MM-YYYY
    date_pattern = re.findall(r'(\d{1,2})[/\-](\d{1,2})(?:[/\-](\d{2,4}))?', text)
    if date_pattern:
        parsed_dates = []
        for d, m, y in date_pattern:
            day = int(d)
            month = int(m)
            year = int(y) if y else current_year
            if year < 100:
                year += 2000
            try:
                parsed_dates.append(datetime(year, month, day))
            except ValueError:
                continue

        if parsed_dates:
            result["depart_date"] = parsed_dates[0].strftime("%d/%m/%Y")
            if len(parsed_dates) >= 2:
                result["return_date"] = parsed_dates[1].strftime("%d/%m/%Y")

    # Pattern: "ngày X tháng Y"
    if not result["depart_date"]:
        ngay_match = re.search(r'ngày\s+(\d{1,2})\s*[/\-]?\s*(\d{1,2})?', msg_lower)
        if ngay_match:
            day = int(ngay_match.group(1))
            month = int(ngay_match.group(2)) if ngay_match.group(2) else today.month
            year = current_year
            try:
                dt = datetime(year, month, day)
                if dt < today:
                    dt = dt.replace(year=year + 1)
                result["depart_date"] = dt.strftime("%d/%m/%Y")
            except ValueError:
                pass

    # Relative dates
    if not result["depart_date"]:
        if "ngày mai" in msg_lower:
            dt = today + __import__("datetime", fromlist=["timedelta"]).timedelta(days=1)
            result["depart_date"] = dt.strftime("%d/%m/%Y")
        elif "ngày kia" in msg_lower:
            dt = today + __import__("datetime", fromlist=["timedelta"]).timedelta(days=2)
            result["depart_date"] = dt.strftime("%d/%m/%Y")
        elif "cuối tuần" in msg_lower:
            # Find next Saturday
            days_ahead = 5 - today.weekday()  # Saturday = 5
            if days_ahead <= 0:
                days_ahead += 7
            dt = today + __import__("datetime", fromlist=["timedelta"]).timedelta(days=days_ahead)
            result["depart_date"] = dt.strftime("%d/%m/%Y")

    # Extract passenger count
    pax_patterns = [
        (r'(\d+)\s*(?:vé|người|khách|pax)', 1),
        (r'(\d+)\s*(?:người lớn|adult|lon)', 1),
        (r'(\d+)\s*(?:trẻ em|child|tre em)', 1),
    ]
    total_pax = 0
    for pat, group in pax_patterns:
        m = re.search(pat, msg_lower)
        if m:
            total_pax += int(m.group(group))
    if total_pax > 0:
        result["pax_count"] = total_pax

    logger.info("extract_flight_info result: %s", result)
    return result


# ─── Singleton ──────────────────────────────────────────────────────────────

_gateway: LLMGateway | None = None


def get_llm() -> LLMGateway:
    global _gateway
    if _gateway is None:
        _gateway = LLMGateway()
    return _gateway


async def close_llm():
    global _gateway
    if _gateway:
        await _gateway.close()
        _gateway = None
