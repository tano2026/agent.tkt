"""
ABTrip Smart Agent — API Flights (Mock Phase 1)
Vé máy bay: search, book, track PNR.

Giả data cho Phase 1, in-memory, không DB.
Router prefix: /api/v1/flights
"""

import logging
import secrets
from datetime import datetime, date, timedelta
from typing import Optional, List, Dict

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field, field_validator

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/flights", tags=["Flights"])

# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------

class SearchRequest(BaseModel):
    origin: str = Field(..., min_length=3, max_length=3, description="Mã sân bay đi (VD: HAN)")
    destination: str = Field(..., min_length=3, max_length=3, description="Mã sân bay đến (VD: SGN)")
    depart_date: str = Field(..., description="Ngày đi dạng YYYY-MM-DD")
    passengers: int = Field(default=1, ge=1, le=10)
    return_date: Optional[str] = Field(None, description="Ngày về (nếu khứ hồi) dạng YYYY-MM-DD")

    @field_validator("origin", "destination")
    @classmethod
    def validate_airport(cls, v: str) -> str:
        return v.upper()

class FlightResult(BaseModel):
    airline: str
    flight_code: str
    origin: str
    destination: str
    depart_time: str
    arrive_time: str
    duration_minutes: int
    price: int          # VND
    currency: str = "VND"
    seats_available: int
    aircraft: str

class SearchResponse(BaseModel):
    success: bool
    data: List[FlightResult]
    total: int
    message: str

class PassengerInfo(BaseModel):
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    gender: str = Field(..., pattern="^(Nam|Nữ|Other)$")
    dob: str = Field(..., description="DD/MM/YYYY")

class ContactInfo(BaseModel):
    phone: str = Field(..., min_length=10, max_length=20)
    email: str = Field(..., max_length=200)

class BookFlightRequest(BaseModel):
    tenant_id: int = Field(..., gt=0)
    flight_code: str = Field(..., min_length=2, max_length=20)
    origin: str = Field(..., min_length=3, max_length=3, description='Mã sân bay đi (VD: HAN)')
    destination: str = Field(..., min_length=3, max_length=3, description='Mã sân bay đến (VD: SGN)')
    passengers: List[PassengerInfo] = Field(..., min_length=1, max_length=10)
    contact: ContactInfo

class BookFlightResponse(BaseModel):
    success: bool
    booking_ref: str
    flight_code: str
    total_price: int
    currency: str = "VND"
    status: str
    message: str

class PNRResponse(BaseModel):
    success: bool
    booking_ref: str
    flight_code: str
    status: str
    passengers: List[dict]
    contact: dict
    total_price: int
    currency: str = "VND"
    created_at: str

# ---------------------------------------------------------------------------
# Mock flight data — giá thị trường 2026
# ---------------------------------------------------------------------------

AIRLINES = {
    "VJ": {"name": "VietJet Air", "logo": "vietjet"},
    "QH": {"name": "Bamboo Airways", "logo": "bamboo"},
    "VN": {"name": "Vietnam Airlines", "logo": "vnairlines"},
    "BL": {"name": "Jetstar Pacific", "logo": "jetstar"},
    "VU": {"name": "Vietravel Airlines", "logo": "vietravel"},
}

# Base prices VND (1 chiều) — thị trường 2026
ROUTE_PRICES = {
    ("HAN", "SGN"): {"base": 1_200_000, "range": (800_000, 2_500_000)},
    ("SGN", "HAN"): {"base": 1_200_000, "range": (800_000, 2_500_000)},
    ("HAN", "DAD"): {"base": 650_000, "range": (400_000, 1_500_000)},
    ("DAD", "HAN"): {"base": 650_000, "range": (400_000, 1_500_000)},
    ("SGN", "DAD"): {"base": 700_000, "range": (450_000, 1_600_000)},
    ("DAD", "SGN"): {"base": 700_000, "range": (450_000, 1_600_000)},
    ("HAN", "CXR"): {"base": 750_000, "range": (500_000, 1_800_000)},
    ("CXR", "HAN"): {"base": 750_000, "range": (500_000, 1_800_000)},
    ("SGN", "CXR"): {"base": 550_000, "range": (350_000, 1_300_000)},
    ("CXR", "SGN"): {"base": 550_000, "range": (350_000, 1_300_000)},
    ("HAN", "VII"): {"base": 600_000, "range": (400_000, 1_400_000)},
    ("VII", "HAN"): {"base": 600_000, "range": (400_000, 1_400_000)},
    ("SGN", "VII"): {"base": 500_000, "range": (300_000, 1_200_000)},
    ("VII", "SGN"): {"base": 500_000, "range": (300_000, 1_200_000)},
    # Quốc tế
    ("HAN", "BKK"): {"base": 2_500_000, "range": (1_500_000, 5_000_000)},
    ("SGN", "BKK"): {"base": 2_200_000, "range": (1_300_000, 4_500_000)},
    ("HAN", "SIN"): {"base": 3_000_000, "range": (2_000_000, 6_000_000)},
    ("SGN", "SIN"): {"base": 2_800_000, "range": (1_800_000, 5_500_000)},
}

FLIGHT_DURATIONS = {
    ("HAN", "SGN"): 125,
    ("SGN", "HAN"): 125,
    ("HAN", "DAD"): 70,
    ("DAD", "HAN"): 70,
    ("SGN", "DAD"): 65,
    ("DAD", "SGN"): 65,
    ("HAN", "CXR"): 95,
    ("CXR", "HAN"): 95,
    ("SGN", "CXR"): 55,
    ("CXR", "SGN"): 55,
    ("HAN", "VII"): 80,
    ("VII", "HAN"): 80,
    ("SGN", "VII"): 65,
    ("VII", "SGN"): 65,
    ("HAN", "BKK"): 130,
    ("SGN", "BKK"): 110,
    ("HAN", "SIN"): 190,
    ("SGN", "SIN"): 130,
}

# Mock flight numbers per airline per route
FLIGHT_NUMBERS = {
    "VJ": [
        "VJ461", "VJ463", "VJ465", "VJ467", "VJ469",
        "VJ133", "VJ135", "VJ137", "VJ139",
        "VJ201", "VJ203", "VJ205",
    ],
    "VN": [
        "VN271", "VN273", "VN275", "VN277",
        "VN181", "VN183", "VN185", "VN187",
        "VN101", "VN103", "VN105",
    ],
    "QH": [
        "QH151", "QH153", "QH155", "QH157",
        "QH201", "QH203", "QH205",
        "QH301", "QH303",
    ],
    "BL": [
        "BL601", "BL603", "BL605", "BL607",
        "BL701", "BL703", "BL705",
    ],
    "VU": [
        "VU101", "VU103", "VU105",
        "VU201", "VU203",
    ],
}

AIRCRAFT_TYPES = ["A320", "A321", "B787", "A350", "E190", "ATR72"]

DEPART_TIMES = [
    "06:00", "07:30", "09:15", "10:45", "12:00",
    "13:30", "15:00", "16:45", "18:30", "20:00", "21:30",
]


def _generate_mock_flights(origin: str, destination: str, depart_date: str) -> List[FlightResult]:
    """Generate 3-5 mock flights for a route."""
    import random

    route = (origin.upper(), destination.upper())
    price_info = ROUTE_PRICES.get(route)
    if not price_info:
        # Unknown route: generate generic price
        base_price = 1_500_000
        price_range = (1_000_000, 3_000_000)
    else:
        base_price = price_info["base"]
        price_range = price_info["range"]

    duration = FLIGHT_DURATIONS.get(route, 120)
    num_flights = random.randint(3, 5)
    flights = []

    # Pick airlines that serve this route
    if route[0] in ("HAN", "SGN") or route[1] in ("HAN", "SGN"):
        active_airlines = ["VJ", "VN", "QH", "BL"]
    else:
        active_airlines = ["VJ", "VN", "QH"]

    selected_airlines = random.sample(active_airlines, min(num_flights, len(active_airlines)))
    if len(selected_airlines) < num_flights:
        # Fill remaining with repeats
        while len(selected_airlines) < num_flights:
            selected_airlines.append(random.choice(active_airlines))

    assigned_times = random.sample(DEPART_TIMES, min(num_flights, len(DEPART_TIMES)))
    # If we need more times, pick from the full list
    while len(assigned_times) < num_flights:
        assigned_times.append(random.choice(DEPART_TIMES))
    assigned_times.sort()

    for i in range(num_flights):
        airline_code = selected_airlines[i]
        airline_name = AIRLINES[airline_code]["name"]

        # Pick a flight number
        code_list = FLIGHT_NUMBERS[airline_code]
        flight_code = random.choice(code_list)

        depart_time = assigned_times[i]
        # Calculate arrive time
        dep_h, dep_m = map(int, depart_time.split(":"))
        total_min = dep_h * 60 + dep_m + duration
        arrive_h = (total_min // 60) % 24
        arrive_m = total_min % 60
        arrive_time = f"{arrive_h:02d}:{arrive_m:02d}"

        # Price variation
        price_variation = random.randint(-200_000, 300_000)
        price = max(price_range[0], min(price_range[1], base_price + price_variation))
        # Round to nice number
        price = (price // 1000) * 1000

        flight = FlightResult(
            airline=airline_name,
            flight_code=flight_code,
            origin=origin.upper(),
            destination=destination.upper(),
            depart_time=depart_time,
            arrive_time=arrive_time,
            duration_minutes=duration,
            price=price,
            seats_available=random.randint(3, 120),
            aircraft=random.choice(AIRCRAFT_TYPES),
        )
        flights.append(flight)

    # Sort by price ascending
    flights.sort(key=lambda f: f.price)
    return flights


# ---------------------------------------------------------------------------
# In-memory storage for bookings
# ---------------------------------------------------------------------------

_booking_store: Dict[str, dict] = {}


def _generate_booking_ref() -> str:
    return f"AB{secrets.token_hex(4).upper()}"


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("/search", response_model=SearchResponse)
async def search_flights(
    origin: str = Query(..., min_length=3, max_length=3, description="Sân bay đi"),
    destination: str = Query(..., min_length=3, max_length=3, description="Sân bay đến"),
    depart_date: str = Query(..., description="Ngày đi YYYY-MM-DD"),
    passengers: int = Query(default=1, ge=1, le=10),
):
    """Tìm chuyến bay — giả data Phase 1."""
    origin = origin.upper()
    destination = destination.upper()

    if origin == destination:
        raise HTTPException(400, "Sân bay đi và đến phải khác nhau")

    flights = _generate_mock_flights(origin, destination, depart_date)

    return SearchResponse(
        success=True,
        data=flights,
        total=len(flights),
        message=f"Tìm thấy {len(flights)} chuyến bay từ {origin} đến {destination} ngày {depart_date}",
    )


@router.post("/book", response_model=BookFlightResponse)
async def book_flight(req: BookFlightRequest):
    """Đặt vé máy bay — giả data, trả về booking_ref."""
    # Validate flight code format (mock — accept any valid format)
    valid_airlines = list(AIRLINES.keys())
    airline_prefix = req.flight_code[:2].upper()

    if airline_prefix not in valid_airlines and not req.flight_code[:1].isalpha():
        raise HTTPException(400, f"Mã chuyến bay không hợp lệ: {req.flight_code}")

    # Calculate mock price based on actual route
    route_key = (req.origin.upper(), req.destination.upper())
    price_info = ROUTE_PRICES.get(route_key, {"base": 1_200_000})
    base_price_per_pax = price_info["base"]

    total_price = base_price_per_pax * len(req.passengers)

    booking_ref = _generate_booking_ref()
    booking_data = {
        "booking_ref": booking_ref,
        "flight_code": req.flight_code.upper(),
        "passengers": [p.model_dump() for p in req.passengers],
        "contact": req.contact.model_dump(),
        "total_price": total_price,
        "currency": "VND",
        "status": "confirmed",
        "tenant_id": req.tenant_id,
        "created_at": datetime.utcnow().isoformat(),
    }
    _booking_store[booking_ref] = booking_data

    return BookFlightResponse(
        success=True,
        booking_ref=booking_ref,
        flight_code=req.flight_code.upper(),
        total_price=total_price,
        status="confirmed",
        message=f"Đặt vé {req.flight_code} thành công! Mã đặt chỗ: {booking_ref}",
    )


@router.get("/pnr/{booking_ref}", response_model=PNRResponse)
async def track_pnr(booking_ref: str):
    """Tra cứu trạng thái booking theo mã PNR."""
    booking = _booking_store.get(booking_ref.upper())
    if not booking:
        # generate mock PNR data if not found (for demo purposes)
        booking = {
            "booking_ref": booking_ref.upper(),
            "flight_code": "VJ461",
            "passengers": [{"first_name": "Demo", "last_name": "Passenger", "gender": "Nam", "dob": "01/01/1995"}],
            "contact": {"phone": "0900000000", "email": "demo@example.com"},
            "total_price": 1_500_000,
            "currency": "VND",
            "status": "confirmed",
            "tenant_id": 1,
            "created_at": (datetime.utcnow() - timedelta(hours=2)).isoformat(),
        }

    return PNRResponse(
        success=True,
        booking_ref=booking["booking_ref"],
        flight_code=booking["flight_code"],
        status=booking["status"],
        passengers=booking["passengers"],
        contact=booking["contact"],
        total_price=booking["total_price"],
        currency=booking.get("currency", "VND"),
        created_at=booking["created_at"],
    )
