from __future__ import annotations

from policy_agent.api.schemas import PolicyRequest
from policy_agent.pap.policy_metadata import RetrievedPolicyChunk
from policy_agent.utils.json_utils import unique_in_order

MISSING_ATTRIBUTE_OBLIGATIONS = {
    "pilot_certification_provided": "Confirm that the pilot is covered by a valid Part 107 certificate for this mission.",
    "controlled_airspace authorization evidence": "Confirm that the required controlled-airspace authorization is in place.",
    "remote_id_available": "Confirm that Remote ID will be active during the mission.",
    "anti_collision_lights": "Confirm that anti-collision lighting will be available for the night flight.",
    "visual_line_of_sight": "Confirm that the drone will remain within visual line of sight.",
    "local_restrictions_known": "Confirm local site approval or any local flight restrictions before takeoff.",
    "altitude_ft": "Provide the planned flight altitude.",
    "operation_type": "Provide the mission operation type.",
    "drone_model_or_weight": "Provide the drone model or verified takeoff weight.",
}


def build_obligations(
    policy_request: PolicyRequest,
    missing_attributes: list[str],
    retrieved_chunks: list[RetrievedPolicyChunk],
) -> list[str]:
    obligations = [
        MISSING_ATTRIBUTE_OBLIGATIONS[item] for item in missing_attributes if item in MISSING_ATTRIBUTE_OBLIGATIONS
    ]
    combined_text = " ".join(chunk.text.lower() for chunk in retrieved_chunks)

    if (
        policy_request.controlled_airspace
        and "controlled airspace" in combined_text
        and "authorization" in combined_text
    ):
        obligations.append("Confirm that the required controlled-airspace authorization is in place.")
    if policy_request.remote_id_available is not True and "remote id" in combined_text:
        obligations.append("Confirm that Remote ID will be active during the mission.")
    if policy_request.visual_line_of_sight is not True and (
        "visual line of sight" in combined_text or "vlos" in combined_text
    ):
        obligations.append("Confirm that the drone will remain within visual line of sight.")
    if policy_request.local_restrictions_known is not True and (
        "local" in combined_text or "property" in combined_text or "campus" in combined_text
    ):
        obligations.append("Confirm local site approval or any local flight restrictions before takeoff.")

    return unique_in_order(obligations)
