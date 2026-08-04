from __future__ import annotations

import io
import shutil
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from policy_agent.api.routes import create_app
from policy_agent.config import build_settings
from policy_agent.utils.json_utils import write_json_file

SAMPLE_POLICY_TEXT = """# Sample Research Night Operations Policy

## Night Operations
Night operations are permitted for research missions only when Remote ID is active, visual line of sight is maintained, and the operator provides pilot certification evidence.

## Controlled Airspace
Operations in controlled airspace require documented authorization before flight.

## Altitude
Flights must not exceed 400 feet above ground level unless a specific waiver is documented.

## Operations Over People
Flights must not occur directly over uninvolved people without an applicable waiver.

## Local Property Restrictions
University property flights require local site approval before takeoff.
"""


def build_pdf_bytes(text: str) -> bytes:
    escaped = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    stream = f"BT\n/F1 18 Tf\n72 720 Td\n({escaped}) Tj\nET"
    stream_bytes = stream.encode("latin-1")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
        f"<< /Length {len(stream_bytes)} >>\nstream\n{stream}\nendstream".encode("latin-1"),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]

    buffer = io.BytesIO()
    buffer.write(b"%PDF-1.4\n")
    offsets = [0]
    for index, obj in enumerate(objects, start=1):
        offsets.append(buffer.tell())
        buffer.write(f"{index} 0 obj\n".encode("latin-1"))
        buffer.write(obj)
        buffer.write(b"\nendobj\n")

    xref_position = buffer.tell()
    buffer.write(f"xref\n0 {len(objects) + 1}\n".encode("latin-1"))
    buffer.write(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        buffer.write(f"{offset:010d} 00000 n \n".encode("latin-1"))
    buffer.write(
        (f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_position}\n%%EOF").encode("latin-1")
    )
    return buffer.getvalue()


@pytest.fixture()
def settings():
    test_runs_root = Path.cwd() / ".tmp" / "test-runs"
    test_runs_root.mkdir(parents=True, exist_ok=True)
    project_root = Path(tempfile.mkdtemp(prefix="uavguard-policy-agent-", dir=str(test_runs_root)))
    settings = build_settings(project_root=project_root)
    settings.ensure_directories()
    try:
        yield settings
    finally:
        shutil.rmtree(project_root, ignore_errors=True)


@pytest.fixture()
def sample_policy_text() -> str:
    return SAMPLE_POLICY_TEXT


@pytest.fixture()
def sample_drone_catalog(settings):
    payload = [
        {
            "model_id": "dji-mini-4-pro",
            "manufacturer": "DJI",
            "model_name": "Mini 4 Pro",
            "uas_class": "C0",
            "weight_grams": 249,
            "max_takeoff_weight_grams": 249,
            "endurance_minutes": 34,
            "night_lights": True,
            "anti_collision_lights": True,
            "has_camera": True,
            "is_toy": False,
        }
    ]
    write_json_file(settings.drone_catalog_path, payload)
    return payload


@pytest.fixture()
def client(settings):
    with TestClient(create_app(settings)) as test_client:
        yield test_client


@pytest.fixture()
def registered_user(client):
    response = client.post(
        "/api/auth/register",
        json={
            "full_name": "Avery Rhodes",
            "email": "avery@example.com",
            "password": "ResearchPass123",
            "organization": "TAMU-CC",
        },
    )
    assert response.status_code == 200
    return response.json()


@pytest.fixture()
def auth_headers(registered_user):
    return {"Authorization": f"Bearer {registered_user['access_token']}"}


@pytest.fixture()
def populated_profile(client, auth_headers):
    response = client.post(
        "/api/profiles",
        headers=auth_headers,
        json={
            "full_name": "Avery Rhodes",
            "email": "avery@example.com",
            "jurisdiction": "US",
            "operator_type": "research",
            "organization": "TAMU-CC",
            "preferred_units": "imperial",
            "remote_pilot_certificate_number": "RPC-12345",
            "remote_pilot_certificate_issue_date": "2025-01-10",
            "remote_pilot_certificate_expiration": "2027-01-10",
            "recurrent_training_completed": True,
            "recurrent_training_date": "2026-04-01",
        },
    )
    assert response.status_code == 200
    return response.json()


@pytest.fixture()
def populated_drone(client, auth_headers):
    response = client.post(
        "/api/drones",
        headers=auth_headers,
        json={
            "nickname": "Research Mini",
            "manufacturer": "DJI",
            "model": "Mini 4 Pro",
            "weight_grams": 249,
            "maximum_takeoff_weight_grams": 249,
            "category": "small_uas",
            "remote_id_type": "standard",
            "remote_id_serial_number": "RID-001",
            "anti_collision_lighting": True,
            "light_visibility_statute_miles": 3.5,
            "maximum_endurance_minutes": 34,
            "maximum_operating_altitude_ft": 400,
            "verification_status": "verified",
            "is_default": True,
        },
    )
    assert response.status_code == 200
    return response.json()


@pytest.fixture()
def populated_mission(client, auth_headers, populated_profile, populated_drone):
    response = client.post(
        "/api/missions",
        headers=auth_headers,
        json={
            "drone_id": populated_drone["drone_id"],
            "purpose": "Research shoreline mapping",
            "start_time": "2026-07-23T21:00:00",
            "end_time": "2026-07-23T22:00:00",
            "launch_location": {
                "type": "Feature",
                "geometry": None,
                "properties": {"label": "TAMU-CC waterfront launch"},
            },
            "operational_area": {
                "type": "Feature",
                "geometry": None,
                "properties": {"label": "Corpus Christi Bay shoreline"},
            },
            "maximum_altitude_agl_ft": 300,
            "maximum_distance_from_pilot_m": 600,
            "operation_over_people": False,
            "operation_over_moving_vehicles": False,
            "visual_line_of_sight": True,
            "night_operation": True,
            "expected_people_count": 0,
            "controlled_ground_area": True,
            "notes": "Night mapping near campus waterfront.",
        },
    )
    assert response.status_code == 200
    return response.json()
