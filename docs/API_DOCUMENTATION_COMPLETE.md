# WebSocket API Documentation - Collaborative Checkmate (Complete)

This document defines the complete WebSocket API contract between the client and server for the Collaborative Checkmate game.

## Connection

### WebSocket URL
```
wss://collaborative-checkmate-server.fly.dev/ws/game/{gameId}/player/{playerId}[?is_private=true]
```

**Parameters:**
- `gameId`: Unique identifier for the game session
- `playerId`: Unique identifier for the player
- `is_private` (optional): Boolean query parameter to create/join private games

## Message Format

All messages are JSON objects with a `type` field indicating the message type.

---

## Client → Server Messages

### 1. Take Seat
**Purpose:** Request to occupy a specific seat in the game

```json
{
  "type": "take_seat",
  "seat": "t1p1" | "t1p2" | "t2p1" | "t2p2"
}
```

**Fields:**
- `seat`: The seat identifier
  - `t1p1`: Team 1, Player 1 (White team)
  - `t1p2`: Team 1, Player 2 (White team)
  - `t2p1`: Team 2, Player 1 (Black team)
  - `t2p2`: Team 2, Player 2 (Black team)

**Expected Response:** `game_state_update` with updated seat assignments

---

### 2. Ready Up
**Purpose:** Indicate that the player is ready to start the game

```json
{
  "type": "ready",
  "player_id": "string"
}
```

**Fields:**
- `player_id`: The player's unique identifier

**Expected Response:** `player_ready` message followed by potential `game_state_update`

---

### 3. Not Ready
**Purpose:** Indicate that the player is no longer ready

```json
{
  "type": "not_ready",
  "player_id": "string"
}
```

**Fields:**
- `player_id`: The player's unique identifier

**Expected Response:** `game_state_update` with updated ready status

---

### 4. Submit Move
**Purpose:** Submit a chess move during selection phase

```json
{
  "type": "submit_move",
  "player_id": "string",
  "move": "string"
}
```

**Fields:**
- `player_id`: The player's unique identifier
- `move`: FEN string representing the board state after the move

**Expected Response:** `move_submitted` confirmation

---

### 5. Lock In Move
**Purpose:** Confirm the submitted move (prevents further changes)

```json
{
  "type": "lock_in_move",
  "player_id": "string"
}
```

**Fields:**
- `player_id`: The player's unique identifier

**Expected Response:** Move is locked and cannot be changed

---

### 6. Heartbeat
**Purpose:** Keep connection alive and detect connection issues

```json
{
  "type": "heartbeat",
  "timestamp": number,
  "connectionId": "string"
}
```

**Fields:**
- `timestamp`: Client timestamp when heartbeat was sent
- `connectionId`: Unique connection identifier

**Expected Response:** `heartbeat_response` message

---

## Server → Client Messages

### 1. Connection Established
**Purpose:** Confirm successful WebSocket connection

```json
{
  "type": "connection_established",
  "player_id": "string",
  "is_reconnection": boolean
}
```

**Fields:**
- `player_id`: The player's unique identifier
- `is_reconnection`: Whether this is a reconnection or new connection

---

### 2. Game State Update
**Purpose:** Comprehensive game state synchronization

```json
{
  "type": "game_state_update",
  "game_phase": "setup" | "team1_selection" | "team1_computing" | "team2_selection" | "team2_computing" | "cooldown",
  "duration": number,
  "fen": "string",
  "last_move": "string",
  "move_count": "string",
  "t1_same_moves": "string",
  "t2_same_moves": "string",
  "next_relevant_time": "string",
  "t1p1_seat": "string",
  "t1p1_ready": "true" | "false",
  "t1p1_locked_in": "true" | "false",
  "t1p1_selection": "string",
  "t1p2_seat": "string", 
  "t1p2_ready": "true" | "false",
  "t1p2_locked_in": "true" | "false",
  "t1p2_selection": "string",
  "t2p1_seat": "string",
  "t2p1_ready": "true" | "false",
  "t2p1_locked_in": "true" | "false",
  "t2p1_selection": "string",
  "t2p2_seat": "string",
  "t2p2_ready": "true" | "false",
  "t2p2_locked_in": "true" | "false",
  "t2p2_selection": "string"
}
```

**Fields:**
- `game_phase`: Current phase of the game
- `duration`: Time remaining in current phase (seconds)
- `fen`: Current chess position in FEN notation
- `last_move`: Last move played in algebraic notation (e.g., "e2e4")
- `move_count`: Total number of moves played
- `t1_same_moves`: Number of times team 1 players selected the same move
- `t2_same_moves`: Number of times team 2 players selected the same move
- `next_relevant_time`: Timestamp for next phase transition
- `{seat}_seat`: Player ID occupying the seat (empty string if vacant)
- `{seat}_ready`: Ready status of the seat ("true"/"false")
- `{seat}_locked_in`: Whether the player has locked in their move selection
- `{seat}_selection`: The move selected by the player in that seat

**Game Phases:**
- `setup`: Initial game setup, players joining seats
- `team1_selection`: White team selecting their move
- `team1_computing`: Server computing white team's move
- `team2_selection`: Black team selecting their move  
- `team2_computing`: Server computing black team's move
- `cooldown`: After game is over or abandoned

---

### 3. Timer Update
**Purpose:** Real-time timer synchronization

```json
{
  "type": "timer_update",
  "seconds_remaining": number,
  "key": "string"
}
```

**Fields:**
- `seconds_remaining`: Exact time remaining in current phase
- `key`: Unique identifier for this timer instance

---

### 4. Player Ready
**Purpose:** Notification when a player becomes ready

```json
{
  "type": "player_ready",
  "player_id": "string"
}
```

**Fields:**
- `player_id`: ID of the player who became ready

---

### 5. Move Submitted
**Purpose:** Confirmation that a move was submitted

```json
{
  "type": "move_submitted",
  "player_id": "string",
  "seat": "t1p1" | "t1p2" | "t2p1" | "t2p2"
}
```

**Fields:**
- `player_id`: ID of the player who submitted the move
- `seat`: The seat from which the move was submitted

---

### 6. Move Selected
**Purpose:** Notification of the final move chosen by the engine

```json
{
  "type": "move_selected",
  "move": {
    "from": "string",
    "to": "string", 
    "submitted_by": "string"
  }
}
```

**Fields:**
- `move.from`: Starting square (e.g., "e2")
- `move.to`: Destination square (e.g., "e4")
- `move.submitted_by`: Player ID who submitted the selected move

---

### 7. Player Disconnected
**Purpose:** Notification when a player disconnects (with grace period)

```json
{
  "type": "player_disconnected",
  "player_id": "string",
  "grace_period": number
}
```

**Fields:**
- `player_id`: ID of the disconnected player
- `grace_period`: Seconds allowed for reconnection

---

### 8. Player Reconnected
**Purpose:** Notification when a player reconnects within grace period

```json
{
  "type": "player_reconnected",
  "player_id": "string",
  "seat": "t1p1" | "t1p2" | "t2p1" | "t2p2"
}
```

**Fields:**
- `player_id`: ID of the reconnected player
- `seat`: The seat they reconnected to

---

### 9. Player Permanently Disconnected
**Purpose:** Notification when a player's grace period expires

```json
{
  "type": "player_permanently_disconnected",
  "player_id": "string"
}
```

**Fields:**
- `player_id`: ID of the permanently disconnected player

---

### 10. Player Seats
**Purpose:** Update on current seat assignments

```json
{
  "type": "player_seats",
  "seats": {
    "t1p1": "string",
    "t1p2": "string",
    "t2p1": "string",
    "t2p2": "string"
  }
}
```

**Fields:**
- `seats`: Object mapping seat keys to player IDs (empty string if vacant)

---

### 11. Reconnection State Sync
**Purpose:** Restore game state for reconnecting player

```json
{
  "type": "reconnection_state_sync",
  "game_state": {
    // Full game state object
  },
  "your_seat": "t1p1" | "t1p2" | "t2p1" | "t2p2"
}
```

**Fields:**
- `game_state`: Complete current game state
- `your_seat`: The seat the reconnecting player occupies

---

### 12. Reconnection Successful
**Purpose:** Confirm successful reconnection

```json
{
  "type": "reconnection_successful",
  "message": "string"
}
```

**Fields:**
- `message`: Welcome back message for the player

---

### 13. Heartbeat Response
**Purpose:** Response to client heartbeat

```json
{
  "type": "heartbeat_response",
  "timestamp": number
}
```

**Fields:**
- `timestamp`: Server timestamp when response was sent

---

### 14. Game Over
**Purpose:** Notification when the game ends

```json
{
  "type": "game_over",
  "result": "string",
  "message": "string",
  "total_moves": number,
  "team_coordination": {
    "team1_same_moves": number,
    "team2_same_moves": number
  },
  "final_position": "string"
}
```

**Fields:**
- `result`: Game result (e.g., "checkmate", "stalemate", "draw")
- `message`: Human-readable game over message
- `total_moves`: Total number of moves played
- `team_coordination`: Statistics on team coordination
- `final_position`: Final board position in FEN notation

---

## REST API Endpoints

### Check Reconnection Status
**Purpose:** Check if a player can reconnect to a game

```
GET /api/games/{game_id}/reconnection/{player_id}
```

**Response:**
```json
{
  "can_reconnect": boolean,
  "player_seat": "string" | null,
  "game_phase": "setup" | "team1_selection" | "team1_computing" | "team2_selection" | "team2_computing" | "cooldown" | null,
  "remaining_grace_time": number,
  "grace_period_total": number
}
```

---

## Connection Handling

### Heartbeat System
- **Interval**: 10 seconds
- **Timeout**: 5 seconds
- **Purpose**: Detect stale connections and maintain connection health

### Reconnection Strategy
The client implements automatic reconnection with exponential backoff:
- Initial delay: 1 second
- Maximum delay: 30 seconds  
- Maximum attempts: 10
- Jitter added to prevent thundering herd

### Grace Period System
- **Duration**: 30 seconds
- **Purpose**: Allow temporary disconnections without losing game state
- **Cleanup**: Automatic cleanup after grace period expires

### State Restoration
On reconnection, the client:
1. Receives `connection_established` with `is_reconnection: true`
2. Gets `reconnection_state_sync` with full game state
3. Receives `reconnection_successful` confirmation
4. Resumes normal game flow

### Error Handling
- Invalid seat assignments are rejected
- Move submissions outside selection phase are ignored
- Ready requests from unseated players are rejected
- Malformed messages are logged and ignored

---

## Game Flow

1. **Setup Phase**
   - Players connect and take seats
   - Players ready up when satisfied with team composition
   - Game starts when all 4 seats are filled and ready

2. **Selection Phases**
   - Active team has limited time to submit moves
   - Players can submit multiple moves, latest overwrites previous
   - Players can lock in moves to prevent further changes

3. **Computing Phases**
   - Server selects final move (implementation-specific algorithm)
   - Move is executed and board state updated
   - Game transitions to next team's selection phase

4. **Game End**
   - Standard chess end conditions (checkmate, stalemate, etc.)
   - Statistics and final position provided
   - Players can start new game or disconnect

---

## Configuration Constants

```json
{
  "SELECTION_TIME": 15,
  "RECONNECTION_GRACE_PERIOD": 30,
  "HEARTBEAT_INTERVAL": 10000,
  "HEARTBEAT_TIMEOUT": 5000,
  "MAX_RECONNECT_ATTEMPTS": 10,
  "INITIAL_RECONNECT_DELAY": 1000,
  "MAX_RECONNECT_DELAY": 30000
}
```

---

## Type Safety with Pydantic

The server now uses Pydantic models for message validation, ensuring:
- **Runtime validation** of all WebSocket messages
- **Type safety** between client and server
- **Automatic serialization/deserialization**
- **Clear error messages** for malformed data
- **Documentation generation** from type definitions

See `shared/message_types.py` for complete Pydantic model definitions. 