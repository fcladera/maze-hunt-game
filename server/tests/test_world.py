"""World generation: border, radial lines, 8-connectivity, carve fallback.

Critical tests #1 (and the carve fallback, §3.3).
"""
import numpy as np
from scipy.ndimage import label

import config
from world import generate_world

STRUCTURE = np.ones((3, 3), dtype=int)


def n_components(grid):
    obs = grid == config.OBSTACLE
    _, n = label(~obs, structure=STRUCTURE)
    return n


def test_border_is_fully_walled():
    g, s, c = generate_world(seed=123)
    assert bool(g[0, :].all())
    assert bool(g[-1, :].all())
    assert bool(g[:, 0].all())
    assert bool(g[:, -1].all())
    # Corners too.
    assert g[0, 0] == config.OBSTACLE
    assert g[-1, -1] == config.OBSTACLE


def test_single_8_connected_component():
    g, s, c = generate_world(seed=123)
    assert n_components(g) == 1


def test_many_worlds_are_connected():
    fails = 0
    for _ in range(40):
        g, s, c = generate_world()
        if n_components(g) != 1:
            fails += 1
    assert fails == 0


def test_has_radial_lines_interior():
    """Beyond the border, there must be some interior obstacles (the spokes)."""
    g, s, c = generate_world(seed=123)
    interior = g[1:-1, 1:-1]
    assert int((interior == config.OBSTACLE).sum()) > 0


def test_8_conn_not_4_conn_diagonal_link_counts():
    """A diagonal-only connection must count as connected (8-connectivity)."""
    grid = np.zeros((10, 10), dtype=np.uint8)
    grid[0, :] = 1
    grid[-1, :] = 1
    grid[:, 0] = 1
    grid[:, -1] = 1
    # Two free regions touching only at a corner (diagonal contact, no edge
    # contact). Build it as a checkerboard bridge across a vertical wall.
    for y in range(1, 9):
        grid[y, 5] = 1
    # Only crossing: (4,4)-(5,5) diagonal. Block the edge-adjacent alternates.
    grid[4, 4] = 0   # left opening (row 4)
    grid[5, 5] = 0   # right opening (row 5)
    grid[4, 5] = 1   # wall between them on row 4
    grid[5, 4] = 1   # wall between them on row 5
    # 4-conn: left and right touch only at the (4,4)/(5,5) corner -> 2 comps
    _, n4 = label(grid == 0, structure=np.array([[0, 1, 0], [1, 1, 1], [0, 1, 0]]))
    # 8-conn: one component via the diagonal
    _, n8 = label(grid == 0, structure=STRUCTURE)
    assert n8 == 1
    assert n4 == 2  # confirms 8-conn is the correct, stricter choice


def test_carve_keeps_border_and_connects():
    """Force disconnection so the carve fallback runs; border must stay walled."""
    import world
    # Small grid, many long lines -> very likely disconnected before carve.
    saved = (config.GRID_SIZE, config.NUM_LINES, config.MIN_LINE_LEN,
             config.MAX_LINE_LEN, config.MAX_GEN_ATTEMPTS)
    config.GRID_SIZE = 25
    config.NUM_LINES = 60
    config.MIN_LINE_LEN = 8
    config.MAX_LINE_LEN = 12
    config.MAX_GEN_ATTEMPTS = 5
    try:
        g, s, carved = generate_world()
        assert bool(g[0, :].all()) and bool(g[-1, :].all())
        assert bool(g[:, 0].all()) and bool(g[:, -1].all())
        assert n_components(g) == 1
    finally:
        (config.GRID_SIZE, config.NUM_LINES, config.MIN_LINE_LEN,
         config.MAX_LINE_LEN, config.MAX_GEN_ATTEMPTS) = saved


def test_carve_isolates_interior_pocket():
    """A fully walled interior pocket is carved open without touching the border."""
    import world
    g = np.zeros((20, 20), dtype=np.uint8)
    g[0, :] = 1; g[-1, :] = 1; g[:, 0] = 1; g[:, -1] = 1
    for i in range(7, 14):
        g[7, i] = 1; g[13, i] = 1; g[i, 7] = 1; g[i, 13] = 1
    assert world._component_count(g) == 2
    world._carve(g, 20)
    assert world._component_count(g) == 1
    assert bool(g[0, :].all()) and bool(g[-1, :].all())
    assert bool(g[:, 0].all()) and bool(g[:, -1].all())


def test_gen_seed_returned_and_reproducible():
    # A seed that connects on the first attempt is returned unchanged.
    g0, s0, c0 = generate_world(seed=229)
    assert s0 == 229 and c0 is False
    # Any seed (even one needing retries) is reproducible: same seed -> same world.
    g1, s1, _ = generate_world(seed=999)
    g2, s2, _ = generate_world(seed=999)
    assert s1 == s2
    assert np.array_equal(g1, g2)


def test_map_values_are_only_empty_or_obstacle():
    g, s, c = generate_world(seed=123)
    vals = set(np.unique(g).tolist())
    assert vals <= {config.EMPTY, config.OBSTACLE}
