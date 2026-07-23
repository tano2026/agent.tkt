"""
Auth Middleware — JWT token verification + API key authentication for CTV Platform.

Usage:
    from app.middleware.auth_middleware import get_current_user, get_api_key_user

    @router.get("/protected")
    async def protected_route(user: dict = Depends(get_current_user)):
        return {"user_id": user["tenant_id"], "tier": user["tier"]}

    @router.get("/api-protected")
    async def api_protected_route(user: dict = Depends(get_api_key_user)):
        return {"tenant_id": user["tenant_id"]}

The middleware reads:
1. Authorization: Bearer <JWT> — for web/mobile clients
2. X-API-Key: <key> — for Pro/White-label API integration
"""
from __future__ import annotations

import logging
import os
from typing import Optional, Any

from fastapi import Request, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt

logger = logging.getLogger(__name__)

# Same JWT config as auth_service.py
JWT_SECRET = os.getenv("JWT_SECRET", "abtrip-ctv-jwt-secret-key-change-in-production")
JWT_ALGORITHM = "HS256"

# Security scheme for Swagger docs
security = HTTPBearer(auto_error=False)


# ---------------------------------------------------------------------------
# JWT token verification
# ---------------------------------------------------------------------------

async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> dict[str, Any]:
    """
    FastAPI dependency — extracts and verifies the JWT Bearer token.
    Returns user payload dict with tenant_id, phone, tier.

    Raises 401 if token is missing, invalid, or expired.
    """
    if not credentials:
        raise HTTPException(
            status_code=401,
            detail="Thiếu token xác thực. Vui lòng đăng nhập.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        tenant_id = payload.get("sub")
        phone = payload.get("phone")
        tier = payload.get("tier", "free")

        if not tenant_id:
            raise HTTPException(401, "Token không hợp lệ: thiếu thông tin người dùng")

        return {
            "tenant_id": int(tenant_id),
            "phone": phone or "",
            "tier": tier,
        }

    except JWTError as e:
        logger.warning("JWT verification failed: %s", str(e))
        raise HTTPException(
            status_code=401,
            detail="Token không hợp lệ hoặc đã hết hạn. Vui lòng đăng nhập lại.",
        )


# ---------------------------------------------------------------------------
# API key authentication (from X-API-Key header)
# ---------------------------------------------------------------------------

async def get_api_key_user(
    request: Request,
) -> dict[str, Any]:
    """
    FastAPI dependency — extracts and validates X-API-Key header.
    Returns user payload with tenant_id, tier, api_key.

    NOTE: This only extracts the key value. Actual DB lookup should be
    performed by the endpoint handler (or a composite dependency).

    Raises 401 if X-API-Key header is missing.
    """
    api_key = request.headers.get("X-API-Key")
    if not api_key:
        raise HTTPException(
            status_code=401,
            detail="Thiếu API key. Vui lòng cung cấp X-API-Key header.",
        )

    return {
        "api_key": api_key,
        "auth_method": "api_key",
    }


# ---------------------------------------------------------------------------
# Composite: try JWT first, fallback to API key
# ---------------------------------------------------------------------------

async def get_current_user_or_api_key(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> dict[str, Any]:
    """
    Composite auth dependency:
    1. Try JWT Bearer token first
    2. Fallback to X-API-Key header
    3. Return user payload with 'auth_method' field

    This is useful for endpoints that support both auth methods.
    """
    # Try JWT
    if credentials:
        token = credentials.credentials
        try:
            payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
            tenant_id = payload.get("sub")
            if tenant_id:
                return {
                    "tenant_id": int(tenant_id),
                    "phone": payload.get("phone", ""),
                    "tier": payload.get("tier", "free"),
                    "auth_method": "jwt",
                }
        except JWTError:
            pass  # Fall through to API key check

    # Try API key
    api_key = request.headers.get("X-API-Key")
    if api_key:
        return {
            "api_key": api_key,
            "auth_method": "api_key",
        }

    raise HTTPException(
        status_code=401,
        detail="Cần xác thực: dùng Bearer token (JWT) hoặc X-API-Key.",
    )
