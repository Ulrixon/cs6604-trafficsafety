"""
Main entry point for the FastAPI backend server.

This module creates a FastAPI application, configures CORS,
loads settings, and includes API routers.

Run the server with:
    uvicorn backend.app.main:app --reload

Make sure the required dependencies are installed:
    pip install -r backend/requirements.txt
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging

logger = logging.getLogger(__name__)

from .schemas.intersection import IntersectionRead
from .core.config import settings  # type: ignore
from .api.intersection import router as intersection_router
from .services.db_client import get_db_client, close_db_client

# Optional routers - import conditionally to avoid startup failures
try:
    from .api.vcc import router as vcc_router

    VCC_AVAILABLE = True
except Exception as e:
    logger.warning(f"VCC router not available: {e}")
    VCC_AVAILABLE = False

try:
    from .api.history import router as history_router

    HISTORY_AVAILABLE = True
except Exception as e:
    logger.warning(f"History router not available: {e}")
    HISTORY_AVAILABLE = False


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager for FastAPI app.
    Handles startup and shutdown events.
    """
    # Startup: Initialize database connection (non-blocking)
    logger.info("Starting Traffic Safety API...")
    # Database connection will be established lazily on first request

    yield

    # Shutdown: Close database connection
    logger.info("Shutting down Traffic Safety API...")
    try:
        close_db_client()
        logger.info("✓ Database connection closed")
    except Exception as e:
        logger.warning(f"Error closing database: {e}")


def create_app() -> FastAPI:
    """
    Create and configure the FastAPI application.
    """
    app = FastAPI(
        title=settings.PROJECT_NAME,
        version=settings.VERSION,
        description="Traffic safety API for intersections with MCDM-based safety scoring.",
        lifespan=lifespan,
    )

    # Set up CORS (allow all origins for development; adjust for production)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # TODO: restrict in production
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Include API routers
    app.include_router(intersection_router, prefix="/api/v1")

    # Optional routers
    if VCC_AVAILABLE:
        app.include_router(vcc_router, prefix="/api/v1")
        logger.info("✓ VCC router registered")

    if HISTORY_AVAILABLE:
        app.include_router(history_router, prefix="/api/v1")
        logger.info("✓ History router registered")

    # Simple health‑check endpoint
    @app.get("/health", tags=["Health"])
    async def health_check() -> dict:
        """
        Health‑check endpoint used by monitoring tools.
        Returns a simple JSON payload confirming the service is alive.
        """
        return {"status": "ok"}

    return app


# Instantiate the FastAPI app
app = create_app()

# If this file is executed directly, run the server with uvicorn
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "backend.app.main:app",
        host="0.0.0.0",
        port=8080,
        reload=True,
    )
