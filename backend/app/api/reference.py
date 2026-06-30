"""
Reference data API routes.

Wraps AGT API endpoints: GetAirports, GetAirlines, GetAircrafts.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException
from app.services.abtrip_client import get_client

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/reference", tags=["reference"])


# ---------------------------------------------------------------------------
# GET /api/reference/airports
# ---------------------------------------------------------------------------

@router.get("/airports")
async def get_airports() -> dict[str, Any]:
    """
    Get list of airports.

    Wraps AGT POST /Flight/GetAirports.
    """
    logger.info("Fetching airports list")
    client = get_client()
    result = await client.get_airports()

    if not result.get("Success", False):
        logger.warning("Get airports failed: %s", result.get("Message"))
        raise HTTPException(status_code=502, detail=result)

    return result


# ---------------------------------------------------------------------------
# GET /api/reference/airlines
# ---------------------------------------------------------------------------

@router.get("/airlines")
async def get_airlines() -> dict[str, Any]:
    """
    Get list of airlines.

    Wraps AGT POST /Flight/GetAirlines.
    """
    logger.info("Fetching airlines list")
    client = get_client()
    result = await client.get_airlines()

    if not result.get("Success", False):
        logger.warning("Get airlines failed: %s", result.get("Message"))
        raise HTTPException(status_code=502, detail=result)

    return result


# ---------------------------------------------------------------------------
# GET /api/reference/aircrafts
# ---------------------------------------------------------------------------

@router.get("/aircrafts")
async def get_aircrafts() -> dict[str, Any]:
    """
    Get list of aircraft types.

    Wraps AGT POST /Flight/GetAircrafts.
    """
    logger.info("Fetching aircrafts list")
    client = get_client()
    result = await client.get_aircrafts()

    if not result.get("Success", False):
        logger.warning("Get aircrafts failed: %s", result.get("Message"))
        raise HTTPException(status_code=502, detail=result)

    return result
