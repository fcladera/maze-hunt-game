"""API flows: join/move/state, auth, death, rejoin rejection, error codes.

Critical tests #7, #11 (and the full §8 contract).
"""
import config
from helpers import advance, make_game, place, set_life


# --- /join -----------------------------------------------------------------

def test_join_returns_required_fields(client):
    r = client.post("/join", json={"user_name": "alice"})
    assert r.status_code == 200
    body = r.json()
    assert set(body) == {"auth_key", "player_id", "user_name", "current_position"}
    assert body["user_name"] == "alice"
    assert isinstance(body["auth_key"], str) and body["auth_key"]
    assert isinstance(body["player_id"], int)
    x, y = body["current_position"]
    assert 1 <= x <= config.GRID_SIZE - 2
    assert 1 <= y <= config.GRID_SIZE - 2


def test_join_invalid_name_empty(client):
    r = client.post("/join", json={"user_name": ""})
    assert r.status_code == 400
    assert r.json()["code"] == "INVALID_NAME"


def test_join_invalid_name_missing(client):
    r = client.post("/join", json={})
    assert r.status_code == 422  # pydantic validation


def test_already_joined(client):
    client.post("/join", json={"user_name": "alice"})
    r = client.post("/join", json={"user_name": "alice"})
    assert r.status_code == 409
    assert r.json()["code"] == "ALREADY_JOINED"


def test_dead_cannot_rejoin(client):
    import main
    body = client.post("/join", json={"user_name": "alice"}).json()
    pid = body["player_id"]
    p = main.game.players[pid]
    set_life(p, 1)
    advance(main.game, {p.id: "up"})      # dies of exhaustion
    assert not p.alive
    r = client.post("/join", json={"user_name": "alice"})
    assert r.status_code == 403
    assert r.json()["code"] == "DEAD_CANNOT_REJOIN"


def test_no_room_when_full(monkeypatch):
    import main, game as game_mod
    async def _noop_loop(self):
        return None
    monkeypatch.setattr(game_mod.GameState, "run_tick_loop", _noop_loop)
    config.MAX_PLAYERS = 2
    try:
        main.game = game_mod.GameState(seed=7)
        from fastapi.testclient import TestClient
        with TestClient(main.app) as c:
            c.post("/join", json={"user_name": "a"})
            c.post("/join", json={"user_name": "b"})
            r = c.post("/join", json={"user_name": "c"})
            assert r.status_code == 409
            assert r.json()["code"] == "NO_ROOM"
    finally:
        config.MAX_PLAYERS = 100


# --- /move -----------------------------------------------------------------

def test_move_ok(client):
    key = client.post("/join", json={"user_name": "alice"}).json()["auth_key"]
    r = client.post("/move", json={"auth_key": key, "direction": "up"})
    assert r.status_code == 200
    assert r.json() == {"ok": True}


def test_move_invalid_auth(client):
    r = client.post("/move", json={"auth_key": "bogus", "direction": "up"})
    assert r.status_code == 401
    assert r.json()["code"] == "INVALID_AUTH"


def test_move_invalid_direction(client):
    key = client.post("/join", json={"user_name": "alice"}).json()["auth_key"]
    r = client.post("/move", json={"auth_key": key, "direction": "sideways"})
    assert r.status_code == 400
    assert r.json()["code"] == "INVALID_DIRECTION"


def test_move_dead_returns_DEAD(client):
    """Critical test #7: dead player's /move -> DEAD, no state change."""
    import main
    body = client.post("/join", json={"user_name": "alice"}).json()
    key, pid = body["auth_key"], body["player_id"]
    p = main.game.players[pid]
    set_life(p, 1)
    advance(main.game, {p.id: "up"})      # dies
    assert not p.alive
    mc_before = p.motion_count
    r = client.post("/move", json={"auth_key": key, "direction": "up"})
    assert r.status_code == 403
    assert r.json()["code"] == "DEAD"
    assert p.motion_count == mc_before    # no state change


# --- /current_tick ---------------------------------------------------------

def test_current_tick(client):
    key = client.post("/join", json={"user_name": "alice"}).json()["auth_key"]
    r = client.get("/current_tick", params={"auth_key": key})
    assert r.status_code == 200
    assert r.json() == {"current_tick": 0}
    import main
    advance(main.game, {})
    r = client.get("/current_tick", params={"auth_key": key})
    assert r.json() == {"current_tick": 1}


def test_current_tick_bad_auth(client):
    r = client.get("/current_tick", params={"auth_key": "bogus"})
    assert r.status_code == 401
    assert r.json()["code"] == "INVALID_AUTH"


# --- /state ----------------------------------------------------------------

def test_state_shape_and_self(client):
    key = client.post("/join", json={"user_name": "alice"}).json()["auth_key"]
    r = client.get("/state", params={"auth_key": key})
    assert r.status_code == 200
    body = r.json()
    assert set(body) == {"current_tick", "you", "players",
                         "coins_uncollected_location", "obstacles_location"}
    you = body["you"]
    assert set(you) == {"id", "current_position", "motion_count",
                        "coins_captured", "life", "alive",
                        "has_pending_move", "pending_direction"}
    assert you["alive"] is True
    assert you["has_pending_move"] is False
    assert you["pending_direction"] is None


def test_state_shows_pending_move(client):
    import main
    key = client.post("/join", json={"user_name": "alice"}).json()["auth_key"]
    client.post("/move", json={"auth_key": key, "direction": "up"})
    body = client.get("/state", params={"auth_key": key}).json()
    assert body["you"]["has_pending_move"] is True
    assert body["you"]["pending_direction"] == "up"


def test_state_lists_other_alive_players_only(client):
    """Critical test #11: players excludes you and all dead players."""
    import main
    ka = client.post("/join", json={"user_name": "alice"}).json()["auth_key"]
    bb = client.post("/join", json={"user_name": "bob"}).json()
    bob_id = bb["player_id"]
    body = client.get("/state", params={"auth_key": ka}).json()
    assert len(body["players"]) == 1
    assert body["players"][0]["name"] == "bob"
    # Kill bob; he must disappear from alice's players list.
    b = main.game.players[bob_id]
    set_life(b, 1)
    advance(main.game, {b.id: "up"})
    assert not b.alive
    body = client.get("/state", params={"auth_key": ka}).json()
    assert body["players"] == []
    assert body["you"]["alive"] is True


def test_state_dead_self_reports_alive_false(client):
    import main
    body = client.post("/join", json={"user_name": "alice"}).json()
    key, pid = body["auth_key"], body["player_id"]
    p = main.game.players[pid]
    set_life(p, 1)
    advance(main.game, {p.id: "up"})
    body = client.get("/state", params={"auth_key": key}).json()
    assert body["you"]["alive"] is False


def test_state_bad_auth(client):
    r = client.get("/state", params={"auth_key": "bogus"})
    assert r.status_code == 401
    assert r.json()["code"] == "INVALID_AUTH"


def test_state_obstacles_include_border(client):
    key = client.post("/join", json={"user_name": "alice"}).json()["auth_key"]
    body = client.get("/state", params={"auth_key": key}).json()
    obs = {tuple(c) for c in body["obstacles_location"]}
    # Corners and edges of the border are present.
    assert (0, 0) in obs
    assert (config.GRID_SIZE - 1, config.GRID_SIZE - 1) in obs
    assert (0, 50) in obs
    assert (50, 0) in obs


def test_state_coins_list(client):
    """Coins appear in /state once spawned."""
    import main
    key = client.post("/join", json={"user_name": "alice"}).json()["auth_key"]
    for _ in range(10):
        advance(main.game, {})
    body = client.get("/state", params={"auth_key": key}).json()
    assert len(body["coins_uncollected_location"]) >= 1


def test_state_motion_and_life_after_move(client):
    """After a tick resolves a move, /state reflects motion+1 and life-1."""
    import main
    from helpers import find_blocked_origin
    body = client.post("/join", json={"user_name": "alice"}).json()
    key, pid = body["auth_key"], body["player_id"]
    p = main.game.players[pid]
    origin = find_blocked_origin(main.game, "right")
    place(main.game, p, *origin)
    client.post("/move", json={"auth_key": key, "direction": "right"})  # blocked
    advance(main.game)                    # resolves pending
    body = client.get("/state", params={"auth_key": key}).json()
    assert body["you"]["motion_count"] == 1
    assert body["you"]["life"] == config.BASE_LIFE - 1
    assert body["you"]["current_position"] == [origin[0], origin[1]]
    assert body["you"]["has_pending_move"] is False
