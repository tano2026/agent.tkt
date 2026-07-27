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

    today = datetime.now().strftime("%d/%m/%Y")

    # ── RAG routing: operational queries (policy, rules, FAQ) hit knowledge base ──
    ops_keywords = ("hủy", "hoàn", "đổi", "hành lý", "chính sách", "quy định",
                    "thủ tục", "giấy tờ", "visa", "cách", "làm sao", "bao nhiêu kg",
                    "phí", "lệ phí", "điều kiện", "yêu cầu", "cần gì")
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
            system_prompt = f"""Bạn là Ticketing Manager + chuyên gia hàng không của Smart Agent. Hôm nay: {today}

{rag_context}

===== PHONG CÁCH =====
- Xưng "tôi", gọi khách "bạn/anh/chị"
- Dùng THÔNG TIN TRA CỨU ở trên để trả lời CHÍNH XÁC, không bịa
- Nói chuyện như thằng em trong nghề: chân thành, đi thẳng
- Không dùng bảng biểu — dùng bullet list
- Luôn gợi ý hành động tiếp theo (CTA) sau mỗi câu"""
        else:
            # Booking flow — lean prompt, LLM extracts: from/to/date/pax → forward to flight search
            system_prompt = f"""Bạn là Ticketing Manager của Smart Agent — phòng vé AI. Hôm nay: {today}

Nhiệm vụ: Hiểu yêu cầu đặt vé của khách, trích xuất: điểm đi, điểm đến, ngày bay, số khách, hạng vé (nếu có). Đáp tự nhiên, thân thiện. Nếu thiếu thông tin thì hỏi lại nhẹ nhàng.

===== PHONG CÁCH =====
- Xưng "tôi", gọi khách "bạn/anh/chị"
- Nói chuyện như thằng em trong nghề: chân thành, đi thẳng
- Không dùng bảng biểu — dùng bullet list
- Luôn gợi ý hành động tiếp theo (CTA) sau mỗi câu"""

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
                    flight_text = _format_flight_results(result, fp)
                    text = flight_text + "\n\n👉 Bạn chọn chuyến bay nào ở trên để tôi tiến hành giữ chỗ và lấy thông tin xuất vé nhé?"
                except Exception as e:
                    logger.warning("AGT search failed: %s", e)
                    text = f"⚠️ Đang tìm vé {fp['from']}→{fp['to']} ngày {fp['date']}...\n(Lỗi kết nối AGT: {e})" + ("\n\n" + text if text else "")

        # If LLM failed and no AGT results, use fallback
        if not text:
            text = "Xin chào! Tôi là Smart Agent — trợ lý phòng vé AI.\n\nTôi có thể giúp gì cho bạn hôm nay?\n• ✈️ Đặt vé máy bay\n• ⚡ Fast Track Nội Bài\n• 📱 eSIM du lịch\n• Nói 1 câu, tôi lo hết!"

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
                    flight_text = _format_flight_results(result, fp)
                    text = flight_text + "\n\n👉 Bạn chọn chuyến bay nào ở trên để tôi tiến hành giữ chỗ và lấy thông tin xuất vé nhé?"
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
