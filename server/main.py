"""FastAPI app: endpoints, startup tick loop, error mapping."""
import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import JSONResponse

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
