"""
FINAL CLEAN VERIFICATION
"""
import requests, uuid

BASE = "http://localhost:8138/api/chat"

def test(name, msg, expected_contains=None, expected_type="text", sid=None):
    sid = sid or str(uuid.uuid4())
    r = requests.post(BASE, json={"message": msg, "session_id": sid}, timeout=30)
    d = r.json()
    reply = d.get("reply", "")
    resp_type = d.get("type", "?")
    
    if r.status_code != 200:
        print(f"  ❌ {name} — HTTP {r.status_code}"); return False
    if resp_type != expected_type:
        print(f"  ❌ {name} — type={resp_type} (expect {expected_type})"); return False
    if expected_contains and not any(p in reply for p in ([expected_contains] if isinstance(expected_contains, str) else expected_contains)):
        print(f"  ❌ {name} — missing '{expected_contains}' in reply")
        print(f"     Reply: {reply[:100]}")
        return False
    print(f"  ✅ {name}")
    return True

results = []
print("=" * 55)
print("  FINAL VERDICT — ABTrip Chat Bot")
print("=" * 55)

print("\n── Slang / Dialect ──")
results.append(test("SG HN viết tắt", "SG HN ngày mai 2 người", "TP.HCM → Hà Nội", "confirm"))
results.append(test("SGN HAN code", "SGN HAN ngày mai 2 người", "TP.HCM → Hà Nội", "confirm"))
results.append(test("sgn han lowercase", "sgn han mai 2 nguoi", "Xác nhận", "confirm"))
results.append(test("hcm không dấu", "hcm đi đà nẵng", "TP.HCM → Đà Nẵng", "clarify"))
results.append(test("dng = Đà Nẵng", "saigon đi dng", "TP.HCM → Đà Nẵng", "clarify"))
results.append(test("HN→SG direction", "từ Hà Nội vào SG ngày kia", "Hà Nội → TP.HCM", "confirm"))
results.append(test("Sài Gòn→Nha Trang", "Sài Gòn đi Nha Trang", "TP.HCM → Nha Trang", "clarify"))
results.append(test("→Hải Phòng", "từ SG đi Hải Phòng", "Hải Phòng", "clarify"))
results.append(test("→Quy Nhơn", "từ SG đi Quy Nhơn", "Quy Nhơn", "clarify"))
results.append(test("có hàng SG-HN", "có hàng SG-HN không?", "TP.HCM → Hà Nội", "clarify"))
results.append(test("kiểm tra hàng cuối tuần", "kiểm tra hàng SG HN cuối tuần", "Xác nhận", "confirm"))
results.append(test("báo giá HN→PQ", "báo giá HN đi Phú Quốc 2 người", "Hà Nội → Phú Quốc", "clarify"))
results.append(test("'ra' = direction", "từ sài gòn ra hà nội", "TP.HCM → Hà Nội", "clarify"))
results.append(test("'vào' = direction", "từ SG vào Đà Nẵng", "TP.HCM → Đà Nẵng", "clarify"))
results.append(test("khứ hồi", "Hà Nội đi Sài Gòn vé khứ hồi", "Hà Nội → TP.HCM", "clarify"))
results.append(test("July 20 English", "SG HN July 20", "20/07/2026", "confirm"))
results.append(test("Jul 20 short", "sgn han Jul 20 2", "Xác nhận", "confirm"))
results.append(test("DD-MM date", "SGN DAD 20-7 3 người", "Xác nhận", "confirm"))
results.append(test("business class", "SGN HAN 20/7 bussiness", "Xác nhận", "confirm"))

print("\n── Policy ──")
results.append(test("hành lý VNA", "hành lý VNA bao nhiêu kg", ["hành lý xách tay", "7kg", "Hành lý"], "text"))
results.append(test("hành lý chung", "hành lý bao nhiêu kg", "7kg", "text"))
results.append(test("đổi vé Vietjet", "đổi vé vietjet", "Đổi vé", "text"))
results.append(test("chính sách đổi vé", "chính sách đổi vé", "đổi", "text"))
results.append(test("đổi ngày bay", "đổi ngày bay được không", "đổi", "text"))
results.append(test("hủy vé", "hủy vé được không", "Hủy vé", "text"))
results.append(test("giấy tờ bay", "cần giấy tờ gì khi bay", "CMND", "text"))
results.append(test("thủ tục checkin", "thủ tục check-in", "Thủ tục", "text"))
results.append(test("chính sách hoàn vé", "chính sách hoàn vé", None, "text"))
results.append(test("policy hỗn hợp", "cho hỏi chính sách đổi vé và hủy", None, "text"))

print("\n── Greeting ──")
results.append(test("xin chào", "xin chào", "ABTrip", "text"))
results.append(test("chào bot", "chào bot", None, "text"))
results.append(test("alo", "alo", None, "text"))

print("\n── Multi-turn confirm ──")
sid = str(uuid.uuid4())
if test("Step 1: query+confirm", "SG HN ngày mai 2 người", None, "confirm", sid):
    r = requests.post(BASE, json={"message": "OK", "session_id": sid}, timeout=30)
    d = r.json()
    reply = d.get("reply", "")
    has_data = "TP.HCM" in reply and "→" in reply
    print(f"  {'✅' if has_data else '❌'} Step 2: OK → flight data ({r.status_code})")
    results.append(has_data)
    if has_data:
        print(f"     {reply.split(chr(10))[0]}")

print("\n── Edge ──")
r = requests.post(BASE, json={"message": "xin chào", "session_id": str(uuid.uuid4()), "extra": "data"}, timeout=30)
print(f"  {'✅' if r.status_code == 200 else '❌'} Extra fields [{r.status_code}]"); results.append(r.status_code == 200)

r = requests.post(BASE, json={"session_id": str(uuid.uuid4())}, timeout=30)
print(f"  {'✅' if r.status_code == 422 else '❌'} Missing message [{r.status_code}]"); results.append(r.status_code == 422)

print("\n" + "=" * 55)
p = sum(1 for r in results if r)
t = len(results)
print(f"  VERDICT: {p}/{t} PASSED ({p/t*100:.0f}%)")
print("=" * 55)
if p == t:
    print("  🎉 READY FOR DEPLOYMENT")
else:
    print(f"  ⚠️  {t-p} failures remain")
