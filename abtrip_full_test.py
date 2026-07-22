"""
ABTrip Chat Bot — Comprehensive Test Suite
Tests 23 scenarios across 5 categories.
Each test uses fresh UUID session to avoid contamination.
"""
import requests, json, uuid, sys

BASE = "http://localhost:8138/api/chat"
TOTAL = 0
PASS = 0
FAIL = 0

def test(category, name, message, expected_type, check_fn=None, session_id=None):
    global TOTAL, PASS, FAIL
    TOTAL += 1
    sid = session_id or str(uuid.uuid4())
    try:
        r = requests.post(BASE, json={"message": message, "session_id": sid}, timeout=30)
        d = r.json()
        actual_type = d.get("type", "?")
        ok = (r.status_code == 200) and (actual_type == expected_type)

        if check_fn:
            fn_ok = check_fn(d)
            ok = ok and fn_ok

        if ok:
            print(f"  ✅ [{category}] {name}")
            PASS += 1
        else:
            print(f"  ❌ [{category}] {name}")
            print(f"     Expected type={expected_type}, got {actual_type}")
            if r.status_code != 200:
                print(f"     HTTP {r.status_code}: {r.text[:150]}")
            reply = d.get("reply", "")[:120]
            print(f"     Reply: {reply}")
            FAIL += 1
        return d
    except Exception as e:
        print(f"  ❌ [{category}] {name} — ERROR: {e}")
        FAIL += 1
        return None

def has_vietnamese_names(d):
    """Check no English airport names leak through"""
    reply = d.get("reply", "")
    # Only flag if actual raw IATA codes appear as standalone words
    import re
    banned_patterns = [
        (r'\btan son nhat\b', "tan son nhat"),
        (r'\bnoi bai\b', "noi bai"),
        (r'\b(?:dng|dad|cxr|pqc|hph|uih|dli|vii|din|bmy|vcs)\b', "raw IATA code"),
    ]
    for pat, label in banned_patterns:
        if re.search(pat, reply.lower()):
            print(f"     ❌ Contains English name: '{label}'")
            return False
    # Check for Vietnamese names — at least one expected name if flight-related
    if "✈️" in reply or "vé" in reply or "TP." in reply or "Hà Nội" in reply:
        good = ["TP.HCM", "Hà Nội", "Đà Nẵng", "Nha Trang", "Phú Quốc",
                "Hải Phòng", "Đà Lạt", "Huế", "Cần Thơ", "Vinh", "Buôn Ma Thuột"]
        if not any(g in reply for g in good):
            print(f"     ⚠️ No Vietnamese airport name found")
            return False
    return True

def has_policy_content(d):
    reply = d.get("reply", "")
    keywords = ["hành lý", "xách tay", "ký gửi", "7kg", "20kg",
                "thủ tục", "giấy tờ", "hủy", "đổi", "quy định", "hoàn",
                "vé không", "non-refund", "phí"]
    matches = [kw for kw in keywords if kw in reply.lower()]
    if len(matches) >= 2:
        return True
    # For short replies (policy cancel/change), 1 specific keyword may be enough
    if len(matches) >= 1 and ("hủy" in matches or "đổi" in matches or "hoàn" in matches):
        return True
    print(f"     ❌ Not enough policy keywords (found {len(matches)}: {matches})")
    print(f"     Reply: {reply[:200]}")
    return False

def has_search_results(d):
    reply = d.get("reply", "")
    # Check for airline codes or prices
    has_airline = any(al in reply for al in ["VJ", "VN", "QH", "VU", "BL", "9G"])
    has_price = "₫" in reply or "VND" in reply
    has_time = ":" in reply  # departure times
    has_flight = has_airline and has_price
    if not has_flight:
        print(f"     ⚠️ Search results missing - airline={has_airline}, price={has_price}, time={has_time}")
        return False
    return True

# ══════════════════════════════════════════════════════════════
print("=" * 72)
print("  ABTRIP CHAT BOT — COMPREHENSIVE TEST SUITE")
print("  Server: " + BASE)
print("=" * 72)

# ── A. Slang & Dialect ───────────────────────────────────────
print("\n📌 A. SLANG & DIALECT PARSING")
test("A", "1. SG HN ngày mai 2 người", "SG HN ngày mai 2 người", "confirm", has_vietnamese_names)
test("A", "2. HN→SG ngày kia", "từ Hà Nội vào SG ngày kia", "confirm", has_vietnamese_names)
test("A", "3. sgn han 5/7 1 nguoi", "sgn han 5/7 1 nguoi", "confirm", has_vietnamese_names)
test("A", "4. sgn dng 20/7", "sgn dng 20/7", "confirm", has_vietnamese_names)
test("A", "5. có hàng SG-HN", "có hàng SG-HN không?", "clarify", has_vietnamese_names)
test("A", "6. báo giá HN→PQ", "báo giá HN đi Phú Quốc 2 người", "clarify", has_vietnamese_names)
test("A", "7. saigon đi dng", "saigon đi dng", "clarify", has_vietnamese_names)
test("A", "8. từ SG đi Nha Trang", "từ SG đi Nha Trang", "clarify", has_vietnamese_names)
test("A", "9. Vé SG đi Hải Phòng", "Vé SG đi Hải Phòng", "clarify", has_vietnamese_names)
test("A", "10. SG HN July 20 1 người", "SG HN July 20 1 người", "confirm", has_vietnamese_names)
test("A", "11. SGN DAD 20/7 bussiness 3 người", "SGN DAD 20/7 bussiness 3 người", "confirm", has_vietnamese_names)
test("A", "12. sgn han mai 2 nguoi", "sgn han mai 2 nguoi", "confirm", has_vietnamese_names)

# ── B. Policy Intents ─────────────────────────────────────────
print("\n📌 B. POLICY INTENTS")
test("B", "13. hành lý VNA", "hành lý VNA bao nhiêu kg", "text", has_policy_content)
test("B", "14. đổi vé Vietjet", "đổi vé Vietjet", "text", has_policy_content)
test("B", "15. hủy vé", "hủy vé", "text", has_policy_content, session_id=str(uuid.uuid4()))
test("B", "16. cần giấy tờ gì", "cần giấy tờ gì khi bay", "text", has_policy_content, session_id=str(uuid.uuid4()))
test("B", "17. chính sách hoàn vé", "chính sách hoàn vé", "text", has_policy_content)

# ── C. Greetings ──────────────────────────────────────────────
print("\n📌 C. GREETINGS & OTHER")
test("C", "18. xin chào", "xin chào", "text")
test("C", "19. chào bot", "chào bot", "text")
test("C", "20. cảm ơn", "cảm ơn", "text")

# ── D. Confirm Flow ───────────────────────────────────────────
print("\n📌 D. CONFIRM FLOW")
# Test 21: Full flow with same session
sid21 = str(uuid.uuid4())
test("D", "21a. SG HN ngày mai 2 người", "SG HN ngày mai 2 người", "confirm",
     check_fn=has_vietnamese_names, session_id=sid21)
test("D", "21b. Xác nhận OK", "OK", "flight_results",
     check_fn=has_search_results, session_id=sid21)

# Test 22: Multi-step clarify flow
sid22 = str(uuid.uuid4())
test("D", "22a. có hàng SG (thiếu điểm đến)", "có hàng SG", "clarify",
     check_fn=has_vietnamese_names, session_id=sid22)
test("D", "22b. Hà Nội (thiếu ngày)", "Hà Nội", "clarify",
     check_fn=has_vietnamese_names, session_id=sid22)
r = test("D", "22c. ngày mai (xác nhận)", "ngày mai", "confirm",
     check_fn=has_vietnamese_names, session_id=sid22)
test("D", "22d. OK (tìm vé)", "OK", "flight_results",
     check_fn=has_search_results, session_id=sid22)

# ── E. Extra fields ───────────────────────────────────────────
print("\n📌 E. EXTRA FIELDS TOLERANCE")
try:
    r = requests.post(BASE, json={
        "message": "xin chào",
        "session_id": "test-extra",
        "source": "web",
        "timestamp": "2026-07-21T10:00:00",
        "unknown_field": "should_not_crash"
    }, timeout=15)
    if r.status_code == 200:
        print(f"  ✅ [E] 23. Extra fields không crash")
        PASS += 1
    else:
        print(f"  ❌ [E] 23. Extra fields — HTTP {r.status_code}")
        FAIL += 1
    TOTAL += 1
except Exception as e:
    print(f"  ❌ [E] 23. Extra fields — ERROR: {e}")
    FAIL += 1
    TOTAL += 1

# ══════════════════════════════════════════════════════════════
print(f"\n{'='*72}")
print(f"  RESULTS: {PASS}/{TOTAL} PASSED, {FAIL}/{TOTAL} FAILED")
print(f"{'='*72}")

sys.exit(0 if FAIL == 0 else 1)
