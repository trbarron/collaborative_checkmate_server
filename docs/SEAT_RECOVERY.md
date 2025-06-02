# Seat Recovery System

## Overview

The seat recovery system automatically handles cases where players temporarily lose their seat assignments due to various synchronization issues. This ensures a robust gaming experience even when network issues or timing conflicts occur.

## When Seat Recovery Is Triggered

Seat recovery is automatically triggered when:

1. **Move Submission**: A player tries to submit a move but has no seat assigned
2. **Lock-in Move**: A player tries to lock in their move but has no seat assigned  
3. **Ready Status**: A player tries to change their ready status but has no seat assigned
4. **WebSocket Connection**: Initial connection fails to assign a seat properly

## Recovery Strategies

The system uses a multi-tier recovery strategy:

### Strategy 1: Active Team Priority (During Selection Phase)
- **When**: Game is in `TEAM1_SELECTION` or `TEAM2_SELECTION` phase
- **Logic**: If only one seat is available for the currently active team, auto-assign the player to that seat
- **Rationale**: Prioritizes players who are likely trying to participate in the current turn

```python
# Example: Team 1 is selecting, only t1p2 is empty
if current_phase == GamePhase.TEAM1_SELECTION and empty_team_seats == ["t1p2"]:
    assign_player_to_seat("t1p2")
```

### Strategy 2: Single Seat Available
- **When**: Only one seat is empty in the entire game
- **Logic**: Auto-assign to the single available seat regardless of team
- **Rationale**: Clear and unambiguous assignment

### Strategy 3: First Available Seat (Fallback)
- **When**: Multiple seats are available
- **Logic**: Assign to the first empty seat in order: `t1p1`, `t1p2`, `t2p1`, `t2p2`
- **Rationale**: Consistent and predictable behavior

## Error Handling

If seat recovery fails (no seats available), the system:

1. **Logs the failure** with detailed information
2. **Sends an error message** to the client explaining the situation
3. **Gracefully rejects the action** (move submission, ready status, etc.)
4. **Suggests remediation** (refresh page, manually take a seat)

## Implementation Details

### Core Method
```python
@staticmethod
async def attempt_seat_recovery(game_id: str, player_id: str) -> Optional[str]:
    """
    Attempt to recover a seat for a player who lost their assignment.
    Returns the assigned seat key or None if recovery fails.
    """
```

### Integration Points
- `PlayerActionHandler.submit_move()`
- `PlayerActionHandler.lock_in_move()`
- `PlayerActionHandler.set_ready_status()`
- `websocket_endpoint()` connection handler

### Broadcast Updates
When seat recovery succeeds, the system automatically:
- Updates Redis with the new seat assignment
- Broadcasts seat updates to all players via `player_seats` message
- Ensures game state consistency

## Logging and Monitoring

The system provides detailed logging for debugging:

```
🔧 Starting seat recovery for player123 in game abc...
📊 Current phase: team1_selection
🪑 Current seats: {'t1p1': 'existing_player', 't1p2': '', 't2p1': 'other1', 't2p2': 'other2'}
🎯 Auto-assigning player123 to t1p2 (only empty seat for active team)
✅ Successfully recovered seat t1p2 for player123
```

## Common Scenarios Addressed

1. **Race Conditions**: Player connects and immediately submits move before seat assignment propagates
2. **Redis TTL Expiration**: Seat assignments expire due to Redis TTL settings
3. **Network Reconnection**: Player reconnects but loses seat during grace period
4. **Client-Server Sync Issues**: Local state shows seat but server doesn't recognize it

## Benefits

- **Improved User Experience**: Players don't get cryptic "no seat" errors
- **Robust Game Flow**: Games continue smoothly despite technical issues
- **Automatic Resolution**: Most seat assignment issues resolve without user intervention
- **Intelligent Assignment**: Prioritizes meaningful seat assignments based on game state

## Testing

The seat recovery system includes comprehensive tests:

- `test_seat_recovery_during_selection_phase()`
- `test_seat_recovery_one_seat_available()`
- `test_seat_recovery_no_seats_available()`
- `test_submit_move_with_seat_recovery()`

Run tests with:
```bash
python3 -m pytest tests/test_game_logic.py::TestPlayerActionHandler -k seat_recovery -v
``` 