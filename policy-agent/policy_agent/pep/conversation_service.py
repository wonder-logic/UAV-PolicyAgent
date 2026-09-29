from __future__ import annotations

from policy_agent.api.schemas import DroneCatalogEntry, PolicyAssistResponse, PolicyRequest

QUESTION_MAP = {
    "remote_id_available": "Will Remote ID be active and broadcasting during this mission?",
    "anti_collision_lights": "Will the drone have anti-collision lighting visible for the night flight?",
    "controlled_airspace authorization evidence": "If any part of the route enters controlled airspace, do you already have the required authorization?",
    "operation_type": "What kind of operation is this: recreational, commercial, research, or public safety?",
    "pilot_certification_provided": "Is the pilot already covered by a valid Part 107 remote pilot certificate for this mission?",
    "altitude_ft": "What altitude do you plan to fly, in feet?",
    "visual_line_of_sight": "Will the pilot or visual observer be able to keep the drone directly in sight for the entire mission?",
    "over_moving_vehicles": "Will the route include sustained flight over moving vehicles?",
    "drone_model_or_weight": "What aircraft are you flying, or what is its verified takeoff weight in grams?",
}


def build_follow_up_questions(missing_attributes: list[str]) -> list[str]:
    return [QUESTION_MAP.get(item, f"Please provide {item}.") for item in missing_attributes]


def build_assistant_message(
    *,
    drone_profile: DroneCatalogEntry | None,
    catalog_warnings: list[str],
    missing_attributes: list[str],
    preview_decision: dict | None,
) -> str:
    segments: list[str] = []

    if drone_profile is not None:
        segments.append(f"Matched drone catalog profile for {drone_profile.manufacturer} {drone_profile.model_name}.")
    if catalog_warnings:
        segments.append("Some supplied drone details do not match the stored catalog profile.")
    if preview_decision is not None:
        segments.append(
            f"Current policy status is {preview_decision['uavguard_status']} ({preview_decision['decision']})."
        )
    if missing_attributes:
        segments.append("I still need a few details before I can confidently produce a simulator-ready policy grid.")
    else:
        segments.append(
            "I have enough information to produce a policy decision and a no-fly-zone grid for the simulator."
        )

    return " ".join(segments)


def build_assist_response(
    *,
    enriched_request: PolicyRequest,
    drone_profile: DroneCatalogEntry | None,
    catalog_warnings: list[str],
    missing_attributes: list[str],
    preview_decision: dict | None,
) -> PolicyAssistResponse:
    return PolicyAssistResponse(
        assistant_message=build_assistant_message(
            drone_profile=drone_profile,
            catalog_warnings=catalog_warnings,
            missing_attributes=missing_attributes,
            preview_decision=preview_decision,
        ),
        ready_for_decision=not missing_attributes,
        missing_attributes=missing_attributes,
        questions=build_follow_up_questions(missing_attributes),
        enriched_request=enriched_request,
        drone_profile=drone_profile,
        catalog_warnings=catalog_warnings,
        preview_decision=preview_decision,
    )
