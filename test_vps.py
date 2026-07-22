"""Test live VPS deployment"""
import requests, json, uuid

BASE = "http://100.64.173.75:8138/api/chat"

tests = [
    ("Viết tắt", "SG HN ngày mai 2 người", "confirm"),
    ("July 20 English date", "SG HN July 20 1 người", "confirm"),
    ("saigon dng", "saigon đi dng", "clarify"),
    ("hành lý VNA", "hành lý VNA bao nhiêu kg", "text"),
    ("đổi vé Vietjet", "đổi vé Vietjet", "text"),
    ("hủy vé", "hủy vé", "text"),
    ("xin chào", "xin chào", "text"),
]

print("=" * 60)
print("LIVE TEST: VPS DEPLOYMENT")
print(f"Server: {BASE}")
print("=" * 60)

passed = 0
failed = 0
for name, msg, expected in tests:
    sid = str(uuid.uuid4())
    try:
        r = requests.post(BASE, json={"message": msg, "session_id": sid}, timeout=30)
        d = r.json()
        resp_type = d.get("type", "?")
        ok = r.status_code == 200 and resp_type == expected
        print(f"  {'✅' if ok else '❌'} {name}: {msg[:30]}")
        if not ok:
            print(f"     Expected {expected}, got {resp_type}")
            print(f"     Reply: {d.get('reply','')[:120]}")
            failed += 1
        else:
            passed += 1
    except Exception as e:
        print(f"  ❌ {name}: ERROR — {e}")
        failed += 1

# Test confirm flow
print("\n--- Confirm flow ---")
sid = str(uuid.uuid4())
try:
    r1 = requests.post(BASE, json={"message": "SG HN ngày mai 2 người", "session_id": sid}, timeout=15)
    d1 = r1.json()
    if d1.get("type") == "confirm":
        r2 = requests.post(BASE, json={"message": "OK", "session_id": sid}, timeout=30)
        d2 = r2.json()
        if d2.get("type") == "flight_results":
            print(f"  ✅ Confirm -> Search results: {d2['reply'][:120]}")
            passed += 2
        else:
            print(f"  ❌ Confirm OK returned {d2.get('type')} instead of flight_results")
            failed += 2
    else:
        print(f"  ❌ First call type={d1.get('type')} (expected confirm)")
        failed += 2
except Exception as e:
    print(f"  ❌ Confirm flow ERROR: {e}")
    failed += 2

print(f"\n{'='*60}")
print(f"RESULT: {passed}/{passed+failed} PASSED")
print(f"{'='*60}")
