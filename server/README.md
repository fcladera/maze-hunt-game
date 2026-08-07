# Maze Game Server

Simultaneous-turn, API-driven multiplayer arena on a 100x100 grid.
See `../SERVER.md` for the full specification.

## Run

```bash
cd server
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000
```

## Endpoints

| Method | Path                          | Body / query                         |
|--------|-------------------------------|--------------------------------------|
| POST   | `/join`                       | `{"user_name": "alice"}`             |
| POST   | `/move`                       | `{"auth_key": "...", "direction": "up"}` |
| GET    | `/current_tick?auth_key=KEY`  |                                      |
| GET    | `/state?auth_key=KEY`         |                                      |
| GET    | `/health`                     |                                      |

Errors are non-2xx with `{"error": "...", "code": "..."}`.

## Configuration (env overrides)

| Var                 | Default | Meaning                              |
|---------------------|---------|--------------------------------------|
| `MG_GRID_SIZE`      | 100     | grid edge length                     |
| `MG_BASE_LIFE`      | 50      | starting life                        |
| `MG_COIN_LIFE_BONUS`| 20      | life granted per captured coin       |
| `MG_COIN_INTERVAL`  | 10      | spawn a coin every N ticks           |
| `MG_MAX_COINS`      | 10      | cap on simultaneous coins            |
| `MG_TICK_INTERVAL`  | 2.0     | seconds per tick                     |
| `MG_NUM_LINES`      | 16      | radial obstacle lines                |
| `MG_MIN_LINE_LEN`   | 15      | min line length                      |
| `MG_MAX_LINE_LEN`   | 45      | max line length                      |
| `MG_MAX_GEN_ATTEMPTS`| 200    | connectivity retry attempts          |
| `MG_MAX_PLAYERS`    | 100     | max alive players                    |
| `MG_GEN_SEED`       | random  | fixed obstacle-generation seed      |

## Layout

```
main.py     FastAPI app, endpoints, startup tick loop, error mapping
game.py     GameState, Player, tick loop, collision/coin resolution
world.py    border + radial-line generation, 8-conn connectivity, carve
coins.py    coin spawn logic
config.py   constants + env overrides
api.py      pydantic request schemas + error codes
```
