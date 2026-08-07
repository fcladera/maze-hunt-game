# Maze Game Server

Simultaneous-turn, API-driven multiplayer arena on an 80x80 grid.
See `../SERVER.md` for the full specification.

## Run

```bash
cd server
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000
```

Then open the web GUI at <http://localhost:8000/gui>.
If `MG_VIEWER_KEY` is not set, the server logs an auto-generated spectator
key on startup — paste it into the GUI's "Viewer key" field to see the
board (or set `MG_VIEWER_KEY` to pin it).

## Endpoints

| Method | Path                          | Body / query                         |
|--------|-------------------------------|--------------------------------------|
| POST   | `/join`                       | `{"user_name": "alice"}`             |
| POST   | `/move`                       | `{"auth_key": "...", "direction": "up"}` |
| GET    | `/current_tick?auth_key=KEY`  |                                      |
| GET    | `/state?auth_key=KEY`         |                                      |
| GET    | `/health`                     |                                      |
| GET    | `/view?viewer_key=KEY`        | read-only full board (spectator)     |
| GET    | `/view_tick?viewer_key=KEY`   | read-only tick counter               |
| GET    | `/gui`                        | web GUI (`index.html`)               |

Errors are non-2xx with `{"error": "...", "code": "..."}`.

## Configuration (env overrides)

| Var                 | Default | Meaning                              |
|---------------------|---------|--------------------------------------|
| `MG_GRID_SIZE`      | 80      | grid edge length                     |
| `MG_BASE_LIFE`      | 50      | starting life                        |
| `MG_COIN_LIFE_BONUS`| 20      | life granted per captured coin       |
| `MG_COIN_INTERVAL`  | 10      | spawn a coin every N ticks           |
| `MG_MAX_COINS`      | 10      | cap on simultaneous coins            |
| `MG_TICK_INTERVAL`  | 2.0     | seconds per tick                     |
| `MG_NUM_LINES`      | 16      | radial obstacle lines                |
| `MG_MIN_LINE_LEN`   | 12      | min line length                      |
| `MG_MAX_LINE_LEN`   | 36      | max line length                      |
| `MG_MAX_GEN_ATTEMPTS`| 200    | connectivity retry attempts          |
| `MG_MAX_PLAYERS`    | 100     | max alive players                    |
| `MG_GEN_SEED`       | random  | fixed obstacle-generation seed      |
| `MG_VIEWER_KEY`     | auto    | spectator secret for `/view` (auto-generated if unset, logged on startup) |

## Layout

```
main.py     FastAPI app, endpoints, startup tick loop, error mapping
game.py     GameState, Player, tick loop, collision/coin resolution
world.py    border + radial-line generation, 8-conn connectivity, carve
coins.py    coin spawn logic
config.py   constants + env overrides
api.py      pydantic request schemas + error codes
gui/        web GUI (index.html, style.css, app.js) served at /gui
tests/      pytest suite (world, tick, collisions, coins, api, view)
```

## Tests

```bash
cd server
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/python -m pytest
```

The suite covers all 11 critical tests from `../SERVER.md` plus extra edge
cases (direction aliases, last-move-wins, three-way ties, exhaustion vacating
an origin, blocked-mover collisions, no-room spawn, API auth/shape checks).
Tests pin deterministic config and drive the engine directly
(`game.resolve_tick`) or via FastAPI's `TestClient` with the tick loop stubbed.

## Web GUI

`/gui` serves a single-page **spectator** client (`server/gui/index.html`)
that renders the 80x80 board on a canvas by polling
`/view?viewer_key=...` (read-only, all alive players / coins / obstacles, no
per-player auth needed). Players are drawn as bigger triangles, each in a
random color; coins pulse gold; a colored life bar sits under each player.

Open <http://localhost:8000/gui>, enter the server URL + viewer key, connect.

> Note: the GUI is view-only. To actually play, use the `/join` + `/move`
> endpoints directly (e.g. via a bot/client).

