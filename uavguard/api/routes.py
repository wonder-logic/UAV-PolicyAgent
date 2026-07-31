"""FastAPI routes for UAVGuard."""

from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException, Query

from ..agents.orchestrator import UAVGuardOrchestrator
from ..config.settings import Settings
from ..knowledge_base.drone_repository import DroneRepository
from ..knowledge_base.ingest_drones import ingest_directory
from ..knowledge_base.db import initialize_database
from ..policy.ingest_policies import ingest_policy_directory
from .schemas import (
    DroneSearchResponse,
    FlightDecisionResponse,
    FlightRequest,
    HealthResponse,
    IngestResponse,
    SimulationAssessment,
)


def build_router(settings: Settings) -> APIRouter:
    """Construct the API router using the provided settings."""

    settings.ensure_directories()
    initialize_database(settings.database_path)
    repository = DroneRepository(settings)
    orchestrator = UAVGuardOrchestrator(settings)
    router = APIRouter()

    @router.get("/health", response_model=HealthResponse)
    def health() -> HealthResponse:
        indexed_count = len(
            [
                path
                for path in settings.faa_docs_dir.iterdir()
                if path.is_file() and path.suffix.lower() in {".txt", ".pdf"}
            ]
        )
        return HealthResponse(
            status="ok",
            database_path=str(settings.database_path),
            policy_docs_dir=str(settings.faa_docs_dir),
            indexed_policy_collection=f"{settings.policy_collection} ({indexed_count} docs on disk)",
        )

    @router.post("/flight-request", response_model=FlightDecisionResponse)
    def flight_request(request: FlightRequest) -> FlightDecisionResponse:
        return orchestrator.run(request)

    @router.post("/ingest/drones", response_model=IngestResponse)
    def ingest_drones(directory: str | None = None) -> IngestResponse:
        target_dir = directory or str(settings.raw_data_dir)
        count = ingest_directory(target_dir, settings.database_path)
        return IngestResponse(
            status="ok",
            items_indexed=count,
            detail=f"Ingested {count} drone records from {target_dir}.",
        )

    @router.post("/ingest/policies", response_model=IngestResponse)
    def ingest_policies(directory: str | None = None) -> IngestResponse:
        target_dir = directory or str(settings.faa_docs_dir)
        count = ingest_policy_directory(target_dir, settings)
        return IngestResponse(
            status="ok",
            items_indexed=count,
            detail=f"Indexed {count} policy chunks from {target_dir}.",
        )

    @router.get("/drones/search", response_model=DroneSearchResponse)
    def search_drones(
        q: str = Query(..., min_length=1),
        manufacturer: str | None = None,
        limit: int = Query(default=5, ge=1, le=20),
    ) -> DroneSearchResponse:
        return DroneSearchResponse(
            query=q,
            matches=repository.search(q, manufacturer=manufacturer, limit=limit),
        )

    @router.get("/simulator/demo", response_model=SimulationAssessment)
    def simulator_demo() -> SimulationAssessment:
        sample_request_path = settings.sample_requests_dir / "sample_flight_request.json"
        if not sample_request_path.exists():
            raise HTTPException(status_code=404, detail="No sample request file was found.")
        payload = json.loads(sample_request_path.read_text(encoding="utf-8"))
        request = FlightRequest.model_validate(payload)
        result = orchestrator.run(request)
        return result.simulation_assessment

    return router
