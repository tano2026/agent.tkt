"""
Pydantic models for the LLM Chat Bot — structured input/output for all agents.

Defines:
- Chat message models (user/assistant/system)
- Tool call argument models (search_flight, book_flight, etc.)
- Session state machine (idle → selecting → booking → confirmed)
- LLM response models with structured output
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator


# ─── Chat Messages ──────────────────────────────────────────────────────────

class MessageRole(str, Enum):
    user = "user"
    assistant = "assistant"
    system = "system"


class ChatMessage(BaseModel):
    """A single message in the conversation history."""
    role: MessageRole
    content: str
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())
    metadata: dict[str, Any] = Field(default_factory=dict)


# ─── Tool Arguments (Structured LLM Output) ─────────────────────────────────

class RouteInfo(BaseModel):
    """A single flight leg for search."""
    StartPoint: str = Field(..., description="Departure airport code (e.g. HAN, SGN)")
    EndPoint: str = Field(..., description="Arrival airport code (e.g. SGN, DAD)")
    DepartDate: str = Field(..., description="Departure date in DDMMYYYY format")


class FlightSearchArgs(BaseModel):
    """Arguments for the search_flight tool."""
    system: str = Field("1", description="AGT system code")
    adt: int = Field(1, ge=0, le=9, description="Number of adults")
    chd: int = Field(0, ge=0, le=9, description="Number of children")
    inf: int = Field(0, ge=0, le=9, description="Number of infants")
    routes: list[RouteInfo] = Field(..., min_length=1, description="Flight routes to search")


class PassengerInfo(BaseModel):
    """Passenger details collected from the user."""
    type: str = Field("adult", description="adult | child | infant")
    title: str = Field("", description="Mr | Mrs | Ms | Miss")
    lastName: str = Field(..., min_length=1, description="Last/family name")
    firstName: str = Field(..., min_length=1, description="First/given name")
    gender: str = Field("", description="Male | Female")
    birthDate: str = Field("", description="Birth date in DDMMYYYY")
    passport: str = Field("", description="Passport number (optional)")
    passportExpDate: str = Field("", description="Passport expiry in DDMMYYYY (optional)")
    nationality: str = Field("VN", description="ISO country code")

    @field_validator("type")
    @classmethod
    def validate_type(cls, v: str) -> str:
        if v not in ("adult", "child", "infant"):
            return "adult"
        return v

    @field_validator("title")
    @classmethod
    def validate_title(cls, v: str) -> str:
        valid = ("Mr", "Mrs", "Ms", "Miss")
        if v and v not in valid:
            # Try to match common Vietnamese titles
            mapping = {
                "anh": "Mr", "ông": "Mr", "chú": "Mr",
                "chị": "Ms", "cô": "Ms", "bà": "Mrs",
                "em": "Ms",
            }
            return mapping.get(v.lower(), "Mr" if v in ("male", "Male", "M") else "Ms")
        return v or "Mr"


class ContactInfo(BaseModel):
    """Contact information for the booking."""
    fullName: str = Field("", description="Full name of the contact person")
    phone: str = Field("", description="Phone number")
    email: str = Field("", description="Email address")
    address: str = Field("", description="Address (optional)")


class BookFlightArgs(BaseModel):
    """Arguments for the book_flight tool."""
    session: str = Field(..., description="Session code from search results")
    airline: str = Field(..., description="Airline code (VN, VJ, QH, etc.)")
    flightNumber: str = Field(..., description="Flight number")
    startPoint: str = Field(..., description="Departure airport")
    endPoint: str = Field(..., description="Arrival airport")
    departDate: str = Field(..., description="Departure date DDMMYYYY")
    departTime: str = Field(..., description="Departure time HHMM")
    arriveTime: str = Field(..., description="Arrival time HHMM")
    fareClass: str = Field("", description="Fare class code")
    price: float = Field(0.0, description="Price per passenger")
    currency: str = Field("VND", description="Currency code")
    passengers: list[PassengerInfo] = Field(..., min_length=1)
    contact: ContactInfo = Field(default_factory=ContactInfo)


# ─── Session State Machine ──────────────────────────────────────────────────

class SessionStep(str, Enum):
    """Booking flow state machine."""
    idle = "idle"
    search_results = "search_results"         # Just showed search results
    selecting_flight = "selecting_flight"     # User is selecting a specific flight
    collecting_passengers = "collecting_passengers"  # Gathering passenger info
    awaiting_confirmation = "awaiting_confirmation"  # Confirm before booking
    booking_in_progress = "booking_in_progress"      # BookFlight API call in progress
    booking_result = "booking_result"         # Booking complete, showing result


class SearchResult(BaseModel):
    """Cached search results for a session."""
    raw_data: dict[str, Any] = Field(default_factory=dict)
    formatted: str = ""
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())
    selected_flight_index: int | None = None


class BookingDraft(BaseModel):
    """Partial booking data being collected."""
    selected_route: dict[str, Any] = Field(default_factory=dict)
    passengers: list[PassengerInfo] = Field(default_factory=list)
    contact: ContactInfo = Field(default_factory=ContactInfo)
    step: SessionStep = SessionStep.idle
    error_message: str = ""


class SessionData(BaseModel):
    """Full session state persisted in Redis."""
    agent: str = "ticketing"
    messages: list[ChatMessage] = Field(default_factory=list)
    step: SessionStep = SessionStep.idle
    search_results: list[SearchResult] = Field(default_factory=list)
    booking_draft: BookingDraft = Field(default_factory=BookingDraft)
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now().isoformat())


# ─── LLM Response Models ────────────────────────────────────────────────────

class LLMResponse(BaseModel):
    """Structured response from the LLM gateway."""
    type: str = Field(..., description="text | tool_call | booking_result | error")
    content: str | dict[str, Any]
    tool_name: str = ""
    tool_args: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ToolDefinition(BaseModel):
    """OpenAI-compatible tool/function definition."""
    type: str = "function"
    function: dict[str, Any]


# ─── Shared tool definitions (used in both OpenAI and Gemini formats) ───────

SEARCH_FLIGHT_TOOL: ToolDefinition = ToolDefinition(
    function={
        "name": "search_flight",
        "description": "Search for available flights. Use this when the user asks to find/book flights between airports.",
        "parameters": {
            "type": "object",
            "properties": {
                "system": {"type": "string", "description": "AGT system code", "default": "1"},
                "adt": {"type": "integer", "description": "Number of adults (>=0)", "default": 1},
                "chd": {"type": "integer", "description": "Number of children (>=0)", "default": 0},
                "inf": {"type": "integer", "description": "Number of infants (>=0)", "default": 0},
                "routes": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "StartPoint": {"type": "string", "description": "Departure airport code (e.g. HAN, SGN, DAD)"},
                            "EndPoint": {"type": "string", "description": "Arrival airport code (e.g. SGN, DAD, HAN)"},
                            "DepartDate": {"type": "string", "description": "Departure date in DDMMYYYY format"}
                        },
                        "required": ["StartPoint", "EndPoint", "DepartDate"]
                    },
                    "minItems": 1
                }
            },
            "required": ["routes"]
        }
    }
)

BOOK_FLIGHT_TOOL: ToolDefinition = ToolDefinition(
    function={
        "name": "book_flight",
        "description": "Proceed to book a selected flight. Collect passenger information first, then call this tool to confirm the booking with AGT API.",
        "parameters": {
            "type": "object",
            "properties": {
                "session": {"type": "string", "description": "Session code from the search results"},
                "airline": {"type": "string", "description": "Airline code (VN, VJ, QH, etc.)"},
                "flightNumber": {"type": "string", "description": "Flight number"},
                "startPoint": {"type": "string", "description": "Departure airport code"},
                "endPoint": {"type": "string", "description": "Arrival airport code"},
                "departDate": {"type": "string", "description": "Departure date DDMMYYYY"},
                "departTime": {"type": "string", "description": "Departure time HHMM"},
                "arriveTime": {"type": "string", "description": "Arrival time HHMM"},
                "fareClass": {"type": "string", "description": "Fare class", "default": ""},
                "price": {"type": "number", "description": "Price per passenger"},
                "currency": {"type": "string", "description": "Currency code", "default": "VND"},
                "passengers": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "type": {"type": "string", "enum": ["adult", "child", "infant"], "default": "adult"},
                            "title": {"type": "string", "description": "Mr | Ms | Mrs"},
                            "lastName": {"type": "string", "description": "Last/family name"},
                            "firstName": {"type": "string", "description": "First/given name"},
                            "gender": {"type": "string", "description": "Male | Female"},
                            "birthDate": {"type": "string", "description": "Birth date DDMMYYYY"},
                            "passport": {"type": "string", "description": "Passport number", "default": ""},
                            "passportExpDate": {"type": "string", "description": "Passport expiry DDMMYYYY", "default": ""},
                            "nationality": {"type": "string", "description": "Nationality code", "default": "VN"}
                        },
                        "required": ["lastName", "firstName"]
                    }
                },
                "contact": {
                    "type": "object",
                    "description": "Contact information",
                    "properties": {
                        "fullName": {"type": "string", "description": "Contact full name"},
                        "phone": {"type": "string", "description": "Phone number"},
                        "email": {"type": "string", "description": "Email address"},
                        "address": {"type": "string", "description": "Address", "default": ""}
                    },
                    "default": {}
                }
            },
            "required": ["session", "airline", "flightNumber", "startPoint", "endPoint", "departDate", "departTime", "arriveTime", "passengers"]
        }
    }
)

# All available tools
AVAILABLE_TOOLS: list[ToolDefinition] = [
    SEARCH_FLIGHT_TOOL,
    BOOK_FLIGHT_TOOL,
]

# Tool name constants
TOOL_SEARCH_FLIGHT = "search_flight"
TOOL_BOOK_FLIGHT = "book_flight"
