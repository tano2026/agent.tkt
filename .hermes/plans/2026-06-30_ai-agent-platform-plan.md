# ABTrip AI Agent Platform — Implementation Plan

> **For Hermes:** Use this plan to implement task-by-task. Each task is 5-15 phút.

**Goal:** Transform ABTrip từ form-based booking truyền thống thành **AI Agent Platform** — giao diện chat tự nhiên, white-label cho CTV, 3 agent: Ticketing | SIM | Visa.

**Kiến trúc tổng thể:**
```
Frontend (Next.js PWA)           Backend (FastAPI)
┌─────────────────────┐          ┌──────────────────────┐
│  Chat AI Interface   │◄─HTTP──►│  LLM Gateway         │
│  White-label Theme   │         │  Intent Parser        │
│  Agent Cards (3)     │         │  Tenant/CTV Manager   │
│  CTV Admin Panel     │         │  Fee Engine           │
│  Share Link Feature  │         │  AGT API Client       │
└─────────────────────┘         │  SIM Service          │
                                │  Visa Service         │
                                └──────────────────────┘
```

**Tech Stack:**
- Frontend: Next.js 14 + TailwindCSS (PWA-ready)
- Backend: FastAPI (hiện có)
- LLM: Gemini API (đã có sẵn) — parse intent từ chat tự nhiên
- Database: SQLite (POC) → PostgreSQL sau
- Auth: JWT cho CTV, share-link token cho khách hàng

---

## Phase 1: Core Chat Interface + LLM Engine

### Task 1: ChatBackend — LLM Intent Parser API

**Objective:** Tạo endpoint `/api/chat` nhận text tự nhiên, parse ra intent + entities, gọi AGT API tương ứng, trả về kết quả dạng card.

**Files:**
- Create: `backend/app/api/chat.py` — chat router
- Create: `backend/app/services/llm_gateway.py` — Gemini/LLM client
- Create: `backend/app/services/intent_parser.py` — parse tự nhiên → structured
- Modify: `backend/app/main.py` — register chat router

**Intent types cần parse:**
```json
{
  "intent": "search_flight" | "book_flight" | "retrieve_booking" | "search_sim" | "buy_sim" | "visa_info" | "visa_apply",
  "entities": {
    "origin": "HAN",
    "destination": "SGN",
    "date": "15072026",
    "passengers": 2,
    ...
  },
  "tenant_id": "ctv_abc"
}
```

**Prompt mẫu cho LLM:**
```
Bạn là trợ lý đặt vé cho ABTrip. Từ câu hỏi của user, trích xuất:
- intent: search_flight | book_flight | retrieve_booking | search_sim | buy_sim | visa_info
- entities: {origin, destination, date, passengers, ...}
- Trả về JSON, không thêm text.
User: {message}
```

---

### Task 2: Chat Frontend — Giao diện chat AI

**Objective:** Thay thế form-based search bằng chat interface mobile-first.

**Files:**
- Create: `frontend/components/chat/ChatInterface.tsx` — container chat chính
- Create: `frontend/components/chat/ChatMessage.tsx` — bubble tin nhắn
- Create: `frontend/components/chat/ChatInput.tsx` — input gửi tin nhắn
- Create: `frontend/components/chat/AgentCard.tsx` — card kết quả (flight, sim, visa)
- Modify: `frontend/app/page.tsx` — tích hợp chat thay vì form cũ

**Chat flow:**
```
User: "cho tôi vé Hà Nội Sài Gòn ngày 20/7 2 người lớn"
Bot:  "✈️ Đang tìm chuyến bay HAN→SGN ngày 20/07/2026..."
      [Hiện card kết quả chuyến bay]

User: "chuyến VN 230 giá bao nhiêu?"
Bot:  "Chuyến VN230 HAN→SGN 07:30→09:45: 1.250.000₫/khách
       Tổng: 2.500.000₫. Bạn muốn đặt không?"

User: "đặt đi"
Bot:  "Vui lòng nhập thông tin hành khách..."
```

**State management:**
```typescript
interface ChatState {
  messages: Message[];
  pendingIntent?: 'search' | 'book' | 'confirm';
  sessionData?: SearchSession | BookingSession;
  agent: 'ticketing' | 'sim' | 'visa';
}
```

---

### Task 3: Tích hợp 3 Agent Tabs vào Chat

**Objective:** 3 tab vẫn giữ nhưng mỗi tab là 1 chat riêng với context riêng.

**Files:**
- Modify: `frontend/app/page.tsx` — mỗi tab là 1 ChatInterface riêng
- Create: `frontend/components/chat/SimChat.tsx` — chat tìm SIM
- Modify: `frontend/components/chat/ChatInterface.tsx` — support multi-agent

**Agent-specific behaviors:**
| Agent | LLM System Prompt | Backend API |
|-------|------------------|-------------|
| Ticketing | Parse flight search/book | AGT API (existing) |
| SIM | Parse SIM package search/buy | SIM API (new) |
| Visa | Parse visa info/apply | Visa API (new) |

---

## Phase 2: White-label & Fee System

### Task 4: Database — Tenants (CTV) + Fee Config

**Files:**
- Create: `backend/app/models/tenant.py` — Tenant, FeeConfig models
- Create: `backend/app/services/database.py` — SQLite/Postgres setup
- Create: `backend/app/api/admin.py` — CTV admin API

**Tenant model:**
```python
class Tenant(Base):
    id: str           # slug: "ctv-ngoc-anh"
    name: str         # "Phòng vé Ngọc Anh"
    logo_url: str     # white-label logo
    primary_color: str  # hex color
    domain: str       # ctv-ngocanh.abtrip.vn
    fees: list[FeeConfig]
    api_key: str      # cho CTV tích hợp
```

**FeeConfig model:**
```python
class FeeConfig(Base):
    tenant_id: str
    service: str       # "ticketing" | "sim" | "visa"
    fee_type: str      # "fixed" | "percent"
    fee_value: float   # 50000 VND or 2.0 (%)
    min_fee: float     # minimum fee
    max_fee: float     # cap fee
```

### Task 5: White-label Theme Engine

**Files:**
- Create: `frontend/lib/white-label.ts` — load theme từ tenant
- Create: `frontend/components/WhiteLabelProvider.tsx` — React context cho theme
- Modify: `frontend/components/Header.tsx` — dynamic logo+color

**Cách hoạt động:**
```
User mở link: abtrip.vn/ctv/ngoc-anh
→ Frontend gọi GET /api/tenants/ngoc-anh
→ Nhận: {name, logo, color, fees}
→ Render với brand của CTV đó
```

**Share Link feature:**
```
Nút "Gửi khách hàng" → tạo link dạng:
abtrip.vn/s/abc123 (short-lived token)
→ Khách hàng mở ra thấy brand CTV, tự tra cứu
→ Nếu đặt, CTV hưởng fee
```

---

## Phase 3: SIM Travel Agent

### Task 6: SIM Agent Backend

**Files:**
- Create: `backend/app/models/sim.py` — SIM package models
- Create: `backend/app/api/sim.py` — SIM API routes
- Create: `backend/app/services/sim_provider.py` — SIM provider integration

**SIM packages:**
```python
class SimPackage(Base):
    country: str
    name: str            # "eSIM Du lịch Thái Lan 7 ngày"
    price: float
    data: str            # "10GB"
    validity: str        # "7 ngày"
    type: str            # "esim" | "physical"
    provider: str
```

### Task 7: SIM Agent Frontend

**Files:**
- Create: `frontend/components/sim/SimResultCard.tsx` — card kết quả SIM
- Modify: `frontend/components/chat/SimChat.tsx` — full chat flow

---

## Phase 4: Visa & Passport Agent

### Task 8: Visa Agent Backend

**Files:**
- Create: `backend/app/models/visa.py` — Visa models
- Create: `backend/app/api/visa.py` — Visa API routes
- Create: `backend/app/services/visa_service.py` — Visa logic

### Task 9: Visa Agent Frontend

**Files:**
- Create: `frontend/components/visa/VisaResultCard.tsx` — card kết quả visa
- Modify: `frontend/components/chat/ChatInterface.tsx` — integrate visa chat

---

## Phase 5: PWA & Mobile Optimization

### Task 10: PWA Setup

**Files:**
- Create: `frontend/public/manifest.json` — PWA manifest
- Create: `frontend/public/sw.js` — service worker (cơ bản)
- Modify: `frontend/app/layout.tsx` — thêm meta tags PWA

### Task 11: Mobile UX Polish

**Files:**
- Modify: `frontend/globals.css` — mobile-first refinements
- Modify: `frontend/components/chat/ChatInterface.tsx` — bottom sheet, keyboard handling

---

## Risk & Trade-offs

| Risk | Mitigation |
|------|-----------|
| LLM chi phí cao nếu mỗi request đều gọi Gemini | Cache intent parsing, chỉ gọi LLM cho câu mới, dùng template cho câu phổ biến |
| AGT API rate limit | Queue + retry mechanism |
| CTV tự ý đặt markup quá cao | Config min/max fee ở backend, server-enforced |
| Bảo mật share link | Token có expiry (24h), one-time use |
| LLM parse sai intent | Fallback về form truyền thống, cho user sửa |

---

## File Change Summary

```
backend/app/
├── api/
│   ├── chat.py          (NEW)  ← LLM chat endpoint
│   ├── admin.py         (NEW)  ← CTV admin
│   ├── sim.py           (NEW)  ← SIM agent
│   ├── visa.py          (NEW)  ← Visa agent
│   └── bookings.py      (KEEP)
├── models/
│   ├── tenant.py        (NEW)  ← White-label
│   ├── sim.py           (NEW)
│   ├── visa.py          (NEW)
│   └── abtrip.py        (KEEP)
├── services/
│   ├── llm_gateway.py   (NEW)  ← Gemini integration
│   ├── intent_parser.py (NEW)
│   ├── database.py      (NEW)
│   ├── sim_provider.py  (NEW)
│   ├── visa_service.py  (NEW)
│   └── abtrip_client.py (KEEP)
├── main.py              (MODIFY) ← register new routers
└── config.py            (MODIFY) ← add LLM settings

frontend/
├── components/
│   ├── chat/
│   │   ├── ChatInterface.tsx   (NEW)
│   │   ├── ChatMessage.tsx     (NEW)
│   │   ├── ChatInput.tsx       (NEW)
│   │   ├── AgentCard.tsx       (NEW)
│   │   └── SimChat.tsx         (NEW)
│   ├── sim/
│   │   └── SimResultCard.tsx   (NEW)
│   ├── visa/
│   │   └── VisaResultCard.tsx  (NEW)
│   ├── WhiteLabelProvider.tsx  (NEW)
│   ├── SearchForm.tsx         (KEEP — fallback)
│   ├── TourAgent.tsx          (DELETE)
│   └── Header.tsx             (MODIFY — dynamic brand)
├── lib/
│   ├── white-label.ts         (NEW)
│   └── api.ts                 (MODIFY — add chat API)
├── app/
│   ├── page.tsx               (MODIFY — chat interface)
│   ├── layout.tsx             (MODIFY — PWA meta)
│   └── s/[token]/page.tsx     (NEW — share link)
├── public/
│   ├── manifest.json          (NEW)
│   └── sw.js                  (NEW)
└── globals.css                (MODIFY — mobile refinements)
```

---

## Implementation Order

```
Phase 1: Chat + LLM (ưu tiên cao nhất)
├── Task 1: ChatBackend LLM Intent Parser
├── Task 2: Chat Frontend
└── Task 3: 3 Agent Tabs → Chat

Phase 2: White-label + Fee
├── Task 4: Tenant DB + Fee Config
└── Task 5: White-label Theme Engine

Phase 3: SIM Agent
├── Task 6: SIM Backend
└── Task 7: SIM Frontend

Phase 4: Visa Agent
├── Task 8: Visa Backend
└── Task 9: Visa Frontend

Phase 5: PWA + Mobile
├── Task 10: PWA Setup
└── Task 11: Mobile UX Polish
```

---

## Câu hỏi cần confirm trước khi code

1. **SIM Agent**: Có supplier API cụ thể cho eSIM/SIM du lịch không? Hay tự hardcode packages?
2. **Visa Agent**: Chỉ tra cứu thông tin thủ tục hay có thể nộp hồ sơ luôn?
3. **LLM Model**: Dùng Gemini 2.5 Flash (đã có sẵn) hay muốn dùng OpenRouter để chọn model khác?
4. **CTV signup**: CTV tự đăng ký được không, hay chỉ do AGT cấp 1 tạo?
5. **Share link**: Cần tracking để CTV biết khách nào book từ link của họ không?
