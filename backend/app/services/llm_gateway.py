"""
LLM Gateway — SmartAgent brain with dual-tier routing.

Provider chain (ordered):
  1. HHTech API (primary, dual-tier Sonnet/Opus)
  2. OmniRoute (fallback)
  3. Gemini (backup)
  4. Smart Mock (last resort)

Dual-tier system:
- OPUS tier: for complex/code/technical queries (claude-opus-4.8 via HHTech)
- SONNET tier: for regular chat (claude-sonnet-4 via HHTech)
- OmniRoute fallback: uses configured deepseek-chat model
"""

from __future__ import annotations

import json
import logging
import os
import re
from typing import Any

import httpx

logger = logging.getLogger(__name__)


# ── Helpers ────────────────────────────────────────────────────────────────────

_JSON_RE = re.compile(r"```(?:json)?\s*\n?(.*?)\n?```", re.DOTALL)


def _parse_json(raw: str) -> dict[str, Any] | None:
    """Extract JSON from LLM text reply (handles ```json … ``` too)."""
    text = raw.strip()
    if not text:
        return None
    # Try direct parse first
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # Try extracting from code blocks
    for block in _JSON_RE.findall(text):
        try:
            return json.loads(block.strip())
        except json.JSONDecodeError:
            continue
    # Try finding first {…} block
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end > start:
        try:
            return json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            pass
    return None


# ── System prompt ────────────────────────────────────────────────────────────

_SYSTEM_PROMPT = """Bạn là trợ lý đặt vé máy bay ABTrip. Nhiệm vụ của bạn là giúp khách hàng tìm kiếm thông tin và đặt vé.

QUAN TRỌNG: Đôi khi bạn sẽ nhận được [THÔNG TIN TRA CỨU] từ hệ thống. 
- Đây là kiến thức tra cứu từ cơ sở dữ liệu hàng không — hãy dùng nó để trả lời chính xác.
- Nếu câu hỏi của khách về chính sách (hành lý, đổi vé, hủy vé, giấy tờ...), hãy ưu tiên dùng thông tin từ [THÔNG TIN TRA CỨU].
- Nếu không có thông tin phù hợp trong [THÔNG TIN TRA CỨU], hãy trả lời dựa trên kiến thức chung.

QUY TẮC QUAN TRỌNG:
1. Luôn phải trả về JSON. Không được trả về text thuần.
2. JSON format: {"reply": "câu trả lời", "type": "text"}
3. Nếu người dùng muốn tìm chuyến bay → trả về {"type": "search_flight", "params": {"origin": "...", "destination": "...", "date": "YYYY-MM-DD", "adults": 1, "children": 0, "infants": 0}}
4. Nếu người dùng hỏi thông tin chung → trả về {"type": "reply", "reply": "câu trả lời"}
5. Mã sân bay: SGN (TP.HCM), HAN (Hà Nội), DAD (Đà Nẵng), CXR (Nha Trang), HUI (Huế), PQC (Phú Quốc), VII (Vinh), DIN (Điện Biên), VCS (Côn Đảo), TBB (Tuy Hòa), UIH (Quy Nhơn), CAH (Cà Mau), VKG (Rạch Giá), NYA (Nakasongola/đừng dùng)
6. Nếu thiếu thông tin → trả về {"type": "clarify", "reply": "câu hỏi", "missing": ["origin"]}"""


# ── Gateway class ─────────────────────────────────────────────────────────────

class LLMGateway:
    """SmartAgent's brain — LLM with provider failover."""

    def __init__(self) -> None:
        from app.services.config import get_settings

        _cfg = get_settings()

        # ── HHTech API (primary, dual-tier Sonnet/Opus) ───────────
        self._use_hhtech = bool(_cfg.hhtech_api_key)
        self._hhtech_key = _cfg.hhtech_api_key
        self._hhtech_base = _cfg.hhtech_base_url.rstrip("/")
        # Dual models: Sonnet (fast/cheap) and Opus (quality)
        self._sonnet_model = _cfg.hhtech_sonnet_model
        self._opus_model = _cfg.hhtech_opus_model

        # ── OmniRoute (fallback) ──────────────────────────────────
        self._use_omniroute = bool(_cfg.omniroute_api_key)
        self._omni_key = _cfg.omniroute_api_key
        self._omni_base = _cfg.omniroute_base_url.rstrip("/")
        self._omni_model = _cfg.omniroute_model

        # ── Gemini (backup) ───────────────────────────────────────
        gemini_key = os.environ.get("GEMINI_API_KEY", "")
        self._gemini_client = None
        self._gemini_models = ["gemini-2.5-flash"]
        if gemini_key:
            try:
                import google.genai as genai

                self._gemini_client = genai.Client(api_key=gemini_key)
                logger.info("Gemini client initialized")
            except Exception as e:
                logger.warning("Gemini init failed: %s", e)

        # ── HTTP client ───────────────────────────────────────────
        self._http = httpx.AsyncClient(timeout=30)

    # ── Public API ─────────────────────────────────────────────────────────

    async def chat(
        self,
        message: str,
        history: list[dict[str, str]] | None = None,
        agent: str = "ticketing",
        context: str | None = None,
    ) -> dict[str, Any] | None:
        """Send a chat message to the LLM with automatic tier routing + failover.

        Provider chain: HHTech → OmniRoute → Gemini → Smart Mock.
        """
        messages = self._build_messages(message, history, agent, context)

        # Determine which tier to use
        use_opus = self._should_use_opus(message)
        tier_name = "OPUS" if use_opus else "SONNET"
        logger.info("Routing to %s tier for message: %s...", tier_name, message[:50])

        # 1) Try HHTech (dual-tier)
        if self._use_hhtech:
            try:
                result = await self._call_hhtech_tiered(messages, use_opus)
                if result:
                    logger.info("HHTech %s success: type=%s", tier_name, result.get("type"))
                    return result
            except Exception as e:
                logger.error("HHTech %s error: %s", tier_name, e)
                # Fall through to OmniRoute

        # 2) Try OmniRoute
        if self._use_omniroute:
            logger.info("Trying OmniRoute: model=%s", self._omni_model)
            try:
                result = await self._call_omniroute(messages)
                if result:
                    logger.info("OmniRoute success: type=%s", result.get("type"))
                    return result
            except Exception as e:
                logger.error("OmniRoute error: %s", e)
                # Fall through to Gemini

        # 3) Try Gemini
        if self._gemini_client:
            for model_name in self._gemini_models:
                result = await self._call_gemini(model_name, messages)
                if result:
                    logger.info("Gemini %s success: type=%s", model_name, result.get("type"))
                    return result

        # 4) Last resort: Smart Mock (rule-based)
        logger.info("All providers failed, using Smart Mock")
        return self._smart_mock(message)

    # ── Tier Router ────────────────────────────────────────────────────────

    def _should_use_opus(self, message: str) -> bool:
        """Determine if this message needs Opus tier vs Sonnet.

        Opus is used for code, technical writing, complex analysis, and very long messages.
        Sonnet handles everything else (faster, cheaper).

        Returns True if Opus should be used, False for Sonnet (regular chat).
        """
        msg_lower = message.lower().strip()

        # Clear indicators for Opus tier (code, technical writing, complex analysis)
        opus_indicators = [
            # Code-related patterns
            "```",  # Code blocks
            "def ", "function ", "class ", "import ", "from ",  # Function/class definitions
            "const ", "let ", "var ", "=>",  # Variable declarations
            "{", "}", "[", "]", ";",  # Code syntax
            "if ", "else ", "for ", "while ", "try ", "except ",  # Control flow
            "return ", "yield ", "async ", "await ",  # Special keywords
            "# ", "// ", "/*", "*/",  # Comments

            # Technical writing indicators
            "api", "endpoint", "database", "sql", "query", "algorithm",
            "framework", "library", "package", "module", "dependency",
            "debug", "test", "unit test", "integration", "deploy",
            "version", "release", "patch", "bug", "fix", "issue",

            # Complex analysis/requests
            "phân tích", "tối ưu", "so sánh", "đánh giá", "kết luận",
            "giải thích", "hướng dẫn", "bài viết",
            "nghiên cứu", "tổng hợp", "tóm tắt", "biểu đồ", "bảng",

            # Vietnamese technical terms
            "mã nguồn", "lập trình", "phát triển", "kiểm tra lỗi",
            "cải thiện", "nâng cấp", "phiên bản", "tài liệu kỹ thuật",
        ]

        # Check for string-based Opus indicators
        for indicator in opus_indicators:
            if isinstance(indicator, str) and indicator in msg_lower:
                return True

        # Check for question patterns that might benefit from Opus
        # These often benefit from deeper reasoning even if not extremely long
        question_patterns = ["làm sao", "như thế nào", "tại sao", "vì sao"]
        if any(pattern in msg_lower for pattern in question_patterns):
            # Lower threshold for question patterns since they often indicate complex queries
            if len(message) > 20:  # Reduced from 50 to catch shorter but meaningful questions
                return True

        # Length-based heuristic (very long messages often need complex processing)
        if len(message) > 300:
            return True

        # Default to Sonnet for regular chat
        return False

    # ── HHTech (Dual-tier) ─────────────────────────────────────────────────

    async def _call_hhtech_tiered(
        self,
        messages: list[dict[str, str]],
        use_opus: bool,
    ) -> dict[str, Any] | None:
        """Call HHTech API with dual-tier model selection."""
        model = self._opus_model if use_opus else self._sonnet_model

        # Build HHTech-compatible payload
        payload = {
            "model": model,
            "messages": messages,
            "max_tokens": 2048,
            "temperature": 0.3,
        }

        try:
            resp = await self._http.post(
                f"{self._hhtech_base}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self._hhtech_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
            if resp.status_code != 200:
                logger.warning("HHTech %s HTTP %s: %s", model, resp.status_code, resp.text[:200])
                return None

            data = resp.json()
            content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            if not content:
                return None

            return _parse_json(content)
        except httpx.TimeoutException:
            logger.warning("HHTech %s timed out", model)
            return None

    # ── OmniRoute ──────────────────────────────────────────────────────────

    async def _call_omniroute(
        self,
        messages: list[dict[str, str]],
    ) -> dict[str, Any] | None:
        """Call OmniRoute (OpenRouter-compatible) API."""
        # Convert system message to user message for models that don't support system
        clean = []
        sys_text = ""
        for m in messages:
            if m["role"] == "system":
                sys_text += m["content"] + "\n"
            else:
                clean.append(m)
        if sys_text and clean:
            clean[0]["content"] = sys_text + "\n---\n" + clean[0]["content"]

        payload = {
            "model": self._omni_model,
            "messages": clean,
            "max_tokens": 1024,
            "temperature": 0.3,
        }

        try:
            resp = await self._http.post(
                f"{self._omni_base}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self._omni_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
            if resp.status_code != 200:
                logger.warning("OmniRoute HTTP %s: %s", resp.status_code, resp.text[:200])
                return None

            data = resp.json()
            content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            if not content:
                return None

            return _parse_json(content)
        except httpx.TimeoutException:
            logger.warning("OmniRoute timed out")
            return None

    # ── Gemini ───────────────────────────────────────────────────────────────

    async def _call_gemini(self, model_name: str, messages: list[dict[str, str]]) -> dict[str, Any] | None:
        """Call Gemini API. Returns None if the model is unavailable."""
        if not self._gemini_client:
            return None
        try:
            # Extract system prompt
            sys_msg = ""
            msgs = []
            for m in messages:
                if m["role"] == "system":
                    sys_msg += m["content"] + "\n"
                else:
                    msgs.append({"role": m["role"], "content": m["content"]})

            # Merge system into first user message (Gemini doesn't have native system prompt in all models)
            if sys_msg and msgs and msgs[0]["role"] == "user":
                msgs[0]["content"] = sys_msg + "\n---\n" + msgs[0]["content"]

            # Convert messages to Gemini format
            gemini_history = []
            for i, msg in enumerate(msgs):
                role = "user" if msg["role"] in ("user", "system") else "model"
                gemini_history.append({
                    "role": role,
                    "parts": [{"text": msg["content"]}],
                })

            resp = await self._gemini_client.aio.models.generate_content(
                model=model_name,
                contents=gemini_history[-1:],  # latest message
                config={
                    "max_output_tokens": 1024,
                    "temperature": 0.3,
                } if hasattr(self._gemini_client.aio.models, 'generate_content') else {},
            )
            text = resp.text if hasattr(resp, "text") else ""
            return _parse_json(text)
        except Exception as e:
            logger.debug("Gemini %s call failed: %s", model_name, e)
            return None

    # ── Smart Mock ───────────────────────────────────────────────────────────

    def _smart_mock(self, message: str) -> dict[str, Any]:
        """Rule-based fallback using intent parser."""
        from app.services.intent_parser import parse_flight_search

        params = parse_flight_search(message)
        if params and params.get("origin") and params.get("destination"):
            return {"type": "search_flight", "params": params}
        return {"type": "reply", "reply": "Xin lỗi, hiện tại hệ thống đang bảo trì. Vui lòng thử lại sau."}

    # ── Message Builder ──────────────────────────────────────────────────────

    def _build_messages(
        self,
        message: str,
        history: list[dict[str, str]] | None = None,
        agent: str = "ticketing",
        context: str | None = None,
    ) -> list[dict[str, str]]:
        """Build message list with system context, history, and current message.

        If context is provided (RAG results or last search results), it's added as a system-level
        reminder so the LLM can answer follow-up questions intelligently.
        """
        messages = [{"role": "system", "content": _SYSTEM_PROMPT}]

        if context:
            messages.append({
                "role": "system",
                "content": f"[THÔNG TIN PHIÊN LÀM VIỆC HIỆN TẠI]\n{context}",
            })

        if history:
            for msg in history[-10:]:  # keep last 10
                role = msg.get("role", "user")
                content = msg.get("content", "")
                if role in ("user", "assistant"):
                    messages.append({"role": role, "content": content})

        # Add current message if not already in history
        if not history or not history[-1].get("content", "").startswith(message[:10]):
            messages.append({"role": "user", "content": message})

        return messages


# ── Singleton ──────────────────────────────────────────────────────────────────

_instance: LLMGateway | None = None


def get_llm() -> LLMGateway:
    global _instance
    if _instance is None:
        _instance = LLMGateway()
    return _instance


async def close_llm() -> None:
    """Close the LLM gateway (no-op for now)."""
    pass
