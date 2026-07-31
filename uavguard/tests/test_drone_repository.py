from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from uavguard.knowledge_base.ingest_drones import ingest_json_file
from uavguard.knowledge_base.drone_repository import DroneRepository
from uavguard.tests import build_test_settings


class DroneRepositoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.base_dir = Path(self.tempdir.name)
        self.settings = build_test_settings(self.base_dir)
        sample_path = self.settings.raw_data_dir / "sample.json"
        sample_path.write_text(
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
        ingest_json_file(sample_path, self.settings.database_path)
        self.repository = DroneRepository(self.settings)

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def test_exact_lookup_returns_profile(self) -> None:
        result = self.repository.lookup("DJI", "Mini 3")
        self.assertEqual(result.profile.model, "Mini 3")
        self.assertEqual(result.match_type, "exact")

    def test_unresolved_lookup_returns_warning(self) -> None:
        result = self.repository.lookup("Unknown", "Prototype X")
        self.assertEqual(result.match_type, "unresolved")
        self.assertTrue(result.warnings)


if __name__ == "__main__":
    unittest.main()
