"""
Auth Service — JWT-based authentication + API key management for CTV Platform.

Endpoints:
  POST /api/v1/auth/register    — Register a new CTV (name, phone, email, password)
  POST /api/v1/auth/login       — Login, returns JWT access_token
  POST /api/v1/auth/api-key     — Generate API key (Pro/White-label only)
  GET  /api/v1/auth/profile     — Current user profile (tier, balance, api_key)

Dependencies: python-jose[cryptography], passlib[bcrypt], sqlalchemy+aiosqlite
"""
from __future__ import annotations

import logging
import secrets
import os
from datetime import datetime, timedelta
from typing import Optional, Any

from fastapi import APIRouter, Depends, HTTPException, Header
from pydantic import BaseModel, Field
from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, ForeignKey, Text, select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base

# JWT & password
from jose import JWTError, jwt
from passlib.context import CryptContext

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

# JWT secret — from env or hardcoded default for dev
JWT_SECRET = os.getenv("JWT_SECRET", "abtrip-ctv-jwt-secret-key-change-in-production")
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_MINUTES = 60 * 24  # 24 hours

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

DB_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
os.makedirs(DB_DIR, exist_ok=True)
DATABASE_URL = f"sqlite+aiosqlite:///{os.path.join(DB_DIR, 'smart_agent.db')}"

engine = create_async_engine(DATABASE_URL, echo=False)
async_session_factory = async_sessionmaker(engine, expire_on_commit=False)
Base = declarative_base()


# ---------------------------------------------------------------------------
# Auth User model — links to sa_tenants via tenant_id
# ---------------------------------------------------------------------------

class CTVUser(Base):
    """CTV account with password authentication. Links to existing Tenant in sa_tenants."""
    __tablename__ = "sa_auth_users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, ForeignKey("sa_tenants.id"), nullable=False, unique=True)
    phone = Column(String(20), nullable=False, unique=True)
    email = Column(String(200), nullable=False)
    full_name = Column(String(100), nullable=False)
    password_hash = Column(String(128), nullable=False)
    is_active = Column(Boolean, default=True)
    api_key = Column(String(64), unique=True, nullable=True)
    balance = Column(Float, default=0.0)  # hoa hồng khả dụng
    total_commission = Column(Float, default=0.0)  # tổng hoa hồng đã nhận
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------

class RegisterRequest(BaseModel):
    full_name: str = Field(..., min_length=1, max_length=100, description="Họ và tên")
    phone: str = Field(..., min_length=10, max_length=20, description="Số điện thoại")
    email: str = Field(..., max_length=200, description="Email")
    password: str = Field(..., min_length=6, max_length=128, description="Mật khẩu")


class LoginRequest(BaseModel):
    phone: str = Field(..., description="Số điện thoại")
    password: str = Field(..., description="Mật khẩu")


class LoginResponse(BaseModel):
    success: bool
    access_token: str
    token_type: str = "bearer"
    tenant_id: int
    full_name: str
    tier: str
    message: str


class ApiKeyResponse(BaseModel):
    success: bool
    api_key: str
    message: str


class ProfileResponse(BaseModel):
    success: bool
    tenant_id: int
    full_name: str
    phone: str
    email: str
    tier: str
    api_key: Optional[str] = None
    balance: float
    total_commission: float
    commission_rate: float
    booking_count: int
    booking_limit: int
    status: str
    registered_at: Optional[str] = None
    subscription_expires_at: Optional[str] = None


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------

async def get_db() -> AsyncSession:
    async with async_session_factory() as session:
        yield session


async def init_auth_db():
    """Create auth tables if they don't exist."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Auth service tables created/verified.")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=JWT_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, JWT_SECRET, algorithm=JWT_ALGORITHM)


def generate_api_key() -> str:
    return f"sa_{secrets.token_hex(24)}"


# ---------------------------------------------------------------------------
# Helper: get Tenant data from sa_tenants (reads existing smart_agent data)
# ---------------------------------------------------------------------------

async def _get_tenant_data(tenant_id: int, db: AsyncSession) -> Optional[dict[str, Any]]:
    """Read tenant info from sa_tenants table (smart_agent.py schema)."""
    from sqlalchemy import text as sa_text
    result = await db.execute(
        sa_text("SELECT * FROM sa_tenants WHERE id = :id"),
        {"id": tenant_id}
    )
    row = result.fetchone()
    if not row:
        return None
    # Map row to dict — row is a Row object
    return dict(row._mapping)


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

router = APIRouter(prefix="/api/v1/auth", tags=["CTV Auth"])


# ─── POST /api/v1/auth/register ───────────────────────────────────────────────

@router.post("/register")
async def register(req: RegisterRequest, db: AsyncSession = Depends(get_db)):
    """Register a new CTV account with password authentication."""
    # Check if phone already registered in auth_users
    existing = await db.execute(
        select(CTVUser).where(CTVUser.phone == req.phone)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(400, "Số điện thoại đã được đăng ký")

    # Create a tenant in sa_tenants first (reuse smart_agent logic)
    from sqlalchemy import text as sa_text
    api_key = generate_api_key()

    # Check existing tenant by phone in sa_tenants
    existing_tenant = await db.execute(
        sa_text("SELECT id FROM sa_tenants WHERE phone = :phone"),
        {"phone": req.phone}
    )
    tenant_row = existing_tenant.fetchone()

    if tenant_row:
        tenant_id = tenant_row[0]
    else:
        # Create new tenant
        result = await db.execute(
            sa_text("""
                INSERT INTO sa_tenants
                    (company_name, full_name, phone, email, business_type,
                     agent_tier, api_key, commission_rate, monthly_booking_limit,
                     booking_count, status, registered_at)
                VALUES
                    (:company, :name, :phone, :email, :biz_type,
                     :tier, :api_key, :comm, :limit,
                     0, 'active', :now)
            """),
            {
                "company": req.full_name,
                "name": req.full_name,
                "phone": req.phone,
                "email": req.email,
                "biz_type": "ctv",
                "tier": "free",
                "api_key": api_key,
                "comm": 0.08,
                "limit": 50,
                "now": datetime.utcnow(),
            }
        )
        await db.commit()
        tenant_id = result.lastrowid

    # Create auth user
    ctv_user = CTVUser(
        tenant_id=tenant_id,
        phone=req.phone,
        email=req.email,
        full_name=req.full_name,
        password_hash=hash_password(req.password),
        api_key=api_key,
        balance=0.0,
        total_commission=0.0,
    )
    db.add(ctv_user)
    await db.commit()
    await db.refresh(ctv_user)

    return {
        "success": True,
        "tenant_id": tenant_id,
        "full_name": req.full_name,
        "tier": "free",
        "api_key": api_key,
        "commission_rate": 0.08,
        "message": "Đăng ký CTV thành công!",
    }


# ─── POST /api/v1/auth/login ───────────────────────────────────────────────────

@router.post("/login")
async def login(req: LoginRequest, db: AsyncSession = Depends(get_db)):
    """Login with phone + password. Returns JWT access token."""
    # Find auth user
    result = await db.execute(
        select(CTVUser).where(CTVUser.phone == req.phone)
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(401, "Số điện thoại hoặc mật khẩu không đúng")

    if not user.is_active:
        raise HTTPException(403, "Tài khoản đã bị khóa")

    if not verify_password(req.password, user.password_hash):
        raise HTTPException(401, "Số điện thoại hoặc mật khẩu không đúng")

    # Get tier from sa_tenants
    tenant_data = await _get_tenant_data(user.tenant_id, db)
    tier = tenant_data.get("agent_tier", "free") if tenant_data else "free"

    # Create JWT
    access_token = create_access_token(
        data={
            "sub": str(user.tenant_id),
            "phone": user.phone,
            "tier": tier,
        }
    )

    return {
        "success": True,
        "access_token": access_token,
        "token_type": "bearer",
        "tenant_id": user.tenant_id,
        "full_name": user.full_name,
        "tier": tier,
        "message": "Đăng nhập thành công!",
    }


# ─── POST /api/v1/auth/api-key ─────────────────────────────────────────────────

@router.post("/api-key")
async def generate_api_key_endpoint(
    authorization: Optional[str] = Header(None),
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    db: AsyncSession = Depends(get_db),
):
    """Generate a new API key. Requires Pro or White-label tier.

    Authenticate via JWT (Bearer token) or existing X-API-Key.
    """
    tenant_id = None
    tier = None

    # Try JWT first
    if authorization and authorization.startswith("Bearer "):
        token = authorization[7:]
        try:
            payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
            tenant_id = int(payload.get("sub", 0))
            tier = payload.get("tier", "free")
        except JWTError:
            raise HTTPException(401, "Token không hợp lệ hoặc đã hết hạn")

    # Fallback to X-API-Key
    if not tenant_id and x_api_key:
        result = await db.execute(
            select(CTVUser).where(CTVUser.api_key == x_api_key)
        )
        user = result.scalar_one_or_none()
        if not user:
            raise HTTPException(401, "API key không hợp lệ")
        tenant_id = user.tenant_id
        tenant_data = await _get_tenant_data(tenant_id, db)
        tier = tenant_data.get("agent_tier", "free") if tenant_data else "free"

    if not tenant_id:
        raise HTTPException(401, "Cần đăng nhập (Bearer token) hoặc API key")

    # Check tier — only Pro or White-label can generate API keys
    if tier not in ("pro", "whitelabel"):
        raise HTTPException(403, "Chỉ tài khoản Pro hoặc White-label mới được tạo API key")

    # Generate new API key
    new_api_key = generate_api_key()
    result = await db.execute(
        select(CTVUser).where(CTVUser.tenant_id == tenant_id)
    )
    user = result.scalar_one_or_none()
    if user:
        user.api_key = new_api_key
        await db.commit()

    return {
        "success": True,
        "api_key": new_api_key,
        "message": "API key mới đã được tạo!",
    }


# ─── GET /api/v1/auth/profile ─────────────────────────────────────────────────

@router.get("/profile")
async def get_profile(
    authorization: Optional[str] = Header(None),
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    db: AsyncSession = Depends(get_db),
):
    """Get current user profile — tier, balance, API key, bookings count."""
    tenant_id = None

    # Try JWT
    if authorization and authorization.startswith("Bearer "):
        token = authorization[7:]
        try:
            payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
            tenant_id = int(payload.get("sub", 0))
        except JWTError:
            raise HTTPException(401, "Token không hợp lệ hoặc đã hết hạn")

    # Fallback to API key
    if not tenant_id and x_api_key:
        result = await db.execute(
            select(CTVUser).where(CTVUser.api_key == x_api_key)
        )
        user = result.scalar_one_or_none()
        if not user:
            raise HTTPException(401, "API key không hợp lệ")
        tenant_id = user.tenant_id

    if not tenant_id:
        raise HTTPException(401, "Cần đăng nhập (Bearer token) hoặc API key")

    # Get auth user
    auth_result = await db.execute(
        select(CTVUser).where(CTVUser.tenant_id == tenant_id)
    )
    auth_user = auth_result.scalar_one_or_none()
    if not auth_user:
        raise HTTPException(404, "Không tìm thấy tài khoản")

    # Get tenant data
    tenant_data = await _get_tenant_data(tenant_id, db)

    return {
        "success": True,
        "tenant_id": tenant_id,
        "full_name": auth_user.full_name,
        "phone": auth_user.phone,
        "email": auth_user.email,
        "tier": tenant_data.get("agent_tier", "free") if tenant_data else "free",
        "api_key": auth_user.api_key,
        "balance": auth_user.balance,
        "total_commission": auth_user.total_commission,
        "commission_rate": tenant_data.get("commission_rate", 0.08) if tenant_data else 0.08,
        "booking_count": tenant_data.get("booking_count", 0) if tenant_data else 0,
        "booking_limit": tenant_data.get("monthly_booking_limit", 50) if tenant_data else 50,
        "status": tenant_data.get("status", "active") if tenant_data else "active",
        "registered_at": (
            tenant_data["registered_at"].isoformat()
            if tenant_data and tenant_data.get("registered_at")
            else None
        ),
        "subscription_expires_at": (
            tenant_data["subscription_expires_at"].isoformat()
            if tenant_data and tenant_data.get("subscription_expires_at")
            else None
        ),
    }
