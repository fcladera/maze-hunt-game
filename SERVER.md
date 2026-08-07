# SERVER.md — Game Engine Strategy & Design

A simultaneous-turn, API-driven multiplayer arena on a 100×100 grid. The
border is a wall; obstacle lines radiate from the walls toward the center.
Players are single pixels. Each tick all submitted moves resolve at once.
Collisions are decided by **life** (higher survives), where
`life = BASE_LIFE + 20·coins_captured − motion_count` (players start with **base life
`BASE_LIFE = 50`**). Coins spawn every 10 ticks (T=10, 20, 30, …) and grant
+20 life.

---

## 1. Coordinate system, directions, life

- Grid `100×100`, indices `0..99` on each axis.
- `x` = column (→ right), `y` = row (↓ down).
- **Border is always wall**: every cell with `x∈{0,99}` or `y∈{0,99}` is an
  obstacle. Playable interior is `x,y ∈ 1..98` (98×98 = 9604 cells).
- Interior cells are: **empty**, **obstacle** (wall), a **player**, or a
  **coin**. After tick resolution no two players share a cell. If there is a
player collision, only the player who lives keeps the cell.
- Out-of-bounds is wall (already covered by the border, but the rule is
  general).

Directions → delta `(dx, dy)`:

| direction    | aliases                 | dx | dy | cost |
|--------------|-------------------------|----|----|------|
| `up`         | `u`, `north`, `n`       |  0 | -1 | 1 motion |
| `down`       | `d`, `south`, `s`       |  0 | +1 | 1 motion |
| `left`       | `l`, `west`, `w`        | -1 |  0 | 1 motion |
| `right`      | `r`, `east`, `e`        | +1 |  0 | 1 motion |
| `upleft`     | `ul`, `northwest`, `nw` | -1 | -1 | 1 motion |
| `upright`    | `ur`, `northeast`, `ne` | +1 | -1 | 1 motion |
| `downleft`   | `dl`, `southwest`, `sw` | -1 | +1 | 1 motion |
| `downright`  | `dr`, `southeast`, `se` | +1 | +1 | 1 motion |
| `stay`       | `none`, `hold`, `0`     |  0 |  0 | **0 (free)** |

**`stay` is free** (change #1): it neither increments `motion_count` nor
changes life — equivalent to not submitting a move. A directional move that is
blocked by a wall still costs  +1 motion.

---

## 2. World model

The world is represented by a single 100x100 array, uint8. Each cell can be
 - 0: empty
 - 1: obstacle
 - 2: player
 - 3: coin

```
GameState (singleton, in-memory)
├── config            # constants (sizes, intervals, coin ticks, flags)
├── tick              # current resolved time T (starts at 0)
├── coins_uncollected # list<(x,y)> of uncollected coins currently on the board
├── players           # map<player_id, Player>
├── name_to_id        # map<user_name, player_id>
├── pending           # map<player_id, direction>  # queued moves for next tick
├── history           # list<Snapshot>             # per-tick state 
└── gen_seed          # obstacle-generation seed (logged for reproducibility)

Player
├── id, user_name, auth_key
├── position (x,y)
├── motion_count      # total directional moves processed (original spec metric)
├── coins_captured    # number of coins captured
├── alive (bool), died_at (tick | None)
├── joined_at (tick)
```

`life` is computed from `coins_captured` and `motion_count`, so we store the latter two.


---

## 3. Obstacle generation (changes #2, #3, #4)

### 3.1 Border wall (change #2)
Set every border cell (`x=0`, `x=99`, `y=0`, `y=99`) as obstacle. These are
permanent for the round.

### 3.2 Radial lines (change #3)
Generate `NUM_LINES` lines (default 16, configurable). For each line:
1. Pick a side uniformly: top / bottom / left / right.
2. Pick a starting coordinate along that side in `1..98` (interior range; the
   border cell itself is already wall).
3. Pick a length `L` in `[MIN_LINE_LEN, MAX_LINE_LEN]` (default `[15, 45]`).
4. Draw the line perpendicular to the wall, inward, for `L` cells.

This yields "spokes" radiating from the perimeter toward — but stopping short
of — the center (row/col ~49), leaving an open central band. "As far as the
middle" is interpreted as *up to the middle* (lines reach near it, not past
it); the open center keeps corridors connected.

### 3.3 Connectivity check (change #4)
After creating the uint8 map array and placing the border + lines, create a
boolean obstacle_grid array (where map == 1). Then run:

```python
from scipy.ndimage import label
structure = np.ones((3, 3))          # 8-connectivity (see note)
labeled, n = label(~obstacle_grid, structure=structure)
connected = (n == 1)
```

**8-connectivity is used** because diagonal moves are legal (there is no
corner-cutting restriction in the spec), so two free cells touching only at a
corner *are* mutually reachable. Using the default 4-connectivity of
`scipy.ndimage.label` would falsely flag diagonal-only links as isolated.

If `n != 1` (isolated regions exist):
1. **Retry** generation with a fresh random seed/params up to
   `MAX_GEN_ATTEMPTS` (default 200). Accept the first fully-connected layout.
2. If still disconnected after all attempts, **carve** minimal passages: take
   the largest component as the main region; for each other component, remove
   the single obstacle cell on the shortest path (BFS through obstacles) to
   the main region; re-run the label check; repeat until `n == 1`.
3. Log the final `gen_seed` and whether carving was needed.

Guarantee: the playable region is always a single connected component at
round start, so every free cell is reachable from every other.

---

## 4. Coins

- `COIN_INTERVAL = 10`. When the tick advances **into** a value
  `T` with `T > 0 and T % COIN_INTERVAL == 0`, spawn one coin on a random
  **free** interior cell (non-obstacle, not currently occupied by a player, not
  already a coin). If no such cell exists, skip.
- A coin persists until captured. Coins accumulate over time; to bound board
  clutter, `MAX_COINS` (default 10) caps simultaneous coins — skip spawning
  while at the cap.
- **Capture**: after movement + collision resolution each tick, for each coin
  whose cell is occupied by exactly **one alive player**, that player captures
  it: `coins_captured += 1`, coin removed. If the cell is empty or was
  a collision site with no single survivor (tie → all dead), the coin remains.

---

## 5. Time model (ticks)

Discrete global clock `T`. State at `T` is fully resolved and immutable. Moves
submitted during the window after `T` are queued in `pending` and all resolve
at the tick boundary, producing state `T+1`.

The tick advances on a **fixed timer only**: every `TICK_INTERVAL` seconds
(default 2.0 s).

Players who submit nothing (or submit `stay`) stay put for free (no motion,
no life change). Submitting multiple `/move` calls in one tick: **the last one
wins**; only **one** motion is counted for that tick (and only if the final
direction is not `stay`). `/state` returns the latest resolved state `T`.

After each resolution, if the new `tick` is a coin tick (`tick > 0 and
tick % COIN_INTERVAL == 0`) and below `MAX_COINS`, spawn a coin (§4).

---

## 6. Tick resolution algorithm (T → T+1)

```
resolve_tick():
  T = game.tick

  # 1. Compute effective targets and apply motion/life costs.
  targets = {}                                  # player_id -> (x,y)
  for p in alive(players):
      d = pending.get(p.id)
      if d is None or d == "stay":               # no move or explicit stay: FREE
          targets[p.id] = p.position              # no motion_count++, no life--
          continue
      p.motion_count += 1                        # a directional move always counts
      # life = BASE_LIFE + 20*coins_captured - motion_count  => -1 from this move
      (nx, ny) = p.position + delta(d)
      if not in_bounds(nx,ny) or obstacle_grid[nx,ny]:
          targets[p.id] = p.position              # blocked -> stay (but counted, D4)
      else:
          targets[p.id] = (nx, ny)

  # 2. Group players by the cell they effectively end on.
  groups = defaultdict(list)                     # (x,y) -> [player_id,...]
  for pid, cell in targets.items():
      groups[cell].append(pid)

  # 3. Resolve collisions by LIFE (higher survives; tie -> all die).
  deaths = []
  survivors = set()
  for cell, pids in groups.items():
      if len(pids) == 1:
          survivors.add(pids[0])
      else:
          lives = {pid: players[pid].life for pid in pids}   # life already reflects this tick's move
          m = max(lives.values())
          winners = [pid for pid, l in lives.items() if l == m]
          if len(winners) == 1:
              survivors.add(winners[0])
              deaths += [pid for pid in pids if pid != winners[0]]
          else:                                  # tie at the max life -> all die 
              deaths += pids

  # 4. Apply deaths and movement.
  for pid in deaths:
      players[pid].alive = False
      players[pid].died_at = T + 1
  for pid in survivors:
      players[pid].position = targets[pid]

  # 5. Coin capture (after collisions).
  for coin in list(game.coins_uncollected):
      occupants = [pid for pid in survivors if targets[pid] == coin]
      if len(occupants) == 1:                    # exactly one alive player on the coin
          pid = occupants[0]
          players[pid].coins_captured += 1                # => life += 20
          game.coins_uncollected.remove(coin)

  # 6. Advance clock, spawn coins, snapshot.
  game.tick = T + 1
  if game.tick > 0 and game.tick % COIN_INTERVAL == 0 and len(game.coins_uncollected) < MAX_COINS:
      spawn_coin()                               # random free cell, §4
  history.append(snapshot())
  pending.clear()
```

Properties:
- **Simultaneous / order-free**: all moves use state at `T`.
- **Swaps are safe**: A at C1→C2 and B at C2→C1 land on distinct cells → no
  collision; they pass through each other.
- **Mover vs stayer collide** on the stayer's cell, resolved by life.
- **Dead players vacate their origin**, so others may move into it.
- **Blocked moves still cost life/motion**.
- **Coin capture is post-collision**: grabbing a contested coin risks
  dying before you can claim it; the +20 aids future fights.

---

## 7. Motion count & life semantics

- `motion_count` = number of ticks in which a **directional** move was
  processed (up/down/left/right/diagonal), whether or not it displaced the
  player. Blocked moves count. `stay` and "no submission" do **not** count.
- Both `motion_count` (original history) and `life` are frozen at death.
- If a player reaches 0 life, it is also dead.

---

## 8. API contract

All JSON over HTTP. Errors: non-2xx + `{"error": "...", "code": "..."}`.

### `POST /join`
Request: `{"user_name": "alice"}`
Response 200:
```json
{
  "auth_key": "rk7...",
  "player_id": 3,
  "user_name": "alice",
  "current_position": [42, 17],
}
```
Errors: `NO_ROOM`, `ALREADY_JOINED`, `INVALID_NAME`.

### `POST /move`
Request: `{"auth_key": "rk7...", "direction": "up"}`
Response 200:
```json
{
  "ok": true,
}
```
Errors: `INVALID_AUTH`, `DEAD`, `INVALID_DIRECTION`,

### `GET /current_tick?auth_key=KEY`
Response 200:
```json
{
  "current_tick": 4,
}
Errors: `INVALID_AUTH`

### `GET /state?auth_key=KEY`
Response 200:
```json
{
  "current_tick": 4,
  "you": { "id": 3, "current_position": [42,17], "motion_count": 3,
           "coins_captured": 0, "life": 47, "alive": true,
           "has_pending_move": true, "pending_direction": "up" },
  "players": [
    {"id": 1, "name": "bob",  "current_position": [10,10], "motion_count": 2,
     "coins_captured": 1, "life": 68, "alive": true}
  ],
  "coins_uncollected_location": [[50, 50]],
  "obstacles_location": [[0,0], "..."],
}
```
Errors: `INVALID_AUTH`

---

## 9. Concurrency & fairness

- One writer (the tick loop) mutates state; HTTP handlers read resolved state
  and append to `pending` under a lock.
- `pending` writes are mutex-guarded; the tick loop swaps it atomically to a
  local map before resolving, so submission and resolution never race.
- The tick loop is driven by a **fixed timer only**: every `TICK_INTERVAL` seconds it advances. Move submission is
  best-effort within the window; the last move a player submits before the
  boundary is the one resolved. The tick loop waits on a timer condition; no
  early wake-up.

---

## 10. Recommended stack & layout

- **Stack:** Python 3 + FastAPI + uvicorn, **numpy + scipy** (connectivity),
  in-memory, no DB. Single worker; tick loop as an asyncio task.
- Process target: <100 players

```
server/
├── main.py          # FastAPI app, endpoints, startup (tick loop)
├── game.py          # GameState, Player, tick loop, collision/coin resolver
├── world.py         # border + radial-line generation, connectivity check, spawn
├── coins.py         # coin spawn + capture logic (small; could fold into game.py)
├── config.py        # constants + env overrides
├── api.py           # request/response schemas (pydantic), error codes
└── tests/
    ├── test_world.py        # border, lines, 8-conn connectivity, carve fallback
    ├── test_tick.py         # simultaneous moves, swaps, blocked, bounds, stay free
    ├── test_collisions.py   # higher-life wins, tie->all die, mover-vs-stayer
    ├── test_coins.py         # spawn every 10 ticks, capture post-collision, +20 life
    └── test_api.py          # join/move/state flows, death, rejoin, coin in state
```

Critical unit tests (must pass before shipping):
1. Border is fully walled; interior lines radiate; free region is one
   8-connected component (assert `label(...) == 1`).
2. Two movers into one empty cell → higher life survives; tie → both die.
3. Mover (life L) into a stayer (life S): if L>S mover wins, if L<S stayer
   wins, if L==S both die.
4. Swap (A↔B) → both move, no death.
5. Move into wall/border → stay in place, `motion_count+1`, `life−1`.
6. `stay` and no-submit → position unchanged, `motion_count` and `life`
   unchanged.
7. Dead player's `/move` → `DEAD`, no state change.
8. Coins spawn every 10 ticks (T=10,20,30,…) on a free cell up to `MAX_COINS`;
   capturing one → `coins_captured+1`, coin removed; post-collision capture
   only (contested coin not duplicated).
9. Late joiner (life 50) vs coin-holder (life 70) collide → coin-holder lives.
