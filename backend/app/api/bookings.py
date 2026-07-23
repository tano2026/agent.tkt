"""
Booking-related API routes.

Wraps AGT API endpoints: SearchFlight, BookFlight, IssueTicket, RetrieveBooking.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException
from app.services.abtrip_client import get_client

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/bookings", tags=["bookings"])


# ---------------------------------------------------------------------------
# POST /api/bookings/search — Search flights
# ---------------------------------------------------------------------------

@router.post("/search")
async def search_flights(body: dict[str, Any]) -> dict[str, Any]:
    """
    Search for flights.

    Wraps AGT POST /Flight/SearchFlight.

    Expected body fields:
    - System (str): e.g. "VN" for Vietnam Airlines
    - Adt (int): number of adults (default: 1)
    - Chd (int): number of children (default: 0)
    - Inf (int): number of infants (default: 0)
    - ListRoute (list[dict]): routes with Leg, StartPoint, EndPoint, DepartDate (DDMMYYYY)
    """
    logger.info("Search flights: system=%s", body.get("System"))
    client = get_client()

    result = await client.search_flight(
        system=body.get("System", ""),
        adt=body.get("Adt", 1),
        chd=body.get("Chd", 0),
        inf=body.get("Inf", 0),
        routes=body.get("ListRoute", []),
    )

    if not result.get("Success", False):
        logger.warning("Search flight failed: %s", result.get("Message"))
        raise HTTPException(status_code=400, detail=result)

    return result


# ---------------------------------------------------------------------------
# POST /api/bookings/book — Book a flight
# ---------------------------------------------------------------------------

@router.post("/book")
async def book_flight(body: dict[str, Any]) -> dict[str, Any]:
    """
    Book a flight.

    Wraps AGT POST /Flight/BookFlight.

    Expected body fields:
    - Forced (bool)
    - System (str)
    - GuestContact (dict): FullName, Phone, Email, Address
    - AgentContact (dict): FullName, Phone, Email
    - ListPassenger (list[dict]): passenger details
    - ListAirOption (list[dict]): selected flight options
    - Option (str)
    - Payment (dict): Method, BankCode, Amount, Currency
    """
    logger.info("Book flight: system=%s", body.get("System"))
    client = get_client()

    result = await client.book_flight(
        forced=body.get("Forced", False),
        system=body.get("System", ""),
        guest_contact=body.get("GuestContact"),
        agent_contact=body.get("AgentContact"),
        passengers=body.get("ListPassenger"),
        air_options=body.get("ListAirOption"),
        option=body.get("Option", ""),
        payment=body.get("Payment"),
    )

    if not result.get("Success", False):
        logger.warning("Book flight failed: %s", result.get("Message"))
        raise HTTPException(status_code=400, detail=result)

    return result


# ---------------------------------------------------------------------------
# POST /api/bookings/issue-ticket — Issue a ticket
# ---------------------------------------------------------------------------

@router.post("/issue-ticket")
async def issue_ticket(body: dict[str, Any]) -> dict[str, Any]:
    """
    Issue a ticket for a booked flight.

    Wraps AGT POST /Flight/IssueTicket.

    Expected body fields:
    - BookingCode (str): the booking code to issue ticket for
    """
    booking_code = body.get("BookingCode", "")
    if not booking_code:
        raise HTTPException(status_code=400, detail="BookingCode is required")

    logger.info("Issue ticket: booking_code=%s", booking_code)
    client = get_client()

    result = await client.issue_ticket(booking_code)

    if not result.get("Success", False):
        logger.warning("Issue ticket failed: %s", result.get("Message"))
        raise HTTPException(status_code=400, detail=result)

    return result


# ---------------------------------------------------------------------------
# GET /api/bookings/{code} — Retrieve booking details
# ---------------------------------------------------------------------------

@router.get("/{code}")
async def retrieve_booking(code: str) -> dict[str, Any]:
    """
    Retrieve booking details by booking code.

    Wraps AGT POST /Flight/RetrieveBooking.
    """
    if not code:
        raise HTTPException(status_code=400, detail="Booking code is required")

    logger.info("Retrieve booking: code=%s", code)
    client = get_client()

    result = await client.retrieve_booking(code)

    if not result.get("Success", False):
        logger.warning("Retrieve booking failed: %s", result.get("Message"))
        raise HTTPException(status_code=404, detail=result)

    return result
