from __future__ import annotations

from contextlib import contextmanager

from fastapi.testclient import TestClient

from policy_agent.api.routes import create_app


@contextmanager
def build_test_client(settings):
    with TestClient(create_app(settings)) as client:
        yield client


def test_root_serves_website(settings):
    with build_test_client(settings) as client:
        response = client.get("/")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "UAVGuard Policy Agent" in response.text


def test_health_endpoint(settings):
    with build_test_client(settings) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "uavguard-policy-agent"}


def test_ingest_endpoint_uses_builtin_policy_baseline_when_no_uploads_exist(settings):
    with build_test_client(settings) as client:
        response = client.post("/policy-agent/ingest")

    payload = response.json()
    assert response.status_code == 200
    assert payload["documents_loaded"] >= 1
    assert payload["chunks_indexed"] >= 1
    assert payload["policy_directory"] == "builtin://uavguard/part107-baseline"


def test_evaluate_endpoint(settings, sample_policy_text):
    (settings.policy_docs_dir / "policy.txt").write_text(sample_policy_text, encoding="utf-8")
    with build_test_client(settings) as client:
        ingest_response = client.post("/policy-agent/ingest")
        assert ingest_response.status_code == 200

        response = client.post(
            "/policy-agent/evaluate",
            json={
                "drone_manufacturer": "DJI",
                "drone_model": "Mini 4 Pro",
                "operation_type": "research",
                "origin_location": "Texas A&M University-Corpus Christi",
                "destination_location": "Corpus Christi Bay",
                "intended_flight_time": "night",
                "altitude_ft": 350,
                "speed_mph": 20,
                "over_people": False,
                "night_operation": True,
                "controlled_airspace": None,
                "visual_line_of_sight": None,
                "remote_id_available": True,
                "pilot_certification_provided": None,
                "mission_purpose": "research data collection",
            },
        )

    payload = response.json()
    assert response.status_code == 200
    assert payload["decision"] == "INDETERMINATE"
    assert payload["uavguard_status"] == "NEEDS_REVIEW"


def test_assist_endpoint_returns_questions_and_catalog_match(settings, sample_policy_text, sample_drone_catalog):
    (settings.policy_docs_dir / "policy.txt").write_text(sample_policy_text, encoding="utf-8")
    with build_test_client(settings) as client:
        client.post("/policy-agent/ingest")

        response = client.post(
            "/policy-agent/assist",
            json={
                "policy_request": {
                    "drone_manufacturer": "DJI",
                    "drone_model": "Mini 4 Pro",
                    "operation_type": "research",
                    "altitude_ft": 350,
                    "night_operation": True,
                    "remote_id_available": True,
                }
            },
        )

    payload = response.json()
    assert response.status_code == 200
    assert payload["drone_profile"]["model_id"] == "dji-mini-4-pro"
    assert payload["ready_for_decision"] is False
    assert "visual_line_of_sight" in payload["missing_attributes"]
    assert "pilot_certification_provided" in payload["missing_attributes"]
    assert all("anti-collision" not in question.lower() for question in payload["questions"])


def test_chat_endpoint_merges_supported_facts_and_returns_one_follow_up(
    settings,
    sample_policy_text,
    sample_drone_catalog,
):
    (settings.policy_docs_dir / "policy.txt").write_text(sample_policy_text, encoding="utf-8")
    with build_test_client(settings) as client:
        client.post("/policy-agent/ingest")

        response = client.post(
            "/policy-agent/chat",
            json={
                "message": (
                    "We have a DJI Mini 4 Pro for a research mission near the TAMU-CC waterfront. "
                    "We will fly at 280 feet at night, stay within visual line of sight, "
                    "and Remote ID is active with a Part 107 pilot."
                ),
                "policy_request": {},
            },
        )

    payload = response.json()
    assert response.status_code == 200
    assert payload["policy_request"]["drone_model"] == "Mini 4 Pro"
    assert payload["policy_request"]["drone_manufacturer"] == "DJI"
    assert payload["policy_request"]["origin_location"] == "the TAMU-CC waterfront"
    assert payload["policy_request"]["altitude_ft"] == 280
    assert payload["policy_request"]["night_operation"] is True
    assert payload["policy_request"]["visual_line_of_sight"] is True
    assert payload["policy_request"]["remote_id_available"] is True
    assert payload["policy_request"]["pilot_certification_provided"] is True
    assert payload["next_question"] is None
    assert payload["ready_for_decision"] is True
    assert payload["preview_decision"]["uavguard_status"] in {"APPROVED", "NEEDS_REVIEW", "DENIED"}
    assert payload["verified_facts"]
    assert "Night Operations" not in payload["assistant_message"]
    assert "The strongest policy hit I found" not in payload["assistant_message"]
    assert payload["preview_decision"]["citations"]
    assert payload["knowledge_request_preview"]["grid_cells"]
    assert payload["simulator_grid_preview"]["cells"]
    assert payload["simulator_grid_preview"]["total_cells"] >= 1
    assert "structured policy request" not in payload["assistant_message"]
    assert "LLM evaluator not configured" not in payload["assistant_message"]


def test_chat_endpoint_returns_approved_for_fully_covered_daytime_class_g_mission(
    settings,
    sample_policy_text,
    sample_drone_catalog,
):
    (settings.policy_docs_dir / "policy.txt").write_text(sample_policy_text, encoding="utf-8")
    with build_test_client(settings) as client:
        client.post("/policy-agent/ingest")

        response = client.post(
            "/policy-agent/chat",
            json={
                "message": (
                    "We have a DJI Mini 4 Pro for a daytime research mission near the TAMU-CC waterfront "
                    "at 200 feet in Class G airspace. Remote ID is active, the pilot has a valid Part 107 "
                    "certificate, we will remain within visual line of sight for the entire mission, we are "
                    "not flying over people or moving vehicles, and local site approval is confirmed."
                ),
                "policy_request": {},
            },
        )

    payload = response.json()
    assert response.status_code == 200
    assert payload["policy_request"]["origin_location"] == "the TAMU-CC waterfront"
    assert payload["policy_request"]["controlled_airspace"] is False
    assert payload["policy_request"]["over_people"] is False
    assert payload["policy_request"]["local_restrictions_known"] is True
    assert payload["next_question"] is None
    assert payload["ready_for_decision"] is True
    assert payload["final_decision_ready"] is True
    assert payload["preview_decision"]["decision"] == "PERMIT"
    assert payload["preview_decision"]["uavguard_status"] == "APPROVED"
    assert payload["knowledge_request_preview"]["location"]["properties"]["label"] == "the TAMU-CC waterfront"
    assert payload["simulator_grid_preview"]["simulator_recommendation"] == "PROCEED"
    assert payload["preview_decision"]["mission_score"] >= 80
    assert "needs a closer look" not in payload["assistant_message"]
    assert "looks likely approvable" in payload["assistant_message"]


def test_chat_endpoint_missing_info_reply_is_conversational_and_grounded(
    settings,
    sample_policy_text,
    sample_drone_catalog,
):
    (settings.policy_docs_dir / "policy.txt").write_text(sample_policy_text, encoding="utf-8")
    with build_test_client(settings) as client:
        client.post("/policy-agent/ingest")

        response = client.post(
            "/policy-agent/chat",
            json={
                "message": "Can I fly my DJI Mini 4 Pro at 280 feet at night near the TAMU-CC waterfront?",
                "policy_request": {},
            },
        )

    payload = response.json()
    assert response.status_code == 200
    assert payload["next_question"] == "Will Remote ID be active and broadcasting during this mission?"
    assert "I can't give you a clean yes yet" in payload["assistant_message"]
    assert "Night Operations" not in payload["assistant_message"]
    assert "The strongest policy hit I found" not in payload["assistant_message"]
    assert "The next thing I need from you is" in payload["assistant_message"]
    assert "LLM evaluator not configured" not in payload["assistant_message"]
    assert payload["evaluation_stage"] == "PRELIMINARY"
    assert payload["knowledge_agent_called"] is False
    assert payload["knowledge_source"] == "NONE"
    assert payload["simulator_package"] is None
    assert payload["knowledge_response"] is None


def test_chat_endpoint_short_yes_answer_advances_to_the_next_missing_question(
    settings,
    sample_policy_text,
    sample_drone_catalog,
):
    (settings.policy_docs_dir / "policy.txt").write_text(sample_policy_text, encoding="utf-8")
    with build_test_client(settings) as client:
        client.post("/policy-agent/ingest")

        response = client.post(
            "/policy-agent/chat",
            json={
                "message": "yes",
                "policy_request": {
                    "drone_manufacturer": "DJI",
                    "drone_model": "Mini 4 Pro",
                    "operation_type": "research",
                    "origin_location": "TAMU-CC waterfront",
                    "altitude_ft": 280,
                    "night_operation": True,
                    "remote_id_available": True,
                    "pilot_certification_provided": None,
                    "visual_line_of_sight": None,
                },
            },
        )

    payload = response.json()
    assert response.status_code == 200
    assert payload["policy_request"]["pilot_certification_provided"] is True
    assert payload["policy_request"]["visual_line_of_sight"] is None
    assert payload["next_question"] == (
        "Will the pilot or visual observer be able to keep the drone directly in sight for the entire mission?"
    )
    assert "Thanks, that confirms the required pilot certification." in payload["assistant_message"]
    assert "valid Part 107 certificate" not in payload["assistant_message"]


def test_chat_endpoint_complete_mission_uses_grounded_knowledge_pipeline(
    settings,
    sample_policy_text,
    sample_drone_catalog,
):
    (settings.policy_docs_dir / "policy.txt").write_text(sample_policy_text, encoding="utf-8")
    with build_test_client(settings) as client:
        client.post("/policy-agent/ingest")

        response = client.post(
            "/policy-agent/chat",
            json={
                "message": (
                    "We have a DJI Mini 4 Pro for a daytime research mission near the TAMU-CC waterfront "
                    "at 200 feet in Class G airspace. Remote ID is active, the pilot has a valid Part 107 "
                    "certificate, we will remain within visual line of sight for the entire mission, we are "
                    "not flying over people or moving vehicles, and local site approval is confirmed."
                ),
                "policy_request": {},
            },
        )

    payload = response.json()
    assert response.status_code == 200
    assert payload["evaluation_stage"] == "FINAL"
    assert payload["knowledge_agent_called"] is True
    assert payload["knowledge_source"] == "MOCK"
    assert payload["decision"]["status"] == "APPROVED"
    assert payload["knowledge_request"]["request_id"].startswith("kar-")
    assert payload["knowledge_response"]["request_id"] == payload["knowledge_request"]["request_id"]
    assert payload["simulator_package"]["overall_decision"] == "APPROVED"
    assert payload["simulator_grid_preview"]["simulator_recommendation"] == "PROCEED"


def test_chat_endpoint_uses_knowledge_context_for_final_decision_and_scores(
    settings,
    sample_policy_text,
    sample_drone_catalog,
):
    (settings.policy_docs_dir / "policy.txt").write_text(sample_policy_text, encoding="utf-8")
    with build_test_client(settings) as client:
        client.post("/policy-agent/ingest")

        response = client.post(
            "/policy-agent/chat",
            json={
                "message": (
                    "This is a research mission at 280 feet at night. "
                    "Remote ID is active, the pilot has Part 107, and we will stay within visual line of sight."
                ),
                "policy_request": {},
                "knowledge_context": {
                    "agent": "Knowledge Agent",
                    "drone": {
                        "name": "Mini 4 Pro",
                        "uas_class": "C0",
                        "weight_in_grams": "249",
                        "max_takeoff_in_grams": "249",
                        "endurance_in_mins": "34",
                        "anti_collision": False,
                        "has_camera": True,
                        "maximum_operating_altitude_ft": 400,
                        "manufacturer": "DJI",
                    },
                    "battery_percent": 47,
                    "start_location": "TAMUCC",
                    "destination": "Momentum Village",
                    "start_coordinates": {
                        "original_input": "TAMUCC",
                        "normalized_location": "Texas A&M University-Corpus Christi",
                        "resolved_location": "Texas A&M University-Corpus Christi, Corpus Christi, Texas",
                        "latitude": 27.712751,
                        "longitude": -97.323388,
                    },
                    "destination_coordinates": {
                        "original_input": "Momentum Village",
                        "normalized_location": "Momentum Village",
                        "resolved_location": "Momentum Village, Corpus Christi, Texas",
                        "latitude": 27.704075,
                        "longitude": -97.338086,
                    },
                    "restricted_zones": [
                        {
                            "name": "Corpus Christi Naval Air Station (Truax Field)",
                            "type": ["airport", "airport.military"],
                            "latitude": 27.692197,
                            "longitude": -97.2760215,
                        }
                    ],
                    "start_weather": {
                        "status": "SUCCESS",
                        "temperature": 92.9,
                        "temperature_unit": "Â°F",
                        "wind_speed": 27.1,
                        "wind_gusts": 34.2,
                        "wind_direction": "South-Southeast",
                        "weather": "Clear sky",
                    },
                    "destination_weather": {
                        "status": "SUCCESS",
                        "temperature": 93.7,
                        "temperature_unit": "Â°F",
                        "wind_speed": 24.9,
                        "wind_gusts": 33.1,
                        "wind_direction": "South-Southeast",
                        "weather": "Clear sky",
                    },
                    "weather_warning": [
                        "High wind at launch.",
                        "High wind at destination.",
                    ],
                    "start_lookup_status": "SUCCESS",
                    "destination_lookup_status": "SUCCESS",
                    "knowledge_reasoning": {
                        "missing_information": ["max_distance", "max_airspeed", "min_altitude"],
                    },
                },
            },
        )

    payload = response.json()
    assert response.status_code == 200
    assert payload["knowledge_context_used"] is True
    assert payload["policy_request"]["drone_model"] == "Mini 4 Pro"
    assert payload["policy_request"]["drone_manufacturer"] == "DJI"
    assert payload["policy_request"]["origin_location"] == "Texas A&M University-Corpus Christi"
    assert payload["policy_request"]["anti_collision_lights"] is False
    assert payload["next_question"] is None
    assert payload["ready_for_decision"] is True
    assert payload["final_decision_ready"] is True
    assert payload["preview_decision"]["uavguard_status"] == "DENIED"
    assert isinstance(payload["preview_decision"]["mission_score"], int)
    assert 0 <= payload["preview_decision"]["mission_score"] <= 100
    assert isinstance(payload["preview_decision"]["accuracy_score"], int)
    assert 0 <= payload["preview_decision"]["accuracy_score"] <= 100
    assert payload["knowledge_request_preview"]["location"]["properties"]["label"] == "Texas A&M University-Corpus Christi"
    assert any(
        cell["metadata"].get("kind") == "restricted_zone" for cell in payload["simulator_grid_preview"]["cells"]
    )
    assert payload["knowledge_warnings"]
    assert "What is the maximum planned airspeed for the mission?" in payload["knowledge_follow_up_questions"]
    assert "Night Operations" not in payload["assistant_message"]
    assert "The strongest policy hit I found" not in payload["assistant_message"]


def test_chat_endpoint_uses_blocking_knowledge_gap_as_next_question(
    settings,
    sample_policy_text,
    sample_drone_catalog,
):
    (settings.policy_docs_dir / "policy.txt").write_text(sample_policy_text, encoding="utf-8")
    with build_test_client(settings) as client:
        client.post("/policy-agent/ingest")

        response = client.post(
            "/policy-agent/chat",
            json={
                "message": (
                    "This is a research mission at 280 feet at night. "
                    "Remote ID is active, the pilot has Part 107, we will stay within visual line of sight, "
                    "and anti-collision lighting is available."
                ),
                "policy_request": {},
                "knowledge_context": {
                    "drone": {
                        "name": "Mini 4 Pro",
                        "manufacturer": "DJI",
                        "anti_collision": True,
                    },
                    "start_lookup_status": "FAILED",
                    "destination_lookup_status": "SUCCESS",
                    "knowledge_reasoning": {
                        "missing_information": ["no_start_location_found"],
                    },
                },
            },
        )

    payload = response.json()
    assert response.status_code == 200
    assert payload["ready_for_decision"] is True
    assert payload["final_decision_ready"] is False
    assert payload["next_question"] == "Can you confirm the launch point with a more specific location name?"


def test_evaluate_grid_endpoint_returns_no_fly_zones(settings, sample_policy_text, sample_drone_catalog):
    (settings.policy_docs_dir / "policy.txt").write_text(sample_policy_text, encoding="utf-8")
    with build_test_client(settings) as client:
        client.post("/policy-agent/ingest")

        response = client.post(
            "/policy-agent/evaluate-grid",
            json={
                "base_request": {
                    "drone_manufacturer": "DJI",
                    "drone_model": "Mini 4 Pro",
                    "operation_type": "research",
                    "altitude_ft": 350,
                    "night_operation": True,
                    "remote_id_available": True,
                    "visual_line_of_sight": True,
                    "pilot_certification_provided": True,
                    "local_restrictions_known": True,
                },
                "grid_cells": [
                    {
                        "cell_id": "cell-allow",
                        "x_index": 0,
                        "y_index": 0,
                        "altitude_ft": 350,
                        "controlled_airspace": False,
                    },
                    {
                        "cell_id": "cell-deny",
                        "x_index": 0,
                        "y_index": 1,
                        "altitude_ft": 450,
                        "controlled_airspace": False,
                    },
                ],
            },
        )

    payload = response.json()
    assert response.status_code == 200
    assert payload["total_cells"] == 2
    assert "cell-deny" in payload["no_fly_zone_cell_ids"]
    allow_cell = next(cell for cell in payload["cells"] if cell["cell_id"] == "cell-allow")
    deny_cell = next(cell for cell in payload["cells"] if cell["cell_id"] == "cell-deny")
    assert allow_cell["blocked"] is False
    assert deny_cell["blocked"] is True


def test_evaluate_grid_endpoint_blocks_altitude_violation_even_when_base_request_needs_review(
    settings,
    sample_policy_text,
    sample_drone_catalog,
):
    (settings.policy_docs_dir / "policy.txt").write_text(sample_policy_text, encoding="utf-8")
    with build_test_client(settings) as client:
        client.post("/policy-agent/ingest")

        response = client.post(
            "/policy-agent/evaluate-grid",
            json={
                "base_request": {
                    "drone_manufacturer": "DJI",
                    "drone_model": "Mini 4 Pro",
                    "operation_type": "research",
                    "altitude_ft": 350,
                    "night_operation": True,
                    "anti_collision_lights": True,
                    "remote_id_available": True,
                    "visual_line_of_sight": None,
                    "pilot_certification_provided": None,
                },
                "grid_cells": [
                    {
                        "cell_id": "cell-safe-review",
                        "x_index": 0,
                        "y_index": 0,
                        "altitude_ft": 350,
                        "controlled_airspace": False,
                    },
                    {
                        "cell_id": "cell-hard-deny",
                        "x_index": 1,
                        "y_index": 0,
                        "altitude_ft": 450,
                        "controlled_airspace": False,
                    },
                ],
            },
        )

    payload = response.json()
    assert response.status_code == 200
    assert payload["simulator_recommendation"] == "REVIEW"
    assert "cell-hard-deny" in payload["no_fly_zone_cell_ids"]
    assert "cell-safe-review" in payload["review_cell_ids"]
