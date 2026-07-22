"""Test intent parser with various slang and queries."""
import sys
sys.path.insert(0, r"C:\Users\Nguyen Ngoc Tan\agent.tkt\backend")

from app.services.intent_parser import (
    parse_flight_search, classify_intent, check_missing_info,
    generate_clarify_question, parse_relative_date, parse_date,
)

tests = [
    # Format: (input, expected_origin, expected_dest, note)
    ("SG HN ngày mai 2 người", "SGN", "HAN", "viết tắt SG"),
    ("SGN HAN ngày mai 2 người", "SGN", "HAN", "IATA code"),
    ("sgn han mai 2 nguoi", "SGN", "HAN", "no dấu"),
    ("sgn han 5/7 1 người", "SGN", "HAN", "date DD/MM"),
    ("sgn han 5/7 1 nguoi", "SGN", "HAN", "no dấu 2"),
    ("Hà Nội SG ngày kia", "HAN", "SGN", "tên đầy đủ"),
    ("từ HN đi SG ngày mai", "HAN", "SGN", "có từ...đi"),
    ("có hàng SG-HN không?", "SGN", "HAN", "slang phòng vé"),
    ("kiểm tra hàng SG HN cuối tuần", "SGN", "HAN", "kiểm tra hàng"),
    ("từ sài gòn ra hà nội", "SGN", "HAN", "ra = đến"),
    ("từ SG vào Đà Nẵng", "SGN", "DAD", "vào = đến"),
    ("cho tôi xin giá SG đi Nha Trang", "SGN", "CXR", "xin giá"),
    ("báo giá HN đi Phú Quốc", "HAN", "PQC", "báo giá"),
    ("có vé SG đi Đà Lạt tuần sau", "SGN", "DLI", "có vé + tuần sau"),
    ("SGN DAD 20/7 3 người", "SGN", "DAD", "date + pax"),
    ("từ SGN đi HAN 20 tháng 7 2 người lớn", "SGN", "HAN", "tháng text"),
    ("Tìm chuyến từ Hà Nội vào SG ngày kia 1 người", "HAN", "SGN", "câu đầy đủ"),
    ("Vé SG đi Hải Phòng", "SGN", "HPH", "Hải Phòng"),
    ("từ SG đi Quy Nhơn", "SGN", "UIH", "Quy Nhơn"),
    ("sg tphcm đi nha trang 2 pax", "SGN", "CXR", "pax + tphcm"),
    ("hcm đi đà nẵng", "SGN", "DAD", "hcm"),
    ("saigon đi dng", "SGN", "DAD", "saigon + dng"),
    ("SGN HAN 20/7 bussiness", "SGN", "HAN", "business class"),
    ("Hà Nội đi Sài Gòn vé khứ hồi", "HAN", "SGN", "khứ hồi"),
]

# Date-specific tests
date_tests = [
    ("ngày mai", None, "relative: tomorrow"),
    ("mai", None, "relative: mai short"),
    ("ngày kia", None, "relative: day after tomorrow"),
    ("cuối tuần", None, "relative: weekend"),
    ("hôm nay", None, "relative: today"),
    ("hom ni", None, "dialect: hôm ni"),
    ("bữa nay", None, "dialect: bữa nay"),
    ("20/7", None, "date: DD/MM"),
    ("20-7", None, "date: DD-MM"),
    ("20/7/2026", None, "date: DD/MM/YYYY"),
    ("20 tháng 7", None, "date: vietnamese text"),
    ("July 20", None, "date: English"),
    ("Jul 20", None, "date: English short"),
]

print("=" * 60)
print("FLIGHT SEARCH PARSER TESTS")
print("=" * 60)
passed = 0
failed = 0
for inp, exp_orig, exp_dest, note in tests:
    result = parse_flight_search(inp)
    if result and result.get("origin") == exp_orig and result.get("destination") == exp_dest:
        print(f"  ✅ {note}: {inp}")
        print(f"     → {result.get('origin')}→{result.get('destination')} | date={result.get('date','?')} | adults={result.get('adults')}")
        passed += 1
    else:
        print(f"  ❌ {note}: {inp}")
        if result:
            print(f"     Got: {result.get('origin','?')}→{result.get('destination','?')} (expected {exp_orig}→{exp_dest})")
        else:
            print(f"     Got: None (expected {exp_orig}→{exp_dest})")
        failed += 1

print(f"\nPassed: {passed}/{len(tests)}, Failed: {failed}/{len(tests)}")

print("\n" + "=" * 60)
print("INTENT CLASSIFICATION TESTS")
print("=" * 60)
intent_tests = [
    ("hành lý VNA bao nhiêu kg", "policy_baggage"),
    ("đổi vé Vietjet", "policy_change"),
    ("hủy vé", "policy_cancel"),
    ("cần giấy tờ gì", "policy_documents"),
    ("chính sách hàng không", "policy_general"),
    ("có hàng SG HN", "search_flight"),
    ("kiểm tra hàng", "search_flight"),
    ("từ SGN đi HAN ngày mai", "search_flight"),
    ("đặt vé VJ120", "book_flight"),
    ("mua vé SG HN", "book_flight"),
    ("tra cứu mã booking", "retrieve_booking"),
    ("xin chào", "greeting"),
]
p2 = 0
f2 = 0
for inp, exp in intent_tests:
    got = classify_intent(inp)
    if got == exp:
        print(f"  ✅ {inp} → {got}")
        p2 += 1
    else:
        print(f"  ❌ {inp} → {got} (expected {exp})")
        f2 += 1
print(f"Intent: Passed {p2}/{len(intent_tests)}, Failed {f2}")
