from __future__ import annotations

from typing import Literal

from policy_agent.api.schemas import (
    PolicyGridCell,
    PolicyGridCellDecision,
    PolicyGridResponse,
    PolicyRequest,
)

COST_BY_STATUS = {
    "APPROVED": 1.0,
    "NEEDS_REVIEW": 50.0,
    "DENIED": 9999.0,
}


def merge_policy_request_with_cell(base_request: PolicyRequest, cell: PolicyGridCell) -> PolicyRequest:
    updates: dict[str, object] = {}
    shared_fields = (
        "altitude_ft",
        "speed_mph",
        "over_people",
        "night_operation",
        "controlled_airspace",
        "controlled_airspace_authorization_provided",
        "visual_line_of_sight",
        "remote_id_available",
        "pilot_certification_provided",
        "local_restrictions_known",
    )

    for field_name in shared_fields:
        value = getattr(cell, field_name)
        if value is not None:
            updates[field_name] = value

    if cell.location_label:
        updates["live_location"] = cell.location_label
        updates.setdefault("origin_location", cell.location_label)
    elif cell.latitude is not None and cell.longitude is not None:
        coordinate_label = f"{cell.latitude:.6f},{cell.longitude:.6f}"
        updates["live_location"] = coordinate_label
        updates.setdefault("origin_location", coordinate_label)

    if cell.additional_context:
        existing_context = base_request.additional_context or ""
        updates["additional_context"] = f"{existing_context} {cell.additional_context}".strip()

    return base_request.model_copy(update=updates)


def build_grid_cell_decision(cell: PolicyGridCell, decision) -> PolicyGridCellDecision:
    blocked = decision.uavguard_status == "DENIED"
    return PolicyGridCellDecision(
        cell_id=cell.cell_id,
        x_index=cell.x_index,
        y_index=cell.y_index,
        latitude=cell.latitude,
        longitude=cell.longitude,
        location_label=cell.location_label,
        blocked=blocked,
        cost=COST_BY_STATUS[decision.uavguard_status],
        policy_decision=decision.decision,
        uavguard_status=decision.uavguard_status,
        warnings=decision.warnings,
        missing_attributes=decision.missing_attributes,
        citations=[citation.model_dump() for citation in decision.citations],
        explanation=decision.explanation,
        metadata=cell.metadata,
    )


def build_grid_response(base_request_decision, cells: list[PolicyGridCellDecision]) -> PolicyGridResponse:
    no_fly_zone_cell_ids = [cell.cell_id for cell in cells if cell.blocked]
    allowed_cell_ids = [cell.cell_id for cell in cells if cell.uavguard_status == "APPROVED"]
    review_cell_ids = [cell.cell_id for cell in cells if cell.uavguard_status == "NEEDS_REVIEW"]
    simulator_recommendation: Literal["PROCEED", "BLOCK", "REVIEW"]

    if base_request_decision.uavguard_status == "DENIED" or len(no_fly_zone_cell_ids) == len(cells):
        simulator_recommendation = "BLOCK"
    elif base_request_decision.uavguard_status == "NEEDS_REVIEW" or review_cell_ids:
        simulator_recommendation = "REVIEW"
    else:
        simulator_recommendation = "PROCEED"

    return PolicyGridResponse(
        base_request_decision=base_request_decision.model_dump(),
        simulator_recommendation=simulator_recommendation,
        total_cells=len(cells),
        no_fly_zone_cell_ids=no_fly_zone_cell_ids,
        allowed_cell_ids=allowed_cell_ids,
        review_cell_ids=review_cell_ids,
        cells=cells,
    )
