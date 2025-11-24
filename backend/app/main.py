"""
Main entry point for the FastAPI backend server.

This module creates a FastAPI application, configures CORS,
loads settings, and includes API routers.

Run the server with:
    uvicorn backend.app.main:app --reload

Make sure the required dependencies are installed:
    pip install -r backend/requirements.txt
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging

logger = logging.getLogger(__name__)

from .schemas.intersection import IntersectionRead
from .core.config import settings  # type: ignore
from .api.intersection import router as intersection_router
from .db.connection import init_db, close_db, check_db_health
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

try:
    from .api.database_explorer import router as db_explorer_router

    DB_EXPLORER_AVAILABLE = True
except Exception as e:
    logger.warning(f"Database Explorer router not available: {e}")
    DB_EXPLORER_AVAILABLE = False


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager for application startup and shutdown.

    Handles:
    - PostgreSQL database connection initialization (if enabled)
    - MCDM database connection (lazy initialization)
    - Database connection cleanup
    """
    # Startup
    logger.info("Starting Traffic Safety API...")

    # Initialize PostgreSQL connection if enabled (for safety index storage)
    if settings.USE_POSTGRESQL:
        try:
            logger.info("Initializing PostgreSQL connection...")
            init_db(
                database_url=settings.DATABASE_URL,
                pool_size=settings.DB_POOL_SIZE,
                max_overflow=settings.DB_MAX_OVERFLOW,
            )

            # Check database health
            health = check_db_health()
            if health["status"] == "healthy":
                logger.info(
                    f"PostgreSQL connection successful: {health['database']} ({health['postgis_version']})"
                )
            else:
                logger.error(f"PostgreSQL health check failed: {health['error']}")
        except Exception as e:
            logger.error(f"Failed to initialize PostgreSQL: {e}")
            if not settings.FALLBACK_TO_PARQUET:
                raise
            logger.warning("Continuing with Parquet fallback...")
    else:
        logger.info("PostgreSQL disabled - using Parquet storage only")

    # MCDM database connection will be established lazily on first request

    yield  # Application is running

    # Shutdown
    logger.info("Shutting down Traffic Safety API...")

    # Close PostgreSQL connection
    if settings.USE_POSTGRESQL:
        try:
            close_db()
            logger.info("✓ PostgreSQL connections closed")
        except Exception as e:
            logger.warning(f"Error closing PostgreSQL: {e}")

    # Close MCDM database connection
    try:
        close_db_client()
        logger.info("✓ MCDM database connection closed")
    except Exception as e:
        logger.warning(f"Error closing MCDM database: {e}")


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

    if DB_EXPLORER_AVAILABLE:
        app.include_router(
            db_explorer_router, prefix="/api/v1/database", tags=["Database Explorer"]
        )
        logger.info("✓ Database Explorer router registered")

    # Simple health‑check endpoint
    @app.get("/health", tags=["Health"])
    async def health_check() -> dict:
        """
        Health‑check endpoint used by monitoring tools.
        Returns status of the service and database connection.
        """
        response = {
            "status": "ok",
            "version": settings.VERSION,
            "database": {
                "enabled": settings.USE_POSTGRESQL,
                "status": "not_configured",
            },
        }

        if settings.USE_POSTGRESQL:
            try:
                db_health = check_db_health()
                response["database"]["status"] = db_health["status"]
                if db_health["status"] == "healthy":
                    response["database"]["name"] = db_health["database"]
                    response["database"]["postgis_version"] = db_health[
                        "postgis_version"
                    ]
                    response["database"]["connection_pool"] = db_health[
                        "connection_pool"
                    ]
                else:
                    response["database"]["error"] = db_health.get("error")
                    response["status"] = "degraded"
            except Exception as e:
                response["database"]["status"] = "error"
                response["database"]["error"] = str(e)
                response["status"] = "degraded"

        return response

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
