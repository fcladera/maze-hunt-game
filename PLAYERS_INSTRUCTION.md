# Maze Game — Player Instructions

A simultaneous-turn, API-driven multiplayer arena on a 100×100 grid. You are
a single pixel. Every tick, all submitted moves resolve at once. Collect
coins to gain life, outlast or crush other players, and survive.

This document describes **only the API a player needs**. All calls are JSON
over HTTP. Replace `http://HOST:8000` with the address of your server.

---

## 1. The world

- Grid is `100×100`, indices `0..99` on each axis.
- `x` = column (→ right), `y` = row (↓ down). A position is given as `[x, y]`.
- The **border is always a wall** (`x` or `y` of `0` or `99`). The playable
  interior is `x, y ∈ 1..98`.
- Interior cells are one of: **empty**, **obstacle** (wall), a **player**, or
  a **coin**. Walls block movement.
- Diagonal moves are legal; you can "cut corners" between two obstacle cells.

## 2. Life

Your life is:

```
life = 50 + 20 × coins_captured − motion_count
```

- You start at **life 50**.
- Each **directional** move you make adds `+1` to `motion_count` (so `−1`
  life), whether or not the move is blocked by a wall.
- Each coin you capture adds `+20` life (and `+1` to `coins_captured`).
- **`stay` is free**: it does not change `motion_count` or life.
- If your life drops to `≤ 0`, you die immediately. **Death is permanent —
  you can never rejoin this round under the same name.**

## 3. Turns (ticks)

- There is a global clock that advances on a **fixed timer** (every 2 seconds
  by default). All moves submitted during one window resolve together at the
  next tick boundary.
- **Last move wins:** if you call `/move` several times before a tick, only
  the final direction is used, and only **one** motion is counted.
- If you submit nothing (or submit `stay`), you stay put for free.

## 4. Movement and collisions

When a tick resolves:

1. Every alive player's submitted move is applied (or they stay).
2. If two or more players land on the **same cell**, they collide: the one
   with the **highest life survives**, the others die. A **tie at the top
   life kills everyone** involved in that collision.
3. A player whose life drops to `≤ 0` from the motion cost dies *before*
   collisions and takes no part in them.
4. Coins are captured *after* collisions (see below).

Notes that follow from these rules:

- **Swaps are safe:** if A moves onto B's cell and B moves onto A's cell, they
  pass through each other — no collision.
- **Mover vs. stayer:** if you move into a player who is staying, you collide
  on their cell, decided by life.
- A **blocked move still costs life/motion.**

## 5. Coins

- A new coin spawns every 10 ticks (at tick 10, 20, 30, …) on a random free
  cell, up to a cap of 10 coins on the board at once.
- A coin is captured when, after collisions, **exactly one alive player** is
  on the coin's cell. That player gets `coins_captured + 1` and `+20` life.
- A contested coin (two+ players land on it) is **not** captured — and the
  colliding players may die before claiming it. Grabbing a coin while someone
  else is racing for it is risky.

---

## 6. API reference

All responses are JSON. Errors return a non-2xx status with:

```json
{ "error": "human-readable message", "code": "ERROR_CODE" }
```

Keep your `auth_key` secret — it identifies your player.

### `POST /join` — enter the round

Request body:

```json
{ "user_name": "alice" }
```

Success `200`:

```json
{
  "auth_key": "rk7abc...",
  "player_id": 3,
  "user_name": "alice",
  "current_position": [42, 17]
}
```

Save `auth_key` immediately; you need it for every other call.

Errors:

| code                | meaning                                            |
|---------------------|----------------------------------------------------|
| `INVALID_NAME`      | `user_name` missing or empty.                      |
| `ALREADY_JOINED`    | this name is already an **alive** player.          |
| `DEAD_CANNOT_REJOIN`| this name belongs to a **dead** player (permanent).|
| `NO_ROOM`           | server is full or no free cell to spawn.          |

Example:

```bash
curl -sX POST http://HOST:8000/join \
  -H 'Content-Type: application/json' \
  -d '{"user_name":"alice"}'
```

### `POST /move` — submit a move for the next tick

Request body:

```json
{ "auth_key": "rk7abc...", "direction": "up" }
```

Success `200`:

```json
{ "ok": true }
```

`direction` accepts the canonical name or any alias (case-insensitive):

| canonical    | aliases                 | delta (dx, dy) | cost  |
|--------------|-------------------------|---------------|-------|
| `up`         | `u`, `north`, `n`       | (0, -1)       | 1     |
| `down`       | `d`, `south`, `s`        | (0, +1)       | 1     |
| `left`       | `l`, `west`, `w`         | (-1, 0)       | 1     |
| `right`      | `r`, `east`, `e`         | (+1, 0)       | 1     |
| `upleft`     | `ul`, `northwest`, `nw`  | (-1, -1)      | 1     |
| `upright`    | `ur`, `northeast`, `ne`  | (+1, -1)      | 1     |
| `downleft`   | `dl`, `southwest`, `sw`  | (-1, +1)      | 1     |
| `downright`  | `dr`, `southeast`, `se`  | (+1, +1)      | 1     |
| `stay`       | `none`, `hold`, `0`      | (0, 0)        | **0** |

A directional move costs 1 motion (life −1) even if blocked. `stay` is free.
Submitting multiple times in one tick: **only the last call counts**, and it
counts as a single move (or zero if the last is `stay`).

Errors:

| code                | meaning                                  |
|---------------------|------------------------------------------|
| `INVALID_AUTH`      | unknown/invalid `auth_key`.              |
| `DEAD`              | you are dead; moves are no longer accepted.|
| `INVALID_DIRECTION`| `direction` not recognized.              |

Example:

```bash
curl -sX POST http://HOST:8000/move \
  -H 'Content-Type: application/json' \
  -d '{"auth_key":"rk7abc...","direction":"up"}'
```

### `GET /current_tick` — what tick the server is on

Query: `?auth_key=KEY`

Success `200`:

```json
{ "current_tick": 4 }
```

Use this to pace your moves against the tick timer without downloading the
full state.

Errors:

| code           | meaning                       |
|----------------|-------------------------------|
| `INVALID_AUTH` | unknown/invalid `auth_key`.   |

Example:

```bash
curl -s "http://HOST:8000/current_tick?auth_key=rk7abc..."
```

### `GET /state` — full board snapshot

Query: `?auth_key=KEY`

Success `200`:

```json
{
  "current_tick": 4,
  "you": {
    "id": 3,
    "current_position": [42, 17],
    "motion_count": 3,
    "coins_captured": 0,
    "life": 47,
    "alive": true,
    "has_pending_move": true,
    "pending_direction": "up"
  },
  "players": [
    {
      "id": 1,
      "name": "bob",
      "current_position": [10, 10],
      "motion_count": 2,
      "coins_captured": 1,
      "life": 68,
      "alive": true
    }
  ],
  "coins_uncollected_location": [[50, 50]],
  "obstacles_location": [[0, 0], [0, 1], "..."]
}
```

Field notes:

- `you` is your own status. `has_pending_move`/`pending_direction` show what
  you have queued for the next tick (`pending_direction` is `null` if you
  have nothing queued).
- `players` lists **other alive players only** — it excludes `you` and all
  dead players. Dead players never appear anywhere in the response.
- `coins_uncollected_location` is a list of `[x, y]` coin positions.
- `obstacles_location` is a list of `[x, y]` wall cells (border + radial
  lines). It can be large; cache it per round — the obstacles never move.

Errors:

| code           | meaning                       |
|----------------|-------------------------------|
| `INVALID_AUTH` | unknown/invalid `auth_key`.   |

Example:

```bash
curl -s "http://HOST:8000/state?auth_key=rk7abc..."
```

---

## 7. Minimal play loop

```text
1. POST /join            {"user_name": "alice"}        -> keep auth_key
2. GET  /state           ?auth_key=KEY                 -> learn your position
3. (every tick, before the timer fires)
     GET /current_tick   ?auth_key=KEY                 -> (optional) pace check
     ...decide a direction using /state...
     POST /move           {"auth_key":KEY, "direction": "..."}
     (you may POST /move again to change your mind; last one wins)
4. repeat 3 until you die (you.alive == false) or the round ends
```

Tips:

- You do **not** need to move every tick. `stay` (or no submission) preserves
  your life — useful when the path ahead is unsafe.
- Watch other players' `life`: avoid colliding with anyone who has higher
  life than you; seek out players with lower life.
- Coins raise your life by 20 each. Early on, grabbing coins is safer and
  more valuable than fighting.
- Submit your move a little before the tick boundary; the server does not
  wait for latecomers — whatever is queued when the timer fires is resolved.
- Once dead, that `user_name` is barred from `/join` for the rest of the
  round. Pick a new name only if the operator allows new rounds.
