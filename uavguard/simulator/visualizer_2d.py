"""2D grid rendering for UAVGuard simulation outputs."""

from __future__ import annotations

from pathlib import Path

try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
except ImportError:  # pragma: no cover - optional dependency
    plt = None


def _grid_bounds(grid: dict[tuple[int, int], int]) -> tuple[int, int, int, int]:
    xs = [cell[0] for cell in grid]
    ys = [cell[1] for cell in grid]
    return min(xs), max(xs), min(ys), max(ys)


def _render_svg(
    grid: dict[tuple[int, int], int],
    start: tuple[int, int],
    goal: tuple[int, int],
    path: list[tuple[int, int]],
    output_path: Path,
) -> str:
    cell_px = 28
    min_x, max_x, min_y, max_y = _grid_bounds(grid)
    width = (max_x - min_x + 1) * cell_px
    height = (max_y - min_y + 1) * cell_px

    def point_for(cell: tuple[int, int]) -> tuple[int, int]:
        x = (cell[0] - min_x) * cell_px + cell_px // 2
        y = height - ((cell[1] - min_y) * cell_px + cell_px // 2)
        return x, y

    rects = []
    for (x, y), allowed in grid.items():
        fill = "#2e8b57" if allowed == 1 else "#cf3b2e"
        px = (x - min_x) * cell_px
        py = height - ((y - min_y + 1) * cell_px)
        rects.append(
            f'<rect x="{px}" y="{py}" width="{cell_px}" height="{cell_px}" '
            f'fill="{fill}" stroke="#ffffff" stroke-width="1" />'
        )

    path_points = " ".join(f"{x},{y}" for x, y in (point_for(cell) for cell in path))
    start_x, start_y = point_for(start)
    goal_x, goal_y = point_for(goal)
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width + 40}" height="{height + 40}" viewBox="-20 -20 {width + 40} {height + 40}">
<rect x="-20" y="-20" width="{width + 40}" height="{height + 40}" fill="#f7f8fb" />
{''.join(rects)}
<polyline fill="none" stroke="#0a58ca" stroke-width="4" points="{path_points}" />
<circle cx="{start_x}" cy="{start_y}" r="7" fill="#1d4ed8" />
<circle cx="{goal_x}" cy="{goal_y}" r="7" fill="#111827" />
<text x="{start_x + 10}" y="{start_y - 8}" font-size="12" fill="#0f172a">Start</text>
<text x="{goal_x + 10}" y="{goal_y - 8}" font-size="12" fill="#0f172a">Goal</text>
</svg>"""
    output_path.write_text(svg, encoding="utf-8")
    return str(output_path)


def _render_matplotlib(
    grid: dict[tuple[int, int], int],
    start: tuple[int, int],
    goal: tuple[int, int],
    path: list[tuple[int, int]],
    output_path: Path,
) -> str:
    min_x, max_x, min_y, max_y = _grid_bounds(grid)
    fig, ax = plt.subplots(figsize=(7, 7))
    for (x, y), allowed in grid.items():
        color = "#2e8b57" if allowed == 1 else "#cf3b2e"
        ax.add_patch(plt.Rectangle((x - 0.5, y - 0.5), 1, 1, color=color, ec="white"))
    if path:
        xs = [cell[0] for cell in path]
        ys = [cell[1] for cell in path]
        ax.plot(xs, ys, color="#0a58ca", linewidth=2.5)
    ax.scatter([start[0]], [start[1]], color="#1d4ed8", s=80, label="Drone position")
    ax.scatter([goal[0]], [goal[1]], color="#111827", s=80, label="Goal")
    ax.set_xlim(min_x - 1, max_x + 1)
    ax.set_ylim(min_y - 1, max_y + 1)
    ax.set_aspect("equal")
    ax.set_xlabel("X cells")
    ax.set_ylabel("Y cells")
    ax.set_title("UAVGuard 2D No-Fly-Zone Grid")
    ax.grid(False)
    ax.legend(loc="upper right")
    fig.tight_layout()
    fig.savefig(output_path, dpi=180)
    plt.close(fig)
    return str(output_path)


def render_grid_visualization(
    grid: dict[tuple[int, int], int],
    start: tuple[int, int],
    goal: tuple[int, int],
    path: list[tuple[int, int]],
    output_dir: str | Path,
    stem: str = "grid_visualization",
) -> str:
    """Render the mission grid to an image artifact."""

    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)
    if plt is not None:
        return _render_matplotlib(grid, start, goal, path, directory / f"{stem}.png")
    return _render_svg(grid, start, goal, path, directory / f"{stem}.svg")
