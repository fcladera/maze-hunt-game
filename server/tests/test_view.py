"""Spectator /view endpoint: shared viewer_key auth and full public state.

Covers the GUI read path: all alive players visible (no `you` filter), coins,
obstacles, tick, and the viewer_key auth gating.
"""
import config
import pytest
import api
from helpers import advance, make_game, set_life


def test_view_requires_viewer_key(client):
    # No viewer_key at all -> 401.
    r = client.get("/view")
    assert r.status_code == 401
    assert r.json()["code"] == "INVALID_VIEWER_KEY"


def test_view_rejects_bad_viewer_key(client):
    r = client.get("/view", params={"viewer_key": "bogus"})
    assert r.status_code == 401
    assert r.json()["code"] == "INVALID_VIEWER_KEY"


def test_view_returns_full_public_state(client):
    config.VIEWER_KEY = "test-viewer"
    try:
        ka = client.post("/join", json={"user_name": "alice"}).json()["auth_key"]
        client.post("/join", json={"user_name": "bob"})
        r = client.get("/view", params={"viewer_key": "test-viewer"})
        assert r.status_code == 200
        body = r.json()
        assert set(body) == {"current_tick", "players",
                             "coins_uncollected_location", "obstacles_location"}
        names = {p["name"] for p in body["players"]}
        assert names == {"alice", "bob"}  # all alive players, no `you` filter
        # player dict shape matches the public projection (no secrets).
        p0 = body["players"][0]
        assert set(p0) == {"id", "name", "current_position", "motion_count",
                           "coins_captured", "life", "alive"}
        # No auth_key leaks anywhere.
        assert "auth_key" not in p0
        assert "auth_key" not in body
    finally:
        config.VIEWER_KEY = ""


def test_view_excludes_dead_players(client):
    import main
    config.VIEWER_KEY = "test-viewer"
    try:
        client.post("/join", json={"user_name": "alice"})
        bb = client.post("/join", json={"user_name": "bob"}).json()
        bob = main.game.players[bb["player_id"]]
        set_life(bob, 1)
        advance(main.game, {bob.id: "up"})   # bob dies
        body = client.get("/view", params={"viewer_key": "test-viewer"}).json()
        names = {p["name"] for p in body["players"]}
        assert names == {"alice"}
    finally:
        config.VIEWER_KEY = ""


def test_view_tick_lightweight(client):
    config.VIEWER_KEY = "test-viewer"
    try:
        import main
        r = client.get("/view_tick", params={"viewer_key": "test-viewer"})
        assert r.status_code == 200
        assert r.json() == {"current_tick": 0}
        advance(main.game, {})
        r = client.get("/view_tick", params={"viewer_key": "test-viewer"})
        assert r.json() == {"current_tick": 1}
    finally:
        config.VIEWER_KEY = ""


def test_view_tick_rejects_bad_key(client):
    config.VIEWER_KEY = "test-viewer"
    try:
        r = client.get("/view_tick", params={"viewer_key": "wrong"})
        assert r.status_code == 401
        assert r.json()["code"] == "INVALID_VIEWER_KEY"
    finally:
        config.VIEWER_KEY = ""


def test_state_public_unit():
    """Direct unit check: state_public lists all alive players and coins."""
    g = make_game(seed=7)
    a = g.join("a")
    b = g.join("b")
    body = g.state_public()
    assert body["current_tick"] == 0
    assert len(body["players"]) == 2
    assert {p["name"] for p in body["players"]} == {"a", "b"}
    assert body["players"][0]["current_position"] == [a.position[0], a.position[1]]
    assert isinstance(body["obstacles_location"], list)
    assert body["coins_uncollected_location"] == []
    # advance to a coin tick and confirm a coin appears
    for _ in range(10):
        advance(g, {})
    body = g.state_public()
    assert len(body["coins_uncollected_location"]) >= 1


def test_viewer_disabled_when_key_unset(monkeypatch):
    """_check_viewer raises VIEWER_DISABLED when no key is configured."""
    import main
    config.VIEWER_KEY = ""
    try:
        # Bypass the import-time auto-gen by clearing the key now.
        with pytest.raises(api.GameError) as ei:
            main._check_viewer("")
        assert ei.value.code == "VIEWER_DISABLED"
    finally:
        config.VIEWER_KEY = ""
