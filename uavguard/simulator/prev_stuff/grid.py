"""Grid generation helpers for the lightweight UAVGuard simulator."""

from __future__ import annotations

from ..api.schemas import Coordinates
from ..knowledge_base.geospatial import relative_offset_meters


Grid = dict[tuple[int, int], int]
Rectangle = tuple[tuple[int, int], tuple[int, int]]

CELL_SIZE_METERS = 100.0


def meters_to_goal_cell(
    origin: Coordinates,
    destination: Coordinates,
    cell_size_meters: float = CELL_SIZE_METERS,
) -> tuple[int, int]:
    """Convert destination GPS coordinates into a relative grid cell."""

    if cell_size_meters <= 0:
        raise ValueError("cell_size_meters must be greater than zero.")

    east_m, north_m = relative_offset_meters(origin, destination)
    goal_x = round(east_m / cell_size_meters)
    goal_y = round(north_m / cell_size_meters)

    if goal_x == 0 and goal_y == 0:
        return (1, 1)
    return (goal_x, goal_y)


def _apply_rectangle(
    grid: Grid,
    lower_left: tuple[int, int],
    upper_right: tuple[int, int],
    start: tuple[int, int],
    goal: tuple[int, int],
) -> None:
    """Mark cells inside a rectangle as blocked."""

    min_x = min(lower_left[0], upper_right[0])
    max_x = max(lower_left[0], upper_right[0])
    min_y = min(lower_left[1], upper_right[1])
    max_y = max(lower_left[1], upper_right[1])

    for x in range(min_x, max_x + 1):
        for y in range(min_y, max_y + 1):
            cell = (x, y)
            if cell not in grid or cell in {start, goal}:
                continue
            grid[cell] = 0


def generate_sample_no_fly_zones(
    start: tuple[int, int],
    goal: tuple[int, int],
) -> list[Rectangle]:
    """Create a simple vertical no-fly wall with a later gap."""

    rectangles: list[Rectangle] = []
    manhattan_distance = abs(goal[0] - start[0]) + abs(goal[1] - start[1])
    if manhattan_distance >= 4:
        mid_x = round((start[0] + goal[0]) / 2)
        low_y = min(start[1], goal[1]) - 1
        high_y = max(start[1], goal[1]) + 1
        rectangles.append(((mid_x, low_y), (mid_x, high_y)))
    return rectangles


def build_grid(
    start: tuple[int, int] = (0, 0),
    goal: tuple[int, int] = (8, 6),
    padding: int = 4,
    manual_no_fly_rectangles: list[Rectangle] | None = None,
    include_generated_zones: bool = True,
) -> Grid:
    """Build a binary occupancy grid around the mission corridor."""

    if padding < 0:
        raise ValueError("padding must be zero or greater.")

    min_x = min(start[0], goal[0]) - padding
    max_x = max(start[0], goal[0]) + padding
    min_y = min(start[1], goal[1]) - padding
    max_y = max(start[1], goal[1]) + padding

    grid: Grid = {
        (x, y): 1
        for x in range(min_x, max_x + 1)
        for y in range(min_y, max_y + 1)
    }

    for lower_left, upper_right in manual_no_fly_rectangles or []:
        _apply_rectangle(
            grid=grid,
            lower_left=lower_left,
            upper_right=upper_right,
            start=start,
            goal=goal,
        )

    if include_generated_zones:
        generated_rectangles = generate_sample_no_fly_zones(start, goal)
        for lower_left, upper_right in generated_rectangles:
            _apply_rectangle(
                grid=grid,
                lower_left=lower_left,
                upper_right=upper_right,
                start=start,
                goal=goal,
            )

        if generated_rectangles:
            midpoint = (
                round((start[0] + goal[0]) / 2),
                round((start[1] + goal[1]) / 2),
            )
            if midpoint in grid:
                grid[midpoint] = 1

    grid[start] = 1
    grid[goal] = 1
    return grid


def grid_bounds(grid: Grid) -> tuple[int, int, int, int]:
    """Return min/max bounds for a generated grid."""

    xs = [cell[0] for cell in grid]
    ys = [cell[1] for cell in grid]
    return min(xs), max(xs), min(ys), max(ys)


def print_grid(
    grid: Grid,
    start: tuple[int, int],
    goal: tuple[int, int],
) -> None:
    """Print the grid in the terminal."""

    min_x, max_x, min_y, max_y = grid_bounds(grid)
    for y in range(max_y, min_y - 1, -1):
        row: list[str] = []
        for x in range(min_x, max_x + 1):
            cell = (x, y)
            if cell == start:
                row.append("S")
            elif cell == goal:
                row.append("G")
            elif grid.get(cell) == 0:
                row.append("#")
            else:
                row.append(".")
        print(" ".join(row))


if __name__ == "__main__":
    start_cell = (0, 0)
    goal_cell = (8, 6)
    manual_zones: list[Rectangle] = [
        ((-4, 2), (-2, 5)),
        ((4, -5), (6, -3)),
    ]

    mission_grid = build_grid(
        start=start_cell,
        goal=goal_cell,
        padding=4,
        manual_no_fly_rectangles=manual_zones,
        include_generated_zones=True,
    )

    min_x, max_x, min_y, max_y = grid_bounds(mission_grid)
    grid_width = max_x - min_x + 1
    grid_height = max_y - min_y + 1

    print(f"Grid size: {grid_width} x {grid_height}")
    print(f"Total cells: {len(mission_grid)}")
    print(
        "Physical coverage: "
        f"{grid_width * CELL_SIZE_METERS / 1000:.1f} km x "
        f"{grid_height * CELL_SIZE_METERS / 1000:.1f} km"
    )
    print(f"Start: {start_cell}")
    print(f"Goal: {goal_cell}")
    print()

    print_grid(
        grid=mission_grid,
        start=start_cell,
        goal=goal_cell,
    )
