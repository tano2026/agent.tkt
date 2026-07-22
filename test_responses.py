"""Detailed test: see actual responses"""
import requests, json

BASE = "http://localhost:8138"

tests = [
    "SG HN ngày mai 2 người",
    "từ Hà Nội vào SG ngày kia",
    "có hàng SG-HN không?",
    "báo giá HN đi Phú Quốc 2 người",
    "saigon đi dng",
    "hành lý VNA bao nhiêu kg",
]

for msg in tests:
    r = requests.post(f"{BASE}/api/chat", json={"message": msg}, timeout=15)
    d = r.json()
    resp = d.get("reply", "")
    print(f"\n{'='*60}")
    print(f"❓: {msg}")
    print(f"{'='*60}")
    print(resp[:400])
    print()
