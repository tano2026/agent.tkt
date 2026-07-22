"""Final test — each query gets fresh session to avoid contamination"""
import requests, json, uuid

BASE = "http://localhost:8138/api/chat"

tests = [
    ("viết tắt SG HN ngày mai", "SG HN ngày mai 2 người", "confirm"),
    ("tên đầy đủ HN→SG", "từ Hà Nội vào SG ngày kia", "confirm"),
    ("slang có hàng", "có hàng SG-HN không?", "clarify"),
    ("báo giá HN→PQ", "báo giá HN đi Phú Quốc 2 người", "clarify"),
    ("saigon dng", "saigon đi dng", "clarify"),
    ("hành lý VNA", "hành lý VNA bao nhiêu kg", "text"),
    ("đổi vé Vietjet", "đổi vé Vietjet", "text"),
    ("hủy vé", "hủy vé", "text"),
    ("cần giấy tờ gì", "cần giấy tờ gì khi bay", "text"),
    ("chính sách chung", "chính sách hoàn vé", "text"),
    ("chào hỏi", "xin chào", "text"),
    ("ngày đặc biệt July 20", "SG HN July 20 1 người", "confirm"),
    ("không dấu", "sgn han mai 1 nguoi", "confirm"),
    ("dng = Đà Nẵng", "sgn dng 20/7", "confirm"),
]

print("=" * 60)
print("FINAL TEST — ABTrip Bot (fresh session each)")
print("=" * 60)
passed = 0
failed = 0
for name, msg, expected_type in tests:
    sid = str(uuid.uuid4())
    try:
        r = requests.post(BASE, json={"message": msg, "session_id": sid}, timeout=30)
        d = r.json()
        resp_type = d.get("type", "?")
        ok = r.status_code == 200 and resp_type == expected_type
        status = "✅" if ok else "❌"
        if ok:
            passed += 1
        else:
            failed += 1
        print(f"  {status} {name}")
        if not ok:
            print(f"     Expected type={expected_type}, got {resp_type}")
            print(f"     Reply: {d.get('reply','')[:100]}")
    except Exception as e:
        print(f"  ❌ {name} — ERROR: {e}")
        failed += 1

print(f"\n{'='*60}")
print(f"PASSED: {passed}/{len(tests)} | FAILED: {failed}/{len(tests)}")
print(f"{'='*60}")
