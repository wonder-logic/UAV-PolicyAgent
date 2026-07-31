from __future__ import annotations

import json
from pathlib import Path
import tempfile
import gc
from unittest.mock import patch
import unittest

from fastapi.testclient import TestClient

from uavguard.agents.orchestrator import UAVGuardOrchestrator
from uavguard.main import create_app
from uavguard.knowledge_base.ingest_drones import ingest_directory
from uavguard.policy.ingest_policies import ingest_policy_directory
from uavguard.tests import build_test_settings


class _FakeWeatherResponse:
    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return {
            "current": {
                "temperature_2m": 24,
                "wind_speed_10m": 4.5,
                "weather_code": 1,
            }
        }


class ApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.base_dir = Path(self.tempdir.name)
        self.settings = build_test_settings(self.base_dir)
        (self.settings.raw_data_dir / "sample.json").write_text(
            json.dumps(
                [
                    {
                        "manufacturer": "DJI",
                        "model": "Mini 3",
                        "weight_grams": 249,
                        "max_flight_time_minutes": 38,
                        "max_range_meters": 18000,
                        "max_speed_mps": 16,
                        "source": "test",
                    }
                ]
            ),
            encoding="utf-8",
        )
        (self.settings.faa_docs_dir / "policy.txt").write_text(
            "\n".join(
                [
                    "Daylight operations may proceed when the remote pilot maintains visual line of sight.",
                    "Night operations require anti-collision lighting and additional review.",
                    "Missions should be paused when weather conditions prevent safe control.",
                ]
            ),
            encoding="utf-8",
        )
        (self.settings.sample_requests_dir / "sample_flight_request.json").write_text(
            json.dumps(
                {
                    "manufacturer": "DJI",
                    "model": "Mini 3",
                    "origin": "Xavier University of Louisiana, New Orleans, LA",
                    "destination": "Audubon Park, New Orleans, LA",
                    "battery_percentage": 78,
                    "intended_flight_time": "2026-06-24T14:30:00",
                    "mission_purpose": "inspection",
                }
            ),
            encoding="utf-8",
        )
        ingest_directory(self.settings.raw_data_dir, self.settings.database_path)
        ingest_policy_directory(self.settings.faa_docs_dir, self.settings)
        self.client = TestClient(create_app(self.settings))

    def tearDown(self) -> None:
        self.client.close()
        gc.collect()
        self.tempdir.cleanup()

    @patch("uavguard.knowledge_base.weather.httpx.get", return_value=_FakeWeatherResponse())
    def test_flight_request_endpoint_runs_full_workflow(self, _mock_get) -> None:
        payload = {
            "manufacturer": "DJI",
            "model": "Mini 3",
            "origin": "Xavier University of Louisiana, New Orleans, LA",
            "destination": "Audubon Park, New Orleans, LA",
            "battery_percentage": 78,
            "intended_flight_time": "2026-06-24T14:30:00",
            "mission_purpose": "inspection",
        }
        response = self.client.post("/flight-request", json=payload)
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertIn(body["final_decision"], {"APPROVED", "NEEDS_REVIEW"})
        self.assertTrue(body["artifacts"]["mission_file"])

    def test_health_endpoint_reports_ok(self) -> None:
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ok")

    @patch("uavguard.knowledge_base.weather.httpx.get", return_value=_FakeWeatherResponse())
    def test_simulator_demo_endpoint_returns_success(self, _mock_get) -> None:
        response = self.client.get("/simulator/demo")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["status"], "APPROVED")
        self.assertTrue(body["path_found"])
        self.assertTrue(body["visualization_path"])

    def test_final_decision_logic_denies_non_compliant_policy(self) -> None:
        decision = UAVGuardOrchestrator._final_decision(
            knowledge_status="APPROVED",
            policy_status="NON_COMPLIANT",
            simulator_status="APPROVED",
            path_found=True,
        )
        self.assertEqual(decision, "DENIED")


if __name__ == "__main__":
    unittest.main()
