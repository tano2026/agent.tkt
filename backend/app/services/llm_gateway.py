"""
LLM Gateway — Gemini 2.5 Flash + OpenAI-compatible fallback.

Supports:
1. Google Gemini API (direct)
2. OpenAI-compatible endpoints (9Router, OmniRoute)
3. Automatic fallback between providers
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, AsyncGenerator

import httpx
from app.services.config import get_settings

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

2. **LUỒNG HỘI THOẠI:**
   Khi người dùng yêu cầu tìm chuyến bay → bạn phải TRẢ VỀ JSON:
   ```json
   {{"tool": "search_flight", "args": {{
       "system": "1",
       "adt": 1, "chd": 0, "inf": 0,
       "routes": [{{"StartPoint": "HAN", "EndPoint": "SGN", "DepartDate": "01072026"}}]
   }}}}
   ```
   Khi bạn trả lời trực tiếp → trả về TEXT (không JSON).

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
    """Gateway to LLM providers (Gemini > OpenAI-compatible)."""

    def __init__(self):
        settings = get_settings()
        self._gemini_api_key = settings.gemini_api_key or os.getenv("GEMINI_API_KEY", "")
        self._openai_base_url = os.getenv("OPENAI_BASE_URL", "http://localhost:20128/v1")
        self._openai_api_key = os.getenv("OPENAI_API_KEY", "sk-not-needed")
        self._preferred_provider = "gemini" if self._gemini_api_key else "openai"
        self._http_client = httpx.AsyncClient(timeout=60.0)

    async def chat(
        self,
        message: str,
        history: list[dict[str, str]] | None = None,
        system_override: str | None = None,
    ) -> dict[str, Any]:
        """
        Send a chat message and get response.

        Returns:
            {"type": "text", "content": "..."} for text responses
            {"type": "tool_call", "content": {"tool": "...", "args": {...}}} for tool calls
        """
        try:
            if self._preferred_provider == "gemini" and self._gemini_api_key:
                return await self._chat_gemini(message, history, system_override)
            return await self._chat_openai(message, history, system_override)
        except Exception as e:
            logger.error("LLM chat failed: %s", e)
            # Try fallback
            try:
                if self._preferred_provider == "gemini":
                    return await self._chat_openai(message, history, system_override)
                return await self._chat_gemini(message, history, system_override)
            except Exception as e2:
                logger.error("LLM fallback also failed: %s", e2)
                return {
                    "type": "error",
                    "content": "Xin lỗi, hiện tại hệ thống AI đang gặp sự cố. Vui lòng thử lại sau ít phút."
                }

    async def _chat_gemini(
        self,
        message: str,
        history: list[dict[str, str]] | None = None,
        system_override: str | None = None,
    ) -> dict[str, Any]:
        """Call Google Gemini API."""
        from app.services.aviation_db import get_airport_dict_for_prompt, get_airline_dict_for_prompt

        system = system_override or SYSTEM_PROMPT.format(
            airport_info=get_airport_dict_for_prompt(),
            airline_info=get_airline_dict_for_prompt(),
        )

        # Build content array for Gemini
        contents = []

        if history:
            for msg in history[-10:]:  # Last 10 messages
                role = "model" if msg["role"] == "assistant" else "user"
                contents.append({
                    "role": role,
                    "parts": [{"text": msg["content"]}]
                })

        contents.append({
            "role": "user",
            "parts": [{"text": message}]
        })

        payload = {
            "contents": contents,
            "systemInstruction": {"parts": [{"text": system}]},
            "generationConfig": {
                "temperature": 0.3,
                "maxOutputTokens": 2048,
                "topP": 0.95,
            }
        }

        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={self._gemini_api_key}"

        resp = await self._http_client.post(url, json=payload)
        resp.raise_for_status()
        data = resp.json()

        # Extract text
        text = ""
        candidates = data.get("candidates", [])
        if candidates:
            parts = candidates[0].get("content", {}).get("parts", [])
            for part in parts:
                text += part.get("text", "")

        return self._parse_response(text)

    async def _chat_openai(
        self,
        message: str,
        history: list[dict[str, str]] | None = None,
        system_override: str | None = None,
    ) -> dict[str, Any]:
        """Call OpenAI-compatible endpoint (9Router / OmniRoute)."""
        from app.services.aviation_db import get_airport_dict_for_prompt, get_airline_dict_for_prompt

        system = system_override or SYSTEM_PROMPT.format(
            airport_info=get_airport_dict_for_prompt(),
            airline_info=get_airline_dict_for_prompt(),
        )

        messages = [{"role": "system", "content": system}]

        if history:
            for msg in history[-10:]:
                messages.append({
                    "role": "assistant" if msg["role"] == "assistant" else "user",
                    "content": msg["content"]
                })

        messages.append({"role": "user", "content": message})

        payload = {
            "model": "gemini-2.5-flash",
            "messages": messages,
            "temperature": 0.3,
            "max_tokens": 2048,
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

        text = data.get("choices", [{}])[0].get("message", {}).get("content", "")

        return self._parse_response(text)

    def _parse_response(self, text: str) -> dict[str, Any]:
        """Parse LLM response — check for JSON tool call or plain text."""
        text = text.strip()
        import re

        # Try to find JSON code fence block
        json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', text, re.DOTALL)
        if json_match:
            try:
                parsed = json.loads(json_match.group(1))
                if isinstance(parsed, dict) and "tool" in parsed:
                    return {
                        "type": "tool_call",
                        "content": {
                            "tool": parsed["tool"],
                            "args": parsed.get("args", {})
                        }
                    }
            except json.JSONDecodeError:
                pass

        # Try plain JSON (without code fence)
        try:
            parsed = json.loads(text)
            if isinstance(parsed, dict) and "tool" in parsed:
                return {
                    "type": "tool_call",
                    "content": {
                        "tool": parsed["tool"],
                        "args": parsed.get("args", {})
                    }
                }
        except json.JSONDecodeError:
            pass

        # Try to find {"tool": anywhere in the text (Gemini embeds JSON in conversation)
        tool_json_match = re.search(r'(\{"tool":\s*"[^"]+"\s*,\s*"args":\s*\{.*?\}\s*\})', text, re.DOTALL)
        if tool_json_match:
            try:
                parsed = json.loads(tool_json_match.group(1))
                if isinstance(parsed, dict) and "tool" in parsed:
                    return {
                        "type": "tool_call",
                        "content": {
                            "tool": parsed["tool"],
                            "args": parsed.get("args", {})
                        }
                    }
            except json.JSONDecodeError:
                pass

        return {"type": "text", "content": text}

    async def close(self):
        await self._http_client.aclose()


# Singleton
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
