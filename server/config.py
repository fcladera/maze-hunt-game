"""Constants and environment overrides for the maze game server."""
import os


def _int(name, default):
    try:
        return int(os.environ[name])
    except (KeyError, ValueError):
        return default


def _float(name, default):
    try:
        return float(os.environ[name])
    except (KeyError, ValueError):
        return default


# Grid / life
GRID_SIZE = _int("MG_GRID_SIZE", 100)
BASE_LIFE = _int("MG_BASE_LIFE", 50)
COIN_LIFE_BONUS = _int("MG_COIN_LIFE_BONUS", 20)

# Coins
COIN_INTERVAL = _int("MG_COIN_INTERVAL", 10)
MAX_COINS = _int("MG_MAX_COINS", 10)

# Ticks
TICK_INTERVAL = _float("MG_TICK_INTERVAL", 2.0)

# Obstacle generation
NUM_LINES = _int("MG_NUM_LINES", 16)
MIN_LINE_LEN = _int("MG_MIN_LINE_LEN", 15)
MAX_LINE_LEN = _int("MG_MAX_LINE_LEN", 45)
MAX_GEN_ATTEMPTS = _int("MG_MAX_GEN_ATTEMPTS", 200)

# Players
MAX_PLAYERS = _int("MG_MAX_PLAYERS", 100)

# Shared secret for read-only spectator access to the public board state.
# When set, /view?viewer_key=... returns all alive players (no per-player
# auth_key needed). When unset, viewer access is disabled.
VIEWER_KEY = os.environ.get("MG_VIEWER_KEY", "")

# Optional fixed obstacle-generation seed (for reproducibility).
_raw_seed = os.environ.get("MG_GEN_SEED")
GEN_SEED = None
if _raw_seed:
    try:
        GEN_SEED = int(_raw_seed)
    except ValueError:
        GEN_SEED = None

# Cell values for the uint8 world map.
EMPTY = 0
OBSTACLE = 1
PLAYER = 2
COIN = 3
