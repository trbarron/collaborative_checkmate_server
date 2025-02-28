import random
import time
import asyncio
import chess
import chess.engine
import os
from typing import Dict, Optional
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from redis import Redis
from dotenv import load_dotenv
from enum import Enum


load_dotenv()

app = FastAPI()
redis = Redis(
    host='redis-18058.c89.us-east-1-3.ec2.redns.redis-cloud.com',
    port=18058,
    db=0,
    decode_responses=True,
    password=os.getenv("REDIS_PASSWORD")
)

# Game phases as an Enum for better type checking
class GamePhase(str, Enum):
    SETUP = 'setup'
    TEAM1_SELECTION = 'team1_selection'
    TEAM1_COMPUTING = 'team1_computing'
    TEAM2_SELECTION = 'team2_selection'
    TEAM2_COMPUTING = 'team2_computing'
    COOLDOWN = 'cooldown'

# Constants
SELECTION_TIME = 10  # seconds

STOCKFISH_PATH = os.getenv("STOCKFISH_PATH", "/usr/games/stockfish")
engine = chess.engine.SimpleEngine.popen_uci(STOCKFISH_PATH)

# Store active connections
class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, Dict[str, WebSocket]] = {}

    async def connect(self, websocket: WebSocket, game_id: str, player_id: str):
        await websocket.accept()
        if game_id not in self.active_connections:
            self.active_connections[game_id] = {}
        self.active_connections[game_id][player_id] = websocket

    def disconnect(self, game_id: str, player_id: str):
        if game_id in self.active_connections:
            if player_id in self.active_connections[game_id]:
                del self.active_connections[game_id][player_id]
            if not self.active_connections[game_id]:
                del self.active_connections[game_id]

    async def send_personal_message(self, message: dict, game_id: str, player_id: str):
        if game_id in self.active_connections and player_id in self.active_connections[game_id]:
            await self.active_connections[game_id][player_id].send_json(message)

    async def broadcast(self, message: dict, game_id: str):
        if game_id in self.active_connections:
            for websocket in self.active_connections[game_id].values():
                await websocket.send_json(message)

manager = ConnectionManager()

# Game state management functions
class GameManager:
    @staticmethod
    async def update_game_state(game_id: str, **kwargs):
        """
        Update game state in Redis and broadcast changes to clients
        Sets a 24-hour TTL on all entries
        """
        
        pipe = redis.pipeline()
        
        for key, value in kwargs.items():
            if value is not None:
                # Set the value with a 24-hour TTL (86400 seconds)
                pipe.set(f"game:{game_id}:{key}", value, ex=43200)
        
        # Execute all commands in a single network round-trip
        pipe.execute()
        
        # Construct update message with all provided values
        update_msg = {
            "type": "game_state_update",
            **kwargs
        }
        
        await manager.broadcast(update_msg, game_id)
    
    @staticmethod
    def get_game_state(game_id: str, key: str) -> Optional[str]:
        """
        Get a specific game state value from Redis
        """
        return redis.get(f"game:{game_id}:{key}")
    
    @staticmethod
    def get_all_game_state(game_id: str) -> dict:
        """
        Get all game state values for a game using pipelining
        """
        # Define all known game state keys
        known_keys = [
            "fen", 
            # "t1p1_selection",
            # "t1p2_selection",
            # "t2p1_selection",
            # "t2p2_selection",
            "t1p1_seat",
            "t1p2_seat",
            "t2p1_seat",
            "t2p2_seat",
            "t1p1_ready",
            "t1p2_ready",
            "t2p1_ready",
            "t2p2_ready",
            # "computation_lock",
            "game_phase",
            "next_relevant_time"
        ]
        
        # Create a pipeline to batch all requests
        pipe = redis.pipeline()
        for key in known_keys:
            pipe.get(f"game:{game_id}:{key}")
        
        # Execute all commands in a single network round-trip
        values = pipe.execute()
        
        # Combine keys and values into a dictionary
        return dict(zip(known_keys, values))
    
    @staticmethod
    async def transition_phase(game_id: str, new_phase: GamePhase):
        """
        Transition the game to a new phase and set appropriate timers
        """
        current_time = time.time()
        next_time = None
        
        if new_phase in [GamePhase.TEAM1_SELECTION, GamePhase.TEAM2_SELECTION]:
            # Set selection phase timeout
            next_time = current_time + SELECTION_TIME
        
        # Update game state with new phase and next relevant time
        await GameManager.update_game_state(
            game_id=game_id,
            game_phase=new_phase,
            next_relevant_time=str(next_time) if next_time else None
        )
        
        print(f"Game {game_id} transitioned to {new_phase}")
        
        if new_phase == GamePhase.TEAM1_COMPUTING or new_phase == GamePhase.TEAM2_COMPUTING:
            # Add a small delay to ensure the phase transition broadcast is received
            await asyncio.sleep(0.05)
            
            # Perform team's move computation
            team_number = 1 if new_phase == GamePhase.TEAM1_COMPUTING else 2
            await GameManager.compute_team_move(game_id, team_number)
    
    @staticmethod
    async def compute_team_move(game_id: str, team_number: int):
        """
        Compute the move for a team based on player selections
        """
        # Acquire computation lock with TTL to prevent endless locks
        print(f"Acquiring computation lock for game {game_id}")
        if not redis.set(f"game:{game_id}:computation_lock", "1", nx=True, ex=30):  # 30-second TTL on lock
            print(f"Another process is already computing for game {game_id}")
            return
                
        try:
            # Get current FEN
            fen = GameManager.get_game_state(game_id, "fen")
            print(f"Computing move for team {team_number} in game {game_id} with FEN: {fen}")
            if not fen:
                await GameManager.update_game_state(
                    game_id=game_id,
                    game_phase=GamePhase.SETUP,
                    next_relevant_time=None
                )
                return
                
            # Get selections from both players on the team
            p1_selection = GameManager.get_game_state(game_id, f"t{team_number}p1_selection")
            p2_selection = GameManager.get_game_state(game_id, f"t{team_number}p2_selection")
            
            
            if p1_selection and p2_selection:
                p1_board = chess.Board(p1_selection)
                p1_info = engine.analyse(p1_board, chess.engine.Limit(time=2.0))

                p2_board = chess.Board(p2_selection)
                p2_info = engine.analyse(p2_board, chess.engine.Limit(time=2.0))
                
                # For team 1 (WHITE)
                if team_number == 1:
                    # PovScore already exists in the analysis output, no need to create a new one
                    p1_score = p1_info["score"]
                    p2_score = p2_info["score"]
                    # Compare from WHITE's perspective
                    if p1_score.white() > p2_score.white():
                        board = p1_board
                    else:
                        board = p2_board

                # For team 2 (BLACK)
                if team_number == 2:
                    # Same scores but we'll compare from BLACK's perspective
                    p1_score = p1_info["score"]
                    p2_score = p2_info["score"]
                    # Compare from BLACK's perspective
                    if p1_score.black() > p2_score.black():
                        board = p1_board
                    else:
                        board = p2_board

                
            elif p1_selection:
                board = chess.Board(p1_selection)
            elif p2_selection:
                board = chess.Board(p2_selection)
            else:
                board = chess.Board(fen)
                # do a random move
                legal_moves = list(board.legal_moves)
                if legal_moves:
                    move = random.choice(legal_moves)
                    board.push(move)
                

            new_fen = board.fen()
            
            # Update the board state
            await GameManager.update_game_state(
                game_id=game_id,
                fen=new_fen
            )
                
            # Clear selections for this team
            await GameManager.update_game_state(
                game_id=game_id,
                **{f"t{team_number}p1_selection": "", f"t{team_number}p2_selection": ""}
            )
            
            # Check to see if there is a checkmate
            is_checkmate = board.is_checkmate()
            if is_checkmate:
                await GameManager.update_game_state(
                    game_id=game_id,
                    game_phase=GamePhase.COOLDOWN,
                    next_relevant_time=None
                )
                return
            
            # Transition to next phase
            next_phase = GamePhase.TEAM2_SELECTION if team_number == 1 else GamePhase.TEAM1_SELECTION
            await GameManager.transition_phase(game_id, next_phase)
                
        finally:
                # Release the computation lock
                redis.delete(f"game:{game_id}:computation_lock")
    
    @staticmethod
    async def start_game(game_id: str):
        """
        Initialize a new game
        """
        board = chess.Board()
        
        # Set initial game state
        await GameManager.update_game_state(
            game_id=game_id,
            fen=board.fen(),
            game_phase=GamePhase.TEAM1_SELECTION,
            next_relevant_time=str(time.time() + SELECTION_TIME)
        )
        
        print(f"Game {game_id} started")
    
    @staticmethod
    async def check_and_handle_phase_transitions(game_id: str):
        """
        Check if it's time to transition phases based on next_relevant_time
        """
        # Get current phase and next relevant time
        game_phase = GameManager.get_game_state(game_id, "game_phase")
        next_time_str = GameManager.get_game_state(game_id, "next_relevant_time")
        
        if not game_phase or not next_time_str:
            return
            
        current_time = time.time()
        next_time = float(next_time_str)
        
        if current_time >= next_time and game_phase is not GamePhase.COOLDOWN:
            # Time's up, transition to the next phase
            if game_phase == GamePhase.TEAM1_SELECTION:
                await GameManager.transition_phase(game_id, GamePhase.TEAM1_COMPUTING)
            elif game_phase == GamePhase.TEAM2_SELECTION:
                await GameManager.transition_phase(game_id, GamePhase.TEAM2_COMPUTING)
            
            if game_phase in [GamePhase.TEAM1_SELECTION, GamePhase.TEAM2_SELECTION]:
                # Broadcast timer updates
                remaining_seconds = next_time - current_time + SELECTION_TIME
                await manager.broadcast(
                    {
                        "type": "timer_update",
                        "phase": game_phase,
                        "seconds_remaining": round(remaining_seconds, 1)
                    },
                    game_id
                )

# Seat management functions
def set_up_player_seats(game_id: str, player_id: str):
    """
    Set up initial player seats or assign a player to an open seat
    """
    print(f"Player {player_id} joined game {game_id} as t1p1")

    if not redis.exists(f"game:{game_id}:t1p1_seat"):
        # Initialize all seats to None with 24-hour TTL
        pipe = redis.pipeline()
        pipe.set(f"game:{game_id}:t1p2_seat", "", ex=86400)
        pipe.set(f"game:{game_id}:t2p1_seat", "", ex=86400)
        pipe.set(f"game:{game_id}:t2p2_seat", "", ex=86400)
        
        # Initialize player readiness with 24-hour TTL
        pipe.set(f"game:{game_id}:t1p1_ready", "false", ex=86400)
        pipe.set(f"game:{game_id}:t1p2_ready", "false", ex=86400)
        pipe.set(f"game:{game_id}:t2p1_ready", "false", ex=86400)
        pipe.set(f"game:{game_id}:t2p2_ready", "false", ex=86400)
        
        # Set initial phase with 24-hour TTL
        pipe.set(f"game:{game_id}:game_phase", GamePhase.SETUP, ex=86400)
        
        # Assign player to first seat with 24-hour TTL
        pipe.set(f"game:{game_id}:t1p1_seat", player_id, ex=86400)
        
        # Execute all commands in a single network round-trip
        pipe.execute()
    
    return

async def change_player_seat(game_id: str, player_id: str, seat: str):
    """
    Move a player to a different seat
    """
    # Get current seat assignments
    seats = {
        "t1p1": redis.get(f"game:{game_id}:t1p1_seat"),
        "t1p2": redis.get(f"game:{game_id}:t1p2_seat"),
        "t2p1": redis.get(f"game:{game_id}:t2p1_seat"),
        "t2p2": redis.get(f"game:{game_id}:t2p2_seat")
    }
    
    pipe = redis.pipeline()
    
    # Check if player is already in a seat
    for s, p in seats.items():
        if p == player_id:
            pipe.set(f"game:{game_id}:{s}_seat", "", ex=86400)
            pipe.set(f"game:{game_id}:{s}_ready", "false", ex=86400)
    
    # Check if requested seat is available
    if seats[seat] == "":
        pipe.set(f"game:{game_id}:{seat}_seat", player_id, ex=86400)
    
    # Execute all commands in a single network round-trip
    pipe.execute()
    
    game_state = GameManager.get_all_game_state(game_id)
    await GameManager.update_game_state(game_id=game_id, **game_state)
    
    return

async def set_player_ready(game_id: str, player_id: str, ready: bool = True):
    """
    Set player ready status
    """
    # Get current seat assignments
    seats = {
        "t1p1": redis.get(f"game:{game_id}:t1p1_seat"),
        "t1p2": redis.get(f"game:{game_id}:t1p2_seat"),
        "t2p1": redis.get(f"game:{game_id}:t2p1_seat"),
        "t2p2": redis.get(f"game:{game_id}:t2p2_seat")
    }
    
    # Find player's seat
    player_seat = None
    for seat, seat_player_id in seats.items():
        if seat_player_id == player_id:
            player_seat = seat
            break
    
    if player_seat:
        # Set ready status
        redis.set(f"game:{game_id}:{player_seat}_ready", "true" if ready else "false")
        
        # Broadcast ready status
        game_state = GameManager.get_all_game_state(game_id)
        await GameManager.update_game_state(game_id=game_id, **game_state)
        
        # Check if all players are ready
        all_ready = True
        occupied_seats = 0
        
        for seat, seat_player_id in seats.items():
            if seat_player_id:
                occupied_seats += 1
                if redis.get(f"game:{game_id}:{seat}_ready") != "true":
                    all_ready = False
        
        # Start game if all players are ready and we have at least one player on each team
        if all_ready and occupied_seats >= 2:
            team1_has_player = seats["t1p1"] or seats["t1p2"]
            team2_has_player = seats["t2p1"] or seats["t2p2"]
            
            if True: # team1_has_player and team2_has_player:
                current_phase = redis.get(f"game:{game_id}:game_phase")
                if current_phase == GamePhase.SETUP:
                    await GameManager.start_game(game_id)

# WebSocket endpoint
@app.websocket("/ws/game/{game_id}/player/{player_id}")
async def websocket_endpoint(websocket: WebSocket, game_id: str, player_id: str):
    await manager.connect(websocket, game_id, player_id)
    set_up_player_seats(game_id, player_id)
    
    # Send initial connection confirmation
    await manager.send_personal_message(
        {
            "type": "connection_established",
            "player_id": player_id
        },
        game_id, 
        player_id
    )

    # Send current game state
    game_state = GameManager.get_all_game_state(game_id)
    await GameManager.update_game_state(game_id=game_id, **game_state)

    background_task = asyncio.create_task(game_state_checker(game_id))

    try:
        while True:
            # Receive message from client
            data = await websocket.receive_json()
            
            # Process the message based on its type
            if data["type"] == "submit_move":
                player_id = data["player_id"]
                move = data["move"]
                
                # Find player's seat
                seats = {
                    "t1p1": redis.get(f"game:{game_id}:t1p1_seat"),
                    "t1p2": redis.get(f"game:{game_id}:t1p2_seat"),
                    "t2p1": redis.get(f"game:{game_id}:t2p1_seat"),
                    "t2p2": redis.get(f"game:{game_id}:t2p2_seat")
                }
                
                player_seat = None
                for seat, seat_player_id in seats.items():
                    if seat_player_id == player_id:
                        player_seat = seat
                        break
                
                if player_seat:
                    # Check game phase to ensure player can submit a move
                    current_phase = redis.get(f"game:{game_id}:game_phase")
                    is_team1 = player_seat.startswith("t1")
                    is_team2 = player_seat.startswith("t2")
                    
                    can_move = (is_team1 and current_phase == GamePhase.TEAM1_SELECTION) or \
                               (is_team2 and current_phase == GamePhase.TEAM2_SELECTION)
                    
                    if can_move:
                        # Record the player's move
                        await GameManager.update_game_state(
                            game_id=game_id,
                            **{f"{player_seat}_selection": move}
                        )
                        
                        # Notify all players of the selection
                        await manager.broadcast(
                            {
                                "type": "move_submitted",
                                "player_id": player_id,
                                "seat": player_seat
                            },
                            game_id
                        )
            
            elif data["type"] == "take_seat":
                seat = data["seat"]
                await change_player_seat(game_id, player_id, seat)
            
            elif data["type"] == "ready":
                await set_player_ready(game_id, player_id, True)
            
            elif data["type"] == "not_ready":
                await set_player_ready(game_id, player_id, False)

    except WebSocketDisconnect:
        # Handle disconnect
        manager.disconnect(game_id, player_id)
        background_task.cancel()
        
        # Find and clear player's seat
        seats = {
            "t1p1": redis.get(f"game:{game_id}:t1p1_seat"),
            "t1p2": redis.get(f"game:{game_id}:t1p2_seat"),
            "t2p1": redis.get(f"game:{game_id}:t2p1_seat"),
            "t2p2": redis.get(f"game:{game_id}:t2p2_seat")
        }
        
        for seat, seat_player_id in seats.items():
            if seat_player_id == player_id:
                redis.set(f"game:{game_id}:{seat}_seat", "")
                redis.set(f"game:{game_id}:{seat}_ready", "false")
        
        # Notify other players
        await manager.broadcast(
            {
                "type": "player_disconnected", 
                "player_id": player_id
            },
            game_id
        )
        
        # Update seat info
        updated_seats = {
            "t1p1": redis.get(f"game:{game_id}:t1p1_seat"),
            "t1p2": redis.get(f"game:{game_id}:t1p2_seat"),
            "t2p1": redis.get(f"game:{game_id}:t2p1_seat"),
            "t2p2": redis.get(f"game:{game_id}:t2p2_seat")
        }
        
        await manager.broadcast(
            {
                "type": "player_seats",
                "seats": updated_seats
            },
            game_id
        )

# Background task to check game state and manage timers
async def game_state_checker(game_id: str):
    try:
        while True:
            await GameManager.check_and_handle_phase_transitions(game_id)
            await asyncio.sleep(0.5)  # Check every 0.5 seconds
    except asyncio.CancelledError:
        print(f"Game state checker for game {game_id} was cancelled")
    except Exception as e:
        print(f"Error in game state checker for game {game_id}: {e}")

# Run the app with uvicorn
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)