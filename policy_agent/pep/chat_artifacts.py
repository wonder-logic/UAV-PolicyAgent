from __future__ import annotations

from typing import Any

from policy_agent.api.schemas import MissionKnowledgeContext, PolicyGridCell, PolicyRequest

REQUESTED_CONTEXT_CATEGORIES = [
    "airspace_class",
    "controlled_airspace",
    "authorization_requirements",
    "temporary_flight_restrictions",
    "airport_proximity",
    "weather",
    "geographic_restrictions",
    "ground_features",
    "people_density",
    "restricted_areas",
    "grid_cell_facts",
]

MAX_RESTRICTED_ZONE_CELLS = 4
MAX_HUMAN_ZONE_CELLS = 4


def _point_feature(*, label: str | None, latitude: float | None, longitude: float | None) -> dict[str, Any] | None:
    if label is None and (latitude is None or longitude is None):
        return None

    geometry = None
    if latitude is not None and longitude is not None:
        geometry = {
            "type": "Point",
            "coordinates": [longitude, latitude],
        }

    properties: dict[str, Any] = {}
    if label:
        properties["label"] = label

    return {
        "type": "Feature",
        "geometry": geometry,
        "properties": properties,
    }


def _route_feature(
    *,
    start_label: str | None,
    start_latitude: float | None,
    start_longitude: float | None,
    destination_label: str | None,
    destination_latitude: float | None,
    destination_longitude: float | None,
) -> dict[str, Any] | None:
    if start_latitude is not None and start_longitude is not None and destination_latitude is not None and destination_longitude is not None:
        return {
            "type": "Feature",
            "geometry": {
                "type": "LineString",
                "coordinates": [
                    [start_longitude, start_latitude],
                    [destination_longitude, destination_latitude],
                ],
            },
            "properties": {
                "label": f"{start_label or 'Launch point'} to {destination_label or 'Destination'}",
            },
        }

    if start_label or destination_label:
        return {
            "type": "Feature",
            "geometry": None,
            "properties": {
                "label": f"{start_label or 'Launch point'} to {destination_label or 'Destination'}",
            },
        }

    return None


def _base_grid_payload(policy_request: PolicyRequest) -> dict[str, Any]:
    return {
        "altitude_ft": policy_request.altitude_ft,
        "speed_mph": policy_request.speed_mph,
        "over_people": policy_request.over_people,
        "night_operation": policy_request.night_operation,
        "controlled_airspace": policy_request.controlled_airspace,
        "controlled_airspace_authorization_provided": policy_request.controlled_airspace_authorization_provided,
        "visual_line_of_sight": policy_request.visual_line_of_sight,
        "remote_id_available": policy_request.remote_id_available,
        "pilot_certification_provided": policy_request.pilot_certification_provided,
        "local_restrictions_known": policy_request.local_restrictions_known,
    }


def _with_updates(base_payload: dict[str, Any], **updates: Any) -> dict[str, Any]:
    merged = dict(base_payload)
    merged.update(updates)
    return merged


def build_preview_grid_cells(
    *,
    policy_request: PolicyRequest,
    knowledge_context: MissionKnowledgeContext | None,
) -> list[PolicyGridCell]:
    base_payload = _base_grid_payload(policy_request)
    cells: list[PolicyGridCell] = []
    next_x = 0

    start_coordinates = knowledge_context.start_coordinates if knowledge_context is not None else None
    destination_coordinates = knowledge_context.destination_coordinates if knowledge_context is not None else None

    if start_coordinates is not None or policy_request.origin_location:
        cells.append(
            PolicyGridCell(
                cell_id="launch",
                x_index=next_x,
                y_index=0,
                latitude=start_coordinates.latitude if start_coordinates is not None else None,
                longitude=start_coordinates.longitude if start_coordinates is not None else None,
                location_label=policy_request.origin_location or policy_request.live_location or "Launch point",
                metadata={"kind": "launch", "source": "policy_request"},
                **base_payload,
            )
        )
        next_x += 1

    if destination_coordinates is not None or policy_request.destination_location:
        cells.append(
            PolicyGridCell(
                cell_id="destination",
                x_index=next_x,
                y_index=0,
                latitude=destination_coordinates.latitude if destination_coordinates is not None else None,
                longitude=destination_coordinates.longitude if destination_coordinates is not None else None,
                location_label=policy_request.destination_location or "Destination",
                metadata={"kind": "destination", "source": "policy_request"},
                **base_payload,
            )
        )
        next_x += 1

    if knowledge_context is not None:
        for index, zone in enumerate(knowledge_context.restricted_zones[:MAX_RESTRICTED_ZONE_CELLS], start=1):
            cells.append(
                PolicyGridCell(
                    cell_id=f"restricted-{index}",
                    x_index=next_x,
                    y_index=1,
                latitude=zone.latitude,
                longitude=zone.longitude,
                location_label=zone.name,
                **_with_updates(
                    base_payload,
                    controlled_airspace=True,
                    additional_context="Nearby airport or restricted-area reference identified by the knowledge context.",
                    metadata={
                        "kind": "restricted_zone",
                        "source": "knowledge_context",
                        "types": zone.type,
                    },
                ),
            )
        )
        next_x += 1

        for index, zone in enumerate(knowledge_context.human_zones[:MAX_HUMAN_ZONE_CELLS], start=1):
            cells.append(
                PolicyGridCell(
                    cell_id=f"population-{index}",
                    x_index=next_x,
                    y_index=2,
                latitude=zone.latitude,
                longitude=zone.longitude,
                location_label=zone.name,
                **_with_updates(
                    base_payload,
                    additional_context=(
                        "Population-sensitive site identified nearby; keep the route clear of people and property constraints."
                    ),
                    metadata={
                        "kind": "population_sensitive",
                        "source": "knowledge_context",
                        "types": zone.type,
                    },
                ),
            )
        )
        next_x += 1

    if cells:
        return cells

    return [
        PolicyGridCell(
            cell_id="mission-area",
            x_index=0,
            y_index=0,
            location_label=policy_request.origin_location or policy_request.live_location or "Mission area",
            metadata={"kind": "mission_area", "source": "policy_request"},
            **base_payload,
        )
    ]


def build_knowledge_request_preview(
    *,
    policy_request: PolicyRequest,
    knowledge_context: MissionKnowledgeContext | None,
    grid_cells: list[PolicyGridCell],
) -> dict[str, Any]:
    start_coordinates = knowledge_context.start_coordinates if knowledge_context is not None else None
    destination_coordinates = knowledge_context.destination_coordinates if knowledge_context is not None else None

    payload = {
        "request_id": "chat-preview-request",
        "mission_id": "chat-preview-mission",
        "location": _point_feature(
            label=policy_request.origin_location or policy_request.live_location,
            latitude=start_coordinates.latitude if start_coordinates is not None else None,
            longitude=start_coordinates.longitude if start_coordinates is not None else None,
        ),
        "operational_area": _route_feature(
            start_label=policy_request.origin_location or policy_request.live_location,
            start_latitude=start_coordinates.latitude if start_coordinates is not None else None,
            start_longitude=start_coordinates.longitude if start_coordinates is not None else None,
            destination_label=policy_request.destination_location,
            destination_latitude=destination_coordinates.latitude if destination_coordinates is not None else None,
            destination_longitude=destination_coordinates.longitude if destination_coordinates is not None else None,
        ),
        "mission_time_start": None,
        "mission_time_end": None,
        "altitude_ft": policy_request.altitude_ft,
        "drone_characteristics": {
            "manufacturer": policy_request.drone_manufacturer,
            "model": policy_request.drone_model,
            "weight_grams": policy_request.drone_weight_grams,
            "uas_class": policy_request.uas_class,
            "remote_id_available": policy_request.remote_id_available,
            "night_operation": policy_request.night_operation,
        },
        "requested_context_categories": REQUESTED_CONTEXT_CATEGORIES,
        "grid_cells": [cell.model_dump(mode="json", exclude_none=True) for cell in grid_cells],
    }
    return payload
