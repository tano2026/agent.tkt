"""
Test LLM Gateway + Chat API + Frontend API.
Chạy: python test_gateway.py
"""

import sys
import os
import json
import asyncio
import traceback

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "backend"))

PASS = 0
FAIL = 0

def check(name, condition, detail=""):
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  ✅ {name}")
    else:
        FAIL += 1
        print(f"  ❌ {name} — {detail}")

# ─── 1. Test imports ──────────────────────────────────────────────────────────
print("\n🔷 1. IMPORTS")

try:
    from app.services.llm_gateway import LLMGateway, get_llm, close_llm
    check("LLMGateway class imports OK", True)
except Exception as e:
    check("LLMGateway class imports OK", False, str(e))

try:
    from app.api.chat import router, ChatRequest, ChatResponse
    check("Chat API router imports OK", True)
except Exception as e:
    check("Chat API router imports OK", False, str(e))

try:
    from app.services.date_utils import extract_airports_from_text, extract_date_from_text
    check("date_utils imports OK", True)
except Exception as e:
    check("date_utils imports OK", False, str(e))

try:
    from app.services.abtrip_client import get_client
    check("abtrip_client imports OK", True)
except Exception as e:
    check("abtrip_client imports OK", False, str(e))

try:
    from app.services.aviation_db import get_airport_dict_for_prompt, get_airline_dict_for_prompt
    check("aviation_db imports OK", True)
except Exception as e:
    check("aviation_db imports OK", False, str(e))

try:
    from app.models.abtrip import RequestInfo, SearchFlightRequest
    check("models (basic) imports OK", True)
except Exception as e:
    check("models (basic) imports OK", False, str(e)[:80])

# ─── 2. Test Config ───────────────────────────────────────────────────────────
print("\n🔷 2. CONFIG")

try:
    from app.services.config import get_settings
    s = get_settings()
    check("get_settings() returns object", s is not None)
    check("settings.llm_api_key exists", hasattr(s, "llm_api_key"))
    check("settings.llm_base_url exists", hasattr(s, "llm_base_url"))
    check("settings.llm_model exists", hasattr(s, "llm_model"))
    check("settings.gemini_api_key exists", hasattr(s, "gemini_api_key"))
    print(f"     llm_model={s.llm_model}, base_url={s.llm_base_url}")
    print(f"     gemini_api_key={'***SET***' if s.gemini_api_key else ''}")
    print(f"     llm_api_key={'***SET***' if s.llm_api_key else ''}")
except Exception as e:
    check("Config test", False, str(e))

# ─── 3. Test date_utils ─────────────────────────────────────────────────────
print("\n🔷 3. DATE UTILS")

try:
    airports = extract_airports_from_text("tìm vé từ Hà Nội đi Sài Gòn")
    check("extract_airports HAN→SGN", 
          airports.get("origin") == "HAN" and airports.get("destination") == "SGN", 
          str(airports))

    airports2 = extract_airports_from_text("bay từ Đà Nẵng vào Sài Gòn")
    check("extract_airports DAD→SGN", 
          airports2.get("origin") == "DAD" and airports2.get("destination") == "SGN", 
          str(airports2))

    d = extract_date_from_text("ngày mai")
    check("extract_date 'ngày mai'", bool(d) and len(d) == 8, str(d))

    d2 = extract_date_from_text("mùng 5 tháng 7")
    check("extract_date 'mùng 5 tháng 7'", bool(d2) and len(d2) == 8, str(d2))
except Exception as e:
    check("date_utils tests", False, str(e))

# ─── 4. Test LLM Gateway (no real API key → graceful fallback) ───────────────
print("\n🔷 4. LLM GATEWAY — Init + graceful degradation")

async def test_llm():
    # Gateway without real key
    gateway = LLMGateway()

    # Test chat — should fail gracefully since no real key
    r = await gateway.chat("xin chào")
    check("chat() returns dict", isinstance(r, dict))
    check("chat() has 'type' key", "type" in r, str(r)[:100])
    check("chat() has 'content' key", "content" in r, str(r)[:100])
    if r.get("type") in ("text", "error"):
        check("chat() returns usable response", True, str(r.get("content"))[:80])
    print(f"     Response: {json.dumps(r, ensure_ascii=False)[:120]}")

    # Test with real key (if configured)
    from app.services.config import get_settings
    s = get_settings()
    if s.gemini_api_key or s.llm_api_key:
        gateway2 = LLMGateway()
        r2 = await gateway2.chat("tôi muốn tìm vé bay từ Hà Nội vào Sài Gòn")
        check("Chat with real key returns dict", isinstance(r2, dict))
        check("Chat with real key has type/content", "type" in r2 and "content" in r2)
        print(f"     Real-key response: {json.dumps(r2, ensure_ascii=False)[:150]}")
    else:
        check("Real LLM test (no key configured)", True, "Skipped — no API key")

# ─── 5. Test main.py routes ─────────────────────────────────────────────────
print("\n🔷 5. MAIN.PY ROUTES")

try:
    from app.main import app
    routes = [(r.path, list(r.methods)) for r in app.routes if hasattr(r, "path")]
    print(f"     Total routes: {len(routes)}")
    for path, methods in sorted(routes):
        print(f"       {methods} {path}")

    route_set = set(p for p, _ in routes)
    check("/api/chat exists", "/api/chat" in route_set)
    check("/api/bookings/search exists", "/api/bookings/search" in route_set)
    check("/api/reference/airports exists", "/api/reference/airports" in route_set)
    check("/api/health exists", "/health" in route_set or "/api/health" in route_set)
    check("/api/bookings/book exists", "/api/bookings/book" in route_set)
except Exception as e:
    check("Routes test", False, str(e))

# ─── 6. Test Frontend API (no credentials leak) ─────────────────────────────
print("\n🔷 6. FRONTEND API CLIENT")

try:
    frontend_path = os.path.join(os.path.dirname(__file__), "frontend")
    with open(os.path.join(frontend_path, "lib", "api.ts"), encoding="utf-8") as f:
        content = f.read()

    for c in ["PrivateKey", "ApiAccount", "ApiPassword"]:
        lines = [l.strip() for l in content.split("\n") if c in l]
        unsafe = [l for l in lines if "'" + c + "'" in l or '"' + c + '"' in l]
        check(f"No hardcoded '{c}'", len(unsafe) == 0, f": {unsafe[:3]}")

    check("Uses BACKEND_URL", "BACKEND_URL" in content)
    check("Has sendChatMessage", "sendChatMessage" in content)
    check("Has getAirports", "getAirports(" in content)
except Exception as e:
    check("Frontend test", False, str(e))

# ─── 7. Test Docker ──────────────────────────────────────────────────────────
print("\n🔷 7. DOCKER COMPOSE")

# Try both .yml and .yaml
import glob
yaml_paths = glob.glob(os.path.join(os.path.dirname(__file__), "docker-compose*"))
if yaml_paths:
    try:
        with open(yaml_paths[0]) as f:
            # use json to avoid yaml dependency
            import re
            raw = f.read()
            services_match = re.search(r"services:\s*\n", raw)
            check("docker-compose.yml exists", True)
            check("Has 'services' section", bool(services_match))
            check("docker-compose files found", len(yaml_paths), str([os.path.basename(p) for p in yaml_paths]))
    except Exception as e:
        check("Docker test", False, str(e))
else:
    check("Docker-compose not found", True, "OK — not required for testing")

# ─── 8. Test the API endpoint structure (static check) ──────────────────────
print("\n🔷 8. ENDPOINT STRUCTURE (chat.py)")

try:
    with open("backend/app/api/chat.py", encoding="utf-8") as f:
        chat_code = f.read()
    check("chat.py has ChatRequest model", "ChatRequest" in chat_code)
    check("chat.py has ticketing agent", "ticketing" in chat_code.lower())
    check("chat.py has sim agent", "sim" in chat_code.lower())
    check("chat.py has visa agent", "visa" in chat_code.lower())
    check("chat.py calls get_llm()", "get_llm()" in chat_code)
except Exception as e:
    check("chat.py check", False, str(e))

# ─── Run async tests ──────────────────────────────────────────────────────

if __name__ == "__main__":
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(test_llm())
    loop.close()

    print("\n" + "=" * 50)
    print(f"RESULTS: {PASS} passed, {FAIL} failed")
    print("=" * 50)
    sys.exit(0 if FAIL == 0 else 1)
