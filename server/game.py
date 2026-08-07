"""GameState, Player, tick loop, and collision/coin resolution (in-memory)."""
import asyncio
import secrets
from collections import defaultdict

import numpy as np

import api
import config
from coins import spawn_coin
from world import generate_world, obstacle_locations

# Canonical directions -> (dx, dy).
DIRS = {
    "up": (0, -1),
    "down": (0, +1),
    "left": (-1, 0),
    "right": (+1, 0),
    "upleft": (-1, -1),
    "upright": (+1, -1),
    "downleft": (-1, +1),
    "downright": (+1, +1),
    "stay": (0, 0),
}

# Alias -> canonical direction.
_ALIASES = {
    "u": "up", "north": "up", "n": "up",
    "d": "down", "south": "down", "s": "down",
    "l": "left", "west": "left", "w": "left",
    "r": "right", "east": "right", "e": "right",
    "ul": "upleft", "northwest": "upleft", "nw": "upleft",
    "ur": "upright", "northeast": "upright", "ne": "upright",
    "dl": "downleft", "southwest": "downleft", "sw": "downleft",
    "dr": "downright", "southeast": "downright", "se": "downright",
    "none": "stay", "hold": "stay", "0": "stay",
}
for _d in DIRS:
    _ALIASES[_d] = _d


def parse_direction(raw):
    """Normalize a direction/alias to a canonical name, or None if invalid."""
    if not isinstance(raw, str):
        return None
    return _ALIASES.get(raw.strip().lower())


class Player:
    __slots__ = (
        "id", "user_name", "auth_key", "position",
        "motion_count", "coins_captured", "alive", "died_at", "joined_at",
    )

    def __init__(self, pid, user_name, auth_key, position, joined_at):
        self.id = pid
        self.user_name = user_name
        self.auth_key = auth_key
        self.position = position            # (x, y)
        self.motion_count = 0
        self.coins_captured = 0
        self.alive = True
        self.died_at = None
        self.joined_at = joined_at

    @property
    def life(self):
        return config.BASE_LIFE + config.COIN_LIFE_BONUS * self.coins_captured - self.motion_count


class GameState:
    def __init__(self, seed=None):
        map_grid, gen_seed, carved = generate_world(seed)
        self.map_grid = map_grid
        self.obstacle_grid = map_grid == config.OBSTACLE
        self.gen_seed = gen_seed
        self.carved = carved
        self.obstacles_location = obstacle_locations(map_grid)

        self.tick = 0
        self.coins_uncollected = []          # list of (x, y)
        self.players = {}                    # player_id -> Player
        self.name_to_id = {}                 # user_name -> player_id
        self.auth_to_id = {}                 # auth_key -> player_id
        self.pending = {}                    # player_id -> canonical direction
        self.pending_lock = asyncio.Lock()
        self.history = []
        self._next_id = 1
        self.rng = np.random.default_rng(gen_seed)

        self.history.append(self._snapshot())

    # --- joining / spawning -----------------------------------------------
    def join(self, user_name):
        if not isinstance(user_name, str) or not user_name.strip():
            raise api.GameError(api.INVALID_NAME, "user_name must be a non-empty string", 400)
        name = user_name.strip()

        if name in self.name_to_id:
            pid = self.name_to_id[name]
            p = self.players[pid]
            if p.alive:
                raise api.GameError(api.ALREADY_JOINED, f"{name} already joined", 409)
            raise api.GameError(api.DEAD_CANNOT_REJOIN, f"{name} is dead and cannot rejoin", 403)

        alive_count = sum(1 for p in self.players.values() if p.alive)
        if alive_count >= config.MAX_PLAYERS:
            raise api.GameError(api.NO_ROOM, "server is full", 409)

        pos = self._free_spawn_cell()
        if pos is None:
            raise api.GameError(api.NO_ROOM, "no free cell to spawn", 409)

        pid = self._next_id
        self._next_id += 1
        auth_key = secrets.token_urlsafe(12)
        p = Player(pid, name, auth_key, pos, self.tick)
        self.players[pid] = p
        self.name_to_id[name] = pid
        self.auth_to_id[auth_key] = pid
        return p

    def _free_spawn_cell(self):
        blocked = self.obstacle_grid.copy()
        for p in self.players.values():
            if p.alive:
                x, y = p.position
                blocked[y, x] = True
        for (x, y) in self.coins_uncollected:
            blocked[y, x] = True
        free_ys, free_xs = np.where(~blocked)
        if free_ys.size == 0:
            return None
        idx = int(self.rng.integers(0, free_ys.size))
        return (int(free_xs[idx]), int(free_ys[idx]))

    # --- move submission (HTTP side, under lock) --------------------------
    async def submit_move(self, auth_key, direction_raw):
        pid = self.auth_to_id.get(auth_key)
        if pid is None:
            raise api.GameError(api.INVALID_AUTH, "invalid auth_key", 401)
        p = self.players[pid]
        if not p.alive:
            raise api.GameError(api.DEAD, "player is dead", 403)
        d = parse_direction(direction_raw)
        if d is None:
            raise api.GameError(api.INVALID_DIRECTION, "invalid direction", 400)
        async with self.pending_lock:
            self.pending[pid] = d
        return True

    def pending_info(self, pid):
        """Snapshot of a player's queued move (atomic dict read)."""
        pd = self.pending.get(pid)
        return pd

    # --- reads for /state and /current_tick -------------------------------
    def _public_players(self):
        """All alive players as public dicts (no auth secrets)."""
        out = []
        for op in self.players.values():
            if not op.alive:
                continue
            out.append({
                "id": op.id,
                "name": op.user_name,
                "current_position": [op.position[0], op.position[1]],
                "motion_count": op.motion_count,
                "coins_captured": op.coins_captured,
                "life": op.life,
                "alive": True,
            })
        return out

    def state_public(self):
        """Full public board state (no per-player auth_key required).

        Used by the spectator/GUI endpoint. Lists every alive player (the
        per-player /state excludes `you` and the dead); here there is no `you`,
        so all alive players are returned.
        """
        return {
            "current_tick": self.tick,
            "players": self._public_players(),
            "coins_uncollected_location": [[x, y] for (x, y) in self.coins_uncollected],
            "obstacles_location": self.obstacles_location,
        }

    def current_tick_for(self, auth_key):
        if self.auth_to_id.get(auth_key) is None:
            raise api.GameError(api.INVALID_AUTH, "invalid auth_key", 401)
        return {"current_tick": self.tick}

    def state_for(self, auth_key):
        pid = self.auth_to_id.get(auth_key)
        if pid is None:
            raise api.GameError(api.INVALID_AUTH, "invalid auth_key", 401)
        p = self.players[pid]
        pd = self.pending.get(pid)

        you = {
            "id": p.id,
            "current_position": [p.position[0], p.position[1]],
            "motion_count": p.motion_count,
            "coins_captured": p.coins_captured,
            "life": p.life,
            "alive": p.alive,
            "has_pending_move": pd is not None,
            "pending_direction": pd,
        }

        players = []
        for oid, op in self.players.items():
            if oid == pid or not op.alive:
                continue
            players.append({
                "id": op.id,
                "name": op.user_name,
                "current_position": [op.position[0], op.position[1]],
                "motion_count": op.motion_count,
                "coins_captured": op.coins_captured,
                "life": op.life,
                "alive": True,
            })

        return {
            "current_tick": self.tick,
            "you": you,
            "players": players,
            "coins_uncollected_location": [[x, y] for (x, y) in self.coins_uncollected],
            "obstacles_location": self.obstacles_location,
        }

    # --- tick resolution --------------------------------------------------
    def resolve_tick(self, pending):
        """Advance state T -> T+1 using a local snapshot of pending moves."""
        T = self.tick
        players = self.players
        n = config.GRID_SIZE

        # 1. Effective targets + motion/life cost for directional moves.
        targets = {}
        for pid, p in players.items():
            if not p.alive:
                continue
            d = pending.get(pid)
            if d is None or d == "stay":
                targets[pid] = p.position
                continue
            p.motion_count += 1
            dx, dy = DIRS[d]
            x, y = p.position
            nx, ny = x + dx, y + dy
            if not (0 <= nx < n and 0 <= ny < n) or self.obstacle_grid[ny, nx]:
                targets[pid] = p.position   # blocked -> stay in place (but counted)
            else:
                targets[pid] = (nx, ny)

        # 2. Exhaustion: life <= 0 from the move -> die before collisions.
        for pid in list(targets):
            if players[pid].life <= 0:
                players[pid].alive = False
                players[pid].died_at = T + 1
                del targets[pid]

        # 3. Group survivors by target cell.
        groups = defaultdict(list)
        for pid, cell in targets.items():
            groups[cell].append(pid)

        # 4. Collisions: highest life wins; tie at max -> all die.
        deaths = []
        survivors = set()
        for cell, pids in groups.items():
            if len(pids) == 1:
                survivors.add(pids[0])
            else:
                lives = {pid: players[pid].life for pid in pids}
                m = max(lives.values())
                winners = [pid for pid, l in lives.items() if l == m]
                if len(winners) == 1:
                    survivors.add(winners[0])
                    deaths.extend(pid for pid in pids if pid != winners[0])
                else:
                    deaths.extend(pids)

        # 5. Apply deaths and movement.
        for pid in deaths:
            players[pid].alive = False
            players[pid].died_at = T + 1
        for pid in survivors:
            players[pid].position = targets[pid]

        # 6. Coin capture (post-collision): exactly one alive player on a coin.
        for coin in list(self.coins_uncollected):
            occupants = [pid for pid in survivors if targets[pid] == coin]
            if len(occupants) == 1:
                pid = occupants[0]
                players[pid].coins_captured += 1
                self.coins_uncollected.remove(coin)

        # 7. Advance clock, spawn coins, snapshot.
        self.tick = T + 1
        if (self.tick > 0 and self.tick % config.COIN_INTERVAL == 0
                and len(self.coins_uncollected) < config.MAX_COINS):
            spawn_coin(self)
        self.history.append(self._snapshot())

    def _snapshot(self):
        return {
            "tick": self.tick,
            "players": {
                pid: {
                    "pos": p.position,
                    "life": p.life,
                    "coins": p.coins_captured,
                    "motion": p.motion_count,
                    "alive": p.alive,
                }
                for pid, p in self.players.items()
            },
            "coins": list(self.coins_uncollected),
        }

    # --- tick loop (fixed timer only) -------------------------------------
    async def run_tick_loop(self):
        while True:
            await asyncio.sleep(config.TICK_INTERVAL)
            async with self.pending_lock:
                local = self.pending
                self.pending = {}
            # Resolution is synchronous: no HTTP handler interleaves with it.
            self.resolve_tick(local)
