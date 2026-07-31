"""Simulator Agent for no-fly-zone planning and mission export."""

from __future__ import annotations

from pathlib import Path

from ..api.schemas import FlightRequest, KnowledgeAssessment, SimulationAssessment
from ..config.settings import Settings, get_settings
from ..simulator.astar import astar_path
from ..simulator.grid import build_grid, meters_to_goal_cell
from ..simulator.mission_exporter import build_mission_payload, save_mission_file
from ..simulator.visualizer_2d import render_grid_visualization


class SimulatorAgent:
    """Generate simulator-ready missions and path plans."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    def run(
        self,
        request: FlightRequest,
        knowledge_assessment: KnowledgeAssessment,
    ) -> SimulationAssessment:
        """Create a 2D mission plan based on resolved coordinates."""

        origin = knowledge_assessment.resolved_origin.coordinates
        destination = knowledge_assessment.resolved_destination.coordinates
        if origin is None or destination is None:
            return SimulationAssessment(
                status="NEEDS_REVIEW",
                path_found=None,
                warnings=["Simulation requires resolved origin and destination coordinates."],
            )

        route_distance = knowledge_assessment.route_distance_meters or 0.0
        target_span = max(self.settings.grid_target_span_cells, 6)
        cell_size = max(self.settings.grid_cell_size_meters, int(max(route_distance, 1) / target_span))
        start = (0, 0)
        goal = meters_to_goal_cell(origin, destination, float(cell_size))
        grid = build_grid(start=start, goal=goal, padding=4, include_generated_zones=True)
        path = astar_path(grid, start, goal)
        mission = build_mission_payload(
            grid=grid,
            start=start,
            goal=goal,
            path=path,
            metadata={
                "cell_size_meters": cell_size,
                "origin": origin.model_dump(),
                "destination": destination.model_dump(),
                "request_model": request.model,
            },
        )

        artifacts_dir = self.settings.processed_data_dir / "artifacts"
        mission_name = f"{request.manufacturer}_{request.model}".lower().replace(" ", "_")
        mission_file = save_mission_file(mission, artifacts_dir / f"{mission_name}_mission.json")
        visualization_path = render_grid_visualization(
            grid=grid,
            start=start,
            goal=goal,
            path=path,
            output_dir=artifacts_dir,
            stem=f"{mission_name}_grid",
        )
        mission["metadata"]["mission_file"] = mission_file
        mission["metadata"]["visualization_path"] = visualization_path

        return SimulationAssessment(
            status="APPROVED" if path else "DENIED",
            path_found=bool(path),
            warnings=[] if path else ["No path could be found through the generated grid."],
            grid_cell_size_meters=float(cell_size),
            restricted_cell_count=sum(1 for allowed in grid.values() if allowed == 0),
            path=[list(cell) for cell in path],
            mission=mission,
            visualization_path=visualization_path,
        )
