from __future__ import annotations

from policy_agent.api.schemas import PolicyRequest
from policy_agent.drone_catalog.repository import DroneCatalogRepository


def test_drone_catalog_enriches_request(settings, sample_drone_catalog):
    repository = DroneCatalogRepository(settings)
    request = PolicyRequest(drone_manufacturer="DJI", drone_model="Mini 4 Pro")

    enriched_request, matched_entry, warnings = repository.enrich_request(request)

    assert matched_entry is not None
    assert matched_entry.model_id == "dji-mini-4-pro"
    assert enriched_request.drone_weight_grams == 249
    assert enriched_request.anti_collision_lights is True
    assert warnings == []
