from __future__ import annotations

from functools import lru_cache

from policy_agent.api.schemas import DroneCatalogEntry, PolicyRequest
from policy_agent.config import Settings
from policy_agent.utils.json_utils import read_json_file

CATALOG_TO_REQUEST_FIELD_MAP = {
    "model_id": "drone_model_id",
    "manufacturer": "drone_manufacturer",
    "model_name": "drone_model",
    "uas_class": "uas_class",
    "weight_grams": "drone_weight_grams",
    "max_takeoff_weight_grams": "max_takeoff_weight_grams",
    "endurance_minutes": "endurance_minutes",
    "night_lights": "night_lights",
    "anti_collision_lights": "anti_collision_lights",
    "has_camera": "has_camera",
    "is_toy": "is_toy",
}

REQUEST_FIELD_LABELS = {
    "drone_weight_grams": "drone weight",
    "max_takeoff_weight_grams": "maximum takeoff weight",
    "endurance_minutes": "endurance",
    "night_lights": "night lights",
    "anti_collision_lights": "anti-collision lights",
    "has_camera": "camera availability",
    "is_toy": "toy classification",
    "uas_class": "UAS class",
}


def _normalize_text(value: str | None) -> str:
    return (value or "").strip().casefold()


class DroneCatalogRepository:
    def __init__(self, settings: Settings):
        self.settings = settings

    @lru_cache(maxsize=1)
    def load_entries(self) -> tuple[DroneCatalogEntry, ...]:
        payload = read_json_file(self.settings.drone_catalog_path, default=[]) or []
        return tuple(DroneCatalogEntry.model_validate(item) for item in payload)

    def find_match(
        self,
        *,
        model_id: str | None = None,
        manufacturer: str | None = None,
        model_name: str | None = None,
    ) -> DroneCatalogEntry | None:
        entries = self.load_entries()
        normalized_model_id = _normalize_text(model_id)
        if normalized_model_id:
            for entry in entries:
                if _normalize_text(entry.model_id) == normalized_model_id:
                    return entry

        normalized_manufacturer = _normalize_text(manufacturer)
        normalized_model_name = _normalize_text(model_name)
        if normalized_manufacturer and normalized_model_name:
            for entry in entries:
                if (
                    _normalize_text(entry.manufacturer) == normalized_manufacturer
                    and _normalize_text(entry.model_name) == normalized_model_name
                ):
                    return entry
        return None

    def enrich_request(
        self, policy_request: PolicyRequest
    ) -> tuple[PolicyRequest, DroneCatalogEntry | None, list[str]]:
        matched_entry = self.find_match(
            model_id=policy_request.drone_model_id,
            manufacturer=policy_request.drone_manufacturer,
            model_name=policy_request.drone_model,
        )
        if matched_entry is None:
            return policy_request, None, []

        updates: dict[str, object] = {}
        warnings: list[str] = []
        entry_payload = matched_entry.model_dump()

        for catalog_field, request_field in CATALOG_TO_REQUEST_FIELD_MAP.items():
            catalog_value = entry_payload.get(catalog_field)
            current_value = getattr(policy_request, request_field)

            if current_value is None and catalog_value is not None:
                updates[request_field] = catalog_value
                continue

            if current_value is None or catalog_value is None:
                continue

            if current_value != catalog_value and request_field in REQUEST_FIELD_LABELS:
                warnings.append(
                    f"Provided {REQUEST_FIELD_LABELS[request_field]} does not match the drone catalog profile for "
                    f"{matched_entry.manufacturer} {matched_entry.model_name}."
                )

        return policy_request.model_copy(update=updates), matched_entry, warnings
