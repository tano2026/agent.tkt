
import logging
from contextlib import asynccontextmanager
import traceback
from typing import AsyncGenerator, List, Any, Dict, Optional

import uvicorn
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.bookings import router as bookings_router
from app.api.reference import router as reference_router
from app.api.health import router as health_router
# from app.api.chat import router as chat_router  # CRIT-2: replaced by smart_agent
from app.services.config import get_settings
from app.services.abtrip_client import close_client
from app.services.llm_gateway import close_llm
# Rag_service removed — not integrated with smart_agent (CRIT-1)
from app.services.smart_agent import router as smart_agent_router
from app.services.api_flights import router as api_flights_router
from app.services.api_fasttrack import router as api_fasttrack_router
from app.services.api_esim import router as api_esim_router
from app.services.api_visa import router as api_visa_router

# ---------------------------------------------------------------------------
# Logging configuration
# ---------------------------------------------------------------------------

def configure_logging() -> None:
    """Set up application-wide logging."""
    settings = get_settings()
    log_level = getattr(logging, settings.log_level.upper(), logging.INFO)
    logging.basicConfig(level=log_level,
                        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
                        datefmt="%Y-%m-%d %H:%M:%S")


# ---------------------------------------------------------------------------
# Application lifespan
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Application lifespan handler.
    - Startup: configure logging and load settings
    - Shutdown: clean up resources (close HTTP client, LLM client)
    """
    configure_logging()
    logger = logging.getLogger(__name__)
    logger.info("ABTrip backend starting up...")
    # Load settings and initialize clients during startup
    settings = get_settings()
    # Initialize RAG (vector search)
    # await init_rag()  # CRIT-1: dead code, not integrated
    yield
    logger.info("ABTrip backend shutting down...")
    # await close_rag()  # CRIT-1: dead code, not integrated
    await close_client()
    await close_llm()


# ---------------------------------------------------------------------------
# FastAPI application
# ---------------------------------------------------------------------------

app = FastAPI(
    title="ABTrip Flight Booking Backend",
    description="Backend service for ABTrip flight booking system. Wraps AGT cấp 1 API endpoints.",
    version="1.0.0",
    lifespan=lifespan,
)

# Reload settings if needed during development, but primarily rely on lifespan
settings = get_settings()

# ---------------------------------------------------------------------------
# CORS middleware
# ---------------------------------------------------------------------------

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        settings.frontend_origin,
        "http://localhost:4321",
        "http://127.0.0.1:4321",
        "http://192.168.1.253:4321", # Allow LAN access from frontend
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
    tb = traceback.format_exc()
    return JSONResponse(
        status_code=500,
        content={
            "StatusCode": "500",
            "Success": False,
            "Message": f"Internal server error: {str(exc)}",
            #"Traceback": tb, # Disabled for security reasons in production
        },
    )


# ---------------------------------------------------------------------------
# Register routers
# ---------------------------------------------------------------------------

app.include_router(bookings_router)
app.include_router(reference_router)
app.include_router(health_router)
# app.include_router(chat_router)  # CRIT-2: disabled — use smart_agent instead
app.include_router(smart_agent_router)
app.include_router(api_flights_router)
app.include_router(api_fasttrack_router)
app.include_router(api_esim_router)
app.include_router(api_visa_router)

# ---------------------------------------------------------------------------
# Smart Agent Landing Page
# ---------------------------------------------------------------------------

import os
from fastapi.responses import HTMLResponse
from pathlib import Path

TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
async def smart_agent_landing():
    """Serve Smart Agent main chat page (1-screen ChatGPT-style)."""
    landing_path = TEMPLATES_DIR / "main.html"
    if landing_path.exists():
        return HTMLResponse(content=landing_path.read_text(encoding="utf-8"))
    return HTMLResponse(content="<h1>Smart Agent</h1><p>Loading...</p>")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

@app.get("/main", response_class=HTMLResponse, include_in_schema=False)
async def main_landing():
    """Serve main landing page (dark gold theme)."""
    landing_path = TEMPLATES_DIR / "main.html"
    if landing_path.exists():
        return HTMLResponse(content=landing_path.read_text(encoding="utf-8"))
    return HTMLResponse(content="<h1>ABTrip Smart Agent</h1><p>Loading...</p>")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # This block is executed when running `python -m app.main`
    settings = get_settings()
    configure_logging()
    logger = logging.getLogger(__name__)
    logger.info("ABTrip backend starting up...")

    # Use PORT env var if set (e.g. from hosting), otherwise config defaults to 6969
    port = int(os.environ.get("PORT", settings.backend_port))

    uvicorn.run(
        "app.main:app",
        host=settings.backend_host,
        port=port,
        reload=False,
        log_level=settings.log_level.lower(),
    )

