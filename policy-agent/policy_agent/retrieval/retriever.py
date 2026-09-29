from __future__ import annotations

from policy_agent.api.schemas import PolicyRequest
from policy_agent.pap.policy_metadata import RetrievedPolicyChunk
from policy_agent.retrieval.vector_store import VectorStore


def build_policy_query(policy_request: PolicyRequest) -> str:
    fragments: list[str] = ["drone flight authorization"]

    if policy_request.drone_manufacturer and policy_request.drone_model:
        fragments.append(f"drone model {policy_request.drone_manufacturer} {policy_request.drone_model}")
    if policy_request.uas_class:
        fragments.append(f"uas class {policy_request.uas_class}")
    if policy_request.drone_weight_grams is not None:
        fragments.append(f"drone weight {policy_request.drone_weight_grams} grams")
    if policy_request.operation_type != "unknown":
        fragments.append(f"operation type {policy_request.operation_type}")
    if policy_request.night_operation:
        fragments.append("night operations")
    if policy_request.anti_collision_lights is not None:
        fragments.append("anti-collision light requirements")
    if policy_request.over_people:
        fragments.append("operations over people")
    if policy_request.altitude_ft is not None:
        fragments.append(f"altitude limit {policy_request.altitude_ft} feet")
    if policy_request.controlled_airspace:
        fragments.append("controlled airspace authorization")
    if policy_request.controlled_airspace_authorization_provided is not None:
        fragments.append("controlled airspace authorization evidence")
    if policy_request.remote_id_available is not None:
        fragments.append("remote id requirements")
    if policy_request.visual_line_of_sight is not None:
        fragments.append("visual line of sight")
    if policy_request.pilot_certification_provided is not None or policy_request.operation_type in {
        "commercial",
        "research",
    }:
        fragments.append("pilot certification requirements")
    if policy_request.local_restrictions_known is not None:
        fragments.append("local restrictions property authorization")
    if policy_request.mission_purpose:
        fragments.append(policy_request.mission_purpose)
    if policy_request.live_location:
        fragments.append(policy_request.live_location)

    return "; ".join(fragments)


class PolicyRetriever:
    def __init__(self, vector_store: VectorStore, default_top_k: int = 5):
        self.vector_store = vector_store
        self.default_top_k = default_top_k

    def retrieve(self, policy_request: PolicyRequest, top_k: int | None = None) -> list[RetrievedPolicyChunk]:
        query = build_policy_query(policy_request)
        return self.vector_store.search(query, top_k=top_k or self.default_top_k)

    def search(self, query: str, top_k: int | None = None) -> list[RetrievedPolicyChunk]:
        return self.vector_store.search(query, top_k=top_k or self.default_top_k)
