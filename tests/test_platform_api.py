from __future__ import annotations


def test_profile_and_unauthorized_access(client):
    response = client.get("/api/drones")
    assert response.status_code == 401

    profile_response = client.get("/api/profiles/me", headers={"Authorization": "Bearer missing"})
    assert profile_response.status_code == 401


def test_profile_creation_and_drone_ownership(client, auth_headers, populated_profile, populated_drone):
    second_user = client.post(
        "/api/auth/register",
        json={
            "full_name": "Jordan Lee",
            "email": "jordan@example.com",
            "password": "ResearchPass456",
            "organization": "TAMU-CC",
        },
    ).json()
    second_headers = {"Authorization": f"Bearer {second_user['access_token']}"}

    profile_response = client.get("/api/profiles/me", headers=second_headers)
    assert profile_response.status_code == 404

    drone_response = client.get(f"/api/drones/{populated_drone['drone_id']}", headers=second_headers)
    assert drone_response.status_code == 404


def test_mission_create_update_chat_and_evaluate(
    client,
    auth_headers,
    populated_profile,
    populated_drone,
    populated_mission,
):
    mission_id = populated_mission["mission_id"]

    patch_response = client.patch(
        f"/api/missions/{mission_id}",
        headers=auth_headers,
        json={"purpose": "Updated shoreline mapping"},
    )
    assert patch_response.status_code == 200
    assert patch_response.json()["purpose"] == "Updated shoreline mapping"

    chat_response = client.post(
        f"/api/missions/{mission_id}/chat",
        headers=auth_headers,
        json={"message": "We will fly at 320 feet at night and stay within visual line of sight."},
    )
    assert chat_response.status_code == 200
    assert chat_response.json()["mission"]["maximum_altitude_agl_ft"] == 320
    assert chat_response.json()["mission"]["night_operation"] is True

    submit_response = client.post(f"/api/missions/{mission_id}/submit", headers=auth_headers)
    assert submit_response.status_code == 200
    assert submit_response.json()["ready_for_evaluation"] is True

    evaluate_response = client.post(
        f"/api/missions/{mission_id}/evaluate",
        headers=auth_headers,
        json={"grid_cells": [{"cell_id": "cell-a", "controlled_airspace": False}]},
    )
    assert evaluate_response.status_code == 200
    assert evaluate_response.json()["decision"] in {"APPROVED", "NEEDS_REVIEW", "DENIED"}

    package_response = client.get(f"/api/missions/{mission_id}/simulator-package", headers=auth_headers)
    assert package_response.status_code == 200
    assert package_response.json()["grid_cells"][0]["cell_id"] == "cell-a"


def test_mission_ownership_is_enforced(client, auth_headers, populated_mission):
    second_user = client.post(
        "/api/auth/register",
        json={
            "full_name": "Jordan Lee",
            "email": "jordan@example.com",
            "password": "ResearchPass456",
            "organization": "TAMU-CC",
        },
    ).json()
    second_headers = {"Authorization": f"Bearer {second_user['access_token']}"}

    get_response = client.get(f"/api/missions/{populated_mission['mission_id']}", headers=second_headers)
    patch_response = client.patch(
        f"/api/missions/{populated_mission['mission_id']}",
        headers=second_headers,
        json={"purpose": "Unauthorized change"},
    )

    assert get_response.status_code == 404
    assert patch_response.status_code == 404


def test_chat_and_platform_evaluation_align_for_same_daytime_mission(
    client,
    auth_headers,
    populated_profile,
    populated_drone,
    sample_drone_catalog,
):
    chat_response = client.post(
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
    assert chat_response.status_code == 200

    mission_response = client.post(
        "/api/missions",
        headers=auth_headers,
        json={
            "drone_id": populated_drone["drone_id"],
            "purpose": "Research shoreline mapping",
            "start_time": "2026-07-23T14:00:00",
            "end_time": "2026-07-23T15:00:00",
            "launch_location": {
                "type": "Feature",
                "geometry": None,
                "properties": {"label": "the TAMU-CC waterfront"},
            },
            "operational_area": {
                "type": "Feature",
                "geometry": None,
                "properties": {"label": "the TAMU-CC waterfront to Corpus Christi Bay"},
            },
            "maximum_altitude_agl_ft": 200,
            "maximum_distance_from_pilot_m": 600,
            "operation_over_people": False,
            "operation_over_moving_vehicles": False,
            "visual_line_of_sight": True,
            "night_operation": False,
            "expected_people_count": 0,
            "controlled_ground_area": True,
            "notes": "Site approval confirmed.",
        },
    )
    assert mission_response.status_code == 200
    mission_id = mission_response.json()["mission_id"]

    evaluate_response = client.post(
        f"/api/missions/{mission_id}/evaluate",
        headers=auth_headers,
        json={"grid_cells": [{"cell_id": "cell-a", "controlled_airspace": False}]},
    )
    assert evaluate_response.status_code == 200

    assert chat_response.json()["decision"]["status"] == evaluate_response.json()["decision"]
