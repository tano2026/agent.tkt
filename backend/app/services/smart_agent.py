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

from app.services.rag_service import get_rag_service, init_rag
from app.services.abtrip_client import ABTripClient
from decimal import Decimal
from typing import Optional, List
import re

import httpx

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field
from app.middleware.auth_middleware import get_current_user_or_api_key
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
_session_states: dict[str, dict] = {}


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
async def get_tenant(
    tenant_id: int,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user_or_api_key),
):
    """Thông tin CTV — chỉ xem được chính mình hoặc admin."""
    # IDOR fix: chỉ cho phép xem tenant của chính mình
    if "tenant_id" in user and int(user["tenant_id"]) != tenant_id:
        raise HTTPException(403, "Không có quyền xem thông tin CTV khác")

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
    user: dict = Depends(get_current_user_or_api_key),
):
    """Danh sách CTV — yêu cầu auth (thường dành cho admin)."""
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
async def upgrade_tenant(
    req: UpgradeRequest,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user_or_api_key),
):
    """Nâng cấp lên Pro hoặc White-label."""
    # IDOR fix: chỉ được upgrade chính mình
    if "tenant_id" in user and int(user["tenant_id"]) != req.tenant_id:
        raise HTTPException(403, "Không có quyền nâng cấp CTV khác")

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
async def create_fasttrack(
    req: FastTrackRequest,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user_or_api_key),
):
    """Đặt Fast Track / VIP Lounge."""
    # IDOR fix: chỉ được đặt cho chính tenant của mình
    if "tenant_id" in user and int(user["tenant_id"]) != req.tenant_id:
        raise HTTPException(403, "Không có quyền đặt dịch vụ cho CTV khác")

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
    user: dict = Depends(get_current_user_or_api_key),
):
    """Danh sách Fast Track orders — chỉ xem được order của chính mình."""
    # IDOR fix: tự động giới hạn theo tenant_id từ JWT
    if "tenant_id" in user:
        query_tenant_id = int(user["tenant_id"])
    else:
        query_tenant_id = tenant_id

    query = select(FastTrackOrder).where(FastTrackOrder.tenant_id == query_tenant_id)
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
async def create_esim(
    req: ESIMRequest,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user_or_api_key),
):
    """Đặt eSIM du lịch."""
    # IDOR fix: chỉ được đặt cho chính tenant của mình
    if "tenant_id" in user and int(user["tenant_id"]) != req.tenant_id:
        raise HTTPException(403, "Không có quyền đặt dịch vụ cho CTV khác")

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
async def get_dashboard_stats(
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user_or_api_key),
):
    """Thống kê tổng quan — yêu cầu auth."""
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
    user: dict = Depends(get_current_user_or_api_key),
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
# Flight search helpers (AGT integration)
# ────────────────────────────────────────────────────────────────────

_AIRPORT_ALIAS = {
    "sg": "SGN", "sgn": "SGN", "sài gòn": "SGN", "saigon": "SGN", "hcm": "SGN", "tp hcm": "SGN", "tphcm": "SGN", "hồ chí minh": "SGN", "thành phố hồ chí minh": "SGN",
    "hn": "HAN", "han": "HAN", "hà nội": "HAN", "hanoi": "HAN",
    "đn": "DAD", "dad": "DAD", "đà nẵng": "DAD", "danang": "DAD",
    "nt": "CXR", "nha trang": "CXR", "nhatrang": "CXR", "cam ranh": "CXR",
    "pq": "PQC", "phú quốc": "PQC", "phu quoc": "PQC",
    "hp": "HPH", "hải phòng": "HPH", "haiphong": "HPH",
    "huế": "HUI", "hue": "HUI",
    "dl": "DLI", "đà lạt": "DLI", "dalat": "DLI",
    "vt": "VCA", "vũng tàu": "VCS", "vung tau": "VCS", "côn đảo": "VCS",
    "bm": "BMV", "buôn mê": "BMV", "buon me": "BMV",
    "thanh hóa": "THD", "thanh hoa": "THD",
    "vđ": "VDH", "vinh": "VII", "đồng hới": "VDH", "dong hoi": "VDH",
    "quy nhơn": "UIH", "quy nhon": "UIH",
    "tuy hoà": "TBB", "tuy hoa": "TBB",
    "pleiku": "PXU",
    "cần thơ": "VCA", "can tho": "VCA",
    "rách giá": "VKG",
    "cà mau": "CAH",
    # Direction words (default to HAN/SGN hubs)
    "bắc": "HAN", "miền bắc": "HAN", "ngoài bắc": "HAN",
    "nam": "SGN", "miền nam": "SGN", "trong nam": "SGN",
    "miền trung": "DAD", "trung": "DAD",
}

def _extract_flight_params(texts: list[str]) -> dict | None:
    """Extract flight search parameters from a list of user messages."""
    combined = " ".join(texts).lower()
    params = {"from": None, "to": None, "date": None, "adt": 1}

    # Find origin-destination pairs
    od_patterns = [
        # "từ HN đến SG" / "bay từ hn đi sg" / "đi từ hn vào sg"
        r"(?:từ|bay từ|đi từ|chuyến bay từ)\s+(\S+(?:\s+\S+)?)\s+(?:đến|đi|sang|vào|ra|về|vô)\s+(\S+(?:\s+\S+)?)",
        # Direction-aware: "bay nam ra bắc" / "bay hn vô sg" / "bay bắc vào nam"
        r"(?:bay|đi)\s+(\S+(?:\s+\S+)?)\s+(?:ra|vào|về|vô)\s+(\S+(?:\s+\S+)?)",
        # Reversed: "đi SG từ HN" / "đi sg từ hn"
        r"đi\s+(\S+(?:\s+\S+)?)\s+từ\s+(\S+(?:\s+\S+)?)",
        # "HN -> SG" / "HN→SG" (arrow, no-space or with space) / "HN - SG" / "HN — SG"
        r"(\S+)\s*(?:=>|->|→|—|-)\s*(\S+)",
        # "vé HN đi SG" / "vé từ HN sang SG"
        r"vé\s+(?:từ\s+)?(\S+(?:\s+\S+)?)\s+(?:đi|đến|sang|vào|ra|về|vô)\s+(\S+(?:\s+\S+)?)",
    ]
    for pat in od_patterns:
        m = re.search(pat, combined)
        if m:
            params["from"] = _AIRPORT_ALIAS.get(m.group(1).strip(), m.group(1).strip().upper()[:3])
            params["to"] = _AIRPORT_ALIAS.get(m.group(2).strip(), m.group(2).strip().upper()[:3])
            break

    # Date extraction
    today = datetime.now()
    date_pats = [
        r"(\d{1,2})[/-](\d{1,2})(?:[/-](\d{2,4}))?",
        r"ngày\s+(\d{1,2})\s*(?:tháng\s*)?(\d{1,2})",
        r"(thứ \d\s*(?:tuần sau)|hôm nay|mai|ngày mai|mốt|ngày mốt|kia|ngày kia|cuối tuần)",
    ]
    for pat in date_pats:
        m = re.search(pat, combined)
        if m:
            if len(m.groups()) >= 2 and m.group(2) is not None:
                d = int(m.group(1)); mo = int(m.group(2))
                yr = int(m.group(3)) if m.lastindex and m.lastindex >= 3 and m.group(3) else today.year
                if yr < 100: yr += 2000
                params["date"] = f"{d:02d}{mo:02d}{yr}"
            else:
                raw = m.group(1)
                if raw in ("hôm nay", "today"):
                    params["date"] = today.strftime("%d%m%Y")
                elif raw in ("mai", "ngày mai", "tomorrow"):
                    dt = today + timedelta(days=1)
                    params["date"] = dt.strftime("%d%m%Y")
                elif raw in ("mốt", "ngày mốt", "kia", "ngày kia"):
                    dt = today + timedelta(days=2)
                    params["date"] = dt.strftime("%d%m%Y")
                elif raw == "cuối tuần":
                    # Next Saturday
                    days_ahead = 5 - today.weekday()  # Mon=0, Sat=5
                    if days_ahead <= 0: days_ahead += 7
                    dt = today + timedelta(days=days_ahead)
                    params["date"] = dt.strftime("%d%m%Y")
                elif "thứ" in raw and "tuần sau" in raw:
                    # "thứ 6 tuần sau"
                    wd = int(re.search(r"thứ (\d)", raw).group(1))
                    # weekday: Mon=0 -> thứ 2=0, thứ 3=1,... chủ nhật=6
                    target = wd - 2 if wd > 1 else 6  # thứ 2->0, thứ 3->1..., chủ nhật(thứ 8/chủ nhật)->6
                    if target < 0: target = 0
                    days_until = (target - today.weekday()) % 7 + 7  # next week
                    dt = today + timedelta(days=days_until)
                    params["date"] = dt.strftime("%d%m%Y")
            break

    # Pax count
    pax_m = re.search(r"(\d+)\s*(?:người|khách|pax|ng)", combined)
    if pax_m:
        params["adt"] = int(pax_m.group(1))

    # Validate
    if params["from"] and params["to"] and params["date"]:
        return params
    return None


def _format_flight_results(data: dict, params: dict) -> str:
    """Format AGT SearchFlight response to display text."""
    if not data.get("Success"):
        msg = data.get("Message", "Không tìm thấy chuyến bay phù hợp")
        return f"❌ {msg}"

    list_group = data.get("ListGroup", [])
    if not list_group:
        return "❌ Không có chuyến bay nào cho hành trình này."

    _d = params.get("date", "")
    _date_disp = f"{_d[:2]}/{_d[2:4]}/{_d[4:]}" if len(_d) == 8 else _d
    lines = [f"✈️ **{params['from']} → {params['to']}** | {_date_disp} | {params['adt']} khách\n"]

    shown = 0
    for grp in list_group:
        air_options = grp.get("ListAirOption", [])
        if not air_options:
            continue
        for ao in air_options:
            airline = ao.get("Airline", "?")
            # Get flight info from first flight option
            flt_opts = ao.get("ListFlightOption", [])
            flt_info = ""
            if flt_opts:
                flts = flt_opts[0].get("ListFlight", [])
                if flts:
                    f0 = flts[0]
                    fn = f0.get("FlightNumber", "?")
                    start = (f0.get("StartDate") or "")[-4:]  # HHMM
                    end = (f0.get("EndDate") or "")[-4:]
                    flt_info = f"{airline}{fn} {start}→{end}"

            fare_opts = ao.get("ListFareOption", [])
            if not fare_opts:
                continue
            cheapest = fare_opts[0]
            price = cheapest.get("TotalFare", 0)
            family = cheapest.get("FareFamily", "")
            cabin = cheapest.get("CabinName", "")
            avail = cheapest.get("Availability", 0)

            if flt_info:
                lines.append(f"🏷 {flt_info}")
            lines.append(f"  💰 {price:,.0f}đ | {family} ({cabin}) | còn {avail} chỗ")

            # Show 2nd fare if exists (different class)
            if len(fare_opts) > 1:
                f1 = fare_opts[1]
                if f1.get("CabinName") != cabin:
                    lines.append(f"  💰 {f1.get('TotalFare', 0):,.0f}đ | {f1.get('FareFamily', '')} ({f1.get('CabinName', '')}) | còn {f1.get('Availability', 0)} chỗ")

            lines.append("")
            shown += 1
            if shown >= 10:
                break
        if shown >= 10:
            break

    if not shown:
        lines.append("_(không có option vé nào)_")

    lines.append("\n📌 Chọn chuyến để giữ chỗ — tôi sẽ hỗ trợ đặt vé.")
    return "\n".join(lines)


def _get_structured_flights(data: dict, params: dict) -> dict:
    """Parse raw flight results to structured dict for frontend card rendering."""
    if not data.get("Success"):
        return {"flights": [], "from": params.get("from"), "to": params.get("to")}

    list_group = data.get("ListGroup", [])
    flights = []
    for grp in list_group:
        air_options = grp.get("ListAirOption", [])
        for ao in air_options:
            airline = ao.get("Airline", "?")
            flt_opts = ao.get("ListFlightOption", [])
            fn = "?"
            start = ""
            end = ""
            if flt_opts:
                flts = flt_opts[0].get("ListFlight", [])
                if flts:
                    f0 = flts[0]
                    fn = f0.get("FlightNumber", "?")
                    start = (f0.get("StartDate") or "")[-4:]  # HHMM
                    end = (f0.get("EndDate") or "")[-4:]

            fare_opts = ao.get("ListFareOption", [])
            if not fare_opts:
                continue
            cheapest = fare_opts[0]
            price = cheapest.get("TotalFare", 0)
            family = cheapest.get("FareFamily", "")
            cabin = cheapest.get("CabinName", "")
            avail = cheapest.get("Availability", 0)

            time_disp = f"{start[:2]}:{start[2:]} → {end[:2]}:{end[2:]}" if start and end else "Xem chi tiết"

            flights.append({
                "airline": airline,
                "flight_number": f"{airline}{fn}",
                "route": f"{params['from']}→{params['to']}",
                "time": time_disp,
                "price": price,
                "cabin": f"{family} ({cabin})",
                "avail": avail
            })
    return {"flights": flights, "from": params.get("from"), "to": params.get("to"), "date": params.get("date")}


# ────────────────────────────────────────────────────────────────────
# 9. Chat AI — LLM-powered với Gemini 2.5 Flash streaming
# ────────────────────────────────────────────────────────────────────

@router.post("/chat")
async def smart_chat(req: ChatRequest):
    """Chat với AI — dùng Gemini 2.5 Flash + RAG Antigravity, streaming response."""
    sid = req.session_id or str(uuid.uuid4())

    # Get or init session
    if sid not in _chat_sessions:
        _chat_sessions[sid] = []
    history = _chat_sessions[sid]

    # Initialize session state if not exists
    if sid not in _session_states:
        _session_states[sid] = {
            "flight": None,
            "route": None,
            "price": 0,
            "date": None,
            "time": None,
            "pax_name": None,
            "pax_dob": None,
            "pax_email": None,
            "pax_phone": None,
            "ancillaries": "Không đăng ký",
            "state": "idle"
        }
    state = _session_states[sid]

    user_msg = req.message.strip()

    # 1. Detect "Đặt vé <FlightNumber> <Route> <Price> <Date> <Time>" (e.g. from frontend select button)
    import re
    select_match = re.match(r"^Đặt vé\s+(\S+)\s+(\S+)(?:\s+(\d+))?(?:\s+(\d+))?(?:\s+(\S+))?", user_msg, re.IGNORECASE)
    if select_match:
        state["flight"] = select_match.group(1).upper()
        state["route"] = select_match.group(2).upper()
        state["price"] = int(select_match.group(3)) if select_match.group(3) else 0
        state["date"] = select_match.group(4)
        state["time"] = select_match.group(5)
        state["state"] = "awaiting_pax_info"
        
        state["pax_name"] = None
        state["pax_dob"] = None
        state["pax_email"] = None
        state["pax_phone"] = None
        state["ancillaries"] = "Không đăng ký"
        
        raw_date = state.get("date") or ""
        date_disp = f"{raw_date[0:2]}/{raw_date[2:4]}/{raw_date[4:]}" if len(raw_date) == 8 else raw_date
        raw_time = state.get("time") or ""
        time_disp = raw_time.replace("→", " → ")
        
        reply = (
            f"Cảm ơn bạn đã chọn chuyến bay **{state['flight']}** ({state['route']}) ngày **{date_disp}** lúc **{time_disp}**.\n\n"
            f"Để tôi tiến hành giữ chỗ, vui lòng cung cấp thông tin người bay bao gồm:\n"
            f"• **Họ và tên**\n"
            f"• **Ngày sinh**\n"
            f"• **Email**\n"
            f"• **Số điện thoại**\n\n"
            f"Bạn có thể gõ tự nhiên một câu chứa các thông tin này (Ví dụ: *Nguyễn Văn A, 20/10/1990, email@gmail.com, 0987654321*)."
        )
        history.append({"role": "user", "content": user_msg})
        history.append({"role": "assistant", "content": reply})
        return StreamingResponse(_sse_stream(reply, sid), media_type="text/event-stream")

    # 1.5. eSIM Booking State Machine
    # Trigger eSIM flow (matches esim, sim, check sim, tao sim, etc.)
    import re
    is_sim_intent = any(w in user_msg.lower() for w in ("esim", "sim du lịch", "mua sim", "đặt sim", "check sim", "tạo sim", "cần sim", "gói sim")) or re.search(r"\bsim\b", user_msg.lower())
    if is_sim_intent and not state.get("state", "").startswith("awaiting_esim"):
        state["esim_days"] = None
        state["esim_package"] = None
        
        # Check if country is already specified in initial query
        country = None
        for c in ("Hàn Quốc", "Nhật Bản", "Thái Lan", "Châu Âu", "Mỹ", "Trung Quốc", "Singapore", "Malaysia"):
            if c.lower() in user_msg.lower():
                country = c
                break
                
        if country:
            state["esim_country"] = country
            state["state"] = "awaiting_esim_days"
            reply = (
                f"📅 **BẠN ĐI {country.upper()} TRONG MẤY NGÀY?**\n\n"
                f"Vui lòng click chọn số ngày cho chuyến đi của bạn:\n\n"
                f"<button class=\"header-btn-outline\" style=\"padding: 8px 16px; border-radius: 8px; border: 1px solid var(--border); background: transparent; color: var(--text); cursor: pointer;\" onclick=\"sendSuggestion('Tôi đi {country} 5 ngày')\">📅 5 ngày</button>"
                f"<button class=\"header-btn-outline\" style=\"margin-left: 8px; padding: 8px 16px; border-radius: 8px; border: 1px solid var(--border); background: transparent; color: var(--text); cursor: pointer;\" onclick=\"sendSuggestion('Tôi đi {country} 7 ngày')\">📅 7 ngày</button>"
                f"<button class=\"header-btn-outline\" style=\"margin-left: 8px; padding: 8px 16px; border-radius: 8px; border: 1px solid var(--border); background: transparent; color: var(--text); cursor: pointer;\" onclick=\"sendSuggestion('Tôi đi {country} 10 ngày')\">📅 10 ngày</button>"
                f"<button class=\"header-btn-outline\" style=\"margin-left: 8px; padding: 8px 16px; border-radius: 8px; border: 1px solid var(--border); background: transparent; color: var(--text); cursor: pointer;\" onclick=\"sendSuggestion('Tôi đi {country} 15 ngày')\">📅 15 ngày</button>"
            )
        else:
            state["state"] = "awaiting_esim_country"
            state["esim_country"] = None
            reply = (
                f"📶 **BẠN MUỐN MUA eSIM DU LỊCH ĐI NƯỚC NÀO?**\n\n"
                f"Vui lòng chọn quốc gia dưới đây hoặc gõ tên nước bạn muốn đến:\n\n"
                f"<button class=\"header-btn-outline\" style=\"padding: 8px 16px; border-radius: 8px; border: 1px solid var(--border); background: transparent; color: var(--text); cursor: pointer;\" onclick=\"sendSuggestion('Mua eSIM đi Hàn Quốc')\">🇰🇷 Hàn Quốc</button>"
                f"<button class=\"header-btn-outline\" style=\"margin-left: 8px; padding: 8px 16px; border-radius: 8px; border: 1px solid var(--border); background: transparent; color: var(--text); cursor: pointer;\" onclick=\"sendSuggestion('Mua eSIM đi Nhật Bản')\">🇯🇵 Nhật Bản</button>"
                f"<button class=\"header-btn-outline\" style=\"margin-left: 8px; padding: 8px 16px; border-radius: 8px; border: 1px solid var(--border); background: transparent; color: var(--text); cursor: pointer;\" onclick=\"sendSuggestion('Mua eSIM đi Thái Lan')\">🇹🇭 Thái Lan</button>"
                f"<button class=\"header-btn-outline\" style=\"margin-left: 8px; padding: 8px 16px; border-radius: 8px; border: 1px solid var(--border); background: transparent; color: var(--text); cursor: pointer;\" onclick=\"sendSuggestion('Mua eSIM đi Châu Âu')\">🇪🇺 Châu Âu</button>"
                f"<button class=\"header-btn-outline\" style=\"margin-left: 8px; padding: 8px 16px; border-radius: 8px; border: 1px solid var(--border); background: transparent; color: var(--text); cursor: pointer;\" onclick=\"sendSuggestion('Mua eSIM đi Mỹ')\">🇺🇸 Mỹ</button>"
            )
        history.append({"role": "user", "content": user_msg})
        history.append({"role": "assistant", "content": reply})
        return StreamingResponse(_sse_stream(reply, sid), media_type="text/event-stream")

    # Handle awaiting_esim_country
    if state.get("state") == "awaiting_esim_country":
        # Extract country
        country = None
        for c in ("Hàn Quốc", "Nhật Bản", "Thái Lan", "Châu Âu", "Mỹ", "Trung Quốc", "Singapore", "Malaysia"):
            if c.lower() in user_msg.lower():
                country = c
                break
        if not country:
            # Fallback extract last word
            country = user_msg.split()[-1]
        
        state["esim_country"] = country
        state["state"] = "awaiting_esim_days"
        reply = (
            f"📅 **BẠN ĐI {country.upper()} TRONG MẤY NGÀY?**\n\n"
            f"Vui lòng click chọn số ngày cho chuyến đi của bạn:\n\n"
            f"<button class=\"header-btn-outline\" style=\"padding: 8px 16px; border-radius: 8px; border: 1px solid var(--border); background: transparent; color: var(--text); cursor: pointer;\" onclick=\"sendSuggestion('Tôi đi {country} 5 ngày')\">📅 5 ngày</button>"
            f"<button class=\"header-btn-outline\" style=\"margin-left: 8px; padding: 8px 16px; border-radius: 8px; border: 1px solid var(--border); background: transparent; color: var(--text); cursor: pointer;\" onclick=\"sendSuggestion('Tôi đi {country} 7 ngày')\">📅 7 ngày</button>"
            f"<button class=\"header-btn-outline\" style=\"margin-left: 8px; padding: 8px 16px; border-radius: 8px; border: 1px solid var(--border); background: transparent; color: var(--text); cursor: pointer;\" onclick=\"sendSuggestion('Tôi đi {country} 10 ngày')\">📅 10 ngày</button>"
            f"<button class=\"header-btn-outline\" style=\"margin-left: 8px; padding: 8px 16px; border-radius: 8px; border: 1px solid var(--border); background: transparent; color: var(--text); cursor: pointer;\" onclick=\"sendSuggestion('Tôi đi {country} 15 ngày')\">📅 15 ngày</button>"
        )
        history.append({"role": "user", "content": user_msg})
        history.append({"role": "assistant", "content": reply})
        return StreamingResponse(_sse_stream(reply, sid), media_type="text/event-stream")

    # Handle awaiting_esim_days
    if state.get("state") == "awaiting_esim_days":
        # Extract days
        import re
        days_match = re.search(r"(\d+)\s*ngày", user_msg, re.IGNORECASE)
        days = int(days_match.group(1)) if days_match else 7
        
        state["esim_days"] = days
        state["state"] = "awaiting_esim_package"
        
        country = state.get("esim_country", "Nhật Bản")
        
        # Calculate dynamic prices based on region
        c_lower = country.lower()
        if any(w in c_lower for w in ("thái lan", "singapore", "malaysia", "đông nam á")):
            p1, p3, p_unlim = 12000 * days, 18000 * days, 28000 * days
        elif any(w in c_lower for w in ("hàn quốc", "nhật bản", "trung quốc", "châu á")):
            p1, p3, p_unlim = 17000 * days, 25000 * days, 38000 * days
        else:
            p1, p3, p_unlim = 25000 * days, 35000 * days, 55000 * days
            
        p1 = max(79000, (p1 // 1000) * 1000)
        p3 = max(119000, (p3 // 1000) * 1000)
        p_unlim = max(189000, (p_unlim // 1000) * 1000)
        
        reply = (
            f"📶 **CHỌN GÓI CƯỚC eSIM ĐI {country.upper()} ({days} NGÀY)**\n\n"
            f"Tôi xin gửi bạn 3 gói cước dữ liệu tốc độ cao tối ưu nhất:\n\n"
            f"<div style=\"display: flex; flex-direction: column; gap: 8px; margin-top: 10px;\">"
            f"  <div style=\"display: flex; align-items: center; justify-content: space-between; padding: 10px; border-radius: 8px; border: 1px solid var(--border); background: rgba(0,0,0,0.02);\">"
            f"    <div style=\"text-align: left;\">"
            f"      <div style=\"font-weight: 700; font-size: 13px; color: var(--text);\">Gói Tiết Kiệm (1GB/Ngày)</div>"
            f"      <div style=\"font-size: 11px; color: var(--text-muted);\">Phù hợp check bản đồ, nhắn tin chat</div>"
            f"    </div>"
            f"    <button class=\"book-btn\" style=\"padding: 6px 12px; font-size: 11px; border-radius: 4px; cursor: pointer;\" onclick=\"sendSuggestion('Đặt eSIM {country} {days}ngày gói 1GB/ngày {p1}')\">{p1:,}đ</button>"
            f"  </div>"
            f"  <div style=\"display: flex; align-items: center; justify-content: space-between; padding: 10px; border-radius: 8px; border: 1px solid var(--border); background: rgba(0,0,0,0.02);\">"
            f"    <div style=\"text-align: left;\">"
            f"      <div style=\"font-weight: 700; font-size: 13px; color: var(--text);\">Gói Phổ Thông (3GB/Ngày)</div>"
            f"      <div style=\"font-size: 11px; color: var(--text-muted);\">Thoải mái lướt web, đăng ảnh, video call</div>"
            f"    </div>"
            f"    <button class=\"book-btn\" style=\"padding: 6px 12px; font-size: 11px; border-radius: 4px; cursor: pointer;\" onclick=\"sendSuggestion('Đặt eSIM {country} {days}ngày gói 3GB/ngày {p3}')\">{p3:,}đ</button>"
            f"  </div>"
            f"  <div style=\"display: flex; align-items: center; justify-content: space-between; padding: 10px; border-radius: 8px; border: 1px solid var(--border); background: rgba(0,0,0,0.02);\">"
            f"    <div style=\"text-align: left;\">"
            f"      <div style=\"font-weight: 700; font-size: 13px; color: var(--text);\">Gói Không Giới Hạn (Unlimited)</div>"
            f"      <div style=\"font-size: 11px; color: var(--text-muted);\">Data tẹt ga tốc độ cao không lo hết mạng</div>"
            f"    </div>"
            f"    <button class=\"book-btn\" style=\"padding: 6px 12px; font-size: 11px; border-radius: 4px; cursor: pointer;\" onclick=\"sendSuggestion('Đặt eSIM {country} {days}ngày gói Unlimited {p_unlim}')\">{p_unlim:,}đ</button>"
            f"  </div>"
            f"</div>"
            f"<div style=\"margin-top: 12px;\">"
            f"  <button class=\"header-btn-outline\" style=\"width: 100%; padding: 8px; border-radius: 8px; border: 1px solid var(--border); background: transparent; font-weight: bold; cursor: pointer; color: var(--text);\" onclick=\"sendSuggestion('Hủy bỏ')\">❌ Hủy</button>"
            f"</div>"
        )
        history.append({"role": "user", "content": user_msg})
        history.append({"role": "assistant", "content": reply})
        return StreamingResponse(_sse_stream(reply, sid), media_type="text/event-stream")

    # Handle awaiting_esim_package
    import re
    esim_match = re.match(r"^Đặt eSIM\s+(.+)\s+(\d+)ngày\s+gói\s+(.+)\s+(\d+)", user_msg, re.IGNORECASE)
    if esim_match or state.get("state") == "awaiting_esim_package":
        if esim_match:
            state["esim_country"] = esim_match.group(1).strip()
            state["esim_days"] = int(esim_match.group(2))
            state["esim_package"] = esim_match.group(3).strip()
            state["price"] = int(esim_match.group(4))
        
        state["state"] = "awaiting_esim_confirm"
        price_disp = f"{state['price']:,}đ"
        
        name_disp = state.get("pax_name") or "Nguyễn Văn A"
        email_disp = state.get("pax_email") or "customer@gmail.com"
        phone_disp = state.get("pax_phone") or "0987654321"
        
        reply = (
            f"📝 **XÁC NHẬN ĐĂNG KÝ eSIM DU LỊCH**\n\n"
            f"• **Quốc gia:** {state['esim_country']}\n"
            f"• **Thời hạn:** {state['esim_days']} ngày\n"
            f"• **Gói cước:** {state['esim_package']}\n"
            f"• **Email nhận mã QR:** {email_disp}\n"
            f"• **Số điện thoại nhận SMS:** {phone_disp}\n"
            f"• **Tổng thanh toán:** **{price_disp}**\n\n"
            f"👉 Nhận eSIM tự động qua Email và SMS sau khi thanh toán. Xác nhận đặt mua?\n\n"
            f"<button class=\"book-btn\" style=\"padding: 8px 16px; border-radius: 8px; font-weight: bold; cursor: pointer;\" onclick=\"sendSuggestion('Xác nhận đặt eSIM')\">✅ Xác nhận đặt mua</button>"
            f"<button class=\"header-btn-outline\" style=\"margin-left: 8px; padding: 8px 16px; border-radius: 8px; border: 1px solid var(--border); background: transparent; color: var(--text); cursor: pointer;\" onclick=\"sendSuggestion('Hủy bỏ')\">❌ Hủy</button>"
        )
        history.append({"role": "user", "content": user_msg})
        history.append({"role": "assistant", "content": reply})
        return StreamingResponse(_sse_stream(reply, sid), media_type="text/event-stream")

    # Handle confirming eSIM
    if state.get("state") == "awaiting_esim_confirm" and any(w in user_msg.lower() for w in ("xác nhận", "đồng ý", "ok", "yes", "confirm", "chốt")):
        import random
        pnr = "ESIM" + "".join(random.choices("0123456789", k=6))
        price_disp = f"{state['price']:,}đ"
        
        reply = (
            f"🎉 **ĐẶT eSIM THÀNH CÔNG!**\n\n"
            f"• **Mã đơn hàng:** **{pnr}**\n"
            f"• **Quốc gia:** {state['esim_country']}\n"
            f"• **Gói cước:** {state['esim_package']} ({state['esim_days']} ngày)\n"
            f"• **Tổng thanh toán:** **{price_disp}**\n\n"
            f"👉 Vui lòng thanh toán chuyển khoản dưới đây để nhận mã QR kích hoạt eSIM tự động:"
            f"\n\n<button class=\"book-btn\" style=\"padding: 8px 16px; border-radius: 8px; font-weight: bold; background: var(--gold); cursor: pointer;\" onclick=\"sendSuggestion('Thanh toán {pnr}')\">💳 Thanh toán ngay</button>"
        )
        state["pnr"] = pnr
        state["state"] = "hold_success"
        history.append({"role": "user", "content": user_msg})
        history.append({"role": "assistant", "content": reply})
        return StreamingResponse(_sse_stream(reply, sid), media_type="text/event-stream")

    # 2. Handle Cancel booking request
    if (state["state"] in ("awaiting_pax_info", "awaiting_ancillaries", "awaiting_confirm") or state.get("state", "").startswith("awaiting_esim")) and any(w in user_msg.lower() for w in ("hủy", "cancel", "từ chối", "không đồng ý", "hủy bỏ")):
        state["state"] = "idle"
        reply = "Đã hủy tiến trình giao dịch. Tôi có thể giúp gì khác cho bạn?"
        history.append({"role": "user", "content": user_msg})
        history.append({"role": "assistant", "content": reply})
        return StreamingResponse(_sse_stream(reply, sid), media_type="text/event-stream")

    # 3. Handle Payment inquiry with dynamic deadline & cross-sell options
    pay_match = re.match(r"^Thanh toán\s+(\w+)", user_msg, re.IGNORECASE)
    if pay_match or (state["state"] == "hold_success" and "thanh toán" in user_msg.lower()):
        pnr = pay_match.group(1).upper() if pay_match else state.get("pnr", "PNR123")
        price = state.get("price", 0)
        price_disp = f"{price:,}đ" if price else "Liên hệ"
        qr_url = f"https://img.vietqr.io/image/acb-9999998888-compact.png?amount={price}&addInfo=Thanh%20toan%20booking%20{pnr}&accountName=CONG%20TY%20ABTRIP"
        
        deadline = (datetime.now() + timedelta(hours=4)).strftime("%H:%M ngày %d/%m/%Y")
        
        reply = (
            f"💳 **THÔNG TIN THANH TOÁN CHUYỂN KHOẢN**\n\n"
            f"• **Ngân hàng:** Á Châu (ACB)\n"
            f"• **Số tài khoản:** **9999998888**\n"
            f"• **Chủ tài khoản:** CONG TY ABTRIP\n"
            f"• **Số tiền:** **{price_disp}**\n"
            f"• **Hạn thanh toán:** **{deadline}**\n"
            f"• **Nội dung chuyển khoản:** **{pnr}**\n\n"
            f"👉 Quét mã QR dưới đây để thanh toán nhanh qua ứng dụng Ngân hàng của bạn:\n\n"
            f"<img src=\"{qr_url}\" style=\"max-width: 250px; border-radius: 12px; box-shadow: 0 4px 12px rgba(0,0,0,0.1); margin-top: 10px; border: 1px solid var(--border);\" />\n\n"
            f"---\n\n"
            f"🎁 **ƯU ĐÃI ĐI KÈM HÀNH TRÌNH CỦA BẠN:**\n"
            f"Để chuẩn bị tốt nhất cho chuyến đi của bạn, bạn có muốn đăng ký thêm dịch vụ ưu đãi giảm giá 10% này không?\n"
            f"• ⚡ **Fast Track Nội Bài** (Đi lối nhanh VIP)\n"
            f"• 📱 **eSIM du lịch** kết nối mạng 4G tốc độ cao\n"
            f"• 🏨 **Đặt phòng Khách sạn** giá tốt tại điểm đến\n"
            f"• 🛂 **Tư vấn Visa / Hộ chiếu** nhanh chóng\n\n"
            f"👉 Click để đăng ký nhanh:\n\n"
            f"<button class=\"header-btn-outline\" style=\"padding: 6px 12px; border-radius: 8px; border: 1px solid var(--border); background: transparent; cursor: pointer;\" onclick=\"sendSuggestion('Tôi muốn đặt dịch vụ Fast Track')\">⚡ Đặt Fast Track</button>"
            f"<button class=\"header-btn-outline\" style=\"margin-left: 6px; padding: 6px 12px; border-radius: 8px; border: 1px solid var(--border); background: transparent; cursor: pointer;\" onclick=\"sendSuggestion('Tôi muốn mua eSIM du lịch')\">📱 eSIM du lịch</button>"
            f"<button class=\"header-btn-outline\" style=\"margin-left: 6px; padding: 6px 12px; border-radius: 8px; border: 1px solid var(--border); background: transparent; cursor: pointer;\" onclick=\"sendSuggestion('Tư vấn Visa và Khách sạn')\">🏨 Visa & Khách sạn</button>"
        )
        state["state"] = "idle"
        history.append({"role": "user", "content": user_msg})
        history.append({"role": "assistant", "content": reply})
        return StreamingResponse(_sse_stream(reply, sid), media_type="text/event-stream")

    # 3.6. Handle "Xem sơ đồ ghế" or "Chọn ghế"
    if "sơ đồ ghế" in user_msg.lower() or "sơ đồ chỗ" in user_msg.lower():
        reply = (
            f"🗺️ **SƠ ĐỒ CHỖ NGỒI MÁY BAY ({state.get('flight', 'Flight')})**\n\n"
            f"Vui lòng click chọn ghế mong muốn bên dưới để thêm vào đặt chỗ:\n\n"
            f"<div style=\"display: flex; justify-content: center; gap: 12px; font-size: 10px; color: var(--text-muted); margin-bottom: 12px;\">"
            f"  <div style=\"display: flex; align-items: center; gap: 4px;\"><span style=\"display: inline-block; width: 12px; height: 12px; border-radius: 3px; background: rgba(0,0,0,0.05); border: 1px solid var(--border);\"></span> Trống</div>"
            f"  <div style=\"display: flex; align-items: center; gap: 4px;\"><span style=\"display: inline-block; width: 12px; height: 12px; border-radius: 3px; background: #e6a23c; border: 1px solid #e6a23c;\"></span> Chân rộng (+80k)</div>"
            f"  <div style=\"display: flex; align-items: center; gap: 4px;\"><span style=\"display: inline-block; width: 12px; height: 12px; border-radius: 3px; background: #e0e0e0; color: #999; text-align: center; line-height: 12px; font-size: 8px;\">X</span> Đã chọn</div>"
            f"</div>"
            f"<div style=\"max-width: 220px; margin: 0 auto; background: #fff; border-radius: 20px 20px 8px 8px; border: 2px solid var(--border); padding: 20px 10px 10px 10px; position: relative; box-shadow: 0 4px 10px rgba(0,0,0,0.03);\">"
            f"  <div style=\"font-size: 9px; color: var(--text-muted); font-weight: 700; margin-bottom: 10px; text-transform: uppercase; text-align: center;\">✈️ Đầu máy bay (Front)</div>"
            f"  <div style=\"display: flex; flex-direction: column; gap: 6px;\">"
            f"    <div style=\"display: flex; align-items: center; justify-content: space-between;\">"
            f"      <span style=\"font-size: 9px; width: 12px; color: var(--text-muted); font-weight: bold;\">1</span>"
            f"      <div style=\"display: flex; gap: 4px;\">"
            f"        <button class=\"book-btn\" style=\"width: 24px; height: 24px; font-size: 9px; font-weight: bold; background: #fdf6ec; border: 1px solid #f5dab1; color: #e6a23c; border-radius: 4px; padding: 0; cursor: pointer;\" onclick=\"sendSuggestion('Chọn ghế 1A chân rộng')\">1A</button>"
            f"        <button class=\"book-btn\" style=\"width: 24px; height: 24px; font-size: 9px; font-weight: bold; background: #fdf6ec; border: 1px solid #f5dab1; color: #e6a23c; border-radius: 4px; padding: 0; cursor: pointer;\" onclick=\"sendSuggestion('Chọn ghế 1B chân rộng')\">1B</button>"
            f"        <button style=\"width: 24px; height: 24px; font-size: 9px; background: #e0e0e0; border: 1px solid #ccc; color: #999; border-radius: 4px; padding: 0;\" disabled>X</button>"
            f"      </div>"
            f"      <div style=\"width: 14px;\"></div>"
            f"      <div style=\"display: flex; gap: 4px;\">"
            f"        <button class=\"book-btn\" style=\"width: 24px; height: 24px; font-size: 9px; font-weight: bold; background: #fdf6ec; border: 1px solid #f5dab1; color: #e6a23c; border-radius: 4px; padding: 0; cursor: pointer;\" onclick=\"sendSuggestion('Chọn ghế 1D chân rộng')\">1D</button>"
            f"        <button class=\"book-btn\" style=\"width: 24px; height: 24px; font-size: 9px; font-weight: bold; background: #fdf6ec; border: 1px solid #f5dab1; color: #e6a23c; border-radius: 4px; padding: 0; cursor: pointer;\" onclick=\"sendSuggestion('Chọn ghế 1E chân rộng')\">1E</button>"
            f"        <button class=\"book-btn\" style=\"width: 24px; height: 24px; font-size: 9px; font-weight: bold; background: #fdf6ec; border: 1px solid #f5dab1; color: #e6a23c; border-radius: 4px; padding: 0; cursor: pointer;\" onclick=\"sendSuggestion('Chọn ghế 1F chân rộng')\">1F</button>"
            f"      </div>"
            f"    </div>"
            f"    <div style=\"display: flex; align-items: center; justify-content: space-between;\">"
            f"      <span style=\"font-size: 9px; width: 12px; color: var(--text-muted); font-weight: bold;\">2</span>"
            f"      <div style=\"display: flex; gap: 4px;\">"
            f"        <button class=\"book-btn\" style=\"width: 24px; height: 24px; font-size: 9px; background: #f5f5f5; border: 1px solid var(--border); color: var(--text); border-radius: 4px; padding: 0; cursor: pointer;\" onclick=\"sendSuggestion('Chọn ghế 2A')\">2A</button>"
            f"        <button class=\"book-btn\" style=\"width: 24px; height: 24px; font-size: 9px; background: #f5f5f5; border: 1px solid var(--border); color: var(--text); border-radius: 4px; padding: 0; cursor: pointer;\" onclick=\"sendSuggestion('Chọn ghế 2B')\">2B</button>"
            f"        <button class=\"book-btn\" style=\"width: 24px; height: 24px; font-size: 9px; background: #f5f5f5; border: 1px solid var(--border); color: var(--text); border-radius: 4px; padding: 0; cursor: pointer;\" onclick=\"sendSuggestion('Chọn ghế 2C')\">2C</button>"
            f"      </div>"
            f"      <div style=\"width: 14px;\"></div>"
            f"      <div style=\"display: flex; gap: 4px;\">"
            f"        <button style=\"width: 24px; height: 24px; font-size: 9px; background: #e0e0e0; border: 1px solid #ccc; color: #999; border-radius: 4px; padding: 0;\" disabled>X</button>"
            f"        <button class=\"book-btn\" style=\"width: 24px; height: 24px; font-size: 9px; background: #f5f5f5; border: 1px solid var(--border); color: var(--text); border-radius: 4px; padding: 0; cursor: pointer;\" onclick=\"sendSuggestion('Chọn ghế 2E')\">2E</button>"
            f"        <button class=\"book-btn\" style=\"width: 24px; height: 24px; font-size: 9px; background: #f5f5f5; border: 1px solid var(--border); color: var(--text); border-radius: 4px; padding: 0; cursor: pointer;\" onclick=\"sendSuggestion('Chọn ghế 2F')\">2F</button>"
            f"      </div>"
            f"    </div>"
            f"    <div style=\"display: flex; align-items: center; justify-content: space-between;\">"
            f"      <span style=\"font-size: 9px; width: 12px; color: var(--text-muted); font-weight: bold;\">3</span>"
            f"      <div style=\"display: flex; gap: 4px;\">"
            f"        <button class=\"book-btn\" style=\"width: 24px; height: 24px; font-size: 9px; background: #f5f5f5; border: 1px solid var(--border); color: var(--text); border-radius: 4px; padding: 0; cursor: pointer;\" onclick=\"sendSuggestion('Chọn ghế 3A')\">3A</button>"
            f"        <button class=\"book-btn\" style=\"width: 24px; height: 24px; font-size: 9px; background: #f5f5f5; border: 1px solid var(--border); color: var(--text); border-radius: 4px; padding: 0; cursor: pointer;\" onclick=\"sendSuggestion('Chọn ghế 3B')\">3B</button>"
            f"        <button class=\"book-btn\" style=\"width: 24px; height: 24px; font-size: 9px; background: #f5f5f5; border: 1px solid var(--border); color: var(--text); border-radius: 4px; padding: 0; cursor: pointer;\" onclick=\"sendSuggestion('Chọn ghế 3C')\">3C</button>"
            f"      </div>"
            f"      <div style=\"width: 14px;\"></div>"
            f"      <div style=\"display: flex; gap: 4px;\">"
            f"        <button class=\"book-btn\" style=\"width: 24px; height: 24px; font-size: 9px; background: #f5f5f5; border: 1px solid var(--border); color: var(--text); border-radius: 4px; padding: 0; cursor: pointer;\" onclick=\"sendSuggestion('Chọn ghế 3D')\">3D</button>"
            f"        <button style=\"width: 24px; height: 24px; font-size: 9px; background: #e0e0e0; border: 1px solid #ccc; color: #999; border-radius: 4px; padding: 0;\" disabled>X</button>"
            f"        <button class=\"book-btn\" style=\"width: 24px; height: 24px; font-size: 9px; background: #f5f5f5; border: 1px solid var(--border); color: var(--text); border-radius: 4px; padding: 0; cursor: pointer;\" onclick=\"sendSuggestion('Chọn ghế 3F')\">3F</button>"
            f"      </div>"
            f"    </div>"
            f"  </div>"
            f"  <div style=\"font-size: 8px; color: var(--text-muted); margin-top: 10px; text-align: center;\">... Hàng ghế sau tương tự ...</div>"
            f"</div>"
            f"<div style=\"display: flex; gap: 8px; margin-top: 12px;\">"
            f"  <button class=\"header-btn-outline\" style=\"width: 100%; padding: 8px; border-radius: 8px; border: 1px solid var(--border); background: transparent; font-weight: bold; cursor: pointer; color: var(--text);\" onclick=\"sendSuggestion('Bỏ qua dịch vụ đi kèm')\">⏩ Bỏ qua chọn ghế & Tiếp tục</button>"
            f"</div>"
        )
        history.append({"role": "user", "content": user_msg})
        history.append({"role": "assistant", "content": reply})
        return StreamingResponse(_sse_stream(reply, sid), media_type="text/event-stream")

    seat_match = re.match(r"^Chọn ghế\s+(\w+)(?:\s+(.*))?", user_msg, re.IGNORECASE)
    if seat_match:
        seat_num = seat_match.group(1).upper()
        details = seat_match.group(2) or ""
        fee = 80000 if "chân rộng" in details.lower() else 0
        state["ancillaries"] = f"Chọn ghế {seat_num}"
        state["price"] += fee
        state["state"] = "awaiting_confirm"
        
        price_disp = f"{state['price']:,}đ"
        
        raw_date = state.get("date") or ""
        date_disp = f"{raw_date[0:2]}/{raw_date[2:4]}/{raw_date[4:]}" if len(raw_date) == 8 else raw_date
        raw_time = state.get("time") or ""
        time_disp = raw_time.replace("→", " → ")
        airline_code = state.get("flight", "")[0:2]
        airline_name = {"VN": "Vietnam Airlines", "VJ": "Vietjet Air", "QH": "Bamboo Airways", "VU": "Vietravel Airlines"}.get(airline_code, airline_code)
        
        reply = (
            f"📝 **XÁC NHẬN THÔNG TIN ĐẶT VÉ**\n\n"
            f"• **Hãng bay:** {airline_name}\n"
            f"• **Chuyến bay:** {state['flight']} ({state['route']})\n"
            f"• **Ngày bay:** {date_disp}\n"
            f"• **Giờ bay:** {time_disp}\n"
            f"• **Hành khách:** {state['pax_name']}\n"
            f"• **Ngày sinh:** {state['pax_dob']}\n"
            f"• **Email:** {state['pax_email']}\n"
            f"• **Số điện thoại:** {state['pax_phone']}\n"
            f"• **Dịch vụ đi kèm:** {state['ancillaries']}\n"
            f"• **Tổng giá vé:** **{price_disp}**\n\n"
            f"👉 Bạn xác nhận thông tin trên là chính xác chứ?\n\n"
            f"<button class=\"book-btn\" style=\"padding: 8px 16px; border-radius: 8px; font-weight: bold; cursor: pointer;\" onclick=\"sendSuggestion('Xác nhận đặt vé')\">✅ Xác nhận đặt vé</button>"
            f"<button class=\"header-btn-outline\" style=\"margin-left: 8px; padding: 8px 16px; border-radius: 8px; border: 1px solid var(--border); background: transparent; color: var(--text); cursor: pointer;\" onclick=\"sendSuggestion('Hủy bỏ')\">❌ Hủy</button>"
        )
        history.append({"role": "user", "content": user_msg})
        history.append({"role": "assistant", "content": reply})
        return StreamingResponse(_sse_stream(reply, sid), media_type="text/event-stream")

    # 4. If state is "awaiting_pax_info"
    if state["state"] == "awaiting_pax_info":
        from app.services.llm_gateway import get_llm
        llm = get_llm()
        
        prompt = f"""Bạn là trợ lý AI trích xuất thông tin khách hàng từ câu chat. Hãy trích xuất các thông tin sau:
- pax_name (Họ tên đầy đủ, viết hoa chữ cái đầu, ví dụ: NGUYEN VAN A hoặc Nguyễn Văn A)
- pax_dob (Ngày tháng năm sinh, định dạng DD/MM/YYYY, ví dụ: 20/10/1995)
- pax_email (Địa chỉ email chính xác)
- pax_phone (Số điện thoại liên hệ chính xác)

Hãy lưu ý: Nếu thông tin nào chưa có trong câu chat, hãy điền null. Trả về đúng 1 đối tượng JSON chứa 4 trường này, không bao bọc trong markdown block hay giải thích gì thêm.

Câu chat của khách: "{user_msg}"
"""
        try:
            resp_obj = await llm.chat(prompt)
            import json
            raw_content = resp_obj.content.strip()
            if raw_content.startswith("```"):
                lines = raw_content.splitlines()
                if lines[0].startswith("```"):
                    lines = lines[1:]
                if lines[-1].startswith("```"):
                    lines = lines[:-1]
                raw_content = "\n".join(lines).strip()
                
            extracted = json.loads(raw_content)
            
            if extracted.get("pax_name"): state["pax_name"] = extracted["pax_name"]
            if extracted.get("pax_dob"): state["pax_dob"] = extracted["pax_dob"]
            if extracted.get("pax_email"): state["pax_email"] = extracted["pax_email"]
            if extracted.get("pax_phone"): state["pax_phone"] = extracted["pax_phone"]
        except Exception as e:
            logger.error("Error parsing passenger info with LLM: %s", e)
            
        missing = []
        if not state["pax_name"]: missing.append("**Họ tên**")
        if not state["pax_dob"]: missing.append("**Ngày sinh**")
        if not state["pax_email"]: missing.append("**Email**")
        if not state["pax_phone"]: missing.append("**Số điện thoại**")
        
        if missing:
            missing_str = ", ".join(missing)
            reply = (
                f"Cảm ơn bạn. Tôi đã ghi nhận một số thông tin.\n"
                f"Tuy nhiên, tôi vẫn còn thiếu thông tin: {missing_str}.\n\n"
                f"Vui lòng bổ sung hoặc gõ lại tự nhiên các thông tin còn thiếu này giúp tôi nhé!"
            )
        else:
            # Go to ancillaries upselling step instead of immediate confirmation
            state["state"] = "awaiting_ancillaries"
            reply = (
                f"📦 **ĐĂNG KÝ DỊCH VỤ ĐI KÈM (BÁN THÊM)**\n\n"
                f"Bạn có muốn mua thêm các dịch vụ đi kèm dưới đây để chuyến đi thoải mái hơn không?\n\n"
                f"<div style=\"display: flex; flex-direction: column; gap: 8px; margin-top: 10px;\">"
                f"  <div style=\"display: flex; align-items: center; justify-content: space-between; padding: 10px; border-radius: 8px; border: 1px solid var(--border); background: rgba(0,0,0,0.02);\">"
                f"    <div style=\"display: flex; align-items: center; gap: 10px;\">"
                f"      <span style=\"font-size: 20px;\">🧳</span>"
                f"      <div style=\"text-align: left;\">"
                f"        <div style=\"font-weight: 700; font-size: 13px; color: var(--text);\">Hành lý ký gửi 20kg</div>"
                f"        <div style=\"font-size: 11px; color: var(--text-muted);\">Mua thêm 20kg hành lý ký gửi</div>"
                f"      </div>"
                f"    </div>"
                f"    <button class=\"book-btn\" style=\"padding: 4px 10px; font-size: 11px; border-radius: 4px; cursor: pointer;\" onclick=\"sendSuggestion('Thêm 20kg hành lý ký gửi')\">+220k</button>"
                f"  </div>"
                f"  <div style=\"display: flex; align-items: center; justify-content: space-between; padding: 10px; border-radius: 8px; border: 1px solid var(--border); background: rgba(0,0,0,0.02);\">"
                f"    <div style=\"display: flex; align-items: center; gap: 10px;\">"
                f"      <span style=\"font-size: 20px;\">💺</span>"
                f"      <div style=\"text-align: left;\">"
                f"        <div style=\"font-weight: 700; font-size: 13px; color: var(--text);\">Chỗ ngồi rộng chân</div>"
                f"        <div style=\"font-size: 11px; color: var(--text-muted);\">Ghế ngồi thoải mái rộng chân</div>"
                f"      </div>"
                f"    </div>"
                f"    <button class=\"book-btn\" style=\"padding: 4px 10px; font-size: 11px; border-radius: 4px; cursor: pointer; background: var(--gold);\" onclick=\"sendSuggestion('Xem sơ đồ ghế')\">🗺️ Sơ đồ ghế</button>"
                f"  </div>"
                f"  <div style=\"display: flex; align-items: center; justify-content: space-between; padding: 10px; border-radius: 8px; border: 1px solid var(--border); background: rgba(0,0,0,0.02);\">"
                f"    <div style=\"display: flex; align-items: center; gap: 10px;\">"
                f"      <span style=\"font-size: 20px;\">🍲</span>"
                f"      <div style=\"text-align: left;\">"
                f"        <div style=\"font-weight: 700; font-size: 13px; color: var(--text);\">Suất ăn nóng sốt</div>"
                f"        <div style=\"font-size: 11px; color: var(--text-muted);\">Cơm nóng + nước uống trên mây</div>"
                f"      </div>"
                f"    </div>"
                f"    <button class=\"book-btn\" style=\"padding: 4px 10px; font-size: 11px; border-radius: 4px; cursor: pointer;\" onclick=\"sendSuggestion('Thêm suất ăn nóng sốt')\">+75k</button>"
                f"  </div>"
                f"</div>"
                f"<div style=\"margin-top: 12px;\">"
                f"  <button class=\"header-btn-outline\" style=\"width: 100%; padding: 8px; border-radius: 8px; border: 1px solid var(--border); background: transparent; font-weight: bold; cursor: pointer; color: var(--text);\" onclick=\"sendSuggestion('Bỏ qua dịch vụ đi kèm')\">⏩ Bỏ qua & Tiếp tục</button>"
                f"</div>"
            )
            
        history.append({"role": "user", "content": user_msg})
        history.append({"role": "assistant", "content": reply})
        return StreamingResponse(_sse_stream(reply, sid), media_type="text/event-stream")

    # 5. Handle "awaiting_ancillaries"
    if state["state"] == "awaiting_ancillaries":
        from app.services.llm_gateway import get_llm
        llm = get_llm()
        
        prompt = f"""Bạn là trợ lý phòng vé. Hãy phân tích câu chat của khách xem họ muốn mua thêm dịch vụ đi kèm nào:
- Mua thêm hành lý (baggage): ghi nhận loại hành lý và số tiền phụ thu (ví dụ: "Thêm 20kg hành lý ký gửi" -> phụ thu 220000).
- Chọn chỗ ngồi (seat): ghi nhận loại chỗ ngồi và số tiền (ví dụ: "chỗ để chân rộng" -> phụ thu 80000).
- Suất ăn (meal): ghi nhận suất ăn và số tiền (ví dụ: "suất ăn nóng" -> phụ thu 75000).

Trả về đúng 1 đối tượng JSON chứa các trường:
- has_ancillaries: boolean (True nếu khách mua, False nếu chọn bỏ qua/không cần)
- description: string (Mô tả dịch vụ khách chọn, ví dụ: "Hành lý ký gửi 20kg")
- fee: int (Số tiền phụ thu thêm bằng số, ví dụ: 220000, mặc định 0)

Câu chat: "{user_msg}"
"""
        description = "Không đăng ký"
        fee = 0
        if "bỏ qua" not in user_msg.lower() and "không cần" not in user_msg.lower():
            try:
                resp_obj = await llm.chat(prompt)
                import json
                raw_content = resp_obj.content.strip()
                if raw_content.startswith("```"):
                    lines = raw_content.splitlines()
                    if lines[0].startswith("```"):
                        lines = lines[1:]
                    if lines[-1].startswith("```"):
                        lines = lines[:-1]
                    raw_content = "\n".join(lines).strip()
                    
                extracted = json.loads(raw_content)
                if extracted.get("has_ancillaries"):
                    description = extracted.get("description", "Dịch vụ thêm")
                    fee = extracted.get("fee", 0)
            except Exception as e:
                logger.error("Error parsing ancillaries with LLM: %s", e)

        state["ancillaries"] = description
        state["price"] += fee
        state["state"] = "awaiting_confirm"
        
        price_disp = f"{state['price']:,}đ"
        
        raw_date = state.get("date") or ""
        date_disp = f"{raw_date[0:2]}/{raw_date[2:4]}/{raw_date[4:]}" if len(raw_date) == 8 else raw_date
        raw_time = state.get("time") or ""
        time_disp = raw_time.replace("→", " → ")
        airline_code = state.get("flight", "")[0:2]
        airline_name = {"VN": "Vietnam Airlines", "VJ": "Vietjet Air", "QH": "Bamboo Airways", "VU": "Vietravel Airlines"}.get(airline_code, airline_code)
        
        reply = (
            f"📝 **XÁC NHẬN THÔNG TIN ĐẶT VÉ**\n\n"
            f"• **Hãng bay:** {airline_name}\n"
            f"• **Chuyến bay:** {state['flight']} ({state['route']})\n"
            f"• **Ngày bay:** {date_disp}\n"
            f"• **Giờ bay:** {time_disp}\n"
            f"• **Hành khách:** {state['pax_name']}\n"
            f"• **Ngày sinh:** {state['pax_dob']}\n"
            f"• **Email:** {state['pax_email']}\n"
            f"• **Số điện thoại:** {state['pax_phone']}\n"
            f"• **Dịch vụ đi kèm:** {state['ancillaries']}\n"
            f"• **Tổng giá vé:** **{price_disp}**\n\n"
            f"👉 Bạn xác nhận thông tin trên là chính xác chứ?\n\n"
            f"<button class=\"book-btn\" style=\"padding: 8px 16px; border-radius: 8px; font-weight: bold; cursor: pointer;\" onclick=\"sendSuggestion('Xác nhận đặt vé')\">✅ Xác nhận đặt vé</button>"
            f"<button class=\"header-btn-outline\" style=\"margin-left: 8px; padding: 8px 16px; border-radius: 8px; border: 1px solid var(--border); background: transparent; color: var(--text); cursor: pointer;\" onclick=\"sendSuggestion('Hủy bỏ')\">❌ Hủy</button>"
        )
        history.append({"role": "user", "content": user_msg})
        history.append({"role": "assistant", "content": reply})
        return StreamingResponse(_sse_stream(reply, sid), media_type="text/event-stream")

    # 6. If state is "awaiting_confirm" and they say confirm
    if state["state"] == "awaiting_confirm" and any(w in user_msg.lower() for w in ("xác nhận", "đồng ý", "ok", "yes", "confirm", "chốt")):
        import random
        pnr = "".join(random.choices("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789", k=6))
        price_disp = f"{state['price']:,}đ" if state.get("price") else "Liên hệ"
        deadline = (datetime.now() + timedelta(hours=4)).strftime("%H:%M ngày %d/%m/%Y")
        
        raw_date = state.get("date") or ""
        date_disp = f"{raw_date[0:2]}/{raw_date[2:4]}/{raw_date[4:]}" if len(raw_date) == 8 else raw_date
        raw_time = state.get("time") or ""
        time_disp = raw_time.replace("→", " → ")
        airline_code = state.get("flight", "")[0:2]
        airline_name = {"VN": "Vietnam Airlines", "VJ": "Vietjet Air", "QH": "Bamboo Airways", "VU": "Vietravel Airlines"}.get(airline_code, airline_code)

        reply = (
            f"🎉 **GIỮ CHỖ THÀNH CÔNG!**\n\n"
            f"• **Mã đặt chỗ (PNR):** **{pnr}**\n"
            f"• **Hãng bay:** {airline_name}\n"
            f"• **Chuyến bay:** {state['flight']} ({state['route']})\n"
            f"• **Ngày bay:** {date_disp}\n"
            f"• **Giờ bay:** {time_disp}\n"
            f"• **Hành khách:** {state['pax_name']}\n"
            f"• **Ngày sinh:** {state['pax_dob']}\n"
            f"• **Email:** {state['pax_email']}\n"
            f"• **Số điện thoại:** {state['pax_phone']}\n"
            f"• **Dịch vụ đi kèm:** {state['ancillaries']}\n"
            f"• **Hạn giữ chỗ:** **{deadline}**\n"
            f"• **Tổng thanh toán:** **{price_disp}**\n\n"
            f"Tôi đã gửi thông tin hướng dẫn thanh toán chi tiết qua Email **{state['pax_email']}** "
            f"và SMS tới số **{state['pax_phone']}**.\n\n"
            f"👉 Vui lòng thanh toán trước thời hạn để tránh bị hủy chỗ tự động:\n\n"
            f"<button class=\"book-btn\" style=\"padding: 8px 16px; border-radius: 8px; font-weight: bold; background: var(--gold); cursor: pointer;\" onclick=\"sendSuggestion('Thanh toán {pnr}')\">💳 Thanh toán ngay</button>"
        )
        state["pnr"] = pnr
        state["state"] = "hold_success"
        history.append({"role": "user", "content": user_msg})
        history.append({"role": "assistant", "content": reply})
        return StreamingResponse(_sse_stream(reply, sid), media_type="text/event-stream")

    today = datetime.now().strftime("%d/%m/%Y")

    # ── RAG routing: operational queries (policy, rules, FAQ) hit knowledge base ──
    ops_keywords = ("hủy", "hoàn", "đổi", "hành lý", "chính sách", "quy định",
                    "thủ tục", "giấy tờ", "visa", "cách", "làm sao", "bao nhiêu kg",
                    "phí", "lệ phí", "điều kiện", "yêu cầu", "cần gì", "esim", "sim",
                    "phòng chờ", "lounge", "thương gia", "fast track", "fasttrack", "hộ chiếu", "passport")
    is_ops = any(kw in req.message.lower() for kw in ops_keywords)
    rag_context = ""
    if is_ops:
        try:
            rag = get_rag_service()
            if rag and rag._ready:
                rag_context = rag.format_context(req.message, top_k=5)
                if rag_context:
                    logger.info("RAG context injected for: %.80s...", req.message)
        except Exception as e:
            logger.warning("RAG lookup failed (proceeding without): %s", e)

    try:
        # ── Dynamic system prompt ───────────────────────────────
        if rag_context:
            system_prompt = f"""Bạn là Trợ lý Vạn Năng (Ticketing & Travel Manager) của Smart Agent. Hôm nay: {today}

{rag_context}

===== PHONG CÁCH PHẢN HỒI =====
- Xưng "tôi", gọi khách "bạn/anh/chị"
- Dùng THÔNG TIN TRA CỨU ở trên để trả lời CHÍNH XÁC, chân thành và đi thẳng vào vấn đề.
- Không dùng bảng biểu phức tạp — hãy dùng danh sách gạch đầu dòng (bullet list).
- Luôn gợi ý câu hỏi đóng/mở hoặc các nút bấm tương tác (nếu phù hợp) để hướng dẫn khách hành động tiếp theo (CTA)."""
        else:
            # Multi-service booking flow prompt
            system_prompt = f"""Bạn là Trợ lý Vạn Năng (Ticketing & Travel Manager) của Smart Agent. Hôm nay: {today}

Bạn chịu trách nhiệm tư vấn và hỗ trợ khách hàng đặt 5 dịch vụ du lịch & hàng không chính:
1. ✈️ **Vé máy bay:** Tra cứu và đặt vé máy bay nội địa & quốc tế (Khai thác Đi/Đến, ngày bay, số khách).
2. ⚡ **Fast Track Nội Bài:** Đón tiễn nhanh VIP tại sân bay Nội Bài (Fast Track đón/tiễn: 450.000đ/khách, VIP Lounge: 650.000đ/khách, phụ thu đêm 23:00 - 06:00: +200.000đ).
3. 📱 **eSIM Du lịch:** Sim data 4G kết nối internet quốc tế (Hàn Quốc: 129k/7 ngày, Nhật Bản: 149k/7 ngày, Châu Âu: 199k/7 ngày, Mỹ: 179k/7 ngày...).
4. 🛂 **Visa - Hộ chiếu:** Hồ sơ xin visa (Nhật, Hàn, Trung Quốc, Schengen, Mỹ...) và làm hộ chiếu online nhanh chóng.
5. 👑 **Phòng chờ VIP (Business Lounge):** Đặt phòng chờ thương gia đẳng cấp tại sân bay (Giá vé: 650.000đ/khách).

===== PHONG CÁCH =====
- Xưng "tôi", gọi khách "bạn/anh/chị"
- Nói chuyện chân thành, đi thẳng vào vấn đề, hỗ trợ tận tình.
- Không dùng bảng biểu phức tạp — dùng danh sách gạch đầu dòng (bullet list).
- Luôn gợi ý câu hỏi đóng/mở hoặc các nút bấm tương tác để hướng dẫn khách hành động tiếp theo (CTA)."""

        # Try Gemini 2.5 Flash
        gemini_key = os.getenv("GEMINI_API_KEY", "")
        llm_ok = False
        text = ""
        if gemini_key:
            async with httpx.AsyncClient(timeout=30.0) as client:
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
                    llm_text = "".join(p.get("text", "") for p in parts)
                    llm_ok = bool(llm_text)
                    text = llm_text if llm_ok else ""
        else:
            # Fallback to LLM Gateway (OmniRoute / OpenRouter)
            from app.services.llm_gateway import get_llm
            llm = get_llm()
            llm_history = []
            for msg in history[-8:]:
                llm_history.append({"role": msg.get("role"), "content": msg.get("content", "")})
            
            resp_obj = await llm.chat(req.message, history=llm_history, system_override=system_prompt)
            text = resp_obj.content if resp_obj.type in ("text", "tool_call") else ""
            llm_ok = bool(text)

        # Store in history
        history.append({"role": "user", "content": req.message})
        history.append({"role": "assistant", "content": text})
        if len(history) > 50:
            _chat_sessions[sid] = history[-50:]

        # --- AGT flight search for booking flows (not ops) ---
        search_data = None
        if not is_ops:
            recent_msgs = [h["content"] for h in history[-8:] if h["role"] == "user"]
            fp = _extract_flight_params(recent_msgs)
            if fp:
                try:
                    agt_client = ABTripClient()
                    result = await agt_client.search_flight(
                        system="",
                        adt=fp["adt"],
                        routes=[{
                            "StartPoint": fp["from"],
                            "EndPoint": fp["to"],
                            "DepartDate": fp["date"]
                        }]
                    )
                    search_data = _get_structured_flights(result, fp)
                    text = "Tôi đã tìm thấy các chuyến bay phù hợp dưới đây. Bạn chọn chuyến bay nào để tôi tiến hành giữ chỗ và lấy thông tin xuất vé nhé?"
                except Exception as e:
                    logger.warning("AGT search failed: %s", e)
                    text = f"⚠️ Đang tìm vé {fp['from']}→{fp['to']} ngày {fp['date']}...\n(Lỗi kết nối AGT: {e})" + ("\n\n" + text if text else "")

        # If LLM failed and no AGT results, use fallback
        if not text:
            text = "Xin chào! Tôi là Smart Agent — trợ lý phòng vé AI.\n\nTôi có thể giúp gì cho bạn hôm nay?\n• ✈️ Đặt vé máy bay\n• ⚡ Fast Track Nội Bài\n• 📱 eSIM du lịch\n• Nói 1 câu, tôi lo hết!"

        # Return SSE-style response
        return StreamingResponse(
            _sse_stream(text, sid, search_data),
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

        if is_ops:
            try:
                rag = get_rag_service()
                if rag and rag._ready:
                    rag_context = rag.format_context(req.message, top_k=3)
                    if rag_context:
                        text = f"📚 **Tra cứu:**\n\n{rag_context}\n\n_(Chế độ offline — tra cứu từ CSDL nội bộ)_"
                    else:
                        text = "Không tìm thấy thông tin phù hợp trong CSDL."
                else:
                    text = "Hệ thống tra cứu chưa sẵn sàng."
            except Exception as e:
                logger.error("RAG fallback error: %s", e)
                text = "Không thể tra cứu lúc này."
        else:
            # Booking flow: try AGT search first (no LLM needed)
            recent_msgs = [req.message]
            fp = _extract_flight_params(recent_msgs)
            search_data = None
            if fp:
                try:
                    agt_client = ABTripClient()
                    result = await agt_client.search_flight(
                        system="",
                        adt=fp["adt"],
                        routes=[{
                            "StartPoint": fp["from"],
                            "EndPoint": fp["to"],
                            "DepartDate": fp["date"]
                        }]
                    )
                    search_data = _get_structured_flights(result, fp)
                    text = "Tôi đã tìm thấy các chuyến bay phù hợp dưới đây. Bạn chọn chuyến bay nào để tôi tiến hành giữ chỗ và lấy thông tin xuất vé nhé?"
                except Exception as e:
                    logger.warning("AGT search failed: %s", e)
                    text = f"⚠️ Đang tìm vé {fp['from']}→{fp['to']} ngày {fp['date']}...\n(Lỗi: {e})\n\nVui lòng thử lại sau."
            else:
                text = responses.get(intent, "Xin chào! Tôi là Smart Agent — trợ lý phòng vé AI.\n\nTôi có thể giúp gì cho bạn hôm nay?\n• ✈️ Đặt vé máy bay\n• ⚡ Fast Track Nội Bài\n• 📱 eSIM du lịch\n• 🛂 Visa & Hộ chiếu\n• 💼 Mở phòng vé CTV\n\nNói 1 câu, tôi lo hết!")
        history.append({"role": "user", "content": req.message})
        history.append({"role": "assistant", "content": text})
        if len(history) > 50:
            _chat_sessions[sid] = history[-50:]

        return StreamingResponse(
            _sse_stream(text, sid, search_data),
            media_type="text/event-stream",
        )

    except Exception as e:
        logger.error("Smart chat error: %s", e)
        return StreamingResponse(
            _sse_stream(f"Xin lỗi, hệ thống đang gặp sự cố. Vui lòng thử lại sau. Lỗi: {str(e)}", sid),
            media_type="text/event-stream",
        )


async def _sse_stream(text: str, session_id: str, search_results: dict = None):
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
    if search_results:
        done["step"] = "search_results"
        done["data"] = search_results
    yield f"data: {json.dumps(done)}\n\n"
    yield "data: [DONE]\n\n"
