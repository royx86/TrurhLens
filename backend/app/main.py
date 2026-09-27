"""
TruthLens FastAPI application entry point.

Public API surface:
  GET  /health              — health check
  POST /api/v1/analyze      — complete fact-checking analysis
  POST /api/v1/auth/signup  — user registration
  POST /api/v1/auth/login   — user login
  GET  /api/v1/auth/me      — current authenticated user profile
  POST /api/v1/auth/logout  — user logout
"""

from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes.analysis import router as analysis_router
from app.api.routes.auth import router as auth_router
from app.core.config import settings
from app.core.timing import setup_logging
from app.db.database import init_db

# ── Logging setup ─────────────────────────────────────────────────────────────
setup_logging(level=logging.INFO)
logger = logging.getLogger(__name__)


# ── Lifespan Context Manager ──────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize DB tables on startup
    try:
        await init_db()
    except Exception as exc:
        logger.error("Failed to initialize database: %s", exc)
    yield


# ── Application ───────────────────────────────────────────────────────────────
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="TruthLens Backend – AI Social Media Fact-Checking & Verification Platform",
    lifespan=lifespan,
)

# ── CORS ──────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        *settings.cors_origins,
        *([settings.frontend_url.rstrip("/")] if settings.frontend_url else []),
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Primary public routes ─────────────────────────────────────────────────────
app.include_router(auth_router, prefix="/api/v1/auth", tags=["Authentication"])
app.include_router(analysis_router, prefix="/api/v1")

# ── Debug/development routes (disabled by default in production) ──────────────
if settings.debug_routes_enabled:
    from app.api.routes.evidence import router as evidence_router
    from app.api.routes.scrape import router as scrape_router

    app.include_router(scrape_router, prefix="/api/v1/debug", tags=["Debug"])
    app.include_router(evidence_router, prefix="/api/v1/debug", tags=["Debug"])
    logger.warning("DEBUG_ROUTES_ENABLED=true — /debug routes active.")


@app.get("/health", tags=["Health"])
async def health_check() -> dict:
    """Simple health check endpoint."""
    return {"status": "ok", "service": "truthlens-backend", "version": settings.app_version}


logger.info(
    "TruthLens backend initialized — version %s",
    settings.app_version,
)
