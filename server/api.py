"""Request schemas and error codes for the HTTP API."""
from pydantic import BaseModel

# --- Error codes (returned as {"error": "...", "code": "..."}) ---
NO_ROOM = "NO_ROOM"
ALREADY_JOINED = "ALREADY_JOINED"
INVALID_NAME = "INVALID_NAME"
DEAD_CANNOT_REJOIN = "DEAD_CANNOT_REJOIN"
INVALID_AUTH = "INVALID_AUTH"
DEAD = "DEAD"
INVALID_DIRECTION = "INVALID_DIRECTION"
VIEWER_DISABLED = "VIEWER_DISABLED"
INVALID_VIEWER_KEY = "INVALID_VIEWER_KEY"


class GameError(Exception):
    """Raised by game logic; mapped to a non-2xx JSON response by main.py."""

    def __init__(self, code: str, message: str | None = None, status: int = 400):
        self.code = code
        self.message = message or code
        self.status = status
        super().__init__(self.message)


class JoinRequest(BaseModel):
    user_name: str


class MoveRequest(BaseModel):
    auth_key: str
    direction: str
