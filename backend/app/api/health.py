"""
Health check endpoint.
"""

from __future__ import annotations

import logging
from datetime import datetime

from fastapi import APIRouter

logger = logging.getLogger(__name__)

router = APIRouter(tags=["health"])


@router.get("/api/health")
async def health_check() -> dict:
    """
    Health check endpoint.

    Returns basic service status information.
    """
    return {
        "status": "ok",
        "service": "abtrip-backend",
        "timestamp": datetime.utcnow().isoformat(),
    }
