from __future__ import annotations

import unittest

from uavguard.simulator.astar import astar_path


class AStarTests(unittest.TestCase):
    def test_astar_finds_path_around_obstacle(self) -> None:
        grid = {
            (0, 0): 1,
            (1, 0): 0,
            (0, 1): 1,
            (1, 1): 1,
            (2, 1): 1,
            (2, 0): 1,
        }
        path = astar_path(grid, (0, 0), (2, 0))
        self.assertEqual(path[0], (0, 0))
        self.assertEqual(path[-1], (2, 0))

    def test_astar_returns_empty_when_goal_blocked(self) -> None:
        grid = {
            (0, 0): 1,
            (1, 0): 0,
            (0, 1): 0,
            (1, 1): 0,
        }
        path = astar_path(grid, (0, 0), (1, 1))
        self.assertEqual(path, [])


if __name__ == "__main__":
    unittest.main()
