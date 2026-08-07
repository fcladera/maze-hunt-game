"""Collisions: higher-life wins, tie->all die, mover-vs-stayer, exhaustion.

Critical tests #2, #3, #9, #10.
"""
import config
from helpers import (advance, find_adjacent_pair, find_collision_spot,
                      make_game, place, set_life)


def _two_movers_into_one_cell(g, life_a, life_b):
    """Place a and b so both move into a shared empty target T. Returns (a, b, T)."""
    spot = find_collision_spot(g, "right", "left")
    assert spot is not None, "no collision spot found"
    T, oa, ob = spot
    a = g.join("a"); b = g.join("b")
    place(g, a, *oa); place(g, b, *ob)
    set_life(a, life_a); set_life(b, life_b)
    return a, b, T


def test_two_movers_higher_life_survives():
    g = make_game(seed=7)
    a, b, T = _two_movers_into_one_cell(g, 60, 40)
    advance(g, {a.id: "right", b.id: "left"})
    assert a.alive and not b.alive
    assert a.position == T
    assert a.life == 59                   # 60 - 1 motion
    assert b.died_at == 1


def test_two_movers_tie_both_die():
    g = make_game(seed=7)
    a, b, T = _two_movers_into_one_cell(g, 50, 50)
    advance(g, {a.id: "right", b.id: "left"})
    assert not a.alive and not b.alive
    assert a.died_at == 1 and b.died_at == 1


def test_mover_vs_stayer_mover_wins():
    """Mover (L) into a stayer (S): L>S -> mover wins."""
    g = make_game(seed=7)
    spot = find_collision_spot(g, "right", "stay")
    assert spot is not None
    T, oa, ob = spot
    a = g.join("a"); b = g.join("b")
    place(g, a, *oa); place(g, b, *ob)    # b stays at T
    set_life(a, 60); set_life(b, 40)
    advance(g, {a.id: "right", b.id: "stay"})
    assert a.alive and not b.alive
    assert a.position == T
    assert a.life == 59


def test_mover_vs_stayer_stayer_wins():
    g = make_game(seed=7)
    spot = find_collision_spot(g, "right", "stay")
    T, oa, ob = spot
    a = g.join("a"); b = g.join("b")
    place(g, a, *oa); place(g, b, *ob)
    set_life(a, 40); set_life(b, 60)
    advance(g, {a.id: "right", b.id: "stay"})
    assert not a.alive and b.alive
    assert b.position == T
    assert b.life == 60                   # stayer pays no motion


def test_mover_vs_stayer_tie_both_die():
    g = make_game(seed=7)
    spot = find_collision_spot(g, "right", "stay")
    T, oa, ob = spot
    a = g.join("a"); b = g.join("b")
    place(g, a, *oa); place(g, b, *ob)
    set_life(a, 50); set_life(b, 51)       # after mover's -1 -> 49 vs 51? no: tie needed
    set_life(a, 51); set_life(b, 51)      # mover becomes 50 after motion, stayer 51 -> stayer wins
    # Use exact tie: both at 50 AFTER motion. mover starts 51->50, stayer stays 50.
    set_life(a, 51); set_life(b, 50)
    advance(g, {a.id: "right", b.id: "stay"})
    assert a.life == 50 and b.life == 50
    assert not a.alive and not b.alive


def test_three_way_tie_all_die():
    g = make_game(seed=7)
    from helpers import find_collision_spot, free_interior, is_free
    # Find a target T with three distinct free origins around it.
    dirs = [(1, 0), (0, 1), (-1, 0)]  # right-mover, down-mover, left-mover
    T = None; origins = None
    for (tx, ty) in free_interior(g):
        cand = [(tx - dx, ty - dy) for dx, dy in dirs]
        if len(set(cand)) == 3 and all(is_free(g, x, y) for x, y in cand):
            T = (tx, ty); origins = cand
            break
    assert T is not None
    ps = [g.join(f"p{i}") for i in range(3)]
    for p, (x, y) in zip(ps, origins):
        place(g, p, x, y); set_life(p, 50)
    advance(g, {ps[0].id: "right", ps[1].id: "down", ps[2].id: "left"})
    assert all(not p.alive for p in ps)


def test_late_joiner_vs_coin_holder_holder_lives():
    """Critical test #9: life-50 joiner vs life-70 coin-holder collide -> holder lives."""
    g = make_game(seed=7)
    spot = find_collision_spot(g, "right", "left")
    T, oa, ob = spot
    a = g.join("a"); b = g.join("b")
    place(g, a, *oa); place(g, b, *ob)
    set_life(a, 50)                       # late joiner, base life
    set_life(b, 70, coins=1)             # coin holder
    assert b.life == 70
    advance(g, {a.id: "right", b.id: "left"})
    assert not a.alive and b.alive
    assert b.position == T
    assert b.life == 69                   # 70 - 1 motion


def test_exhaustion_dies_pre_collision():
    """Critical test #10: life-1 mover dies before colliding; doesn't engage."""
    g = make_game(seed=7)
    spot = find_collision_spot(g, "right", "left")
    T, oa, ob = spot
    a = g.join("a"); b = g.join("b")
    place(g, a, *oa); place(g, b, *ob)
    set_life(a, 1)                        # mover, will drop to 0 -> die pre-collision
    set_life(b, 50)
    advance(g, {a.id: "right", b.id: "left"})
    assert not a.alive                    # died of exhaustion
    assert b.alive                        # no collision occurred
    assert b.position == T               # b moved unopposed
    assert a.died_at == 1


def test_exhaustion_vacates_origin():
    """An exhausted mover's origin is free for another to move into."""
    g = make_game(seed=7)
    pair = find_adjacent_pair(g, "right")
    c1, c2 = pair
    a = g.join("a"); b = g.join("b")
    place(g, a, *c1)                      # a at c1, will die moving right to c2
    place(g, b, *c2)                      # b at c2 will move left into c1 (a's origin)
    set_life(a, 1)                        # dies moving right (life -> 0)
    set_life(b, 50)
    advance(g, {a.id: "right", b.id: "left"})
    assert not a.alive
    assert b.alive
    assert b.position == c1              # moved into a's vacated origin


def test_blocked_mover_collides_with_stayer():
    """A mover blocked by a wall stays put and can still collide with a stayer there."""
    from helpers import find_blocked_origin
    g = make_game(seed=7)
    origin = find_blocked_origin(g, "right")
    a = g.join("a"); b = g.join("b")
    place(g, a, *origin)
    place(g, b, *origin)                 # same cell -> not physical, but tests grouping
    set_life(a, 60); set_life(b, 40)
    advance(g, {a.id: "right", b.id: "stay"})
    # a's target == origin (blocked), b stays at origin -> collide on origin
    assert a.alive and not b.alive
    assert a.position == origin
