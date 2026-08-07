"""World generation: border wall + radial lines, 8-connectivity check, carve fallback.

Grid layout uses numpy axis order [row, col] == [y, x]; cell (x, y) is
grid[y, x]. Obstacles are stored as OBSTACLE (1) in a uint8 map; a boolean
obstacle_grid is derived from it for movement and connectivity tests.
"""
from collections import deque

import numpy as np
from scipy.ndimage import binary_dilation, label

import config

# 8-connectivity: diagonal moves are legal, so two free cells touching only at
# a corner are mutually reachable.
STRUCTURE = np.ones((3, 3), dtype=int)


def generate_world(seed: int | None = None):
    """Generate a connected obstacle layout.

    Returns (map_grid, gen_seed, carved) where map_grid is uint8 with EMPTY/OBSTACLE,
    gen_seed is the seed used, and carved is True if the carve fallback ran.
    """
    n = config.GRID_SIZE
    last_grid = None
    last_seed = None

    # When a seed is provided, the whole attempt sequence is deterministic:
    # first try `seed`, then seeds derived from a stream seeded by it. When no
    # seed is given, every attempt uses a fresh random seed.
    derived = np.random.default_rng(seed) if seed is not None else None

    for _ in range(config.MAX_GEN_ATTEMPTS):
        if seed is not None and last_seed is None:
            s = int(seed)
        elif seed is not None:
            s = int(derived.integers(0, 2**31))
        else:
            s = int(np.random.default_rng().integers(0, 2**31))
        rng = np.random.default_rng(s)
        grid = _build_grid(rng, n)
        last_grid, last_seed = grid, s
        if _component_count(grid) <= 1:
            return grid, s, False

    # All attempts disconnected: carve minimal passages on the last layout.
    _carve(last_grid, n)
    return last_grid, last_seed, True


def _build_grid(rng, n):
    """Border wall + NUM_LINES radial lines drawn inward from a random side."""
    grid = np.zeros((n, n), dtype=np.uint8)
    # Border is always wall.
    grid[0, :] = config.OBSTACLE
    grid[-1, :] = config.OBSTACLE
    grid[:, 0] = config.OBSTACLE
    grid[:, -1] = config.OBSTACLE

    for _ in range(config.NUM_LINES):
        side = int(rng.integers(0, 4))          # 0 top, 1 bottom, 2 left, 3 right
        coord = int(rng.integers(1, n - 1))     # interior 1..n-2 along the side
        length = int(rng.integers(config.MIN_LINE_LEN, config.MAX_LINE_LEN + 1))
        _draw_line(grid, side, coord, length, n)
    return grid


def _draw_line(grid, side, coord, length, n):
    """Draw `length` obstacle cells perpendicular to the chosen wall, inward."""
    if side == 0:        # top wall -> line grows downward (+y)
        for i in range(length):
            y = 1 + i
            if 1 <= y <= n - 2:
                grid[y, coord] = config.OBSTACLE
    elif side == 1:      # bottom wall -> line grows upward (-y)
        for i in range(length):
            y = n - 2 - i
            if 1 <= y <= n - 2:
                grid[y, coord] = config.OBSTACLE
    elif side == 2:      # left wall -> line grows rightward (+x)
        for i in range(length):
            x = 1 + i
            if 1 <= x <= n - 2:
                grid[coord, x] = config.OBSTACLE
    else:                # right wall -> line grows leftward (-x)
        for i in range(length):
            x = n - 2 - i
            if 1 <= x <= n - 2:
                grid[coord, x] = config.OBSTACLE


def _component_count(grid):
    """Number of 8-connected free components (obstacles excluded)."""
    obstacle = grid == config.OBSTACLE
    _, n = label(~obstacle, structure=STRUCTURE)
    return n


def _carve(grid, n, max_iter=10000):
    """Carve minimal passages until the free region is a single component.

    The border wall is never carved. Each iteration: take the largest component
    as main; for every other component, find the shortest obstacle-path to
    main and remove one non-border obstacle cell adjacent to that component
    (growing it toward main). Repeat.
    """
    carvable = np.ones((n, n), dtype=bool)
    carvable[0, :] = False
    carvable[-1, :] = False
    carvable[:, 0] = False
    carvable[:, -1] = False

    for _ in range(max_iter):
        obstacle = grid == config.OBSTACLE
        labeled, ncomp = label(~obstacle, structure=STRUCTURE)
        if ncomp <= 1:
            return

        sizes = np.bincount(labeled.ravel())
        # Component labels start at 1; index 0 is obstacles.
        main_id = int(np.argmax(sizes[1:])) + 1
        main_mask = labeled == main_id

        removed = False
        for comp_id in range(1, ncomp + 1):
            if comp_id == main_id:
                continue
            comp_mask = labeled == comp_id
            cell = _bridge_cell(obstacle, comp_mask, main_mask, carvable, n)
            if cell is not None:
                grid[cell[0], cell[1]] = config.EMPTY
                removed = True
        if not removed:
            break


def _bridge_cell(obstacle, comp_mask, main_mask, carvable, n):
    """Carvable obstacle cell adjacent to `comp` opening the shortest path to `main`.

    `carvable` masks out cells that must never be removed (the border wall).
    Returns (y, x) of the obstacle cell to remove, or None if comp is not
    bordered by any carvable obstacle.
    """
    comp_dil = binary_dilation(comp_mask, structure=STRUCTURE, border_value=0)
    main_dil = binary_dilation(main_mask, structure=STRUCTURE, border_value=0)
    start_mask = obstacle & comp_dil & carvable   # carvable obstacles touching comp
    goal_mask = obstacle & main_dil & carvable    # carvable obstacles touching main

    if not start_mask.any():
        return None

    # An obstacle touching both comp and main merges them immediately.
    both = start_mask & goal_mask
    if both.any():
        ys, xs = np.where(both)
        return int(ys[0]), int(xs[0])

    if not goal_mask.any():
        # Main has no adjacent carvable obstacle: grow comp into any bordering wall.
        ys, xs = np.where(start_mask)
        return int(ys[0]), int(xs[0])

    # Multi-source BFS from goal obstacles through obstacles; pick nearest start.
    dist = np.full((n, n), -1, dtype=int)
    q = deque()
    gy, gx = np.where(goal_mask)
    for y, x in zip(gy.tolist(), gx.tolist()):
        dist[y, x] = 0
        q.append((y, x))
    while q:
        y, x = q.popleft()
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                if dy == 0 and dx == 0:
                    continue
                ny, nx = y + dy, x + dx
                if 0 <= ny < n and 0 <= nx < n and obstacle[ny, nx] and dist[ny, nx] == -1:
                    dist[ny, nx] = dist[y, x] + 1
                    q.append((ny, nx))

    sy, sx = np.where(start_mask)
    best = None
    best_d = None
    for y, x in zip(sy.tolist(), sx.tolist()):
        d = dist[y, x]
        if d == -1:
            continue  # not reachable via obstacles; skip this iteration
        if best_d is None or d < best_d:
            best_d = d
            best = (y, x)
    if best is None:
        # No obstacle path found: grow comp into a bordering carvable obstacle anyway.
        ys, xs = np.where(start_mask)
        return int(ys[0]), int(xs[0])
    return best


def obstacle_locations(map_grid):
    """Precompute the list of [x, y] obstacle coordinates for /state."""
    ys, xs = np.where(map_grid == config.OBSTACLE)
    return [[int(x), int(y)] for x, y in zip(xs.tolist(), ys.tolist())]
