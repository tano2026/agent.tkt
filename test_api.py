"""Full API test suite for ABTrip Chat Bot"""
import requests, json, sys

BASE = "http://localhost:8138"

def test(name, endpoint, payload, expected_status=200):
    try:
        r = requests.post(f"{BASE}/api/chat", json=payload, timeout=15)
        ok = r.status_code == expected_status
        status = "✅" if ok else "❌"
        print(f"  {status} {name} [{r.status_code}]")
        if not ok:
            print(f"     {r.text[:300]}")
        return r
    except Exception as e:
        print(f"  ❌ {name} — ERROR: {e}")
        return None

print("=" * 60)
print("API TEST SUITE — ABTrip Chat Bot")
print("=" * 60)

# Test 1: Slang SG -> SGN
print("\n--- 1. Tiếng lóng/viết tắt ---")
r = test("SG HN", "/api/chat", {"message": "SG HN ngày mai 2 người"})
if r and r.status_code == 200:
    d = r.json()
    print(f"     Response: {d.get('response','')[:200]}")
    print(f"     Fields: {list(d.keys())}")

# Test 2: tên đầy đủ + direction
r = test("HN vào SG", "/api/chat", {"message": "từ Hà Nội vào SG ngày kia"})

# Test 3: slang phòng vé
r = test("có hàng SG-HN", "/api/chat", {"message": "có hàng SG-HN không?"})

# Test 4: saigon dng 
r = test("saigon dng", "/api/chat", {"message": "saigon đi dng"})

# Test 5: báo giá
r = test("báo giá HN PQ", "/api/chat", {"message": "báo giá HN đi Phú Quốc 2 người"})

# Test 6: say OK
print("\n--- 2. Xác nhận tìm kiếm ---")
r = test("OK confirm 1", "/api/chat", {"message": "OK"})
if r and r.status_code == 200:
    d = r.json()
    print(f"     Response: {d.get('response','')[:300]}")

# Test 7: Chat request with extra fields
print("\n--- 3. Extra fields test ---")
r = test("extra fields", "/api/chat", {
    "message": "xin chào",
    "session_id": "test-api",
    "timestamp": "2026-07-21T10:00:00",
    "source": "web"
})

# Test 8: Policy intent
print("\n--- 4. Policy/Info queries ---")
r = test("chính sách", "/api/chat", {"message": "hành lý VNA bao nhiêu kg"})

# Test 9: Chào hỏi
r = test("chào", "/api/chat", {"message": "chào bot"})
if r and r.status_code == 200:
    d = r.json()
    print(f"     Response: {d.get('response','')[:150]}")

print("\n" + "=" * 60)
print("DONE")
print("=" * 60)
