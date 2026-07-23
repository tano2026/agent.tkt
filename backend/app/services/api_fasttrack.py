"""
ABTrip Smart Agent — API Fast Track Nội Bài (Mock Phase 1)
3 gói: Fast Track 250K, VIP B 550K, Lounge 350K
Phụ thu đêm 23:00-06:00 +200K

Router prefix: /api/v1/fasttrack
"""

import logging
import secrets
from datetime import datetime, date
from typing import Optional, List, Dict

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/fasttrack", tags=["Fast Track"])

# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------

class FastTrackPackage(BaseModel):
    code: str
    name: str
    description: str
    price: int          # VND, cơ bản
    night_surcharge: int = 200_000  # Phụ thu 23:00-06:00
    includes: List[str]

class FastTrackOrderRequest(BaseModel):
    tenant_id: int = Field(..., gt=0, description="ID CTV")
    passenger_name: str = Field(..., min_length=1, max_length=200, description="Tên hành khách")
    flight_date: str = Field(..., description="Ngày bay dạng YYYY-MM-DD")
    package: str = Field(..., description="Mã gói: FT_BASIC, FT_VIP, FT_LOUNGE")
    phone: str = Field(..., min_length=10, max_length=20, description="SĐT hành khách")
    flight_time: Optional[str] = Field(None, description="Giờ bay dạng HH:MM (để tính phụ thu đêm)")
    flight_number: Optional[str] = Field(None, max_length=20, description="Số hiệu chuyến bay")
    pax_count: int = Field(default=1, ge=1, le=20, description="Số lượng khách")

class FastTrackOrderResponse(BaseModel):
    success: bool
    order_ref: str
    package: str
    passenger_name: str
    flight_date: str
    base_price: int
    night_surcharge: int
    total_price: int
    currency: str = "VND"
    qr_content: str
    status: str = "pending"
    message: str

class FastTrackOrderDetail(BaseModel):
    order_ref: str
    tenant_id: int
    passenger_name: str
    flight_date: str
    package: str
    phone: str
    total_price: int
    status: str
    qr_content: str
    created_at: str

# ---------------------------------------------------------------------------
# Mock packages
# ---------------------------------------------------------------------------

FASTTRACK_PACKAGES = [
    FastTrackPackage(
        code="FT_BASIC",
        name="Fast Track Cơ Bản",
        description="Ưu tiên làm thủ tục tại ga đi Nội Bài. Bao gồm: làm thủ tục nhanh, ưu tiên soi chiếu an ninh.",
        price=620_000,
        night_surcharge=200_000,
        includes=[
            "Làm thủ tục nhanh tại quầy",
            "Ưu tiên soi chiếu an ninh",
            "Hỗ trợ viên hướng dẫn",
        ],
    ),
    FastTrackPackage(
        code="FT_VIP",
        name="VIP B (Phòng chờ + Fast Track)",
        description="Gói cao cấp: Fast Track + phòng chờ VIP + xe đưa tận chân máy bay.",
        price=950_000,
        night_surcharge=200_000,
        includes=[
            "Fast Track ưu tiên",
            "Phòng chờ VIP Lounge",
            "Đồ uống & snacks miễn phí",
            "Xe đưa tận chân máy bay",
            "Wifi tốc độ cao",
        ],
    ),
    FastTrackPackage(
        code="FT_LOUNGE",
        name="Lounge (Phòng chờ)",
        description="Phòng chờ hạng thương gia tại Nội Bài. Phù hợp khách đã có Fast Track riêng.",
        price=450_000,
        night_surcharge=0,
        includes=[
            "Phòng chờ VIP Lounge",
            "Buffet nhẹ & đồ uống",
            "Khu vực làm việc riêng",
            "Tạp chí & giải trí",
            "Wifi tốc độ cao",
            "Thông báo lên máy bay",
        ],
    ),
]

PACKAGES_MAP = {pkg.code: pkg for pkg in FASTTRACK_PACKAGES}


def _is_night_time(flight_time: Optional[str]) -> bool:
    """Kiểm tra giờ bay có thuộc khung đêm 23:00-06:00 không."""
    if not flight_time:
        return False
    try:
        parts = flight_time.split(":")
        hour = int(parts[0])
        return hour >= 23 or hour < 6
    except (ValueError, IndexError):
        return False


# ---------------------------------------------------------------------------
# In-memory storage
# ---------------------------------------------------------------------------

_orders_store: List[dict] = []
_orders_seq = 0


def _generate_order_ref() -> str:
    global _orders_seq
    _orders_seq += 1
    return f"FT{_orders_seq:06d}{secrets.token_hex(2).upper()}"


def _generate_qr_link(order_ref: str, package_code: str) -> str:
    """QR content = link mua/thanh toán."""
    return f"https://abtrip.vn/fasttrack/pay/{order_ref}?pkg={package_code}"


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("/packages")
async def get_packages():
    """Lấy danh sách gói Fast Track + VIP Lounge."""
    return {
        "success": True,
        "data": [pkg.model_dump() for pkg in FASTTRACK_PACKAGES],
        "total": len(FASTTRACK_PACKAGES),
    }


@router.post("/orders", response_model=FastTrackOrderResponse)
async def create_order(req: FastTrackOrderRequest):
    """Tạo đơn Fast Track / VIP Lounge."""
    if req.package not in PACKAGES_MAP:
        raise HTTPException(400, f"Gói '{req.package}' không tồn tại. Các gói: {', '.join(PACKAGES_MAP.keys())}")

    pkg = PACKAGES_MAP[req.package]
    base_price = pkg.price * req.pax_count

    # Phụ thu đêm
    surcharge = 0
    if _is_night_time(req.flight_time) and pkg.night_surcharge > 0:
        surcharge = pkg.night_surcharge * req.pax_count

    total_price = base_price + surcharge
    order_ref = _generate_order_ref()
    qr_content = _generate_qr_link(order_ref, req.package)

    order_data = {
        "order_ref": order_ref,
        "tenant_id": req.tenant_id,
        "passenger_name": req.passenger_name,
        "flight_date": req.flight_date,
        "flight_time": req.flight_time,
        "flight_number": req.flight_number,
        "package": req.package,
        "package_name": pkg.name,
        "phone": req.phone,
        "pax_count": req.pax_count,
        "base_price": base_price,
        "night_surcharge": surcharge,
        "total_price": total_price,
        "currency": "VND",
        "qr_content": qr_content,
        "status": "pending",
        "created_at": datetime.utcnow().isoformat(),
    }
    _orders_store.append(order_data)

    msg = f"Đặt {pkg.name} cho {req.passenger_name} thành công! Mã đơn: {order_ref}"
    if surcharge > 0:
        msg += f" (bao gồm phụ thu đêm {surcharge:,}đ)"

    return FastTrackOrderResponse(
        success=True,
        order_ref=order_ref,
        package=req.package,
        passenger_name=req.passenger_name,
        flight_date=req.flight_date,
        base_price=base_price,
        night_surcharge=surcharge,
        total_price=total_price,
        qr_content=qr_content,
        message=msg,
    )


@router.get("/orders")
async def get_orders(
    tenant_id: int = Query(..., gt=0, description="ID CTV"),
    status: Optional[str] = Query(None, description="Lọc theo trạng thái"),
):
    """Lấy lịch sử Fast Track orders theo tenant_id."""
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
