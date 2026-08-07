"""Tick resolution: simultaneous moves, swaps, blocked, bounds, stay-free.

Critical tests #4, #5, #6 (and motion/life semantics §7).
"""
import config
from helpers import (advance, find_adjacent_pair, find_blocked_origin,
                      make_game, place, set_life)


def test_stay_is_free_no_motion_no_life_change():
    g = make_game(seed=7)
    p = g.join("a")
    place(g, p, 50, 50)
    mc, life0 = p.motion_count, p.life
    advance(g, {p.id: "stay"})
    assert p.position == (50, 50)
    assert p.motion_count == mc
    assert p.life == life0


def test_no_submission_is_free():
    g = make_game(seed=7)
    p = g.join("a")
    place(g, p, 50, 50)
    mc, life0 = p.motion_count, p.life
    advance(g, {})  # nothing pending
    assert p.position == (50, 50)
    assert p.motion_count == mc
    assert p.life == life0


def test_directional_move_displaces_and_costs_one_motion():
    g = make_game(seed=7)
    p = g.join("a")
    c1, c2 = find_adjacent_pair(g, "right")
    place(g, p, *c1)
    mc, life0 = p.motion_count, p.life
    advance(g, {p.id: "right"})
    assert p.position == c2
    assert p.motion_count == mc + 1
    assert p.life == life0 - 1


def test_blocked_move_stays_but_costs():
    g = make_game(seed=7)
    p = g.join("a")
    origin = find_blocked_origin(g, "right")
    assert origin is not None
    place(g, p, *origin)
    mc, life0 = p.motion_count, p.life
    advance(g, {p.id: "right"})
    assert p.position == origin
    assert p.motion_count == mc + 1
    assert p.life == life0 - 1


def test_out_of_bounds_blocked():
    """A move toward the border wall from an interior cell adjacent to it is blocked."""
    import numpy as np
    g = make_game(seed=7)
    p = g.join("a")
    # Find a free cell in column 1 (x=1); moving left targets x=0 which is border wall.
    n = config.GRID_SIZE
    found = None
    for y in range(1, n - 1):
        if not g.obstacle_grid[y, 1]:
            found = (1, y)
            break
    assert found is not None
    place(g, p, *found)
    advance(g, {p.id: "left"})
    assert p.position == found          # blocked by border
    assert p.motion_count == 1
    assert p.life == config.BASE_LIFE - 1


def test_swap_is_safe_both_move_no_death():
    from helpers import find_collision_spot
    g = make_game(seed=7)
    a = g.join("a"); b = g.join("b")
    # A at C1 -> right -> C2 ; B at C2 -> left -> C1  (swap, no shared target cell)
    pair = find_adjacent_pair(g, "right")
    c1, c2 = pair
    place(g, a, *c1)
    place(g, b, *c2)
    la, lb = a.life, b.life
    advance(g, {a.id: "right", b.id: "left"})
    assert a.alive and b.alive
    assert a.position == c2
    assert b.position == c1
    assert a.motion_count == 1 and b.motion_count == 1
    assert a.life == la - 1 and b.life == lb - 1


def test_diagonal_move_works():
    g = make_game(seed=7)
    p = g.join("a")
    c1, c2 = find_adjacent_pair(g, "downright")
    place(g, p, *c1)
    advance(g, {p.id: "downright"})
    assert p.position == c2
    assert p.motion_count == 1


def test_direction_aliases_normalize():
    from game import parse_direction, DIRS
    assert parse_direction("u") == "up"
    assert parse_direction("NORTH") == "up"
    assert parse_direction("se") == "downright"
    assert parse_direction("hold") == "stay"
    assert parse_direction("0") == "stay"
    assert parse_direction("xyzzy") is None
    assert parse_direction(5) is None


def test_last_move_in_pending_wins_only_one_motion():
    g = make_game(seed=7)
    p = g.join("a")
    c1, c2 = find_adjacent_pair(g, "right")
    place(g, p, *c1)
    # Simulate two /move calls in the same window: last one wins.
    g.pending[p.id] = "up"
    g.pending[p.id] = "right"
    advance(g)  # uses g.pending
    assert p.position == c2
    assert p.motion_count == 1


def test_motion_and_life_frozen_at_death():
    g = make_game(seed=7)
    p = g.join("a")
    place(g, p, 50, 50)
    # life 1: motion_count = 49
    set_life(p, 1)
    assert p.life == 1
    advance(g, {p.id: "up"})
    assert not p.alive
    assert p.motion_count == 50          # frozen
    assert p.life == 0                   # frozen at death value


def test_current_tick_advances():
    g = make_game(seed=7)
    assert g.tick == 0
    advance(g, {})
    assert g.tick == 1
    advance(g, {})
    assert g.tick == 2
