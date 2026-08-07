"""Coins: spawn cadence, MAX_COINS cap, capture +20, post-collision capture.

Critical test #8.
"""
import config
from helpers import advance, find_adjacent_pair, is_free, make_game, place, set_life


def test_coin_spawns_every_10_ticks():
    g = make_game(seed=7)
    p = g.join("a")
    assert g.tick == 0 and len(g.coins_uncollected) == 0
    for _ in range(9):
        advance(g, {})
    assert g.tick == 9 and len(g.coins_uncollected) == 0
    advance(g, {})                       # tick 10
    assert g.tick == 10
    assert len(g.coins_uncollected) == 1


def test_coins_accumulate_over_time():
    g = make_game(seed=7)
    g.join("a")
    for _ in range(30):
        advance(g, {})
    assert g.tick == 30
    # At least 3 coins spawned (ticks 10,20,30), minus any captured (none).
    assert len(g.coins_uncollected) >= 3


def test_max_coins_cap():
    g = make_game(seed=7)
    g.join("a")
    for _ in range(200):
        advance(g, {})
    assert len(g.coins_uncollected) <= config.MAX_COINS


def test_coin_spawns_on_free_cell():
    g = make_game(seed=7)
    p = g.join("a")
    for _ in range(10):
        advance(g, {})
    coin = g.coins_uncollected[0]
    assert is_free(g, *coin)             # not an obstacle
    assert coin != p.position            # not on a player


def test_capture_grants_plus20_and_removes_coin():
    g = make_game(seed=7)
    p = g.join("a")
    pair = find_adjacent_pair(g, "right")
    c1, c2 = pair
    place(g, p, *c1)
    g.coins_uncollected = [c2]            # put a coin on the target
    life0 = p.life
    advance(g, {p.id: "right"})
    assert p.position == c2
    assert p.coins_captured == 1
    assert p.life == life0 - 1 + 20       # motion -1, coin +20
    assert c2 not in g.coins_uncollected


def test_capture_post_collision_contested_tie_coin_remains():
    """Two movers tie on a coin cell -> both die, coin is NOT captured."""
    from helpers import find_collision_spot
    g = make_game(seed=7)
    spot = find_collision_spot(g, "right", "left")
    T, oa, ob = spot
    a = g.join("a"); b = g.join("b")
    place(g, a, *oa); place(g, b, *ob)
    set_life(a, 50); set_life(b, 50)
    g.coins_uncollected = [T]
    advance(g, {a.id: "right", b.id: "left"})
    assert not a.alive and not b.alive
    assert T in g.coins_uncollected       # coin remains, not duplicated


def test_capture_post_collision_winner_takes_coin():
    """Contested coin: higher-life survivor wins collision then captures the coin."""
    from helpers import find_collision_spot
    g = make_game(seed=7)
    spot = find_collision_spot(g, "right", "left")
    T, oa, ob = spot
    a = g.join("a"); b = g.join("b")
    place(g, a, *oa); place(g, b, *ob)
    set_life(a, 40); set_life(b, 70, coins=1)
    g.coins_uncollected = [T]
    advance(g, {a.id: "right", b.id: "left"})
    assert not a.alive and b.alive
    assert b.position == T
    assert b.coins_captured == 2          # had 1, captured 1
    assert b.life == 70 - 1 + 20          # 89
    assert T not in g.coins_uncollected


def test_coin_not_captured_when_cell_empty_after_deaths():
    """If all would-be occupants die, the coin stays."""
    from helpers import find_collision_spot
    g = make_game(seed=7)
    spot = find_collision_spot(g, "right", "left")
    T, oa, ob = spot
    a = g.join("a"); b = g.join("b")
    place(g, a, *oa); place(g, b, *ob)
    set_life(a, 50); set_life(b, 50)
    g.coins_uncollected = [T]
    advance(g, {a.id: "right", b.id: "left"})  # tie -> both die
    assert T in g.coins_uncollected


def test_no_coin_spawn_when_no_free_cell():
    """If every interior cell is blocked, spawn is skipped (no crash)."""
    g = make_game(seed=7)
    p = g.join("a")
    # Fill all free interior cells as obstacles (except p's cell).
    import numpy as np
    n = config.GRID_SIZE
    g.map_grid[:] = config.OBSTACLE
    g.map_grid[g.players[p.id].position[1], g.players[p.id].position[0]] = config.EMPTY
    g.obstacle_grid = g.map_grid == config.OBSTACLE
    for _ in range(12):
        advance(g, {})
    assert len(g.coins_uncollected) == 0  # no room to spawn
