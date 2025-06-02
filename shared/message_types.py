"""
Pydantic models for WebSocket message validation
Mirrors the TypeScript types in shared/types.ts
"""

from pydantic import BaseModel, Field
from typing import Optional, Literal, Dict, Any, Union
from enum import Enum

# Game Phase Enum
class GamePhase(str, Enum):
    SETUP = "setup"
    TEAM1_SELECTION = "team1_selection"
    TEAM1_COMPUTING = "team1_computing"
    TEAM2_SELECTION = "team2_selection"
    TEAM2_COMPUTING = "team2_computing"
    COOLDOWN = "cooldown"

# Seat Keys
SeatKey = Literal["t1p1", "t1p2", "t2p1", "t2p2"]

# Base WebSocket Message
class WSMessage(BaseModel):
    type: str
    
    class Config:
        extra = "allow"  # Allow additional fields

# Client → Server Messages
class TakeSeatMessage(WSMessage):
    type: Literal["take_seat"]
    seat: SeatKey

class ReadyMessage(WSMessage):
    type: Literal["ready"]
    player_id: str

class NotReadyMessage(WSMessage):
    type: Literal["not_ready"]
    player_id: str

class SubmitMoveMessage(WSMessage):
    type: Literal["submit_move"]
    player_id: str
    move: str

class LockInMoveMessage(WSMessage):
    type: Literal["lock_in_move"]
    player_id: str

class HeartbeatMessage(WSMessage):
    type: Literal["heartbeat"]
    timestamp: float
    connectionId: Optional[str] = ""

# Server → Client Messages
class ConnectionEstablishedMessage(WSMessage):
    type: Literal["connection_established"]
    player_id: str
    is_reconnection: bool

class GameStateUpdateMessage(WSMessage):
    type: Literal["game_state_update"]
    game_phase: Optional[GamePhase] = None
    duration: Optional[int] = None
    fen: Optional[str] = None
    last_move: Optional[str] = None
    move_count: Optional[str] = None
    t1_same_moves: Optional[str] = None
    t2_same_moves: Optional[str] = None
    next_relevant_time: Optional[str] = None
    # Seat assignments
    t1p1_seat: Optional[str] = None
    t1p2_seat: Optional[str] = None
    t2p1_seat: Optional[str] = None
    t2p2_seat: Optional[str] = None
    # Ready states
    t1p1_ready: Optional[str] = None
    t1p2_ready: Optional[str] = None
    t2p1_ready: Optional[str] = None
    t2p2_ready: Optional[str] = None
    # Locked in states
    t1p1_locked_in: Optional[str] = None
    t1p2_locked_in: Optional[str] = None
    t2p1_locked_in: Optional[str] = None
    t2p2_locked_in: Optional[str] = None
    # Move selections
    t1p1_selection: Optional[str] = None
    t1p2_selection: Optional[str] = None
    t2p1_selection: Optional[str] = None
    t2p2_selection: Optional[str] = None

class TimerUpdateMessage(WSMessage):
    type: Literal["timer_update"]
    seconds_remaining: int
    key: str

class PlayerReadyMessage(WSMessage):
    type: Literal["player_ready"]
    player_id: str

class MoveSubmittedMessage(WSMessage):
    type: Literal["move_submitted"]
    player_id: str
    seat: Optional[SeatKey] = None

class MoveSelectedMessage(WSMessage):
    type: Literal["move_selected"]
    move: Dict[str, str]  # {from: str, to: str, submitted_by: str}

class PlayerDisconnectedMessage(WSMessage):
    type: Literal["player_disconnected"]
    player_id: str
    grace_period: int

class PlayerReconnectedMessage(WSMessage):
    type: Literal["player_reconnected"]
    player_id: str
    seat: SeatKey

class PlayerPermanentlyDisconnectedMessage(WSMessage):
    type: Literal["player_permanently_disconnected"]
    player_id: str

class PlayerSeatsMessage(WSMessage):
    type: Literal["player_seats"]
    seats: Dict[SeatKey, str]

class ReconnectionStateSyncMessage(WSMessage):
    type: Literal["reconnection_state_sync"]
    game_state: Dict[str, Any]
    your_seat: SeatKey

class ReconnectionSuccessfulMessage(WSMessage):
    type: Literal["reconnection_successful"]
    message: str

class HeartbeatResponseMessage(WSMessage):
    type: Literal["heartbeat_response"]
    timestamp: float

class GameOverMessage(WSMessage):
    type: Literal["game_over"]
    result: str
    message: str
    total_moves: int
    team_coordination: Dict[str, int]  # {team1_same_moves: int, team2_same_moves: int}
    final_position: str

# Union type for all possible messages
ClientMessage = Union[
    TakeSeatMessage,
    ReadyMessage,
    NotReadyMessage,
    SubmitMoveMessage,
    LockInMoveMessage,
    HeartbeatMessage
]

ServerMessage = Union[
    ConnectionEstablishedMessage,
    GameStateUpdateMessage,
    TimerUpdateMessage,
    PlayerReadyMessage,
    MoveSubmittedMessage,
    MoveSelectedMessage,
    PlayerDisconnectedMessage,
    PlayerReconnectedMessage,
    PlayerPermanentlyDisconnectedMessage,
    PlayerSeatsMessage,
    ReconnectionStateSyncMessage,
    ReconnectionSuccessfulMessage,
    HeartbeatResponseMessage,
    GameOverMessage
]

# API Response Models
class AvailableGame(BaseModel):
    game_id: str
    created_time: float
    occupied_seats: int
    phase: GamePhase

class AvailableGamesResponse(BaseModel):
    games: list[AvailableGame]

class ReconnectionStatusResponse(BaseModel):
    can_reconnect: bool
    player_seat: Optional[str] = None
    game_phase: Optional[GamePhase] = None
    remaining_grace_time: float
    grace_period_total: int

class GameStats(BaseModel):
    total_games: int
    completed_games: int
    in_progress_games: int
    abandoned_games: int
    average_moves: float
    win_stats: Dict[str, int]
    recent_games: list[Any]

# Configuration
class Config(BaseModel):
    SELECTION_TIME: int = 15
    RECONNECTION_GRACE_PERIOD: int = 30
    HEARTBEAT_INTERVAL: int = 10000
    HEARTBEAT_TIMEOUT: int = 5000
    MAX_RECONNECT_ATTEMPTS: int = 10
    INITIAL_RECONNECT_DELAY: int = 1000
    MAX_RECONNECT_DELAY: int = 30000 