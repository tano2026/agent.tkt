# ABTrip AI Agent Platform — Master Plan v2 (Chốt)

> **Triết lý:** Không phải form. Là một **chuyên gia hàng không** biết tất cả, hiểu ý ngay lập tức, trả lời gọn gàng trong 1 giây.

---

## 🧠 Ticketing Bot — "Chuyên gia hàng không AI"

### Domain Knowledge (phải thuộc nằm lòng)

| Mảng | Kiến thức |
|------|----------|
| **Sân bay VN** | HAN (Nội Bài), SGN (Tân Sơn Nhất), DAD (Đà Nẵng), CXR (Cam Ranh), HUI (Phú Bài), PQC (Phú Quốc), HPH (Cát Bi), VCA (Trà Nóc), VII (Vinh), TBB (Tuy Hòa), etc. |
| **Địa danh VN** | "Sài Gòn/SG/HCM" → SGN, "Hà Nội/HN" → HAN, "Đà Nẵng/DN" → DAD, "Nha Trang" → CXR, "Phú Quốc" → PQC, "Hải Phòng/HP" → HPH, "Vinh" → VII, "Huế" → HUI, "Cần Thơ" → VCA |
| **Quốc tế** | BKK (Bangkok), NRT (Tokyo Narita), KIX (Osaka Kansai), ICN (Seoul Incheon), SIN (Singapore), KUL (Kuala Lumpur), PEK/ PKX (Beijing), PVG (Shanghai), CDG (Paris), SFO (San Francisco) |
| **Hãng bay VN** | VN (Vietnam Airlines), VJ (VietJet), QH (Bamboo Airways), BL (Pacific Airlines), VU (Vietravel Airlines) |
| **Hãng quốc tế** | SQ (Singapore Airlines), TG (Thai Airways), KE (Korean Air), JL (Japan Airlines), CX (Cathay Pacific), EK (Emirates) |
| **Chính sách** | Hành lý, đổi vé, hủy vé, hoàn tiền, thủ tục check-in, giờ bay đêm, trẻ em đi máy bay |
| **Quy định** | Giấy tờ bay nội địa (CMND/CCCD), giấy tờ bay quốc tế (hộ chiếu, visa), trẻ em dưới 14t, khách có thai |

### NLP Capabilities — Hiểu tất cả đầu vào

```
"cho 2 vé SG ĐN ngày kia"       → HAN→DAD, date=today+2, adults=2
"tìm HN-SG cuối tuần 2 người"   → HAN→SGN, next Sat/Sun, adults=2
"chuyến sáng 7h đi Sài Gòn"     → HAN→SGN, morning, ~7h
"Nha Trang từ Hà Nội thứ 7"     → HAN→CXR, next Saturday
"vé Hải Phòng SG 20/7           → HPH→SGN, 20/07
"máy bay Đà Lạt"                → DLI
"có chuyến thẳng Băng Cốc không?" → HAN/SGN→BKK
"chuyến rẻ nhất SGN-HN tháng sau" → SGN→HAN, next month, cheapest
"bé 2 tuổi có cần mua vé không?"  → Câu hỏi chính sách (trẻ em dưới 2t mua vé em bé)
"lỡ hủy vé VN có mất tiền không?" → Câu hỏi chính sách hãng
```

### Công cụ tra cứu

| Tool | Mục đích |
|------|---------|
| **AGT SearchFlight** | Tra cứu chuyến bay thật |
| **AGT GetFareRule** | Lấy điều kiện giá vé |
| **AGT GetAncillary** | Tra cứu dịch vụ (hành lý, suất ăn) |
| **Web Search (tích hợp)** | Tra chính sách hãng, promotion, tin tức |
| **Airport DB (local)** | Tra nhanh mã sân bay, địa danh |

### Output Format — Gọn gàng, dễ đọc

```
✈️ HAN → SGN | 20/07/2026

  VN230  07:30→09:45  1.250.000₫  ⭐ Rẻ nhất
  VJ151  08:15→10:20  1.390.000₫
  VN232  14:00→16:10  1.450.000₫  🚀 Bay thẳng
  VJ153  19:30→21:35  1.190.000₫  💥 Khuyến mãi

Tổng 2 người: 2.380.000₫ - 2.900.000₫
Bạn muốn chọn chuyến nào? 👇
```

---

## 📱 SIM Agent

**Supplier:** IST1 (eSIM Integration Protocol)
**API:** RESTful, MD5 signed, 7 endpoints

| Endpoint | Chức năng |
|----------|----------|
| F100 | Get Location (danh sách quố gia) |
| F200 | Obtain Commodities (gói SIM theo quốc gia) |
| F300 | Get Price (giá từng gói) |
| F400 | Query Order |
| F500 | Create ESIM Order (mua) |
| F600 | Query Validity of Card |
| F700 | Daily Flow Query |

**Loại eSIM:** 3105 (eSIM + tự chọn data), 3106 (eSIM + data cố định)

---

## 🛂 Visa Consultant Bot

**Cách vận hành:**
```
User: "muốn đi Nhật"
Bot:  Ở đây có mấy loại visa Nhật:
      1. Visa du lịch (15-30 ngày)
      2. Visa thăm thân
      3. Visa công tác
      Bạn muốn loại nào?

User: "du lịch"
Bot:  ✅ Hồ sơ visa Nhật du lịch:
      • Hộ chiếu (còn hạn 6 tháng)
      • Ảnh 4x6 (2 cái)
      • Đơn xin visa (điền form)
      • Xác nhận công việc
      • Sao kê ngân hàng 3 tháng
      • Lịch trình chuyến đi

      Phí dịch vụ: 500.000₫
      Làm 5-7 ngày làm việc.

      Bạn muốn đặt lịch làm hồ sơ không?
      👉 Để lại SĐT, nhân viên sẽ gọi lại trong 15 phút.
```

---

## 📐 Thiết kế Frontend (Mobile-first Chat)

```
┌─────────────────────────────────┐
│ ABTrip [🛩️ Vé][📱 SIM][🛂 V]   │ ← Tab bar + brand
├─────────────────────────────────┤
│                                 │
│ 🧑 "tìm HN SG ngày mai 2 vé"    │ ← Bubble user
│                                 │
│ 🤖 ✈️ Đang tìm...               │ ← Bubble bot
│                                 │
│ ┌─── Flight Result Card ────┐  │
│ │ VN230  7:30→9:45  1.2tr   │  │
│ │ VJ151  8:15→10:20 1.39tr  │  │
│ │ VN232  14:00→16:10 1.45tr │  │
│ │ VJ153  19:30→21:35 1.19tr │  │ ← Giá rẻ highlight
│ └───────────────────────────┘  │
│                                 │
│ 🧑 "lấy chuyến 7h30"           │
│                                 │
│ 🤖 VN230: thông tin chi tiết    │
│    Bay: 7:30→9:45 (2h15)       │
│    Giá: 1.250.000₫/khách       │
│    Hành lý: 7kg xách tay        │
│    Hủy/đổi: mất 30%             │
│                                 │
│ [ Đặt ngay ] [ Xem thêm ]      │ ← Quick action
│                                 │
├─────────────────────────────────┤
│ [ Nhắn tin...            ✈️  ] │ ← Input sticky
└─────────────────────────────────┘
```

### Design System

| Element | Mô tả |
|---------|-------|
| **Font** | Hệ thống (SF/Inter), size 16 cho chat |
| **Bubble user** | Primary-600, góc bo, text trắng |
| **Bubble bot** | Trắng, border gray-100, shadow nhẹ |
| **Card kết quả** | Mỗi chuyến 1 row, giá tiền nổi bật |
| **Sorting** | Mặc định: rẻ nhất → đắt nhất, có tag "🚀 Nhanh" "⭐ Rẻ" |
| **Quick actions** | Button chip dưới mỗi response |
| **Skeleton** | Trong khi loading: shimmer animation |
| **Mobile** | Chiều rộng tối đa 100%, keyboard adjusted |

---

## 📁 File Structure & Implementation Order

```
Phase 1: Chat Ticketing Bot (domain expert)
├── Task 1: Backend — LLM Gateway + Intent Parser (Vietnamese aviation)
│   ├── Create: backend/app/services/llm_gateway.py
│   ├── Create: backend/app/services/intent_parser.py (aviation-specific)
│   ├── Create: backend/app/services/aviation_db.py (airport/airline DB)
│   └── Create: backend/app/api/chat.py
│
├── Task 2: Frontend — Chat Interface
│   ├── Create: frontend/components/chat/ChatInterface.tsx
│   ├── Create: frontend/components/chat/ChatMessage.tsx
│   ├── Create: frontend/components/chat/ChatInput.tsx
│   ├── Create: frontend/components/chat/FlightResultCard.tsx
│   └── Modify: frontend/app/page.tsx (3 tabs → 3 chats)
│
├── Task 3: Frontend — Mobile UI Polish
│   ├── Modify: frontend/globals.css (mobile refinements)
│   └── Add: Telegram-style input, keyboard handling

Phase 2: White-label + CTV Admin
├── Task 4: Backend Tenant System
│   ├── Create: backend/app/models/tenant.py
│   ├── Create: backend/app/services/database.py
│   ├── Create: backend/app/api/admin.py
│   └── Modify: backend/app/main.py
│
└── Task 5: Frontend CTV Admin
    ├── Create: frontend/app/admin/ (pages)
    └── Create: frontend/components/admin/ (forms)

Phase 3: SIM Agent
├── Task 6: Backend SIM
│   ├── Create: backend/app/api/sim.py
│   ├── Create: backend/app/services/sim_client.py (IST1 API client)
│   └── Create: backend/app/models/sim.py
│
└── Task 7: Frontend SIM
    ├── Create: frontend/components/chat/SimResultCard.tsx
    └── Modify: chat types to support SIM results

Phase 4: Visa Consultant Bot
├── Task 8: Backend Visa
│   ├── Create: backend/app/api/visa.py
│   └── Create: backend/app/services/visa_service.py
│
└── Task 9: Frontend Visa
    ├── Create: frontend/components/chat/VisaResultCard.tsx
    └── Add: handoff-to-human flow

Phase 5: PWA
└── Task 10: PWA manifest + icons
    ├── Create: frontend/public/manifest.json
    └── Modify: frontend/app/layout.tsx
```

---

## 🔥 Priority Execution: Phase 1 trước

Chốt làm **Phase 1 trước** — Ticketing Chat Bot hoàn chỉnh.
Sau đó mới làm CTV Admin → SIM → Visa.

Chấp thuận?
