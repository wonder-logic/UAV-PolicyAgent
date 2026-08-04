from __future__ import annotations

from pydantic import BaseModel, Field

from policy_agent.api.schemas import PolicyRequest
from policy_agent.utils.json_utils import unique_in_order


class RuleEvaluation(BaseModel):
    missing_attributes: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


def evaluate_request_attributes(policy_request: PolicyRequest) -> RuleEvaluation:
    missing_attributes: list[str] = []

    if policy_request.night_operation is True and policy_request.remote_id_available is None:
        missing_attributes.append("remote_id_available")
    if policy_request.night_operation is True and policy_request.anti_collision_lights is None:
        missing_attributes.append("anti_collision_lights")
    if policy_request.controlled_airspace is True and policy_request.controlled_airspace_authorization_provided is None:
        missing_attributes.append("controlled_airspace authorization evidence")
    if policy_request.operation_type == "unknown":
        missing_attributes.append("operation_type")
    if (
        policy_request.operation_type in {"commercial", "research"}
        and policy_request.pilot_certification_provided is None
    ):
        missing_attributes.append("pilot_certification_provided")
    if policy_request.altitude_ft is None:
        missing_attributes.append("altitude_ft")
    if policy_request.visual_line_of_sight is None:
        missing_attributes.append("visual_line_of_sight")
    if policy_request.drone_model is None and policy_request.drone_weight_grams is None:
        missing_attributes.append("drone_model_or_weight")

    missing_attributes = unique_in_order(missing_attributes)
    warnings = (
        ["Conservative review required because one or more required authorization attributes are missing."]
        if missing_attributes
        else []
    )
    return RuleEvaluation(missing_attributes=missing_attributes, warnings=warnings)
