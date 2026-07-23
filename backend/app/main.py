"""
FastAPI application entry point for the ABTrip Flight Booking Backend.

This module initializes the FastAPI app, configures CORS, logging,
and registers all API routers.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import uvicorn
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse

from app.api.bookings import router as bookings_router
from app.api.reference import router as reference_router
from app.api.health import router as health_router
from app.api.chat import router as chat_router
from app.services.config import get_settings
from app.services.abtrip_client import close_client
from app.services.llm_gateway import close_llm

# ---------------------------------------------------------------------------
# Logging configuration
# ---------------------------------------------------------------------------

def configure_logging() -> None:
    """Set up application-wide logging."""
    settings = get_settings()
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


# ---------------------------------------------------------------------------
# Application lifespan
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Application lifespan handler.

    - Startup: configure logging
    - Shutdown: clean up resources (close HTTP client)
    """
    configure_logging()
    logger = logging.getLogger(__name__)
    logger.info("ABTrip backend starting up...")
    yield
    logger.info("ABTrip backend shutting down...")
    await close_client()
    await close_llm()


# ---------------------------------------------------------------------------
# FastAPI application
# ---------------------------------------------------------------------------

app = FastAPI(
    title="ABTrip Flight Booking Backend",
    description="Backend service for ABTrip flight booking system. "
                "Wraps AGT cấp 1 API endpoints.",
    version="1.0.0",
    lifespan=lifespan,
)

settings = get_settings()

# ---------------------------------------------------------------------------
# CORS middleware
# ---------------------------------------------------------------------------

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "*",  # Allow all origins in production
        settings.frontend_origin,
        "http://localhost:4321",
        "http://127.0.0.1:4321",
        "http://localhost:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Global exception handler
# ---------------------------------------------------------------------------

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Catch unhandled exceptions and return a structured error response."""
    logger = logging.getLogger(__name__)
    logger.exception("Unhandled exception on %s %s", request.method, request.url.path)
    import traceback
    tb = traceback.format_exc()
    return JSONResponse(
        status_code=500,
        content={
            "StatusCode": "500",
            "Success": False,
            "Message": f"Internal server error: {str(exc)}",
            "Traceback": tb,
        },
    )


# ---------------------------------------------------------------------------
# Register routers
# ---------------------------------------------------------------------------

app.include_router(bookings_router)
app.include_router(reference_router)
app.include_router(health_router)
app.include_router(chat_router)

# Serve static chat page at root (avoids mount path conflicts)

@app.get("/")
async def serve_chat():
    import os as _os
    _chat_path = _os.path.join(_os.path.dirname(_os.path.dirname(__file__)), "static", "chat.html")
    if _os.path.isfile(_chat_path):
        return FileResponse(_chat_path, media_type="text/html")
    return HTMLResponse("<h1>Chat page not found</h1>", status_code=404)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    """Run the application with uvicorn."""
    uvicorn.run(
        "app.main:app",
        host=settings.backend_host,
        port=settings.backend_port,
        reload=False,
        log_level=settings.log_level.lower(),
    )


if __name__ == "__main__":
    main()
