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
from .services.intersection_service import get_all
from .schemas.intersection import IntersectionRead

# Import configuration (if any) and routers
from .core.config import settings  # type: ignore
from .api.intersection import router as intersection_router
from .api.vcc import router as vcc_router


def create_app() -> FastAPI:
    """
    Create and configure the FastAPI application.
    """
    app = FastAPI(
        title=settings.PROJECT_NAME,
        version=settings.VERSION,
        description="Traffic safety API for intersections.",
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
    app.include_router(vcc_router, prefix="/api/v1")

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
        port=8000,
        reload=True,
    )
