"""Pure-stdlib helpers on immutable ARC grids (tuple of tuples, values 0-9)."""

from collections import Counter

from arcagi.tasks import Grid


def shape(grid: Grid) -> tuple[int, int]:
    return len(grid), len(grid[0]) if grid else 0


def is_valid(grid: object) -> bool:
    """True for a non-empty rectangular grid of ints 0-9 no larger than 30x30."""
    if not isinstance(grid, tuple) or not grid or len(grid) > 30:
        return False
    width = len(grid[0]) if isinstance(grid[0], tuple) else 0
    if not 0 < width <= 30:
        return False
    for row in grid:
        if not isinstance(row, tuple) or len(row) != width:
            return False
        for value in row:
            if not isinstance(value, int) or not 0 <= value <= 9:
                return False
    return True


def color_counts(grid: Grid) -> Counter[int]:
    return Counter(value for row in grid for value in row)


def background(grid: Grid) -> int:
    """Most frequent color, ties broken toward 0 then the smaller color."""
    counts = color_counts(grid)
    return max(counts, key=lambda color: (counts[color], color == 0, -color))


def flip_lr(grid: Grid) -> Grid:
    return tuple(row[::-1] for row in grid)


def flip_ud(grid: Grid) -> Grid:
    return grid[::-1]


def transpose(grid: Grid) -> Grid:
    return tuple(zip(*grid, strict=True))


def rot90(grid: Grid) -> Grid:
    """Rotate clockwise by 90 degrees."""
    return tuple(zip(*grid[::-1], strict=True))


def rot180(grid: Grid) -> Grid:
    return tuple(row[::-1] for row in grid[::-1])


def rot270(grid: Grid) -> Grid:
    return tuple(zip(*grid, strict=True))[::-1]


def anti_transpose(grid: Grid) -> Grid:
    return rot180(transpose(grid))


def upscale(grid: Grid, fy: int, fx: int) -> Grid:
    return tuple(
        tuple(v for v in row for _ in range(fx)) for row in grid for _ in range(fy)
    )


def downscale(grid: Grid, fy: int, fx: int) -> Grid:
    """Keep the top-left cell of every fy x fx block (requires exact division)."""
    height, width = shape(grid)
    if height % fy or width % fx:
        raise ValueError("downscale factor must divide the grid")
    return tuple(row[::fx] for row in grid[::fy])


def tile(grid: Grid, ny: int, nx: int) -> Grid:
    return tuple(row * nx for row in grid) * ny


def crop(grid: Grid, top: int, left: int, height: int, width: int) -> Grid:
    return tuple(row[left : left + width] for row in grid[top : top + height])


def bbox(grid: Grid, bg: int) -> tuple[int, int, int, int] | None:
    """Bounding box (top, left, height, width) of non-background cells."""
    rows = [r for r, row in enumerate(grid) if any(v != bg for v in row)]
    if not rows:
        return None
    cols = [c for c in range(len(grid[0])) if any(row[c] != bg for row in grid)]
    return rows[0], cols[0], rows[-1] - rows[0] + 1, cols[-1] - cols[0] + 1


def recolor(grid: Grid, mapping: dict[int, int]) -> Grid:
    return tuple(tuple(mapping.get(value, value) for value in row) for row in grid)


def objects(
    grid: Grid, bg: int, *, diagonal: bool = False, by_color: bool = True
) -> list[list[tuple[int, int]]]:
    """Connected components of non-background cells, in row-major discovery order."""
    height, width = shape(grid)
    seen = [[False] * width for _ in range(height)]
    steps = [(-1, 0), (1, 0), (0, -1), (0, 1)]
    if diagonal:
        steps += [(-1, -1), (-1, 1), (1, -1), (1, 1)]
    found = []
    for r in range(height):
        for c in range(width):
            if seen[r][c] or grid[r][c] == bg:
                continue
            color = grid[r][c]
            stack, cells = [(r, c)], []
            seen[r][c] = True
            while stack:
                y, x = stack.pop()
                cells.append((y, x))
                for dy, dx in steps:
                    ny, nx = y + dy, x + dx
                    if not (0 <= ny < height and 0 <= nx < width) or seen[ny][nx]:
                        continue
                    value = grid[ny][nx]
                    if value == bg or (by_color and value != color):
                        continue
                    seen[ny][nx] = True
                    stack.append((ny, nx))
            found.append(cells)
    return found


def cells_bbox(cells: list[tuple[int, int]]) -> tuple[int, int, int, int]:
    ys = [y for y, _ in cells]
    xs = [x for _, x in cells]
    return min(ys), min(xs), max(ys) - min(ys) + 1, max(xs) - min(xs) + 1
