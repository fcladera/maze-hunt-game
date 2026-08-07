"""Shared pytest config: pin deterministic defaults and provide fixtures.

Config is pinned here (ignoring any MG_* env overrides) so the suite is
reproducible regardless of the host environment.
"""
import pytest

import config

# --- Pin deterministic defaults ---
config.GRID_SIZE = 100
config.BASE_LIFE = 50
config.COIN_LIFE_BONUS = 20
config.COIN_INTERVAL = 10
config.MAX_COINS = 10
config.TICK_INTERVAL = 2.0
config.NUM_LINES = 16
config.MIN_LINE_LEN = 15
config.MAX_LINE_LEN = 45
config.MAX_GEN_ATTEMPTS = 200
config.MAX_PLAYERS = 100


@pytest.fixture
def game():
    """A fresh GameState on a fixed seed (unit tests drive it directly)."""
    from helpers import make_game
    return make_game(seed=7)


@pytest.fixture
def client(monkeypatch):
    """FastAPI TestClient with the tick loop disabled (deterministic ticks).

    Each test gets a fresh world. Tests advance ticks manually via
    helpers.advance(main.game).
    """
    import game as game_mod
    import main

    async def _noop_loop(self):
        return None

    monkeypatch.setattr(game_mod.GameState, "run_tick_loop", _noop_loop)
    main.game = game_mod.GameState(seed=7)

    from fastapi.testclient import TestClient

    with TestClient(main.app) as c:
        yield c
