"""
ABTrip Smart Agent — API Visa Tư Vấn (Mock Phase 1)
Hỗ trợ: Hàn Quốc, Nhật, Trung Quốc, Schengen, Mỹ, Úc, Anh.
Requirements & consultation checklist.

Router prefix: /api/v1/visa
"""

import logging
import secrets
from datetime import datetime, date
from typing import Optional, List, Dict

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/visa", tags=["Visa"])

# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------

class VisaRequirement(BaseModel):
    country: str
    country_name_vn: str
    passport_type: str         # "VN" | "US" | "UK" | ...
    visa_type: str             # "Tourist" | "Business" | "Student"
    processing_days: str
    visa_fee: int              # VND — phí dịch vụ tư vấn + xử lý
    embassy_fee: int           # VND — phí lãnh sự (tham khảo)
    required_docs: List[str]
    notes: List[str]

class ConsultationRequest(BaseModel):
    tenant_id: int = Field(..., gt=0)
    country: str = Field(..., min_length=2, max_length=50)
    passport_type: str = Field(default="VN", max_length=10, description="Loại hộ chiếu: VN, US, UK...")
    visa_type: str = Field(default="Tourist", pattern="^(Tourist|Business|Student)$")
    passport_info: str = Field(..., max_length=500, description="Thông tin hộ chiếu (số, họ tên) trên passport")
    full_name: str = Field(..., min_length=1, max_length=200)
    notes: Optional[str] = Field(None, max_length=1000, description="Ghi chú thêm")

class ConsultationResponse(BaseModel):
    success: bool
    consultation_ref: str
    country: str
    passport_type: str
    visa_type: str
    status: str
    checklist: List[dict]
    total_estimated_fee: int
    currency: str = "VND"
    message: str

class ConsultationDetail(BaseModel):
    consultation_ref: str
    tenant_id: int
    country: str
    passport_type: str
    visa_type: str
    full_name: str
    status: str
    checklist: List[dict]
    total_estimated_fee: int
    notes: Optional[str]
    created_at: str

# ---------------------------------------------------------------------------
# Visa data — 7 quốc gia, giá thị trường 2026
# ---------------------------------------------------------------------------

VISA_REQUIREMENTS = {
    "Korea": VisaRequirement(
        country="Korea",
        country_name_vn="Hàn Quốc",
        passport_type="VN",
        visa_type="Tourist",
        processing_days="5-7 ngày làm việc",
        visa_fee=850_000,
        embassy_fee=0,  # Miễn phí lãnh sự với đại lý ủy quyền
        required_docs=[
            "Hộ chiếu gốc (còn hạn ≥ 6 tháng)",
            "Đơn xin visa Hàn Quốc (mẫu mới nhất)",
            "Ảnh thẻ 3.5x4.5cm (nền trắng, 2 ảnh)",
            "CMND/CCCD (bản sao công chứng)",
            "Sổ hộ khẩu (bản sao công chứng)",
            "Giấy xác nhận công tác / Hợp đồng lao động",
            "Sao kê tài khoản ngân hàng 3 tháng gần nhất",
            "Giấy đăng ký tạm trú (nếu ở tỉnh khác)",
            "Lịch trình du lịch chi tiết",
            "Xác nhận đặt vé máy bay khứ hồi",
        ],
        notes=[
            "Có thể phỏng vấn nếu hồ sơ có vấn đề.",
            "Nữ dưới 25 tuổi đi một mình: cần giải trình rõ ràng.",
            "Visa Hàn Quốc thường cấp 1 năm multi nếu có lịch sử tốt.",
        ],
    ),
    "Japan": VisaRequirement(
        country="Japan",
        country_name_vn="Nhật Bản",
        passport_type="VN",
        visa_type="Tourist",
        processing_days="7-10 ngày làm việc",
        visa_fee=1_200_000,
        embassy_fee=0,
        required_docs=[
            "Hộ chiếu gốc (còn hạn ≥ 6 tháng)",
            "Đơn xin visa Nhật Bản (có dán ảnh)",
            "Ảnh thẻ 4.5x4.5cm (2 ảnh, nền trắng)",
            "CMND/CCCD (bản sao công chứng)",
            "Sổ hộ khẩu (bản sao công chứng)",
            "Giấy xác nhận công tác / Đăng ký kinh doanh",
            "Sao kê tài khoản ngân hàng 6 tháng (số dư ≥ 100 triệu)",
            "Giấy tờ chứng minh tài sản (sổ đỏ, xe, tiết kiệm)",
            "Lịch trình du lịch chi tiết từng ngày",
            "Xác nhận đặt khách sạn & vé máy bay",
        ],
        notes=[
            "Visa Nhật yêu cầu tài chính khá cao — số dư tối thiểu 100 triệu.",
            "Hồ sơ thiếu sót là lý do từ chối phổ biến nhất.",
            "Có thể yêu cầu bảo hiểm du lịch Nhật Bản.",
        ],
    ),
    "China": VisaRequirement(
        country="China",
        country_name_vn="Trung Quốc",
        passport_type="VN",
        visa_type="Tourist",
        processing_days="4-6 ngày làm việc",
        visa_fee=950_000,
        embassy_fee=0,
        required_docs=[
            "Hộ chiếu gốc (còn hạn ≥ 6 tháng)",
            "Đơn xin visa Trung Quốc (điền online, in ra ký)",
            "Ảnh thẻ 3.3x4.8cm (2 ảnh, nền trắng)",
            "CMND/CCCD (bản sao)",
            "Giấy mời / Xác nhận đặt tour từ công ty lữ hành Trung Quốc",
            "Giấy xác nhận công tác",
            "Sao kê tài khoản ngân hàng 3 tháng",
            "Vé máy bay khứ hồi & xác nhận khách sạn",
            "Bảo hiểm du lịch Trung Quốc",
        ],
        notes=[
            "Visa Trung Quốc cần giấy mời từ đối tác Trung Quốc (nếu đi business).",
            "Công dân Việt Nam đi tour đoàn được ưu tiên xử lý nhanh.",
            "Cần có bảo hiểm du lịch Trung Quốc bắt buộc.",
        ],
    ),
    "Schengen": VisaRequirement(
        country="Schengen",
        country_name_vn="Khối Schengen (Châu Âu)",
        passport_type="VN",
        visa_type="Tourist",
        processing_days="10-15 ngày làm việc",
        visa_fee=2_500_000,
        embassy_fee=1_600_000,
        required_docs=[
            "Hộ chiếu gốc (còn hạn ≥ 6 tháng, còn 2 trang trống)",
            "Đơn xin visa Schengen (điền online, in ra ký)",
            "Ảnh thẻ 3.5x4.5cm (2 ảnh, nền trắng, chụp trong 6 tháng)",
            "CMND/CCCD + Sổ hộ khẩu (bản sao công chứng)",
            "Giấy xác nhận công tác (bằng tiếng Anh)",
            "Sao kê tài khoản ngân hàng 6 tháng gần nhất (số dư ≥ 200 triệu)",
            "Giấy tờ chứng minh tài sản: sổ đỏ, tiết kiệm, cổ phiếu",
            "Bảo hiểm du lịch Schengen (tối thiểu 30.000 EUR)",
            "Lịch trình du lịch chi tiết từng ngày (bằng tiếng Anh)",
            "Xác nhận đặt vé máy bay khứ hồi",
            "Xác nhận đặt khách sạn tất cả các đêm",
            "Sao kê thẻ tín dụng (nếu có)",
        ],
        notes=[
            "Schengen là visa khó nhất — cần chuẩn bị hồ sơ rất kỹ.",
            "Phải nộp tại ĐSQ / Lãnh sự quán nước đến đầu tiên.",
            "Có thể yêu cầu phỏng vấn (nhất là với người đi lần đầu).",
            "Thời gian xử lý có thể lên tới 30 ngày vào mùa cao điểm.",
        ],
    ),
    "USA": VisaRequirement(
        country="USA",
        country_name_vn="Mỹ",
        passport_type="VN",
        visa_type="Tourist",
        processing_days="20-30 ngày làm việc (chờ lịch phỏng vấn)",
        visa_fee=3_500_000,
        embassy_fee=2_300_000,
        required_docs=[
            "Hộ chiếu gốc (còn hạn ≥ 6 tháng)",
            "Đơn DS-160 (điền online, xác nhận in ra)",
            "Ảnh thẻ 5x5cm (nền trắng, chụp trong 6 tháng)",
            "CMND/CCCD + Sổ hộ khẩu (bản sao công chứng)",
            "Giấy xác nhận công tác (bằng tiếng Anh, có mẫu riêng)",
            "Sao kê tài khoản ngân hàng 6 tháng (số dư ≥ 200 triệu)",
            "Giấy tờ chứng minh tài sản: sổ đỏ, xe, tiết kiệm",
            "Giấy đăng ký kết hôn / Ly hôn (nếu có)",
            "Giấy khai sinh của con (nếu đi cùng gia đình)",
            "Lịch trình du lịch Mỹ",
            "Vé máy bay khứ hồi (không bắt buộc nhưng nên có)",
            "Bảo hiểm du lịch Mỹ",
        ],
        notes=[
            "Visa Mỹ bắt buộc phỏng vấn trực tiếp tại ĐSQ Hà Nội hoặc Tổng Lãnh sự quán TP.HCM.",
            "Thời gian chờ lịch phỏng vấn có thể 1-3 tháng.",
            "Cần chuẩn bị kỹ câu hỏi phỏng vấn — rất nhiều người bị từ chối vì trả lời không tốt.",
            "Visa B1/B2 thường cấp 1 năm hoặc 10 năm nếu có lịch sử du lịch tốt.",
        ],
    ),
    "Australia": VisaRequirement(
        country="Australia",
        country_name_vn="Úc",
        passport_type="VN",
        visa_type="Tourist",
        processing_days="10-20 ngày làm việc",
        visa_fee=2_200_000,
        embassy_fee=1_800_000,
        required_docs=[
            "Hộ chiếu gốc (còn hạn ≥ 6 tháng)",
            "Đơn xin visa Úc online (ImmiAccount)",
            "Ảnh thẻ 3.5x4.5cm (bản scan)",
            "CMND/CCCD + Sổ hộ khẩu (bản scan công chứng)",
            "Giấy xác nhận công tác (bằng tiếng Anh)",
            "Sao kê tài khoản ngân hàng 6 tháng (số dư ≥ 150 triệu)",
            "Giấy tờ chứng minh tài sản",
            "Bảo hiểm du lịch Úc",
            "Lịch trình du lịch chi tiết",
            "Giấy tờ chứng minh quan hệ gia đình (nếu có người thân ở Úc)",
        ],
        notes=[
            "Visa Úc nộp online 100% — không cần nộp hộ chiếu gốc.",
            "Thường cấp visa 1 năm multi entry.",
            "Có thể yêu cầu khám sức khỏe nếu ở lại > 3 tháng.",
        ],
    ),
    "UK": VisaRequirement(
        country="UK",
        country_name_vn="Anh Quốc",
        passport_type="VN",
        visa_type="Tourist",
        processing_days="10-15 ngày làm việc",
        visa_fee=2_800_000,
        embassy_fee=2_000_000,
        required_docs=[
            "Hộ chiếu gốc (còn hạn ≥ 6 tháng)",
            "Đơn xin visa UK online (GOV.UK)",
            "Ảnh thẻ 3.5x4.5cm (nền trắng)",
            "CMND/CCCD + Sổ hộ khẩu (bản sao công chứng)",
            "Giấy xác nhận công tác (bằng tiếng Anh)",
            "Sao kê tài khoản ngân hàng 6 tháng (số dư ≥ 200 triệu)",
            "Giấy tờ chứng minh tài sản: sổ đỏ, tiết kiệm",
            "Bảo hiểm du lịch Anh",
            "Lịch trình du lịch chi tiết",
            "Xác nhận đặt khách sạn & vé máy bay",
            "Thư mời (nếu đi thăm người thân hoặc business)",
        ],
        notes=[
            "Visa UK yêu cầu sinh trắc học (vân tay) tại Trung tâm tiếp nhận hồ sơ.",
            "Có dịch vụ xử lý nhanh (priority) với phí cao hơn.",
            "Thường cấp 6 tháng hoặc 2 năm multi entry.",
        ],
    ),
}

# ---------------------------------------------------------------------------
# In-memory storage
# ---------------------------------------------------------------------------

_consultations_store: List[dict] = []
_consultations_seq = 0

SUPPORTED_COUNTRIES = list(VISA_REQUIREMENTS.keys())


def _generate_consultation_ref() -> str:
    global _consultations_seq
    _consultations_seq += 1
    return f"VISA{_consultations_seq:06d}{secrets.token_hex(2).upper()}"


def _build_checklist(country: str, passport_type: str, visa_type: str) -> List[dict]:
    """Build checklist từ VisaRequirement."""
    req = VISA_REQUIREMENTS.get(country)
    if not req:
        return []

    checklist = []
    for i, doc in enumerate(req.required_docs):
        checklist.append({
            "id": i + 1,
            "document": doc,
            "status": "pending",
            "note": "",
        })
    return checklist


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("/supported-countries")
async def get_supported_countries():
    """Danh sách quốc gia hỗ trợ tư vấn visa."""
    countries = []
    for code, req in VISA_REQUIREMENTS.items():
        countries.append({
            "code": code,
            "name": code,
            "name_vn": req.country_name_vn,
            "processing_days": req.processing_days,
            "service_fee": req.visa_fee,
            "embassy_fee": req.embassy_fee,
        })
    return {
        "success": True,
        "data": countries,
        "total": len(countries),
    }


@router.get("/requirements/{country}")
async def get_requirements(
    country: str,
    passport_type: str = Query(default="VN", description="Loại hộ chiếu"),
    visa_type: str = Query(default="Tourist", description="Loại visa"),
):
    """Lấy danh sách giấy tờ cần cho visa."""
    lookup_key = None
    for key in VISA_REQUIREMENTS:
        if key.lower() == country.lower():
            lookup_key = key
            break
        req = VISA_REQUIREMENTS[key]
        if req.country_name_vn.lower() == country.lower():
            lookup_key = key
            break

    if not lookup_key:
        raise HTTPException(404, f"Quốc gia '{country}' không được hỗ trợ. Hỗ trợ: {', '.join(SUPPORTED_COUNTRIES)}")

    req = VISA_REQUIREMENTS[lookup_key]

    return {
        "success": True,
        "country": lookup_key,
        "country_name_vn": req.country_name_vn,
        "passport_type": passport_type,
        "visa_type": visa_type,
        "processing_days": req.processing_days,
        "visa_fee": req.visa_fee,
        "embassy_fee": req.embassy_fee,
        "required_documents": req.required_docs,
        "total_count": len(req.required_docs),
        "notes": req.notes,
    }


@router.post("/consultations", response_model=ConsultationResponse)
async def create_consultation(req: ConsultationRequest):
    """Tạo tư vấn visa mới."""
    # Find country
    lookup_key = None
    for key in VISA_REQUIREMENTS:
        if key.lower() == req.country.lower():
            lookup_key = key
            break
        r = VISA_REQUIREMENTS[key]
        if r.country_name_vn.lower() == req.country.lower():
            lookup_key = key
            break

    if not lookup_key:
        raise HTTPException(404, f"Quốc gia '{req.country}' không được hỗ trợ. Hỗ trợ: {', '.join(SUPPORTED_COUNTRIES)}")

    visa_req = VISA_REQUIREMENTS[lookup_key]
    consultation_ref = _generate_consultation_ref()
    checklist = _build_checklist(lookup_key, req.passport_type, req.visa_type)
    total_fee = visa_req.visa_fee + visa_req.embassy_fee

    consultation_data = {
        "consultation_ref": consultation_ref,
        "tenant_id": req.tenant_id,
        "country": lookup_key,
        "country_name_vn": visa_req.country_name_vn,
        "passport_type": req.passport_type,
        "visa_type": req.visa_type,
        "full_name": req.full_name,
        "passport_info": req.passport_info,
        "status": "pending",
        "checklist": checklist,
        "total_estimated_fee": total_fee,
        "currency": "VND",
        "notes": req.notes,
        "created_at": datetime.utcnow().isoformat(),
    }
    _consultations_store.append(consultation_data)

    return ConsultationResponse(
        success=True,
        consultation_ref=consultation_ref,
        country=lookup_key,
        passport_type=req.passport_type,
        visa_type=req.visa_type,
        status="pending",
        checklist=checklist,
        total_estimated_fee=total_fee,
        message=f"Tạo tư vấn visa {visa_req.country_name_vn} thành công! Mã: {consultation_ref}. Kiểm tra danh sách giấy tờ cần chuẩn bị.",
    )


@router.get("/consultations")
async def get_consultations(
    tenant_id: int = Query(..., gt=0, description="ID CTV"),
    status: Optional[str] = Query(None),
):
    """Lấy lịch sử tư vấn visa theo tenant_id."""
    result = []
    for c in _consultations_store:
        if c["tenant_id"] != tenant_id:
            continue
        if status and c["status"] != status:
            continue
        result.append(c)

    return {
        "success": True,
        "data": result,
        "total": len(result),
        "tenant_id": tenant_id,
    }
