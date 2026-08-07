"""Helpers for tests: game construction, deterministic placement finders."""
from collections import deque

import config
from game import DIRS, GameState


def make_game(seed=7):
    return GameState(seed=seed)


def in_bounds(x, y):
    n = config.GRID_SIZE
    return 0 <= x < n and 0 <= y < n


def is_free(g, x, y):
    return not bool(g.obstacle_grid[y, x])


def free_interior(g):
    """All free interior cells (x, y) with 1 <= x,y <= n-2."""
    n = config.GRID_SIZE
    obs = g.obstacle_grid
    cells = []
    for y in range(1, n - 1):
        for x in range(1, n - 1):
            if not obs[y, x]:
                cells.append((x, y))
    return cells


def nearest_free(g, x, y):
    """Nearest free cell to (x, y) via 8-neighbour BFS (returns (x,y) itself if free)."""
    if is_free(g, x, y):
        return (x, y)
    n = config.GRID_SIZE
    seen = {(x, y)}
    q = deque([(x, y)])
    while q:
        cx, cy = q.popleft()
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                if dx == 0 and dy == 0:
                    continue
                nx, ny = cx + dx, cy + dy
                if 0 <= nx < n and 0 <= ny < n and (nx, ny) not in seen:
                    seen.add((nx, ny))
                    if is_free(g, nx, ny):
                        return (nx, ny)
                    q.append((nx, ny))
    return None


def place(g, player, x, y):
    """Place a player on the nearest free cell to (x, y)."""
    fx, fy = nearest_free(g, x, y)
    player.position = (fx, fy)
    return (fx, fy)


def set_life(player, life, coins=0):
    """Set a player's computed life by adjusting motion_count (and coins)."""
    player.coins_captured = coins
    player.motion_count = config.BASE_LIFE + config.COIN_LIFE_BONUS * coins - life


def find_collision_spot(g, dir_a, dir_b):
    """Free target T with free origins T-delta(dir_a) and T-delta(dir_b).

    Origins are distinct. For a stayer, pass dir='stay' so its origin equals T.
    Returns (T, origin_a, origin_b) or None.
    """
    da = DIRS[dir_a]
    db = DIRS[dir_b]
    for (tx, ty) in free_interior(g):
        oa = (tx - da[0], ty - da[1])
        ob = (tx - db[0], ty - db[1])
        if oa == ob:
            continue
        if is_free(g, *oa) and is_free(g, *ob):
            return (tx, ty), oa, ob
    return None


def find_adjacent_pair(g, direction):
    """Two adjacent free cells (C, C+delta(direction)). Returns (C, C2) or None."""
    d = DIRS[direction]
    for (x, y) in free_interior(g):
        nx, ny = x + d[0], y + d[1]
        if in_bounds(nx, ny) and is_free(g, nx, ny):
            return (x, y), (nx, ny)
    return None


def find_blocked_origin(g, direction):
    """Free cell whose neighbour in `direction` is an obstacle or out of bounds."""
    d = DIRS[direction]
    for (x, y) in free_interior(g):
        nx, ny = x + d[0], y + d[1]
        if not in_bounds(nx, ny) or g.obstacle_grid[ny, nx]:
            return (x, y)
    return None


def advance(game, pending=None):
    """Mimic the tick loop: swap pending and resolve one tick (no lock, test-only)."""
    if pending is None:
        local = game.pending
        game.pending = {}
    else:
        local = pending
    game.resolve_tick(local)
    return game
