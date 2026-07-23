"""
Smart Agent — Phòng vé AI bán cần câu.

Multi-tenant service layer với subscription tiers:
  - CTV Cơ bản (free): 8% commission, 50 booking/month
  - Đại Lý Pro (199K/tháng): 12% commission, 300 booking/month
  - White-label (1.5tr/tháng): 15% commission, unlimited

5 dịch vụ: vé máy bay (core), Fast Track (độc quyền), eSIM, visa, hộ chiếu (tư vấn).
"""

import logging
import secrets
import json
import asyncio
import uuid
from datetime import datetime, date, timedelta

from app.services.rag_service import get_rag_service, init_rag # Import RAG service
from decimal import Decimal
from typing import Optional, List

import httpx

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import (
    Column, Integer, String, Float, Boolean, DateTime, Text, Date,
    ForeignKey, Enum, create_engine, select, func
)
from sqlalchemy.orm import declarative_base, Session, sessionmaker
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from app.services.config import get_settings

# ---------------------------------------------------------------------------
# Database setup
# ---------------------------------------------------------------------------

logger = logging.getLogger(__name__)
settings = get_settings()

import os
DB_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
os.makedirs(DB_DIR, exist_ok=True)
DATABASE_URL = f"sqlite+aiosqlite:///{os.path.join(DB_DIR, 'smart_agent.db')}"

engine = create_async_engine(DATABASE_URL, echo=False)
async_session_factory = async_sessionmaker(engine, expire_on_commit=False)
Base = declarative_base()


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class Tenant(Base):
    """Multi-tenant CTV account."""
    __tablename__ = "sa_tenants"

    id = Column(Integer, primary_key=True, autoincrement=True)
    company_name = Column(String(200), nullable=False)
    full_name = Column(String(100), nullable=False)
    phone = Column(String(20), nullable=False, unique=True)
    email = Column(String(200), nullable=False)
    business_type = Column(String(50), default="ctv")  # ctv | dai_ly | whitelabel
    agent_tier = Column(String(20), default="free")  # free | pro | whitelabel
    api_key = Column(String(64), unique=True, nullable=False)
    commission_rate = Column(Float, default=0.08)
    monthly_booking_limit = Column(Integer, default=50)
    booking_count = Column(Integer, default=0)
    status = Column(String(20), default="active")  # active | suspended | cancelled
    registered_at = Column(DateTime, default=datetime.utcnow)
    subscription_expires_at = Column(DateTime, nullable=True)
    notes = Column(Text, nullable=True)


class Subscription(Base):
    """Payment / subscription history."""
    __tablename__ = "sa_subscriptions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, ForeignKey("sa_tenants.id"), nullable=False)
    tier = Column(String(20), nullable=False)  # free | pro | whitelabel
    amount = Column(Float, default=0)
    payment_method = Column(String(20), nullable=True)  # momo | vnpay | bank
    status = Column(String(20), default="pending")  # pending | completed | failed
    period_start = Column(Date, nullable=False)
    period_end = Column(Date, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class FastTrackOrder(Base):
    """Fast Track Nội Bài orders."""
    __tablename__ = "sa_fasttrack_orders"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, ForeignKey("sa_tenants.id"), nullable=False)
    customer_name = Column(String(100), nullable=False)
    customer_phone = Column(String(20), nullable=False)
    flight_date = Column(Date, nullable=False)
    flight_number = Column(String(20), nullable=False)
    pax_count = Column(Integer, default=1)
    service_type = Column(String(20), default="fasttrack")  # fasttrack | vip_lounge
    total_price = Column(Float, nullable=False)
    commission = Column(Float, default=0)
    status = Column(String(20), default="pending")  # pending | confirmed | completed | cancelled
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class ESIMOrder(Base):
    """eSIM du lịch orders."""
    __tablename__ = "sa_esim_orders"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, ForeignKey("sa_tenants.id"), nullable=False)
    customer_phone = Column(String(20), nullable=False)
    customer_email = Column(String(200), nullable=True)
    package_code = Column(String(50), nullable=False)
    destination = Column(String(100), nullable=False)
    duration_days = Column(Integer, default=7)
    total_price = Column(Float, nullable=False)
    commission = Column(Float, default=0)
    esim_qr = Column(Text, nullable=True)
    status = Column(String(20), default="pending")  # pending | delivered | completed
    created_at = Column(DateTime, default=datetime.utcnow)


class Payment(Base):
    """Payment transaction log."""
    __tablename__ = "sa_payments"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, ForeignKey("sa_tenants.id"), nullable=False)
    order_type = Column(String(20), nullable=False)  # subscription | fasttrack | esim
    order_id = Column(Integer, nullable=False)
    amount = Column(Float, nullable=False)
    payment_method = Column(String(20), nullable=False)  # momo | vnpay | bank
    transaction_id = Column(String(100), nullable=True)
    status = Column(String(20), default="pending")
    created_at = Column(DateTime, default=datetime.utcnow)


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------

class RegisterRequest(BaseModel):
    company_name: str = Field(min_length=1, max_length=200)
    full_name: str = Field(min_length=1, max_length=100)
    phone: str = Field(min_length=10, max_length=20)
    email: str = Field(max_length=200)
    business_type: str = Field(default="ctv")
    notes: Optional[str] = None


class RegisterResponse(BaseModel):
    success: bool
    tenant_id: int
    api_key: str
    tier: str
    commission_rate: float
    message: str


class UpgradeRequest(BaseModel):
    tenant_id: int
    tier: str = Field(pattern="^(pro|whitelabel)$")
    payment_method: str = Field(pattern="^(momo|vnpay)$")
    months: int = Field(default=1, ge=1, le=12)


class FastTrackRequest(BaseModel):
    tenant_id: int
    customer_name: str = Field(min_length=1, max_length=100)
    customer_phone: str = Field(min_length=10, max_length=20)
    flight_date: date
    flight_number: str = Field(min_length=3, max_length=20)
    pax_count: int = Field(default=1, ge=1, le=20)
    service_type: str = Field(default="fasttrack")
    notes: Optional[str] = None


class ESIMRequest(BaseModel):
    tenant_id: int
    customer_phone: str = Field(min_length=10, max_length=20)
    customer_email: Optional[str] = None
    package_code: str
    destination: str = Field(max_length=100)
    duration_days: int = Field(default=7, ge=1, le=90)


# ---------------------------------------------------------------------------
# Price tables
# ---------------------------------------------------------------------------

FASTTRACK_PRICES = {
    "fasttrack": 450_000,  # VND/pax
    "vip_lounge": 650_000,
}

ESIM_PACKAGES = [
    {"code": "ESIM_ASIA_7D", "name": "Châu Á 7 ngày", "price": 99_000, "destinations": ["Thailand", "Singapore", "Malaysia", "Indonesia", "Philippines"]},
    {"code": "ESIM_ASIA_15D", "name": "Châu Á 15 ngày", "price": 179_000, "destinations": ["Thailand", "Singapore", "Malaysia", "Indonesia", "Philippines"]},
    {"code": "ESIM_JP_7D", "name": "Nhật Bản 7 ngày", "price": 149_000, "destinations": ["Japan"]},
    {"code": "ESIM_JP_15D", "name": "Nhật Bản 15 ngày", "price": 249_000, "destinations": ["Japan"]},
    {"code": "ESIM_KR_7D", "name": "Hàn Quốc 7 ngày", "price": 129_000, "destinations": ["Korea", "South Korea"]},
    {"code": "ESIM_EU_7D", "name": "Châu Âu 7 ngày", "price": 199_000, "destinations": ["France", "Germany", "Italy", "Spain", "UK", "Netherlands", "Switzerland"]},
    {"code": "ESIM_US_7D", "name": "Mỹ 7 ngày", "price": 179_000, "destinations": ["USA", "United States"]},
    {"code": "ESIM_GLOBAL_30D", "name": "Toàn cầu 30 ngày", "price": 499_000, "destinations": ["Global", "Worldwide"]},
]

TIER_CONFIG = {
    "free":      {"commission": 0.08, "booking_limit": 50,  "price": 0},
    "pro":       {"commission": 0.12, "booking_limit": 300, "price": 199_000},
    "whitelabel": {"commission": 0.15, "booking_limit": 99999, "price": 1_500_000},
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def generate_api_key() -> str:
    return f"sa_{secrets.token_hex(24)}"


async def get_db() -> AsyncSession:
    async with async_session_factory() as session:
        yield session


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

router = APIRouter(prefix="/api/smart-agent", tags=["Smart Agent"])

# ─── Chat session storage ───
_chat_sessions: dict[str, list[dict]] = {}


class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None


class ChatResponse(BaseModel):
    type: str  # "text" | "tool_call" | "error" | "done"
    content: str
    session_id: str
    step: Optional[str] = None
    data: Optional[dict] = None
    suggestions: list[str] = []
    flow: Optional[str] = None


@router.on_event("startup")
async def init_db():
    """Create all tables on startup."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await init_rag() # Initialize RAG service
    logger.info("Smart Agent tables created/verified.")


# --- 1. Register CTV ---

@router.post("/register")
async def register_tenant(req: RegisterRequest, db: AsyncSession = Depends(get_db)):
    """Đăng ký CTV mới."""
    existing = await db.execute(select(Tenant).where(Tenant.phone == req.phone))
    if existing.scalar_one_or_none():
        raise HTTPException(400, "Số điện thoại đã đăng ký")

    api_key = generate_api_key()
    tier = "free"
    cfg = TIER_CONFIG[tier]

    tenant = Tenant(
        company_name=req.company_name,
        full_name=req.full_name,
        phone=req.phone,
        email=req.email,
        business_type=req.business_type,
        agent_tier=tier,
        api_key=api_key,
        commission_rate=cfg["commission"],
        monthly_booking_limit=cfg["booking_limit"],
        notes=req.notes,
    )
    db.add(tenant)
    await db.commit()
    await db.refresh(tenant)

    return RegisterResponse(
        success=True,
        tenant_id=tenant.id,
        api_key=api_key,
        tier=tier,
        commission_rate=cfg["commission"],
        message="Đăng ký thành công! Bạn đang ở gói CTV Cơ bản.",
    )


# --- 2. Get tenant info ---

@router.get("/tenant/{tenant_id}")
async def get_tenant(tenant_id: int, db: AsyncSession = Depends(get_db)):
    """Thông tin CTV."""
    result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
    tenant = result.scalar_one_or_none()
    if not tenant:
        raise HTTPException(404, "Không tìm thấy CTV")

    return {
        "id": tenant.id,
        "company_name": tenant.company_name,
        "full_name": tenant.full_name,
        "phone": tenant.phone,
        "email": tenant.email,
        "business_type": tenant.business_type,
        "agent_tier": tenant.agent_tier,
        "commission_rate": tenant.commission_rate,
        "booking_count": tenant.booking_count,
        "booking_limit": tenant.monthly_booking_limit,
        "status": tenant.status,
        "registered_at": tenant.registered_at.isoformat() if tenant.registered_at else None,
        "subscription_expires_at": tenant.subscription_expires_at.isoformat() if tenant.subscription_expires_at else None,
    }


# --- 3. List all tenants ---

@router.get("/tenants")
async def list_tenants(
    status: Optional[str] = None,
    tier: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    """Danh sách CTV."""
    query = select(Tenant)
    if status:
        query = query.where(Tenant.status == status)
    if tier:
        query = query.where(Tenant.agent_tier == tier)
    query = query.order_by(Tenant.registered_at.desc())

    result = await db.execute(query)
    tenants = result.scalars().all()

    return [
        {
            "id": t.id,
            "company_name": t.company_name,
            "full_name": t.full_name,
            "phone": t.phone,
            "tier": t.agent_tier,
            "commission": t.commission_rate,
            "bookings": t.booking_count,
            "status": t.status,
            "registered_at": t.registered_at.isoformat() if t.registered_at else None,
        }
        for t in tenants
    ]


# --- 4. Upgrade tier ---

@router.post("/upgrade")
async def upgrade_tenant(req: UpgradeRequest, db: AsyncSession = Depends(get_db)):
    """Nâng cấp lên Pro hoặc White-label."""
    result = await db.execute(select(Tenant).where(Tenant.id == req.tenant_id))
    tenant = result.scalar_one_or_none()
    if not tenant:
        raise HTTPException(404, "Không tìm thấy CTV")

    cfg = TIER_CONFIG[req.tier]
    amount = cfg["price"] * req.months
    now = date.today()
    period_end = now + timedelta(days=30 * req.months)

    # Create subscription record
    sub = Subscription(
        tenant_id=tenant.id,
        tier=req.tier,
        amount=amount,
        payment_method=req.payment_method,
        status="completed",  # Assume payment success for now
        period_start=now,
        period_end=period_end,
    )
    db.add(sub)

    # Update tenant
    tenant.agent_tier = req.tier
    tenant.commission_rate = cfg["commission"]
    tenant.monthly_booking_limit = cfg["booking_limit"]
    tenant.subscription_expires_at = datetime.combine(period_end, datetime.min.time())

    await db.commit()

    return {
        "success": True,
        "tenant_id": tenant.id,
        "new_tier": req.tier,
        "amount": amount,
        "period_end": period_end.isoformat(),
        "message": f"Nâng cấp lên {req.tier} thành công! Hạn đến {period_end}.",
    }


# --- 5. Fast Track ---

FASTTRACK_NIGHT_SURCHARGE = 200_000  # 23:00-06:00


@router.post("/fasttrack")
async def create_fasttrack(req: FastTrackRequest, db: AsyncSession = Depends(get_db)):
    """Đặt Fast Track / VIP Lounge."""
    result = await db.execute(select(Tenant).where(Tenant.id == req.tenant_id))
    tenant = result.scalar_one_or_none()
    if not tenant:
        raise HTTPException(404, "Không tìm thấy CTV")
    if tenant.status != "active":
        raise HTTPException(403, "Tài khoản đã bị khóa")

    unit_price = FASTTRACK_PRICES.get(req.service_type, 450_000)
    total_price = unit_price * req.pax_count
    commission = total_price * tenant.commission_rate

    order = FastTrackOrder(
        tenant_id=tenant.id,
        customer_name=req.customer_name,
        customer_phone=req.customer_phone,
        flight_date=req.flight_date,
        flight_number=req.flight_number,
        pax_count=req.pax_count,
        service_type=req.service_type,
        total_price=total_price,
        commission=commission,
        notes=req.notes,
    )
    db.add(order)
    tenant.booking_count += 1
    await db.commit()
    await db.refresh(order)

    return {
        "success": True,
        "order_id": order.id,
        "total_price": total_price,
        "commission": round(commission, 0),
        "status": "pending",
        "message": f"Đặt {req.service_type} cho {req.customer_name} thành công!",
    }


@router.get("/fasttrack/orders")
async def list_fasttrack_orders(
    tenant_id: Optional[int] = None,
    status: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    """Danh sách Fast Track orders."""
    query = select(FastTrackOrder)
    if tenant_id:
        query = query.where(FastTrackOrder.tenant_id == tenant_id)
    if status:
        query = query.where(FastTrackOrder.status == status)
    query = query.order_by(FastTrackOrder.created_at.desc())

    result = await db.execute(query)
    orders = result.scalars().all()

    return [
        {
            "id": o.id,
            "tenant_id": o.tenant_id,
            "customer_name": o.customer_name,
            "flight_date": o.flight_date.isoformat(),
            "flight_number": o.flight_number,
            "pax": o.pax_count,
            "service": o.service_type,
            "total": o.total_price,
            "commission": o.commission,
            "status": o.status,
            "created_at": o.created_at.isoformat() if o.created_at else None,
        }
        for o in orders
    ]


# --- 6. eSIM ---

@router.get("/esim/packages")
async def list_esim_packages():
    """Danh sách gói eSIM."""
    return ESIM_PACKAGES


@router.post("/esim")
async def create_esim(req: ESIMRequest, db: AsyncSession = Depends(get_db)):
    """Đặt eSIM du lịch."""
    result = await db.execute(select(Tenant).where(Tenant.id == req.tenant_id))
    tenant = result.scalar_one_or_none()
    if not tenant:
        raise HTTPException(404, "Không tìm thấy CTV")

    # Find package
    pkg = next((p for p in ESIM_PACKAGES if p["code"] == req.package_code), None)
    if not pkg:
        raise HTTPException(400, f"Gói eSIM {req.package_code} không tồn tại")

    total_price = pkg["price"]
    commission = total_price * tenant.commission_rate

    order = ESIMOrder(
        tenant_id=tenant.id,
        customer_phone=req.customer_phone,
        customer_email=req.customer_email,
        package_code=req.package_code,
        destination=req.destination,
        duration_days=req.duration_days,
        total_price=total_price,
        commission=round(commission, 0),
    )
    db.add(order)
    tenant.booking_count += 1
    await db.commit()
    await db.refresh(order)

    return {
        "success": True,
        "order_id": order.id,
        "package": pkg["name"],
        "total_price": total_price,
        "commission": round(commission, 0),
        "status": "pending",
        "message": f"Đặt eSIM {pkg['name']} cho {req.customer_phone} thành công!",
    }


# --- 7. Dashboard stats ---

@router.get("/dashboard/stats")
async def get_dashboard_stats(db: AsyncSession = Depends(get_db)):
    """Thống kê tổng quan cho admin."""
    total_tenants = await db.scalar(select(func.count(Tenant.id)))
    active_tenants = await db.scalar(
        select(func.count(Tenant.id)).where(Tenant.status == "active")
    )
    pro_count = await db.scalar(
        select(func.count(Tenant.id)).where(Tenant.agent_tier.in_(["pro", "whitelabel"]))
    )

    total_ft = await db.scalar(select(func.count(FastTrackOrder.id)))
    total_esim = await db.scalar(select(func.count(ESIMOrder.id)))

    ft_revenue = await db.scalar(select(func.sum(FastTrackOrder.total_price))) or 0
    esim_revenue = await db.scalar(select(func.sum(ESIMOrder.total_price))) or 0

    return {
        "total_tenants": total_tenants or 0,
        "active_tenants": active_tenants or 0,
        "paid_tenants": pro_count or 0,
        "total_fasttrack_orders": total_ft or 0,
        "total_esim_orders": total_esim or 0,
        "total_revenue": float(ft_revenue + esim_revenue),
        "estimated_monthly_revenue": float((ft_revenue + esim_revenue) * 0.12),  # estimate at 12% commission avg
    }


# --- 8. Payment callback stub ---

@router.post("/payment/callback")
async def payment_callback(
    tenant_id: int = Query(...),
    order_type: str = Query(...),
    order_id: int = Query(...),
    amount: float = Query(...),
    status: str = Query("completed"),
    db: AsyncSession = Depends(get_db),
):
    """Callback thanh toán từ Momo/VNPay (stub)."""
    payment = Payment(
        tenant_id=tenant_id,
        order_type=order_type,
        order_id=order_id,
        amount=amount,
        payment_method="momo",
        transaction_id=f"txn_{secrets.token_hex(8)}",
        status=status,
    )
    db.add(payment)
    await db.commit()

    return {"success": True, "payment_id": payment.id, "status": status}


# ────────────────────────────────────────────────────────────────────
# 9. Chat AI — LLM-powered với Gemini 2.5 Flash streaming
# ────────────────────────────────────────────────────────────────────

@router.post("/chat")
async def smart_chat(req: ChatRequest):
    """Chat với AI — dùng Gemini 2.5 Flash thật, streaming response."""
    sid = req.session_id or str(uuid.uuid4())

    # Get or init session
    if sid not in _chat_sessions:
        _chat_sessions[sid] = []
    history = _chat_sessions[sid]

    today = datetime.now().strftime("%d/%m/%Y")

    try:
        # Try Gemini 2.5 Flash
        gemini_key = os.getenv("GEMINI_API_KEY", "")
        if gemini_key:
            async with httpx.AsyncClient(timeout=30.0) as client:
                system_prompt = f"""Bạn là một Ticketing Manager cấp cao + chuyên gia hàng không (Aviation Expert) của Smart Agent — phòng vé AI thế hệ mới. Hôm nay: {today}

Bạn có KIẾN THỨC CHUYÊN SÂU như 1 nhân viên hàng không lâu năm + 1 trùm ticketing. Trả lời như 1 chuyên gia thực thụ: tự nhiên, chính xác, đi thẳng vấn đề, không giải thích lan man.

===== KIẾN THỨC NỀN (DOMAIN EXPERTISE) =====

### I. MÃ IATA & HÃNG HÀNG KHÔNG VIỆT NAM
- VN = Vietnam Airlines (full-service, hub: HAN/SGN)
- VJ = Vietjet Air (LCC, hub: SGN/HAN)
- QH = Bamboo Airways (hybrid, hub: HAN)
- VU = Vietravel Airlines (LCC, hub: SGN)
- 9G = Sun PhuQuoc Airways (full-service, hub: PQC/SGN/HAN)
  * 9G là full-service: xách tay 7kg + ký gửi 23kg ĐÃ BAO GỒM trong giá vé
  * Khác LCC (VJ/QH/VU) — phải mua thêm hành lý

### II. THỦ TỤC CHECK-IN
- Online: 24h-1h trước giờ bay (VN, VJ, QH), 12h-1h (9G)
- Quầy: mở 3h trước, đóng 40p (domestic), 50p (quốc tế)
- Lên tàu: đóng cửa 15-20p trước giờ bay
- Domestic: CMND/CCCD hoặc passport
- Quốc tế: Passport + visa (nếu cần)
- Trẻ em 2-12: 75% người lớn. Dưới 2: 10% người lớn (ko ghế riêng)

### III. HÀNH LÝ (BAGGAGE ALLOWANCE)
- VN Economy: 1 kiện 23kg + xách tay 7kg
- VN Business: 2 kiện 32kg + xách tay 14kg
- VJ (LCC): xách tay 7kg. Ký gửi mua thêm (15-32kg)
- QH Eco: 1 kiện 23kg + xách tay 7kg
- 9G full-service: xách tay 7kg + ký gửi 23kg (đã bao gồm)
- Quốc tế VN: Economy = 2 kiện 23kg (US/EU/AU/NZ) hoặc 1 kiện 30kg (Asia)
- Pin dự phòng PHẢI xách tay, vật sắc nhọn PHẢI ký gửi

### IV. FARE RULES & ĐẶT VÉ
- Booking class: Y/B/M/H/Q/V/W (Economy), J/C/D/I/Z (Business)
- Thời gian mở bán: 330 ngày (VN), 360 ngày (VJ), 180 ngày (QH)
- Giờ vàng: 0h-6h và Thứ 3-5 (giá rẻ nhất)
- Peak season: Tết (30 ngày trước/sau), 30/4-1/5, 2/9
- Đặt vé: cần đúng tên CMND/passport, KHÔNG SAI 1 KÝ TỰ
- Đổi tên: VN = 0-400K, VJ = MIỄN ĐỔI (mua vé mới)
- Hủy vé: VN = mất 50-100%, VJ = mất 100%
- Đổi ngày: VN = phí chênh + 200-500K, VJ = ko đổi được
- No-show: ko check-in → hủy ngang (có thể charge full)

### V. GIÁ VÉ & TICKETING HACKS
- Vé đoàn (10+): giảm 5-15% tùy hãng
- Đặt 1 chiều rẻ hơn khứ hồi trên 1 số tuyến LCC
- Giá ẩn: hạng thấp nhất (Class V/W) chỉ mở 10-20% ghế
- Book sớm: 60-90 ngày trước = rẻ nhất (trừ Tết)
- Book sát giờ: VJ có thể giảm sâu 0h-6h (xoá tồn)

### VI. SÂN BAY NỘI BÀI (HAN)
- Ga 1 (T1) = domestic (VJ, QH, VU, 9G)
- Ga 2 (T2) = international (VN quốc tế + hãng nước ngoài)
- Fast Track: cả ga T1+T2, onsite 24/7 — ĐỘC QUYỀN
- Phụ thu đêm 23:00-06:00 = +200K/người
- Transit: quốc tế→nội địa tối thiểu 2h, nội địa→nội địa 45p

### VII. DỊCH VỤ SMART AGENT
1. ✈️ Vé máy bay: AGT Cấp 1, giữ chỗ 24h
2. ⚡ Fast Track Nội Bài: 450K / VIP Lounge 650K. Onsite 24/7
3. 📱 eSIM du lịch: 99K-499K. QR tự động
4. 🛂 Visa: tư vấn + hỗ trợ hồ sơ
5. 📄 Hộ chiếu: tư vấn online

### VIII. GÓI CTV
- Free: 8% hoa hồng, 50 vé/tháng
- Pro 199K/tháng: 12%, 300 vé/tháng
- White-label 1.5tr/tháng: 15%, không giới hạn

===== PHONG CÁCH =====
- Xưng "tôi", gọi khách "bạn/anh/chị"
- Nói chuyện như thằng em trong nghề: chân thành, đi thẳng
- Với khách lẻ: tư vấn tận tình
- Với CTV/đại lý: nói chuyện đồng nghiệp
- Khi hỏi "hàng" — mặc định kiểm tra vé, ko hỏi lại
- Luôn gợi ý hành động tiếp theo (CTA) sau mỗi câu
- KHÔNG dùng bảng biểu — dùng bullet list
- KHÔNG giải thích dài dòng — nói đúng trọng tâm, xong chốt"""

                contents = []
                for msg in history[-8:]:
                    role = "model" if msg.get("role") == "assistant" else "user"
                    contents.append({"role": role, "parts": [{"text": msg.get("content", "")}]})
                contents.append({"role": "user", "parts": [{"text": req.message}]})

                payload = {
                    "contents": contents,
                    "systemInstruction": {"parts": [{"text": system_prompt}]},
                    "generationConfig": {
                        "temperature": 0.7,
                        "maxOutputTokens": 2048,
                        "topP": 0.95,
                    },
                }

                url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"
                resp = await client.post(
            url,
            headers={
                "Authorization": f"Bearer {gemini_key}",
                "Content-Type": "application/json",
            },
            json=payload
        )
                data = resp.json()

                candidates = data.get("candidates", [])
                if candidates:
                    parts = candidates[0].get("content", {}).get("parts", [])
                    text = "".join(p.get("text", "") for p in parts)
                else:
                    text = "Xin lỗi, không nhận được phản hồi từ AI."

                # Store in history
                history.append({"role": "user", "content": req.message})
                history.append({"role": "assistant", "content": text})
                if len(history) > 50:
                    _chat_sessions[sid] = history[-50:]

                # Return SSE-style response
                return StreamingResponse(
                    _sse_stream(text, sid),
                    media_type="text/event-stream",
                )

        # Fallback: rule-based responses
        msg_lower = req.message.lower()
        intent = "other"
        if any(kw in msg_lower for kw in ["visa", "hộ chiếu", "passport", "xuất cảnh", "thị thực"]):
            intent = "visa"
        elif any(kw in msg_lower for kw in ["fast track", "fasttrack", "ưu tiên", "vip", "lounge"]):
            intent = "fasttrack"
        elif any(kw in msg_lower for kw in ["esim", "sim", "data", "4g", "5g", "internet"]):
            intent = "esim"
        elif any(kw in msg_lower for kw in ["vé", "bay", "máy bay", "chuyến", "đặt vé"]):
            intent = "flight"
        elif any(kw in msg_lower for kw in ["mở phòng vé", "ctv", "đại lý", "cộng tác viên", "kiếm tiền"]):
            intent = "ctv"

        responses = {
            "flight": "✈️ Tôi có thể giúp bạn tìm vé máy bay. Hãy cho tôi biết:\n• Điểm đi/đến (VD: SG → Đà Nẵng)\n• Ngày bay\n• Số người\n\nVí dụ: *'Vé SG đi Nha Trang thứ 7, 2 người'*",
            "fasttrack": f"⚡ **Fast Track Nội Bài** — Dịch vụ độc quyền!\n\n• Fast Track: 450,000đ/người\n• VIP Lounge: 650,000đ/người\n• Onsite 24/7 — đơn vị duy nhất tại HAN\n• Phụ thu đêm 23:00-06:00: +200,000đ\n\nBạn đi ngày nào? Mấy người?",
            "esim": f"📱 **eSIM du lịch** — Giá từ 99,000đ\n\n• Châu Á 7 ngày: 99,000đ\n• Nhật Bản 7 ngày: 149,000đ\n• Hàn Quốc 7 ngày: 129,000đ\n• Châu Âu 7 ngày: 199,000đ\n• Mỹ 7 ngày: 179,000đ\n• Toàn cầu 30 ngày: 499,000đ\n\nBạn đi nước nào?",
            "visa": "🛂 **Dịch vụ Visa** — Tư vấn miễn phí\n\nTôi có thể tư vấn:\n• Visa Nhật Bản, Hàn Quốc, Trung Quốc\n• Visa Schengen (châu Âu)\n• Visa Mỹ, Úc, Anh\n• Gia hạn visa, chuyển đổi mục đích\n\nBạn quan tâm nước nào?",
            "ctv": "💼 **Mở phòng vé CTV** — MIỄN PHÍ!\n\n• Gói Free: Hoa hồng 8%, 50 vé/tháng\n• Gói Pro 199K/tháng: Hoa hồng 12%, 300 vé\n• White-label 1.5tr/tháng: Hoa hồng 15%, không giới hạn\n\nĐăng ký ngay: bấm nút 'Đăng ký CTV' trên web.\n\nBạn muốn tư vấn thêm?",
        }

        text = responses.get(intent, "Xin chào! Tôi là Smart Agent — trợ lý phòng vé AI.\n\nTôi có thể giúp gì cho bạn hôm nay?\n• ✈️ Đặt vé máy bay\n• ⚡ Fast Track Nội Bài\n• 📱 eSIM du lịch\n• 🛂 Visa & Hộ chiếu\n• 💼 Mở phòng vé CTV\n\nNói 1 câu, tôi lo hết!")
        history.append({"role": "user", "content": req.message})
        history.append({"role": "assistant", "content": text})
        if len(history) > 50:
            _chat_sessions[sid] = history[-50:]

        return StreamingResponse(
            _sse_stream(text, sid),
            media_type="text/event-stream",
        )

    except Exception as e:
        logger.error("Smart chat error: %s", e)
        return StreamingResponse(
            _sse_stream(f"Xin lỗi, hệ thống đang gặp sự cố. Vui lòng thử lại sau. Lỗi: {str(e)}", sid),
            media_type="text/event-stream",
        )


async def _sse_stream(text: str, session_id: str):
    """Stream text as SSE events."""
    # Yield text in chunks for smooth UX
    chunk_size = 10
    for i in range(0, len(text), chunk_size):
        chunk = text[i:i + chunk_size]
        event = {"type": "text", "content": chunk, "session_id": session_id}
        yield f"data: {json.dumps(event)}\n\n"
        await asyncio.sleep(0.02)

    # Done event
    done = {"type": "done", "content": text, "session_id": session_id}
    yield f"data: {json.dumps(done)}\n\n"
    yield "data: [DONE]\n\n"
