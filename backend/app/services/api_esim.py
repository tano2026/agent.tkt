"""
ABTrip Smart Agent — API eSIM Du Lịch (Mock Phase 1)
8 gói quốc tế: Châu Á 79K, Đông Nam Á 99K, Châu Âu 149K, ...
QR line = link kích hoạt ảo.

Router prefix: /api/v1/esim
"""

import logging
import secrets
from datetime import datetime
from typing import Optional, List, Dict

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/esim", tags=["eSIM"])

# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------

class ESIMPackage(BaseModel):
    code: str
    name: str
    description: str
    price: int              # VND
    data_limit: str         # VD: "3GB/ngày", "10GB/tổng"
    duration_days: int
    destinations: List[str]
    coverage_region: str    # VD: "Châu Á", "Châu Âu", "Toàn cầu"

class ESIMOrderRequest(BaseModel):
    tenant_id: int = Field(..., gt=0)
    package_id: str = Field(..., description="Mã gói eSIM")
    phone: str = Field(..., min_length=10, max_length=20)
    email: str = Field(..., max_length=200)

class ESIMOrderResponse(BaseModel):
    success: bool
    order_ref: str
    package: str
    phone: str
    email: str
    price: int
    currency: str = "VND"
    qr_line: str            # Link kích hoạt ảo
    status: str = "delivered"
    message: str

class ESIMOrderDetail(BaseModel):
    order_ref: str
    tenant_id: int
    package_code: str
    package_name: str
    phone: str
    email: str
    price: int
    qr_line: str
    status: str
    created_at: str

# ---------------------------------------------------------------------------
# Mock eSIM packages — 8 gói, giá thị trường 2026
# ---------------------------------------------------------------------------

ESIM_PACKAGES = [
    ESIMPackage(
        code="ESIM_ASIA_7D",
        name="Châu Á 7 ngày",
        description="7 ngày siêu tiết kiệm — dùng ổn định tại Thái Lan, Singapore, Malaysia, Indonesia.",
        price=79_000,
        data_limit="2GB/ngày (tổng 14GB)",
        duration_days=7,
        destinations=["Thailand", "Singapore", "Malaysia", "Indonesia", "Philippines"],
        coverage_region="Châu Á",
    ),
    ESIMPackage(
        code="ESIM_SEA_7D",
        name="Đông Nam Á 7 ngày",
        description="Băng thông cao, phủ sóng toàn Đông Nam Á. 4G/5G tốc độ tối đa.",
        price=99_000,
        data_limit="3GB/ngày (tổng 21GB)",
        duration_days=7,
        destinations=["Thailand", "Vietnam", "Singapore", "Malaysia", "Indonesia", "Philippines", "Cambodia", "Laos", "Myanmar", "Brunei"],
        coverage_region="Đông Nam Á",
    ),
    ESIMPackage(
        code="ESIM_EU_15D",
        name="Châu Âu 15 ngày",
        description="Phủ 33 nước Châu Âu. Dùng thoải mái, không lo chặn băng thông.",
        price=149_000,
        data_limit="5GB/tổng (15 ngày)",
        duration_days=15,
        destinations=["France", "Germany", "Italy", "Spain", "UK", "Netherlands", "Switzerland", "Portugal", "Austria", "Belgium", "Sweden", "Denmark", "Norway", "Finland", "Greece", "Ireland"],
        coverage_region="Châu Âu",
    ),
    ESIMPackage(
        code="ESIM_JP_7D",
        name="Nhật Bản 7 ngày",
        description="Chuyên dụng cho Nhật Bản. Mạng Docomo/KDDI — ổn định khắp các tỉnh.",
        price=129_000,
        data_limit="2GB/ngày (tổng 14GB)",
        duration_days=7,
        destinations=["Japan"],
        coverage_region="Nhật Bản",
    ),
    ESIMPackage(
        code="ESIM_KR_7D",
        name="Hàn Quốc 7 ngày",
        description="Mạng SK Telecom / KT — 5G tốc độ cao. Phủ sóng toàn Hàn Quốc.",
        price=119_000,
        data_limit="3GB/ngày (tổng 21GB)",
        duration_days=7,
        destinations=["Korea", "South Korea"],
        coverage_region="Hàn Quốc",
    ),
    ESIMPackage(
        code="ESIM_CN_7D",
        name="Trung Quốc 7 ngày",
        description="Vượt tường lửa Trung Quốc. Dùng được Facebook, Google, YouTube.",
        price=139_000,
        data_limit="1GB/ngày (tổng 7GB) + VPN tích hợp",
        duration_days=7,
        destinations=["China", "Hong Kong", "Macau"],
        coverage_region="Trung Quốc",
    ),
    ESIMPackage(
        code="ESIM_US_15D",
        name="Mỹ & Canada 15 ngày",
        description="T-Mobile / AT&T — phủ sóng khắp Mỹ và Canada.",
        price=179_000,
        data_limit="5GB/tổng (15 ngày)",
        duration_days=15,
        destinations=["USA", "United States", "Canada"],
        coverage_region="Bắc Mỹ",
    ),
    ESIMPackage(
        code="ESIM_GLOBAL_30D",
        name="Toàn cầu 30 ngày",
        description="Phủ 100+ quốc gia. Dữ liệu lớn cho chuyến công tác vòng quanh thế giới.",
        price=499_000,
        data_limit="10GB/tổng (30 ngày)",
        duration_days=30,
        destinations=["Global", "Worldwide"],
        coverage_region="Toàn cầu",
    ),
]

PACKAGES_MAP = {pkg.code: pkg for pkg in ESIM_PACKAGES}

# ---------------------------------------------------------------------------
# In-memory storage
# ---------------------------------------------------------------------------

_orders_store: List[dict] = []
_orders_seq = 0


def _generate_order_ref() -> str:
    global _orders_seq
    _orders_seq += 1
    return f"ESIM{_orders_seq:06d}{secrets.token_hex(2).upper()}"


def _generate_qr_line(order_ref: str, package_code: str) -> str:
    """QR line = link kích hoạt eSIM ảo."""
    return f"https://abtrip.vn/esim/activate/{order_ref}?pkg={package_code}&token={secrets.token_hex(16)}"


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("/packages")
async def get_packages():
    """Lấy danh sách gói eSIM du lịch."""
    return {
        "success": True,
        "data": [pkg.model_dump() for pkg in ESIM_PACKAGES],
        "total": len(ESIM_PACKAGES),
    }


@router.post("/orders", response_model=ESIMOrderResponse)
async def create_order(req: ESIMOrderRequest):
    """Đặt mua eSIM du lịch."""
    if req.package_id not in PACKAGES_MAP:
        raise HTTPException(400, f"Gói eSIM '{req.package_id}' không tồn tại")

    pkg = PACKAGES_MAP[req.package_id]
    order_ref = _generate_order_ref()
    qr_line = _generate_qr_line(order_ref, req.package_id)

    order_data = {
        "order_ref": order_ref,
        "tenant_id": req.tenant_id,
        "package_code": req.package_id,
        "package_name": pkg.name,
        "phone": req.phone,
        "email": req.email,
        "price": pkg.price,
        "currency": "VND",
        "qr_line": qr_line,
        "status": "delivered",
        "created_at": datetime.utcnow().isoformat(),
    }
    _orders_store.append(order_data)

    return ESIMOrderResponse(
        success=True,
        order_ref=order_ref,
        package=pkg.name,
        phone=req.phone,
        email=req.email,
        price=pkg.price,
        qr_line=qr_line,
        message=f"Đặt eSIM {pkg.name} thành công! Mã đơn: {order_ref}. Link kích hoạt đã được gửi.",
    )


@router.get("/orders")
async def get_orders(
    tenant_id: int = Query(..., gt=0, description="ID CTV"),
    status: Optional[str] = Query(None),
):
    """Lấy lịch sử đặt eSIM theo tenant_id."""
    result = []
    for o in _orders_store:
        if o["tenant_id"] != tenant_id:
            continue
        if status and o["status"] != status:
            continue
        result.append(o)

    return {
        "success": True,
        "data": result,
        "total": len(result),
        "tenant_id": tenant_id,
    }
