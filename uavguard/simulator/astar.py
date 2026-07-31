"""A* pathfinding for a 2D no-fly-zone grid."""

from __future__ import annotations

from heapq import heappop, heappush


Grid = dict[tuple[int, int], int]


def _heuristic(current: tuple[int, int], goal: tuple[int, int]) -> int:
    return abs(current[0] - goal[0]) + abs(current[1] - goal[1])


def _neighbors(cell: tuple[int, int]) -> list[tuple[int, int]]:
    x, y = cell
    return [(x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)]


def astar_path(grid: Grid, start: tuple[int, int], goal: tuple[int, int]) -> list[tuple[int, int]]:
    """Compute the shortest path while avoiding restricted cells."""

    if grid.get(start) != 1 or grid.get(goal) != 1:
        return []

    frontier: list[tuple[int, tuple[int, int]]] = []
    heappush(frontier, (0, start))
    came_from: dict[tuple[int, int], tuple[int, int] | None] = {start: None}
    cost_so_far: dict[tuple[int, int], int] = {start: 0}

    while frontier:
        _, current = heappop(frontier)
        if current == goal:
            break
        for neighbor in _neighbors(current):
            if grid.get(neighbor) != 1:
                continue
            new_cost = cost_so_far[current] + 1
            if neighbor not in cost_so_far or new_cost < cost_so_far[neighbor]:
                cost_so_far[neighbor] = new_cost
                priority = new_cost + _heuristic(neighbor, goal)
                heappush(frontier, (priority, neighbor))
                came_from[neighbor] = current

    if goal not in came_from:
        return []

    path = [goal]
    current = goal
    while current != start:
        current = came_from[current]
        if current is None:
            return []
        path.append(current)
    path.reverse()
    return path
