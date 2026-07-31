from __future__ import annotations

import unittest

from uavguard.api.schemas import Coordinates
from uavguard.knowledge_base.geospatial import geodesic_distance_meters, resolve_location


class GeospatialTests(unittest.TestCase):
    def test_inline_coordinates_are_resolved(self) -> None:
        resolved = resolve_location("29.9511, -90.0715")
        self.assertIsNotNone(resolved.coordinates)
        self.assertEqual(resolved.source, "inline_coordinates")

    def test_distance_calculation_is_positive(self) -> None:
        origin = Coordinates(latitude=29.9511, longitude=-90.0715)
        destination = Coordinates(latitude=29.9325, longitude=-90.1229)
        distance = geodesic_distance_meters(origin, destination)
        self.assertGreater(distance, 1_000)


if __name__ == "__main__":
    unittest.main()
