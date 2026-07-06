"""
Pydantic models for all AGT (ABTrip) API entities.

These models represent the request/response structures used by the
external AGT cấp 1 API at https://api.abtrip.vn.

NOTE: Python 3.14.4 + Pydantic 2.12.5 bug — fields with type annotations
that match the field name (e.g. RequestInfo: RequestInfo) cause
"unevaluable-type-annotation". Workaround: use alias + lowercase field name.
"""

from typing import Any, Optional, List
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Authentication & Common Structures
# ---------------------------------------------------------------------------

class RequestInfo(BaseModel):
    """Authentication info sent in every AGT API request body."""
    PrivateKey: str = ""
    ApiAccount: str = ""
    ApiPassword: str = ""


class SessionInfo(BaseModel):
    """Session info returned from search results, used for ancillary queries."""
    Session: str = ""
    Airline: str = ""
    BookingCode: str = ""
    StartPoint: str = ""
    EndPoint: str = ""
    DepartDate: str = ""
    FlightNumber: str = ""


# ---------------------------------------------------------------------------
# SearchFlight
# ---------------------------------------------------------------------------

class Route(BaseModel):
    """A single flight leg/route in a search request."""
    Leg: int = 0
    StartPoint: str = ""
    EndPoint: str = ""
    DepartDate: str = ""  # Format: DDMMYYYY (e.g. 28032026)


class SearchFlightRequest(BaseModel):
    """Request body for POST /Flight/SearchFlight."""
    request_info: RequestInfo = Field(default_factory=RequestInfo, alias="RequestInfo")
    System: str = ""
    Adt: int = 1
    Chd: int = 0
    Inf: int = 0
    ListRoute: List[Route] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# BookFlight
# ---------------------------------------------------------------------------

class GuestContact(BaseModel):
    """Guest contact information for booking."""
    FullName: str = ""
    Phone: str = ""
    Email: str = ""
    Address: str = ""


class AgentContact(BaseModel):
    """Agent contact information for booking."""
    FullName: str = ""
    Phone: str = ""
    Email: str = ""


class Passenger(BaseModel):
    """Passenger information for booking."""
    FullName: str = ""
    FirstName: str = ""
    LastName: str = ""
    Birthday: str = ""  # DDMMYYYY
    Gender: str = ""  # Male / Female
    PassengerType: int = 0  # 0=Adult, 1=Child, 2=Infant
    Passport: str = ""
    PassportExpDate: str = ""
    Nationality: str = ""


class AirportFee(BaseModel):
    """Airport fee details per passenger per leg."""
    PassengerType: int = 0
    Leg: int = 0
    Price: float = 0.0
    Currency: str = "VND"
    Items: List[dict[str, Any]] = Field(default_factory=list)


class Baggage(BaseModel):
    """Baggage information per passenger per leg."""
    PassengerType: int = 0
    Leg: int = 0
    Value: str = ""
    Price: float = 0.0
    Currency: str = "VND"


class AirOption(BaseModel):
    """Selected flight option for booking."""
    Session: str = ""
    Airline: str = ""
    FlightNumber: str = ""
    StartPoint: str = ""
    EndPoint: str = ""
    DepartDate: str = ""
    DepartTime: str = ""
    ArriveDate: str = ""
    ArriveTime: str = ""
    Leg: int = 0
    FareClass: str = ""
    Price: float = 0.0
    Currency: str = "VND"
    ListBaggage: List[Baggage] = Field(default_factory=list)
    ListAirportFee: List[AirportFee] = Field(default_factory=list)


class PaymentInfo(BaseModel):
    """Payment information for booking."""
    Method: str = "VNPAY"
    BankCode: str = ""
    Amount: float = 0.0
    Currency: str = "VND"


class BookFlightRequest(BaseModel):
    """Request body for POST /Flight/BookFlight."""
    request_info: RequestInfo = Field(default_factory=RequestInfo, alias="RequestInfo")
    Forced: bool = False
    System: str = ""
    guest_contact: GuestContact = Field(default_factory=GuestContact, alias="GuestContact")
    agent_contact: AgentContact = Field(default_factory=AgentContact, alias="AgentContact")
    ListPassenger: List[Passenger] = Field(default_factory=list)
    ListAirOption: List[AirOption] = Field(default_factory=list)
    Option: str = ""
    payment: PaymentInfo = Field(default_factory=PaymentInfo, alias="Payment")


# ---------------------------------------------------------------------------
# IssueTicket
# ---------------------------------------------------------------------------

class IssueTicketRequest(BaseModel):
    """Request body for POST /Flight/IssueTicket."""
    request_info: RequestInfo = Field(default_factory=RequestInfo, alias="RequestInfo")
    BookingCode: str = ""


# ---------------------------------------------------------------------------
# RetrieveBooking
# ---------------------------------------------------------------------------

class RetrieveBookingRequest(BaseModel):
    """Request body for POST /Flight/RetrieveBooking."""
    request_info: RequestInfo = Field(default_factory=RequestInfo, alias="RequestInfo")
    BookingCode: str = ""


# ---------------------------------------------------------------------------
# GetAncillary, GetFareRule, GetSeatMap
# ---------------------------------------------------------------------------

class AncillaryRequest(BaseModel):
    """Request body for POST /Flight/GetAncillary."""
    request_info: RequestInfo = Field(default_factory=RequestInfo, alias="RequestInfo")
    ListSession: List[SessionInfo] = Field(default_factory=list)


class FareRuleRequest(BaseModel):
    """Request body for POST /Flight/GetFareRule."""
    request_info: RequestInfo = Field(default_factory=RequestInfo, alias="RequestInfo")
    ListSession: List[SessionInfo] = Field(default_factory=list)


class SeatMapRequest(BaseModel):
    """Request body for POST /Flight/GetSeatMap."""
    request_info: RequestInfo = Field(default_factory=RequestInfo, alias="RequestInfo")
    ListSession: List[SessionInfo] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Reference Data Requests
# ---------------------------------------------------------------------------

class ReferenceRequest(BaseModel):
    """Generic request for reference data endpoints (GetAirports, etc.)."""
    request_info: RequestInfo = Field(default_factory=RequestInfo, alias="RequestInfo")


# ---------------------------------------------------------------------------
# Response Models
# ---------------------------------------------------------------------------

class AGTResponse(BaseModel):
    """Base AGT API response wrapper."""
    StatusCode: Optional[str] = None
    Success: Optional[bool] = None
    Message: Optional[str] = None
    Data: Any = None


class BookingInfo(BaseModel):
    """Booking information returned from BookFlight or RetrieveBooking."""
    BookingCode: Optional[str] = None
    OrderId: Optional[str] = None
    OrderCode: Optional[str] = None
    TotalPrice: Optional[float] = None
    Currency: Optional[str] = None
    Status: Optional[str] = None
    ListTicket: Optional[List[dict[str, Any]]] = None
    ListBooking: Optional[List[dict[str, Any]]] = None


class BookFlightResponse(BaseModel):
    """Response from BookFlight endpoint."""
    StatusCode: Optional[str] = None
    Success: Optional[bool] = None
    Message: Optional[str] = None
    OrderId: Optional[str] = None
    OrderCode: Optional[str] = None
    TotalPrice: Optional[float] = None
    ListBooking: Optional[List[dict[str, Any]]] = None


class IssueTicketResponse(BaseModel):
    """Response from IssueTicket endpoint."""
    StatusCode: Optional[str] = None
    Success: Optional[bool] = None
    Message: Optional[str] = None
    Data: Any = None
