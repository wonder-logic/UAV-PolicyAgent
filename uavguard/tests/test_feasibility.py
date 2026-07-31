from __future__ import annotations

from unittest.mock import patch
import unittest

from uavguard.api.schemas import Coordinates, DroneProfile, FlightRequest
from uavguard.knowledge_base.feasibility import assess_feasibility
from uavguard.knowledge_base.weather import fetch_weather


class FeasibilityTests(unittest.TestCase):
    def test_low_battery_denies_flight(self) -> None:
        request = FlightRequest.model_validate(
            {
                "manufacturer": "DJI",
                "model": "Mini 3",
                "origin": "29.95, -90.07",
                "destination": "29.96, -90.06",
                "battery_percentage": 10,
                "intended_flight_time": "2026-06-24T14:00:00",
            }
        )
        drone = DroneProfile(
            manufacturer="DJI",
            model="Mini 3",
            max_range_meters=18000,
            max_flight_time_minutes=38,
            max_speed_mps=16,
            source="test",
        )
        weather = fetch_weather(Coordinates(latitude=29.95, longitude=-90.07))
        result = assess_feasibility(request, drone, 2_000, weather)
        self.assertEqual(result.status, "DENIED")

    @patch("uavguard.knowledge_base.weather.httpx.get", side_effect=RuntimeError("offline"))
    def test_weather_fallback_returns_warning(self, _mock_get) -> None:
        weather = fetch_weather(Coordinates(latitude=29.95, longitude=-90.07))
        self.assertEqual(weather.source, "fallback")
        self.assertTrue(weather.warnings)


if __name__ == "__main__":
    unittest.main()
