"""
COMPREHENSIVE TEST — ABTrip Chat Bot
Tests all intents, slang, edge cases, confirm flow
"""
import requests, json, uuid, time

BASE = "http://localhost:8138/api/chat"

def test(name, msg, expected_type, expected_contains=None, session_id=None, notes=""):
    """Send message and verify response."""
    sid = session_id or str(uuid.uuid4())
    try:
        r = requests.post(BASE, json={"message": msg, "session_id": sid}, timeout=30)
        d = r.json()
        resp_type = d.get("type", "?")
        reply = d.get("reply", "")
        
        ok = r.status_code == 200 and resp_type == expected_type
        if ok and expected_contains:
            ok = any(phrase in reply for phrase in (expected_contains if isinstance(expected_contains, list) else [expected_contains]))
        
        status = "✅" if ok else "❌"
        print(f"\n  {status} {name}")
        if notes:
            print(f"     📝 {notes}")
        print(f"     Input: {msg[:60]}")
        print(f"     Type: {resp_type} (expected {expected_type})")
        
        # Show first 200 chars of reply
        first_line = reply.split('\n')[0][:80]
        print(f"     Reply: {first_line}")
        
        if not ok:
            print(f"     FULL: {reply[:300]}")
            
        return ok, d, sid
    except Exception as e:
        print(f"  ❌ {name} — ERROR: {e}")
        return False, None, None

# ============================================================
print("=" * 70)
print("TESTER REPORT — ABTrip Chat Bot v2.0")
print("=" * 70)

all_results = []

# ──────────── SECTION 1: Slang / Dialect ────────────
print("\n" + "─" * 70)
print("📌 SECTION 1: Slang, Viết tắt, Tiếng địa phương")
print("─" * 70)

tests_slang = [
    # Viết tắt IATA
    ("SG HN viết tắt", "SG HN ngày mai 2 người", "confirm", "TP.HCM → Hà Nội"),
    ("SGN HAN code chuẩn", "SGN HAN ngày mai 2 người", "confirm", "TP.HCM → Hà Nội"),
    ("sgn han lowercase", "sgn han mai 2 nguoi", "confirm", None),
    ("hcm không dấu", "hcm đi đà nẵng", "clarify", None),
    ("dng = Đà Nẵng", "saigon đi dng", "clarify", "Đà Nẵng"),
    # Tên đầy đủ
    ("tên đầy đủ HN→SG", "từ Hà Nội vào SG ngày kia", "confirm", "Hà Nội → TP.HCM"),
    ("Sài Gòn đầy đủ", "Sài Gòn đi Nha Trang", "clarify", None),
    ("Hải Phòng", "từ SG đi Hải Phòng", "clarify", None),
    ("Quy Nhơn", "từ SG đi Quy Nhơn", "clarify", None),
    # Slang phòng vé
    ("có hàng slang", "có hàng SG-HN không?", "clarify", "TP.HCM → Hà Nội"),
    ("kiểm tra hàng", "kiểm tra hàng SG HN cuối tuần", "confirm", "TP.HCM → Hà Nội"),
    ("báo giá", "báo giá HN đi Phú Quốc 2 người", "clarify", "Hà Nội → Phú Quốc"),
    # Direction
    ("direction 'ra'", "từ sài gòn ra hà nội", "clarify", "TP.HCM → Hà Nội"),
    ("direction 'vào'", "từ SG vào Đà Nẵng", "clarify", "TP.HCM → Đà Nẵng"),
    # Khứ hồi
    ("vé khứ hồi", "Hà Nội đi Sài Gòn vé khứ hồi", "clarify", "Hà Nội → TP.HCM"),
    # English format
    ("July 20 English", "SG HN July 20", "confirm", "20/07/2026"),
    ("Jul 20 short", "sgn han Jul 20 2", "confirm", None),
    ("ngày DD-MM", "SGN DAD 20-7 3 người", "confirm", None),
    # Business class
    ("hạng sang", "SGN HAN 20/7 bussiness", "confirm", None),
]

for name, msg, exp_type, exp_contains in tests_slang:
    ok, d, sid = test(name, msg, exp_type, exp_contains)
    all_results.append(ok)

# ──────────── SECTION 2: Policy Intents ────────────
print("\n" + "─" * 70)
print("📌 SECTION 2: Chính sách / Thông tin")
print("─" * 70)

tests_policy = [
    ("hành lý VNA", "hành lý VNA bao nhiêu kg", "text", "hành lý xách tay"),
    ("hành lý chung", "hành lý bao nhiêu kg", "text", "7kg"),
    ("đổi vé Vietjet", "đổi vé vietjet", "text", "Đổi vé"),
    ("đổi vé", "chính sách đổi vé", "text", "đổi"),
    ("đổi ngày", "đổi ngày bay được không", "text", "đổi"),
    ("hủy vé", "hủy vé được không", "text", "Hủy vé"),
    ("cần giấy tờ gì", "cần giấy tờ gì khi bay", "text", "CMND"),
    ("thủ tục checkin", "thủ tục check-in", "text", "Thủ tục"),
    ("chính sách chung", "chính sách hoàn vé", "text", "chính sách"),
    ("chính sách hỗn hợp", "cho hỏi chính sách đổi vé và hủy", "text", None),
]

for name, msg, exp_type, exp_contains in tests_policy:
    ok, d, sid = test(name, msg, exp_type, exp_contains)
    all_results.append(ok)

# ──────────── SECTION 3: Greeting / General ────────────
print("\n" + "─" * 70)
print("📌 SECTION 3: Chào hỏi / Chung")
print("─" * 70)

tests_general = [
    ("xin chào", "xin chào", "text", "ABTrip"),
    ("chào bot", "chào bot", "text", None),
    ("alo", "alo", "text", None),
]

for name, msg, exp_type, exp_contains in tests_general:
    ok, d, sid = test(name, msg, exp_type, exp_contains)
    all_results.append(ok)

# ──────────── SECTION 4: Confirm Flow ────────────
print("\n" + "─" * 70)
print("📌 SECTION 4: Luồng Confirm → Search (multi-turn)")
print("─" * 70)

# Single session flow: ask → confirm → OK → search
flow_sid = str(uuid.uuid4())
print("\n  Flow: SG HN ngày mai 2 người → OK → search result")
ok1, d1, _ = test("Step 1: search query", "SG HN ngày mai 2 người", 
                   "confirm", "Xác nhận", session_id=flow_sid)
all_results.append(ok1)

if ok1:
    ok2, d2, _ = test("Step 2: confirm OK", "OK",
                       "text", None, session_id=flow_sid, 
                       notes="Sau confirm, bot search flight")
    if ok2:
        reply = d2.get("reply", "")
        has_flights = "→" in reply or "đang kiểm tra" in reply or "kết quả" in reply
        print(f"     🔍 Has flight data: {'✅' if has_flights else '⚠️'} (reply: {reply[:150]})")
    all_results.append(ok2)

# ──────────── SECTION 5: Extra Fields ────────────
print("\n" + "─" * 70)
print("📌 SECTION 5: Extra fields + Edge cases")
print("─" * 70)

# Extra fields — should not crash
try:
    r = requests.post(BASE, json={
        "message": "xin chào", "session_id": str(uuid.uuid4()),
        "timestamp": "2026-07-21T10:00:00", "source": "web",
        "user_agent": "Chrome/120", "extra_data": {"test": True}
    }, timeout=30)
    ok_extra = r.status_code == 200
    print(f"  {'✅' if ok_extra else '❌'} Extra fields in request [{r.status_code}]")
    all_results.append(ok_extra)
except Exception as e:
    print(f"  ❌ Extra fields — ERROR: {e}")
    all_results.append(False)

# Empty message
try:
    r = requests.post(BASE, json={"message": "", "session_id": str(uuid.uuid4())}, timeout=30)
    ok_empty = r.status_code == 200
    print(f"  {'✅' if ok_empty else '❌'} Empty message [{r.status_code}]")
    all_results.append(ok_empty)
except Exception as e:
    print(f"  ❌ Empty message — ERROR: {e}")
    all_results.append(False)

# Missing message field
try:
    r = requests.post(BASE, json={"session_id": str(uuid.uuid4())}, timeout=30)
    ok_missing = r.status_code == 422  # Expected validation error
    print(f"  {'✅' if ok_missing else '❌'} Missing message field [{r.status_code}] — expected 422")
    all_results.append(ok_missing)
except Exception as e:
    print(f"  ❌ Missing message — ERROR: {e}")
    all_results.append(False)

# ──────────── SUMMARY ────────────
print("\n" + "=" * 70)
passed = sum(1 for r in all_results if r)
total = len(all_results)
print(f"  📊 FINAL SCORE: {passed}/{total} tests PASSED ({passed/total*100:.0f}%)")
print("=" * 70)
print()

# List failures
if passed < total:
    print("❌ FAILURES:")
    print("  (scroll up for ❌ markers above)")
else:
    print("🎉 ALL TESTS PASSED — Ready for deploy!")

print()
print("─" * 70)
print("Server: http://localhost:8138")
print("PID:", "10752")
print("─" * 70)
