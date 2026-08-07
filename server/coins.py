"""Coin spawn logic. Capture logic lives in game.resolve_tick (post-collision)."""
import numpy as np

import config


def spawn_coin(game):
    """Spawn one coin on a random free interior cell.

    Free = not obstacle, not occupied by an alive player, not already a coin.
    Returns the (x, y) position, or None if no free cell exists.
    """
    blocked = game.obstacle_grid.copy()
    for p in game.players.values():
        if p.alive:
            x, y = p.position
            blocked[y, x] = True
    for (x, y) in game.coins_uncollected:
        blocked[y, x] = True

    free_ys, free_xs = np.where(~blocked)
    if free_ys.size == 0:
        return None
    idx = int(game.rng.integers(0, free_ys.size))
    x, y = int(free_xs[idx]), int(free_ys[idx])
    game.coins_uncollected.append((x, y))
    return (x, y)
