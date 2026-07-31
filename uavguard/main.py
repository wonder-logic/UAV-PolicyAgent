"""FastAPI entrypoint for UAVGuard."""

from __future__ import annotations

from fastapi import FastAPI

from .api.routes import build_router
from .config.settings import Settings, get_settings


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create and configure the FastAPI app."""

    resolved_settings = settings or get_settings()
    app = FastAPI(
        title="UAVGuard",
        version="0.1.0",
        description="Multi-agent drone flight compliance and simulation framework.",
    )
    app.include_router(build_router(resolved_settings))
    return app


app = create_app()
