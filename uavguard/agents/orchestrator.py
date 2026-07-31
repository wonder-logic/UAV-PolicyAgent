"""UAVGuard multi-agent orchestration pipeline."""

from __future__ import annotations

from ..api.schemas import ArtifactPaths, FlightDecisionResponse, FlightRequest
from ..config.settings import Settings, get_settings
from .knowledge_agent import KnowledgeBaseAgent
from .policy_agent import PolicyAgent
from .simulator_agent import SimulatorAgent


class UAVGuardOrchestrator:
    """Coordinate the three major UAVGuard agents."""

    def __init__(
        self,
        settings: Settings | None = None,
        knowledge_agent: KnowledgeBaseAgent | None = None,
        policy_agent: PolicyAgent | None = None,
        simulator_agent: SimulatorAgent | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.knowledge_agent = knowledge_agent or KnowledgeBaseAgent(self.settings)
        self.policy_agent = policy_agent or PolicyAgent(self.settings)
        self.simulator_agent = simulator_agent or SimulatorAgent(self.settings)

    @staticmethod
    def _final_decision(
        knowledge_status: str,
        policy_status: str,
        simulator_status: str,
        path_found: bool | None,
    ) -> str:
        if policy_status == "NON_COMPLIANT":
            return "DENIED"
        if simulator_status == "DENIED" and path_found is False:
            return "DENIED"
        if knowledge_status == "DENIED":
            return "DENIED"
        if (
            knowledge_status == "NEEDS_REVIEW"
            or policy_status == "NEEDS_REVIEW"
            or simulator_status == "NEEDS_REVIEW"
        ):
            return "NEEDS_REVIEW"
        return "APPROVED"

    @staticmethod
    def _compose_explanation(knowledge_assessment, policy_assessment, simulation_assessment, final_decision: str) -> str:
        parts = [
            f"Operational feasibility status: {knowledge_assessment.feasibility.status}.",
            f"Policy assessment status: {policy_assessment.policy_status}.",
            f"Simulation status: {simulation_assessment.status}.",
        ]
        if knowledge_assessment.feasibility.reasons:
            parts.append("Operational blockers: " + "; ".join(knowledge_assessment.feasibility.reasons))
        if policy_assessment.warnings:
            parts.append("Policy cautions: " + "; ".join(policy_assessment.warnings))
        if simulation_assessment.warnings:
            parts.append("Simulation cautions: " + "; ".join(simulation_assessment.warnings))
        parts.append(f"Final UAVGuard decision: {final_decision}.")
        return " ".join(parts)

    def run(self, request: FlightRequest) -> FlightDecisionResponse:
        """Run the full UAVGuard workflow."""

        drone_profile, knowledge_assessment = self.knowledge_agent.run(request)
        policy_assessment = self.policy_agent.run(request, drone_profile, knowledge_assessment)
        simulation_assessment = self.simulator_agent.run(request, knowledge_assessment)
        final_decision = self._final_decision(
            knowledge_assessment.feasibility.status,
            policy_assessment.policy_status,
            simulation_assessment.status,
            simulation_assessment.path_found,
        )
        mission_file = str(simulation_assessment.mission.get("metadata", {}).get("mission_file", ""))
        visualization = simulation_assessment.visualization_path or ""

        return FlightDecisionResponse(
            request=request,
            drone_profile=drone_profile,
            knowledge_assessment=knowledge_assessment,
            policy_assessment=policy_assessment,
            simulation_assessment=simulation_assessment,
            final_decision=final_decision,
            explanation=self._compose_explanation(
                knowledge_assessment,
                policy_assessment,
                simulation_assessment,
                final_decision,
            ),
            artifacts=ArtifactPaths(
                mission_file=mission_file,
                grid_visualization=visualization,
            ),
        )
