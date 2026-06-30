# ABTrip AI Agent Platform — Implementation Plan (Refined)

> **For Hermes:** Use this plan to implement task-by-task.

**Goal:** Transform ABTrip từ form booking thành AI Chat Platform — 3 Agent: Ticketing | SIM | Visa, white-label cho CTV, do AGT cấp 1 quản lý.

---

## Kiến trúc Frontend (Mobile-first Chat)

```
┌──────────────────────────────────┐
│  Header (dynamic brand)          │
├──────────────────────────────────┤
│  [🛩️ Vé] [📱 SIM] [🛂 Visa]     │ ← tab bar (luôn ở trên cùng)
├──────────────────────────────────┤
│                                  │
│  ┌── Chat Messages ───────────┐  │
│  │ User: "vé HN SG ngày mai"   │  │
│  │ Bot:  ✈️ Đang tìm...        │  │
│  │       [Card kết quả bay]    │  │
│  │ User: "chuyến 7h30"         │  │
│  │ Bot:  VN230, 1.250.000₫…   │  │
│  └────────────────────────────┘  │
│                                  │
│  ┌── Chat Input ──────────────┐  │
│  │ [ Nhắn tin tự nhiên... ] 📎 │  │
│  └────────────────────────────┘  │
├──────────────────────────────────┤
│  Footer                          │
└──────────────────────────────────┘
```

**Key design decisions:**
- Chat full-width, mobile-first, bottom input sticky
- Tab bar đổi màu gradient theo agent
- Kết quả dạng card trong chat (không popup)
- Click card để tiếp tục conversation
- PWA: install được trên điện thoại

---

## Phase 1: Chat Ticketing Agent (LLM + intent)

### Task 1: Backend — LLM Gateway + Chat API

**Files:**
- Create: `backend/app/services/llm_gateway.py` — Gemini + OmniRoute client
- Create: `backend/app/services/intent_parser.py` — parse NL → structured
- Create: `backend/app/api/chat.py` — `/api/chat` endpoint
- Modify: `backend/app/main.py` — register chat router
- Modify: `backend/app/services/config.py` — add LLM settings

**LLM flow:**
```
User: "tìm vé Hà Nội đi Sài Gòn 20/7 2 người"
  ↓
POST /api/chat { message, agent: "ticketing", session_id }
  ↓
Intent Parser (Gemini):
  {
    "intent": "search_flight",
    "entities": {
      "origin": "HAN", "destination": "SGN",
      "date": "20072026", "adults": 2
    }
  }
  ↓
Backend: gọi AGT API → format kết quả
  ↓
{
  "type": "card_results",
  "agent": "ticketing",
  "content": {
    "flights": [...],
    "summary": "Tìm thấy 5 chuyến bay HAN→SGN ngày 20/07"
  },
  "suggestions": ["chuyến 7h30", "chuyến giá rẻ nhất", "chuyến bay thẳng"]
}
```

### Task 2: Frontend — Chat Interface

**Files:**
- Create: `frontend/components/chat/ChatInterface.tsx`
- Create: `frontend/components/chat/ChatMessage.tsx`
- Create: `frontend/components/chat/ChatInput.tsx`
- Create: `frontend/components/chat/FlightResultCard.tsx`
- Modify: `frontend/app/page.tsx` — 3 tabs → 3 ChatInterface instances
- Delete: `frontend/components/TourAgent.tsx`

**Chat states:**
```typescript
type Message = {
  role: 'user' | 'assistant' | 'system';
  content: string;
  type?: 'text' | 'flight_results' | 'booking_confirm' | 'sim_results' | 'visa_info';
  data?: FlightResult[] | BookingResult | SimPackage[] | VisaInfo;
  timestamp: Date;
};

type ChatSession = {
  id: string;
  agent: 'ticketing' | 'sim' | 'visa';
  messages: Message[];
  context: {
    pendingAction?: 'search' | 'book' | 'confirm_passenger' | 'issue_ticket';
    sessionData?: any;
  };
};
```

---

## Phase 2: White-label + CTV Admin

### Task 3: Backend — Tenant System

**Files:**
- Create: `backend/app/models/tenant.py`
- Create: `backend/app/services/database.py`
- Create: `backend/app/api/admin.py`
- Modify: `backend/app/main.py`

**Tenant model:**
```python
class Tenant:
    id: str              # "ctv-001"
    name: str            # "Phòng vé Ngọc Anh"
    slug: str            # "ngoc-anh" (URL-safe)
    logo: str            # base64/URL
    primary_color: str   # "#2563eb"
    status: str          # "active" | "suspended"
    created_by: str      # AGT account
    fees: list[FeeConfig]
    api_key: str
```

**CTV Admin API:**
```
POST   /api/admin/tenants              — AGT tạo CTV mới
GET    /api/admin/tenants              — danh sách CTV
PUT    /api/admin/tenants/:id          — update CTV
PUT    /api/admin/tenants/:id/fees     — update phí dịch vụ
```

### Task 4: Frontend — CTV Admin Panel

**Files:**
- Create: `frontend/app/admin/page.tsx` — admin dashboard
- Create: `frontend/app/admin/tenants/page.tsx` — quản lý CTV
- Create: `frontend/app/admin/tenants/[id]/page.tsx` — chi tiết CTV
- Create: `frontend/components/admin/TenantForm.tsx` — form tạo CTV
- Create: `frontend/components/admin/FeeConfigForm.tsx` — form cấu hình phí

---

## Phase 3: SIM Travel Agent

⚠️ **Cần confirm**: chưa tìm thấy folder SIM — mày chỉ chỗ đi.

**Files:**
- Create: `backend/app/api/sim.py`
- Create: `backend/app/services/sim_provider.py`
- Create: `frontend/components/chat/SimResultCard.tsx`

---

## Phase 4: Visa Consultant Bot

### Task 5: Visa Bot Backend

**Files:**
- Create: `backend/app/api/visa.py`
- Create: `backend/app/services/visa_service.py`

**Visa Bot flow:**
```
User: "muốn đi Nhật cần visa gì?"
  ↓
Gemini tư vấn: loại visa, thủ tục, giấy tờ
  ↓
User: "hồ sơ cần những gì?"
  ↓
Bot liệt kê + hỏi: "Bạn muốn làm thủ tục không?"
  ↓
User: "có, làm giúp tôi"
  ↓
Bot: "Tôi sẽ kết nối bạn với nhân viên tư vấn. 
      Vui lòng để lại SĐT, chúng tôi sẽ gọi lại trong 15 phút."
  ↓
Gửi notification cho nhân viên phòng vé
```

### Task 6: Visa Bot Frontend

**Files:**
- Create: `frontend/components/chat/VisaResultCard.tsx`
- Modify: `frontend/components/chat/ChatInterface.tsx` — support handoff

---

## Phase 5: PWA + Mobile Polish

### Task 7: PWA Setup

**Files:**
- Create: `frontend/public/manifest.json`
- Create: `frontend/public/icon-192.png`, `icon-512.png`
- Modify: `frontend/app/layout.tsx` — PWA meta

### Task 8: Mobile UX

- Bottom input sticky (không bị keyboard đẩy)
- Swipe để chuyển tab (mobile)
- Pull-to-refresh cho chat
- Virtual scroll cho messages

---

## Implementation Order

```
Phase 1: Chat Ticketing ← MÀY MUỐN LÀM TRƯỚC
├── Task 1: Backend LLM Gateway + Chat API
└── Task 2: Frontend Chat Interface

Phase 2: White-label + CTV Admin
├── Task 3: Backend Tenant System
└── Task 4: Frontend CTV Admin Panel

Phase 3: SIM Agent
├── Task 5: SIM Backend + Frontend

Phase 4: Visa Consultant Bot
├── Task 6: Visa Bot Backend
└── Task 7: Visa Bot Frontend

Phase 5: PWA + Mobile
├── Task 8: PWA
└── Task 9: Mobile UX
```

---

## Trả lời confirm từ mày:

| Câu hỏi | Trả lời |
|---------|---------|
| SIM supplier? | ✅ "Có trong folder rồi" — **chỉ giúp tao folder nào** |
| Visa xử lý đến đâu? | ✅ Bot tư vấn → chuyển nhân viên chốt |
| LLM Model? | ✅ Gemini 2.5 Flash + OmniRoute |
| CTV tạo tk? | ✅ Chỉ AGT cấp 1 mới tạo được |
| Share link? | ❌ Bỏ qua, chưa cần |
