"""FastAPI app: endpoints, startup tick loop, error mapping."""
import asyncio
import logging
import secrets
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

import api
import config
from game import GameState

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("maze")

# Build the world once at import (so gen_seed is logged on startup).
game = GameState(seed=config.GEN_SEED)
log.info("world ready: gen_seed=%s carved=%s obstacles=%d free_cells=%d",
         game.gen_seed, game.carved, len(game.obstacles_location),
         int((~game.obstacle_grid).sum()))

# If MG_VIEWER_KEY is unset at startup, generate a random one and log it so the
# GUI always has a spectator secret available (overridable via env for prod).
if not config.VIEWER_KEY:
    config.VIEWER_KEY = secrets.token_urlsafe(16)
    log.info("viewer key auto-generated: %s (set MG_VIEWER_KEY to pin it)", config.VIEWER_KEY)
else:
    log.info("viewer key loaded from MG_VIEWER_KEY")


@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(game.run_tick_loop())
    log.info("tick loop started (interval=%.2fs)", config.TICK_INTERVAL)
    try:
        yield
    finally:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


app = FastAPI(title="Maze Game", lifespan=lifespan)

# Serve the web GUI static assets at /gui/... (index.html at /gui).
GUI_DIR = Path(__file__).resolve().parent / "gui"
if GUI_DIR.is_dir():
    app.mount("/gui/static", StaticFiles(directory=str(GUI_DIR)), name="gui-static")


def _err(e: api.GameError):
    return JSONResponse(status_code=e.status, content={"error": e.message, "code": e.code})


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "tick": game.tick,
        "alive_players": sum(1 for p in game.players.values() if p.alive),
        "coins": len(game.coins_uncollected),
        "gen_seed": game.gen_seed,
        "carved": game.carved,
        "viewer_enabled": bool(config.VIEWER_KEY),
    }


@app.post("/join")
async def join(req: api.JoinRequest):
    try:
        p = game.join(req.user_name)
    except api.GameError as e:
        return _err(e)
    return {
        "auth_key": p.auth_key,
        "player_id": p.id,
        "user_name": p.user_name,
        "current_position": [p.position[0], p.position[1]],
    }


@app.post("/move")
async def move(req: api.MoveRequest):
    try:
        await game.submit_move(req.auth_key, req.direction)
    except api.GameError as e:
        return _err(e)
    return {"ok": True}


@app.get("/current_tick")
async def current_tick(auth_key: str):
    try:
        return game.current_tick_for(auth_key)
    except api.GameError as e:
        return _err(e)


@app.get("/state")
async def state(auth_key: str):
    try:
        return game.state_for(auth_key)
    except api.GameError as e:
        return _err(e)


# --- spectator / GUI endpoints -------------------------------------------
def _check_viewer(viewer_key: str):
    """Validate the shared spectator secret. Raises GameError on failure."""
    if not config.VIEWER_KEY:
        raise api.GameError(api.VIEWER_DISABLED, "viewer access disabled", 404)
    if not viewer_key or viewer_key != config.VIEWER_KEY:
        raise api.GameError(api.INVALID_VIEWER_KEY, "invalid viewer_key", 401)


@app.get("/view")
async def view(viewer_key: str | None = None):
    """Full public board state for spectators/the GUI (no player auth_key).

    Returns all alive players (no `you` filter), coins, obstacles and tick.
    """
    try:
        _check_viewer(viewer_key or "")
    except api.GameError as e:
        return _err(e)
    return game.state_public()


@app.get("/view_tick")
async def view_tick(viewer_key: str | None = None):
    """Lightweight tick counter for spectators (cheaper polling)."""
    try:
        _check_viewer(viewer_key or "")
    except api.GameError as e:
        return _err(e)
    return {"current_tick": game.tick}


@app.get("/gui")
async def gui_root():
    """Serve the web GUI index.html."""
    idx = GUI_DIR / "index.html"
    if not idx.is_file():
        return JSONResponse(
            status_code=404,
            content={"error": "gui not installed", "code": "NO_GUI"},
        )
    return FileResponse(str(idx))


@app.get("/")
async def root():
    return {
        "service": "maze-game",
        "gui": "/gui",
        "endpoints": ["/health", "/join", "/move", "/state",
                      "/current_tick", "/view", "/view_tick", "/gui"],
    }
