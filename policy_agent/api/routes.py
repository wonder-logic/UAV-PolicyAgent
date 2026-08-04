from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, FastAPI, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from policy_agent.api.schemas import (
    HealthResponse,
    IngestResponse,
    PolicyAssistRequest,
    PolicyAssistResponse,
    PolicyChatRequest,
    PolicyChatResponse,
    PolicyGridRequest,
    PolicyGridResponse,
    PolicyRequest,
    PolicySearchResponse,
)
from policy_agent.api.v1_routes import router as api_v1_router
from policy_agent.config import Settings, get_settings
from policy_agent.core import DomainError
from policy_agent.core.rate_limit import InMemoryRateLimiter
from policy_agent.db import create_database
from policy_agent.pep.enforcement_point import PolicyEnforcementPoint

router = APIRouter()


def _web_root(settings: Settings) -> Path:
    _ = settings
    return Path(__file__).resolve().parents[1] / "web"


@router.get("/", include_in_schema=False)
def root(request: Request):
    settings: Settings = request.app.state.settings
    return FileResponse(_web_root(settings) / "index.html")


@router.get("/health", response_model=HealthResponse)
def health(request: Request) -> HealthResponse:
    settings: Settings = request.app.state.settings
    return HealthResponse(status="ok", service=settings.service_name)


@router.post("/policy-agent/evaluate")
def evaluate_policy(policy_request: PolicyRequest, request: Request):
    pep: PolicyEnforcementPoint = request.app.state.pep
    return pep.evaluate_request(policy_request)


@router.post("/policy-agent/assist", response_model=PolicyAssistResponse)
def assist_policy(assist_request: PolicyAssistRequest, request: Request) -> PolicyAssistResponse:
    pep: PolicyEnforcementPoint = request.app.state.pep
    return pep.assist_request(assist_request)


@router.post("/policy-agent/chat", response_model=PolicyChatResponse)
def chat_policy(chat_request: PolicyChatRequest, request: Request) -> PolicyChatResponse:
    pep: PolicyEnforcementPoint = request.app.state.pep
    return pep.chat_request(chat_request)


@router.post("/policy-agent/evaluate-grid", response_model=PolicyGridResponse)
def evaluate_policy_grid(grid_request: PolicyGridRequest, request: Request) -> PolicyGridResponse:
    pep: PolicyEnforcementPoint = request.app.state.pep
    return pep.evaluate_grid(grid_request)


@router.post("/policy-agent/ingest", response_model=IngestResponse)
def ingest_policies(request: Request) -> IngestResponse:
    pep: PolicyEnforcementPoint = request.app.state.pep
    summary = pep.ingest_policies()
    return IngestResponse.model_validate(summary.model_dump())


@router.get("/policy-agent/search", response_model=PolicySearchResponse)
def search_policies(
    request: Request,
    q: str = Query(..., min_length=1),
    top_k: int = Query(5, ge=1, le=10),
) -> PolicySearchResponse:
    pep: PolicyEnforcementPoint = request.app.state.pep
    results = pep.search_policies(q, top_k=top_k)
    return PolicySearchResponse(query=q, results=[result.model_dump() for result in results])


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved_settings = settings or get_settings()
    resolved_settings.ensure_directories()
    database = create_database(resolved_settings)
    database.create_all()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        try:
            yield
        finally:
            request_database = getattr(app.state, "database", None)
            if request_database is not None:
                request_database.dispose()

    app = FastAPI(title=resolved_settings.project_name, lifespan=lifespan)
    app.state.settings = resolved_settings
    app.state.database = database
    app.state.rate_limiter = InMemoryRateLimiter()
    app.state.pep = PolicyEnforcementPoint(resolved_settings)
    app.mount(
        "/static",
        StaticFiles(directory=_web_root(resolved_settings) / "static"),
        name="static",
    )
    if resolved_settings.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=list(resolved_settings.cors_origins),
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    @app.middleware("http")
    async def attach_request_id(request: Request, call_next):
        request_id = request.headers.get("X-Request-ID", str(uuid4()))
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response

    @app.exception_handler(DomainError)
    async def handle_domain_error(request: Request, exc: DomainError):
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": exc.error_code,
                "message": exc.message,
                "request_id": getattr(request.state, "request_id", None),
            },
        )

    app.include_router(router)
    app.include_router(api_v1_router)
    return app
