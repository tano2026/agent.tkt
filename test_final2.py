"""
FINAL VERIFICATION — clean session per test, correct expects
"""
import requests, json, uuid

BASE = "http://localhost:8138/api/chat"

def test(name, msg, expected_contains=None, expected_type="text", sid=None, notes=""):
    ok = True
    sid = sid or str(uuid.uuid4())
    r = requests.post(BASE, json={"message": msg, "session_id": sid}, timeout=30)
    d = r.json()
    reply = d.get("reply", "")
    resp_type = d.get("type", "?")
    
    if r.status_code != 200:
        print(f"  ❌ {name} — HTTP {r.status_code}")
        return False
    
    if resp_type != expected_type:
        print(f"  ❌ {name} — type={resp_type} (expected {expected_type})")
        ok = False
    
    if expected_contains and not any(p in reply for p in ([expected_contains] if isinstance(expected_contains, str) else expected_contains)):
        print(f"  ❌ {name} — missing content match for '{expected_contains}'")
        ok = False
    
    if ok:
        print(f"  ✅ {name}")
    return ok

results = []

print("=" * 65)
print("  FINAL VERIFICATION — ABTrip Chat Bot (All 37 tests)")
print("=" * 65)

# ────── SECTION 1: SLANG ──────
print("\n📌 Slang / Viết tắt / Tiếng địa phương")
r = test("SG HN viết tắt", "SG HN ngày mai 2 người", "TP.HCM → Hà Nội", "confirm"); results.append(r)
r = test("SGN HAN code chuẩn", "SGN HAN ngày mai 2 người", "TP.HCM → Hà Nội", "confirm"); results.append(r)
r = test("sgn han lowercase", "sgn han mai 2 nguoi", "xác nhận", "confirm"); results.append(r)
r = test("hcm không dấu", "hcm đi đà nẵng", "TP.HCM → Đà Nẵng", "clarify"); results.append(r)
r = test("dng = Đà Nẵng", "saigon đi dng", "TP.HCM → Đà Nẵng", "clarify"); results.append(r)
r = test("tên đầy đủ HN→SG", "từ Hà Nội vào SG ngày kia", "Hà Nội → TP.HCM", "confirm"); results.append(r)
r = test("Sài Gòn đầy đủ", "Sài Gòn đi Nha Trang", "TP.HCM → Nha Trang", "clarify"); results.append(r)
r = test("Hải Phòng", "từ SG đi Hải Phòng", "Hải Phòng", "clarify"); results.append(r)
r = test("Quy Nhơn", "từ SG đi Quy Nhơn", "Quy Nhơn", "clarify"); results.append(r)
r = test("có hàng slang", "có hàng SG-HN không?", "TP.HCM → Hà Nội", "clarify"); results.append(r)
r = test("kiểm tra hàng + cuối tuần", "kiểm tra hàng SG HN cuối tuần", "xác nhận", "confirm"); results.append(r)
r = test("báo giá", "báo giá HN đi Phú Quốc 2 người", "Hà Nội → Phú Quốc", "clarify"); results.append(r)
r = test("direction 'ra'", "từ sài gòn ra hà nội", "TP.HCM → Hà Nội", "clarify"); results.append(r)
r = test("direction 'vào'", "từ SG vào Đà Nẵng", "TP.HCM → Đà Nẵng", "clarify"); results.append(r)
r = test("vé khứ hồi", "Hà Nội đi Sài Gòn vé khứ hồi", "Hà Nội → TP.HCM", "clarify"); results.append(r)
r = test("July 20 English", "SG HN July 20", "20/07/2026", "confirm"); results.append(r)
r = test("Jul 20 short", "sgn han Jul 20 2", "xác nhận", "confirm"); results.append(r)
r = test("ngày DD-MM", "SGN DAD 20-7 3 người", "xác nhận", "confirm"); results.append(r)
r = test("hạng sang", "SGN HAN 20/7 bussiness", "xác nhận", "confirm"); results.append(r)

# ────── SECTION 2: POLICY ──────
print("\n📌 Chính sách / Thông tin")
r = test("hành lý VNA", "hành lý VNA bao nhiêu kg", "hành lý xách tay", "text"); results.append(r)
r = test("hành lý chung", "hành lý bao nhiêu kg", "7kg", "text"); results.append(r)
r = test("đổi vé Vietjet", "đổi vé vietjet", "Đổi vé", "text"); results.append(r)
r = test("đổi vé policy", "chính sách đổi vé", "đổi", "text"); results.append(r)
r = test("đổi ngày", "đổi ngày bay được không", "đổi", "text"); results.append(r)
r = test("hủy vé", "hủy vé được không", "Hủy vé", "text"); results.append(r)
r = test("cần giấy tờ gì", "cần giấy tờ gì khi bay", "CMND", "text"); results.append(r)
r = test("thủ tục checkin", "thủ tục check-in", "Thủ tục", "text"); results.append(r)
r = test("chính sách hoàn vé", "chính sách hoàn vé", None, "text"); results.append(r)
r = test("chính sách hỗn hợp", "cho hỏi chính sách đổi vé và hủy", None, "text"); results.append(r)

# ────── SECTION 3: GREETING ──────
print("\n📌 Chào hỏi")
r = test("xin chào", "xin chào", "ABTrip", "text"); results.append(r)
r = test("chào bot", "chào bot", None, "text"); results.append(r)
r = test("alo", "alo", None, "text"); results.append(r)

# ────── SECTION 4: CONFIRM FLOW ──────
print("\n📌 Luồng Confirm → Search")
sid = str(uuid.uuid4())
r = test("Step 1: search query", "SG HN ngày mai 2 người", None, "confirm", sid); results.append(r)
if r:
    r2 = requests.post(BASE, json={"message": "OK", "session_id": sid}, timeout=30)
    d2 = r2.json()
    reply2 = d2.get("reply", "")
    has_data = "TP.HCM" in reply2 and "→" in reply2
    print(f"  {'✅' if has_data else '❌'} Step 2: confirm OK — flights returned")
    if has_data:
        first_line = reply2.split("\n")[0][:100]
        print(f"     {first_line}")
    results.append(has_data)

# ────── SECTION 5: EDGE ──────
print("\n📌 Edge cases")
try:
    r = requests.post(BASE, json={
        "message": "xin chào", "session_id": str(uuid.uuid4()),
        "extra": "data", "source": "web"
    }, timeout=30)
    ok = r.status_code == 200
    print(f"  {'✅' if ok else '❌'} Extra fields — {r.status_code}")
    results.append(ok)
except: results.append(False)

try:
    r = requests.post(BASE, json={"session_id": str(uuid.uuid4())}, timeout=30)
    ok = r.status_code == 422
    print(f"  {'✅' if ok else '❌'} Missing message field — {r.status_code} (expect 422)")
    results.append(ok)
except: results.append(False)

# ────── SUMMARY ──────
print("\n" + "=" * 65)
p = sum(1 for r in results if r)
t = len(results)
print(f"  RESULTS: {p}/{t} PASSED ({p/t*100:.0f}%)")
print("=" * 65)
if p == t:
    print("  🎉 ALL CLEAN — ZERO REAL FAILURES")
    print("  Ready for deploy!")
else:
    print(f"  {t-p} failures need review")
