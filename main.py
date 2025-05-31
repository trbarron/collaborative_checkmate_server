import random
import time
import asyncio
import uuid
import chess
import chess.engine
import os
from typing import Dict, Optional, List, Any, Tuple
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from redis import Redis
from dotenv import load_dotenv
from enum import Enum
from supabase import create_client, Client
import traceback

load_dotenv()

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:8000",
        "http://localhost:8811",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:8000",
        "http://127.0.0.1:8811",
        "https://tylerbarron.com",
        "https://www.tylerbarron.com"
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-Requested-With"],
)

# Game configuration
class GameConfig:
    SELECTION_TIME = 15  # seconds in selection phase
    
    # Redis connection settings
    REDIS_HOST = 'redis-18058.c89.us-east-1-3.ec2.redns.redis-cloud.com'
    REDIS_PORT = 18058
    REDIS_DB = 0
    REDIS_PASSWORD = os.getenv("REDIS_PASSWORD")
    
    REDIS_SHORT_TTL = 43200  # 12 hours
    REDIS_LONG_TTL = 86400   # 24 hours
    
    STOCKFISH_PATH = os.getenv("STOCKFISH_PATH", "/usr/games/stockfish")
    
    STOCKFISH_ANALYSIS_TIME = 2.0  # seconds
    
    # Supabase configuration
    SUPABASE_URL = os.getenv("SUPABASE_URL")
    SUPABASE_KEY = os.getenv("SUPABASE_ANON_KEY")

# Game phases
class GamePhase(str, Enum):
    SETUP = 'setup'
    TEAM1_SELECTION = 'team1_selection'
    TEAM1_COMPUTING = 'team1_computing'
    TEAM2_SELECTION = 'team2_selection'
    TEAM2_COMPUTING = 'team2_computing'
    COOLDOWN = 'cooldown'

# Initialize Redis client
redis = Redis(
    host=GameConfig.REDIS_HOST,
    port=GameConfig.REDIS_PORT,
    db=GameConfig.REDIS_DB,
    decode_responses=True,
    password=GameConfig.REDIS_PASSWORD
)

# Initialize chess engine
engine = chess.engine.SimpleEngine.popen_uci(GameConfig.STOCKFISH_PATH)

# Initialize Supabase client
supabase: Client = None
if GameConfig.SUPABASE_URL and GameConfig.SUPABASE_KEY:
    supabase = create_client(GameConfig.SUPABASE_URL, GameConfig.SUPABASE_KEY)
    print("Supabase client initialized successfully")
else:
    print("Warning: Supabase credentials not found, game logging will be disabled")

# Game logging to Supabase
class GameLogger:
    @staticmethod
    async def log_game_start(game_id: str, player_names: Dict[str, str]):
        """Log when a game starts with initial player information"""
        if not supabase:
            print("Supabase not available, skipping game start log")
            return
            
        try:
            # Get player names for each seat
            team1_player1 = player_names.get("t1p1", "Unknown")
            team1_player2 = player_names.get("t1p2", "Unknown") 
            team2_player1 = player_names.get("t2p1", "Unknown")
            team2_player2 = player_names.get("t2p2", "Unknown")
            
            game_log = {
                "game_id": game_id,
                "lobby_name": game_id,
                "started_at": time.time(),
                "team1_player1": team1_player1,
                "team1_player2": team1_player2,
                "team2_player1": team2_player1,
                "team2_player2": team2_player2,
                "move_count": 0,
                "game_status": "in_progress"
            }
            
            result = supabase.table("game_logs").insert(game_log).execute()
            print(f"Game start logged for {game_id}: {result}")
            
        except Exception as e:
            print(f"Error logging game start for {game_id}: {e}")
    
    @staticmethod
    async def log_game_end(game_id: str, game_result: str, winner: str = None):
        """Log when a game ends with final statistics"""
        if not supabase:
            print("Supabase not available, skipping game end log")
            return
            
        try:
            # Get current move count from database
            current_log = supabase.table("game_logs").select("move_count").eq("game_id", game_id).execute()
            move_count = 0
            if current_log.data:
                move_count = current_log.data[0].get("move_count", 0)
            
            update_data = {
                "ended_at": time.time(),
                "move_count": move_count,
                "game_result": game_result,
                "game_status": "completed"
            }
            
            if winner:
                update_data["winner"] = winner
            
            result = supabase.table("game_logs").update(update_data).eq("game_id", game_id).execute()
            print(f"Game end logged for {game_id}: {result}")
            
        except Exception as e:
            print(f"Error logging game end for {game_id}: {e}")
    
    @staticmethod
    async def increment_move_count(game_id: str):
        """Increment the move count for a game"""
        if not supabase:
            return
            
        try:
            # Get current move count
            current_log = supabase.table("game_logs").select("move_count").eq("game_id", game_id).execute()
            
            if current_log.data:
                current_count = current_log.data[0].get("move_count", 0)
                new_count = current_count + 1
                
                supabase.table("game_logs").update({"move_count": new_count}).eq("game_id", game_id).execute()
                print(f"Move count updated for {game_id}: {new_count}")
                
        except Exception as e:
            print(f"Error updating move count for {game_id}: {e}")
    
    @staticmethod
    async def log_game_abandoned(game_id: str):
        """Log when a game is abandoned due to player disconnections"""
        if not supabase:
            return
            
        try:
            # Get current move count from database
            current_log = supabase.table("game_logs").select("move_count").eq("game_id", game_id).execute()
            move_count = 0
            if current_log.data:
                move_count = current_log.data[0].get("move_count", 0)
            
            update_data = {
                "ended_at": time.time(),
                "move_count": move_count,
                "game_result": "abandoned",
                "game_status": "abandoned"
            }
            
            result = supabase.table("game_logs").update(update_data).eq("game_id", game_id).execute()
            print(f"Game abandonment logged for {game_id}: {result}")
            
        except Exception as e:
            print(f"Error logging game abandonment for {game_id}: {e}")

# WebSocket connection manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, Dict[str, WebSocket]] = {}

    async def connect(self, websocket: WebSocket, game_id: str, player_id: str):
        """Accept a new WebSocket connection and store it"""
        await websocket.accept()
        if game_id not in self.active_connections:
            self.active_connections[game_id] = {}
        self.active_connections[game_id][player_id] = websocket

    def disconnect(self, game_id: str, player_id: str):
        """Remove a WebSocket connection"""
        if game_id in self.active_connections:
            if player_id in self.active_connections[game_id]:
                del self.active_connections[game_id][player_id]
            if not self.active_connections[game_id]:
                del self.active_connections[game_id]

    async def send_personal_message(self, message: dict, game_id: str, player_id: str):
        """Send a message to a specific player"""
        if game_id in self.active_connections and player_id in self.active_connections[game_id]:
            await self.active_connections[game_id][player_id].send_json(message)

    async def broadcast(self, message: dict, game_id: str):
        """Broadcast a message to all players in a game"""
        if game_id in self.active_connections:
            for websocket in self.active_connections[game_id].values():
                await websocket.send_json(message)

# Initialize the connection manager
manager = ConnectionManager()

# Redis interaction helper
class RedisHelper:
    @staticmethod
    def game_key(game_id: str, key: str) -> str:
        """Create a Redis key for a game attribute"""
        return f"game:{game_id}:{key}"
    
    @staticmethod
    def set_with_ttl(key: str, value: str, ttl: int = GameConfig.REDIS_LONG_TTL):
        """Set a Redis key with a TTL"""
        redis.set(key, value, ex=ttl)
    
    @staticmethod
    def get(key: str) -> Optional[str]:
        """Get a value from Redis"""
        return redis.get(key)
    
    @staticmethod
    def delete(key: str):
        """Delete a key from Redis"""
        redis.delete(key)
    
    @staticmethod
    def set_if_not_exists(key: str, value: str, ttl: int = GameConfig.REDIS_LONG_TTL) -> bool:
        """Set a key only if it doesn't exist (with TTL)"""
        return redis.set(key, value, nx=True, ex=ttl)
    
    @staticmethod
    def get_multiple(keys: List[str]) -> List[Optional[str]]:
        """Get multiple values from Redis in a single operation"""
        pipe = redis.pipeline()
        for key in keys:
            pipe.get(key)
        return pipe.execute()
    
    @staticmethod
    def set_multiple(key_values: Dict[str, str], ttl: int = GameConfig.REDIS_LONG_TTL):
        """Set multiple key-value pairs with TTL in a single operation"""
        pipe = redis.pipeline()
        for key, value in key_values.items():
            pipe.set(key, value, ex=ttl)
        pipe.execute()

# Game state management
class GameStateManager:
    @staticmethod
    async def update_game_state(game_id: str, **kwargs):
        """Update game state in Redis and broadcast changes to clients"""
        key_values = {}
        
        for key, value in kwargs.items():
            if value is not None:
                key_values[RedisHelper.game_key(game_id, key)] = value
        
        RedisHelper.set_multiple(key_values)
        
        # Construct update message with all provided values
        update_msg = {
            "type": "game_state_update",
            **kwargs
        }
        
        await manager.broadcast(update_msg, game_id)
    
    @staticmethod
    def get_game_state(game_id: str, key: str) -> Optional[str]:
        """Get a specific game state value"""
        return RedisHelper.get(RedisHelper.game_key(game_id, key))
    
    @staticmethod
    def get_all_game_state(game_id: str) -> dict:
        """Get all game state values for a game"""
        # Define all known game state keys
        known_keys = [
            "fen", 
            "t1p1_seat",
            "t1p2_seat",
            "t2p1_seat",
            "t2p2_seat",
            "t1p1_ready",
            "t1p2_ready",
            "t2p1_ready",
            "t2p2_ready",
            "game_phase",
            "next_relevant_time"
        ]
        
        redis_keys = [RedisHelper.game_key(game_id, key) for key in known_keys]
        values = RedisHelper.get_multiple(redis_keys)
        
        return dict(zip(known_keys, values))

# Game phase management
class PhaseManager:
    @staticmethod
    async def transition_phase(game_id: str, new_phase: GamePhase):
        """Transition the game to a new phase and set appropriate timers"""
        current_time = time.time()
        next_time = None
        
        if new_phase in [GamePhase.TEAM1_SELECTION, GamePhase.TEAM2_SELECTION]:
            # Set selection phase timeout
            next_time = current_time + GameConfig.SELECTION_TIME
            
            # Immediately broadcast the correct initial timer
            await manager.broadcast(
                {
                    "type": "timer_update",
                    "phase": new_phase,
                    "seconds_remaining": GameConfig.SELECTION_TIME,
                    "key": uuid.uuid4().hex
                },
                game_id
            )
        
        # Update game state with new phase and next relevant time
        await GameStateManager.update_game_state(
            game_id=game_id,
            game_phase=new_phase,
            next_relevant_time=str(next_time) if next_time else None,
            t1p1_locked_in="false",
            t1p2_locked_in="false",
            t2p1_locked_in="false",
            t2p2_locked_in="false"
        )
        
        print(f"Game {game_id} transitioned to {new_phase}")
        
        if new_phase in [GamePhase.TEAM1_COMPUTING, GamePhase.TEAM2_COMPUTING]:
            # Add a small delay to ensure the phase transition broadcast is received
            await asyncio.sleep(0.05)
            
            # Perform team's move computation
            team_number = 1 if new_phase == GamePhase.TEAM1_COMPUTING else 2
            await MoveCalculator.compute_team_move(game_id, team_number)
    
    @staticmethod
    async def check_and_handle_phase_transitions(game_id: str):
        """Check if it's time to transition phases based on next_relevant_time"""
        # Get current phase and next relevant time
        game_phase = GameStateManager.get_game_state(game_id, "game_phase")
        next_time_str = GameStateManager.get_game_state(game_id, "next_relevant_time")
        
        # If we're in an invalid state, exit early
        if not game_phase or not next_time_str:
            return
        
        # If we're in a non-selection phase, we don't need to check for transitions
        if game_phase not in [GamePhase.TEAM1_SELECTION, GamePhase.TEAM2_SELECTION]:
            return
        
        # Calculate if we should transition based on team readiness
        ready_to_compute_early = False
        if game_phase == GamePhase.TEAM1_SELECTION:
            ready_to_compute_early = PhaseManager._check_team_ready(game_id, 1)
        elif game_phase == GamePhase.TEAM2_SELECTION:
            ready_to_compute_early = PhaseManager._check_team_ready(game_id, 2)
        
        # Calculate if we should transition based on time
        current_time = time.time()
        next_time = float(next_time_str)
        time_expired = current_time >= next_time
        
        # Determine if we need to transition
        should_transition = ready_to_compute_early or time_expired
        
        if should_transition:
            # Create a lock to prevent multiple transitions
            lock_key = f"game:{game_id}:transition_lock"
            if not RedisHelper.set_if_not_exists(lock_key, "1", ttl=5):  # 5-second TTL
                # Another process is already handling the transition
                return
                
            try:
                # Ensure we're still in the same phase (double-check)
                current_phase = GameStateManager.get_game_state(game_id, "game_phase")
                if current_phase != game_phase:
                    return
                
                # Send a single timer update with 0 seconds
                await manager.broadcast(
                    {
                        "type": "timer_update",
                        "phase": game_phase,
                        "seconds_remaining": 0,
                        "key": uuid.uuid4().hex
                    },
                    game_id
                )
                
                # Small delay to ensure the timer update is processed
                await asyncio.sleep(0.1)
                
                # Determine the next phase
                next_phase = None
                if game_phase == GamePhase.TEAM1_SELECTION:
                    next_phase = GamePhase.TEAM1_COMPUTING
                elif game_phase == GamePhase.TEAM2_SELECTION:
                    next_phase = GamePhase.TEAM2_COMPUTING
                
                if next_phase:
                    await PhaseManager.transition_phase(game_id, next_phase)
            finally:
                RedisHelper.delete(lock_key)
                
    @staticmethod
    def _check_team_ready(game_id: str, team_number: int) -> bool:
        """Check if a team is ready to compute (both players locked in or not present)"""
        p1_locked_in = GameStateManager.get_game_state(game_id, f"t{team_number}p1_locked_in") == "true"
        p2_locked_in = GameStateManager.get_game_state(game_id, f"t{team_number}p2_locked_in") == "true"
        p1_ready = GameStateManager.get_game_state(game_id, f"t{team_number}p1_ready") == "true"
        p2_ready = GameStateManager.get_game_state(game_id, f"t{team_number}p2_ready") == "true"
        
        return (p1_locked_in or not p1_ready) and (p2_locked_in or not p2_ready)

# Chess move computation
class MoveCalculator:
    @staticmethod
    async def compute_team_move(game_id: str, team_number: int):
        """Compute the move for a team based on player selections"""
        # Acquire computation lock with TTL to prevent endless locks
        lock_key = RedisHelper.game_key(game_id, "computation_lock")
        print(f"Acquiring computation lock for game {game_id}")
        
        if not RedisHelper.set_if_not_exists(lock_key, "1", ttl=30):  # 30-second TTL on lock
            print(f"Another process is already computing for game {game_id}")
            return
                
        try:
            # Get current FEN
            fen = GameStateManager.get_game_state(game_id, "fen")
            print(f"Computing move for team {team_number} in game {game_id} with FEN: {fen}")
            
            if not fen:
                await GameStateManager.update_game_state(
                    game_id=game_id,
                    game_phase=GamePhase.SETUP,
                    next_relevant_time=None
                )
                return
                
            # Get selections from both players on the team
            p1_selection = GameStateManager.get_game_state(game_id, f"t{team_number}p1_selection")
            p2_selection = GameStateManager.get_game_state(game_id, f"t{team_number}p2_selection")
            
            # Determine which board to use
            board = await MoveCalculator._select_best_board(team_number, p1_selection, p2_selection, fen)
            new_fen = board.fen()
            
            # Find the last move
            last_move = MoveCalculator._find_last_move(fen, new_fen)

            # Update the board state
            await GameStateManager.update_game_state(
                game_id=game_id,
                fen=new_fen,
                last_move=last_move
            )
                
            # Clear selections for this team
            await GameStateManager.update_game_state(
                game_id=game_id,
                **{f"t{team_number}p1_selection": "", f"t{team_number}p2_selection": ""}
            )
            
            # Increment move count in Supabase
            await GameLogger.increment_move_count(game_id)
            
            # Check if game is over
            if board.is_checkmate():
                # Determine winner and log game end
                winner = "Team 1" if board.turn == chess.BLACK else "Team 2"  # Opposite of current turn
                await GameLogger.log_game_end(game_id, "checkmate", winner)
                
                await GameStateManager.update_game_state(
                    game_id=game_id,
                    game_phase=GamePhase.COOLDOWN,
                    next_relevant_time=None
                )
                return
            
            # Check for stalemate
            if board.is_stalemate():
                await GameLogger.log_game_end(game_id, "stalemate")
                
                await GameStateManager.update_game_state(
                    game_id=game_id,
                    game_phase=GamePhase.COOLDOWN,
                    next_relevant_time=None
                )
                return
            
            # Check for draw by other means
            if board.is_insufficient_material() or board.is_seventyfive_moves() or board.is_fivefold_repetition():
                await GameLogger.log_game_end(game_id, "draw")
                
                await GameStateManager.update_game_state(
                    game_id=game_id,
                    game_phase=GamePhase.COOLDOWN,
                    next_relevant_time=None
                )
                return
            
            # Transition to next phase
            next_phase = GamePhase.TEAM2_SELECTION if team_number == 1 else GamePhase.TEAM1_SELECTION
            await PhaseManager.transition_phase(game_id, next_phase)
                
        finally:
            RedisHelper.delete(lock_key)
    
    @staticmethod
    async def _select_best_board(team_number: int, p1_selection: Optional[str], 
                                p2_selection: Optional[str], fen: str) -> chess.Board:
        """Select the best board based on player selections and engine analysis"""
        if p1_selection and p2_selection:
            # Analyze both positions
            p1_board = chess.Board(p1_selection)
            p1_info = engine.analyse(p1_board, chess.engine.Limit(time=GameConfig.STOCKFISH_ANALYSIS_TIME))

            p2_board = chess.Board(p2_selection)
            p2_info = engine.analyse(p2_board, chess.engine.Limit(time=GameConfig.STOCKFISH_ANALYSIS_TIME))
            
            # Compare scores from the team's perspective
            if team_number == 1:  # WHITE
                p1_score = p1_info["score"]
                p2_score = p2_info["score"]
                return p1_board if p1_score.white() > p2_score.white() else p2_board
            else:  # BLACK
                p1_score = p1_info["score"]
                p2_score = p2_info["score"]
                return p1_board if p1_score.black() > p2_score.black() else p2_board
                
        elif p1_selection:
            return chess.Board(p1_selection)
        elif p2_selection:
            return chess.Board(p2_selection)
        else:
            # No selections, make a random move
            board = chess.Board(fen)
            legal_moves = list(board.legal_moves)
            if legal_moves:
                move = random.choice(legal_moves)
                board.push(move)
            return board
    
    @staticmethod
    def _find_last_move(old_fen: str, new_fen: str) -> str:
        """Find the move that was made from old FEN to new FEN"""
        old_board = chess.Board(old_fen)
        # Loop through all legal moves on the old board
        for move in old_board.legal_moves:
            test_board = chess.Board(old_fen)
            test_board.push(move)
            # Check if this results in the same position as our new board
            if test_board.fen() == new_fen:
                return str(move)
        return ""

# Game initialization and management
class GameManager:
    @staticmethod
    async def start_game(game_id: str, is_private: bool = False):
        """Initialize a new game"""
        board = chess.Board()
        
        await GameStateManager.update_game_state(
            game_id=game_id,
            fen=board.fen(),
            game_phase=GamePhase.TEAM1_SELECTION,
            next_relevant_time=str(time.time() + GameConfig.SELECTION_TIME),
            created_time=str(time.time()),
            is_private="true" if is_private else "false"
        )
        
        await manager.broadcast(
            {
                "type": "timer_update",
                "seconds_remaining": round(GameConfig.SELECTION_TIME, 1),
                "key": uuid.uuid4().hex
            },
            game_id
        )
        
        # Log game start to Supabase
        seats = GameManager.get_all_seats(game_id)
        player_names = {seat: player_id for seat, player_id in seats.items() if player_id}
        await GameLogger.log_game_start(game_id, player_names)
        
        print(f"Game {game_id} started (Private: {is_private})")
    
    @staticmethod
    def initialize_player_seats(game_id: str, player_id: str):
        """Set up initial player seats or assign a player to an open seat"""
        print(f"Player {player_id} joined game {game_id}")

        t1p1_seat_key = RedisHelper.game_key(game_id, "t1p1_seat")
        
        if not redis.exists(t1p1_seat_key):
            # Initialize game state with empty values
            key_values = {}
            
            # Initialize seats
            for seat in ["t1p1_seat", "t1p2_seat", "t2p1_seat", "t2p2_seat"]:
                key_values[RedisHelper.game_key(game_id, seat)] = ""
            
            # Initialize player readiness
            for ready in ["t1p1_ready", "t1p2_ready", "t2p1_ready", "t2p2_ready"]:
                key_values[RedisHelper.game_key(game_id, ready)] = "false"
            
            # Initialize locked in status
            for locked in ["t1p1_locked_in", "t1p2_locked_in", "t2p1_locked_in", "t2p2_locked_in"]:
                key_values[RedisHelper.game_key(game_id, locked)] = "false"
            
            # Set initial phase
            key_values[RedisHelper.game_key(game_id, "game_phase")] = GamePhase.SETUP
            
            # Set player in first seat
            key_values[t1p1_seat_key] = player_id
            
            # Set all values at once
            RedisHelper.set_multiple(key_values)
        
        return
    
    @staticmethod
    def get_player_seat(game_id: str, player_id: str) -> Optional[str]:
        """Find which seat a player is in"""
        seat_keys = ["t1p1", "t1p2", "t2p1", "t2p2"]
        for seat in seat_keys:
            if GameStateManager.get_game_state(game_id, f"{seat}_seat") == player_id:
                return seat
        return None
        
    @staticmethod 
    def get_all_seats(game_id: str) -> Dict[str, Optional[str]]:
        """Get all seat assignments for a game"""
        seats = {}
        for seat in ["t1p1", "t1p2", "t2p1", "t2p2"]:
            seats[seat] = GameStateManager.get_game_state(game_id, f"{seat}_seat")
        return seats

# Player action handlers
class PlayerActionHandler:
    @staticmethod
    async def change_seat(game_id: str, player_id: str, new_seat: str):
        """Move a player to a different seat"""
        # Get current seat assignments
        seats = GameManager.get_all_seats(game_id)
        key_values = {}
        
        # If player is already in a seat, remove them from it
        current_seat = GameManager.get_player_seat(game_id, player_id)
        if current_seat:
            key_values[RedisHelper.game_key(game_id, f"{current_seat}_seat")] = ""
            key_values[RedisHelper.game_key(game_id, f"{current_seat}_ready")] = "false"
        
        # If requested seat is available, place player there
        if not seats[new_seat]:
            key_values[RedisHelper.game_key(game_id, f"{new_seat}_seat")] = player_id
        
        # Update Redis in a single operation
        RedisHelper.set_multiple(key_values)
        
        # Broadcast updated game state
        game_state = GameStateManager.get_all_game_state(game_id)
        await GameStateManager.update_game_state(game_id=game_id, **game_state)
    
    @staticmethod
    async def set_ready_status(game_id: str, player_id: str, ready: bool = True):
        """Set player ready status and potentially start the game"""
        # Find player's seat
        player_seat = GameManager.get_player_seat(game_id, player_id)
        
        if player_seat:
            # Set ready status
            RedisHelper.set_with_ttl(
                RedisHelper.game_key(game_id, f"{player_seat}_ready"), 
                "true" if ready else "false"
            )
            
            # Broadcast ready status
            game_state = GameStateManager.get_all_game_state(game_id)
            await GameStateManager.update_game_state(game_id=game_id, **game_state)
            
            # Check if all players are ready
            seats = GameManager.get_all_seats(game_id)
            all_ready = True
            occupied_seats = 0
            
            for seat, seat_player_id in seats.items():
                if seat_player_id:
                    occupied_seats += 1
                    if GameStateManager.get_game_state(game_id, f"{seat}_ready") != "true":
                        all_ready = False
            
            # Start game if all players are ready and we have at least two players
            if all_ready and occupied_seats >= 4:
                current_phase = GameStateManager.get_game_state(game_id, "game_phase")
                if current_phase == GamePhase.SETUP:
                    await GameManager.start_game(game_id)
    
    @staticmethod
    async def submit_move(game_id: str, player_id: str, move: str):
        """Submit a move for a player"""
        player_seat = GameManager.get_player_seat(game_id, player_id)
        
        if not player_seat:
            return
        
        # Check if it's this player's team's turn
        current_phase = GameStateManager.get_game_state(game_id, "game_phase")
        is_team1 = player_seat.startswith("t1")
        is_team2 = player_seat.startswith("t2")
        
        can_move = (is_team1 and current_phase == GamePhase.TEAM1_SELECTION) or \
                   (is_team2 and current_phase == GamePhase.TEAM2_SELECTION)
        
        if can_move:
            # Record the player's move
            await GameStateManager.update_game_state(
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
    
    @staticmethod
    async def lock_in_move(game_id: str, player_id: str):
        """Lock in a player's move selection"""
        player_seat = GameManager.get_player_seat(game_id, player_id)
        
        if player_seat:
            await GameStateManager.update_game_state(
                game_id=game_id,
                **{f"{player_seat}_locked_in": "true"}
            )
            print(f"Player {player_id} locked in move in seat {player_seat}")
    
    @staticmethod
    async def handle_disconnect(game_id: str, player_id: str):
        """Handle player disconnection"""
        # Find and clear player's seat
        player_seat = GameManager.get_player_seat(game_id, player_id)
        
        if player_seat:
            # Clear seat and ready status
            RedisHelper.set_with_ttl(RedisHelper.game_key(game_id, f"{player_seat}_seat"), "")
            RedisHelper.set_with_ttl(RedisHelper.game_key(game_id, f"{player_seat}_ready"), "false")
        
        # Notify other players
        await manager.broadcast(
            {
                "type": "player_disconnected", 
                "player_id": player_id
            },
            game_id
        )
        
        # Update seat info
        seats = GameManager.get_all_seats(game_id)
        formatted_seats = {seat: player_id for seat, player_id in seats.items()}
        
        await manager.broadcast(
            {
                "type": "player_seats",
                "seats": formatted_seats
            },
            game_id
        )

# WebSocket endpoint
@app.websocket("/ws/game/{game_id}/player/{player_id}")
async def websocket_endpoint(
    websocket: WebSocket, 
    game_id: str, 
    player_id: str, 
    is_private: bool = Query(False)
):
    # Accept connection and set up player
    await manager.connect(websocket, game_id, player_id)
    GameManager.initialize_player_seats(game_id, player_id)
    
    game_exists = redis.exists(RedisHelper.game_key(game_id, "created_time"))
    if not game_exists:
        RedisHelper.set_with_ttl(
            RedisHelper.game_key(game_id, "is_private"),
            "true" if is_private else "false"
        )
        RedisHelper.set_with_ttl(
            RedisHelper.game_key(game_id, "created_time"),
            str(time.time())
        )
    
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
    game_state = GameStateManager.get_all_game_state(game_id)
    await GameStateManager.update_game_state(game_id=game_id, **game_state)

    # Start background task to check game state
    background_task = asyncio.create_task(game_state_checker(game_id))

    try:
        while True:
            # Receive message from client
            data = await websocket.receive_json()
            
            # Process the message based on its type
            message_type = data.get("type", "")
            
            if message_type == "submit_move":
                await PlayerActionHandler.submit_move(
                    game_id, data["player_id"], data["move"]
                )
            
            elif message_type == "take_seat":
                await PlayerActionHandler.change_seat(
                    game_id, player_id, data["seat"]
                )
            
            elif message_type == "ready":
                await PlayerActionHandler.set_ready_status(
                    game_id, player_id, True
                )
            
            elif message_type == "not_ready":
                await PlayerActionHandler.set_ready_status(
                    game_id, player_id, False
                )

            elif message_type == "lock_in_move":
                await PlayerActionHandler.lock_in_move(
                    game_id, data["player_id"]
                )

    except WebSocketDisconnect:
        # Handle disconnect
        manager.disconnect(game_id, player_id)
        background_task.cancel()
        await PlayerActionHandler.handle_disconnect(game_id, player_id)
    except Exception as e:
        # Log any unexpected errors
        print(f"Error in websocket handler for game {game_id}, player {player_id}: {e}")
        # Attempt to clean up connections and tasks
        manager.disconnect(game_id, player_id)
        background_task.cancel()

# Background task to check game state and manage timers
async def game_state_checker(game_id: str):
    try:
        while True:
            await PhaseManager.check_and_handle_phase_transitions(game_id)
            await asyncio.sleep(0.5)  # Check every 0.5 seconds
    except asyncio.CancelledError:
        print(f"Game state checker for game {game_id} was cancelled")
    except Exception as e:
        print(f"Error in game state checker for game {game_id}: {e}")

@app.get("/api/games/available")
async def get_available_games():
    """Return a list of available games that can be joined"""
    try:
        # Get all game keys from Redis
        all_game_keys = redis.keys("game:*:game_phase")
        
        game_ids = set()
        
        # Extract unique game IDs
        for key in all_game_keys:
            parts = key.split(":")
            if len(parts) >= 2:
                game_ids.add(parts[1])
        
        available_games = []
        current_time = time.time()
        
        # Check each game for availability
        for game_id in game_ids:
            game_phase = RedisHelper.get(RedisHelper.game_key(game_id, "game_phase"))
            created_time = RedisHelper.get(RedisHelper.game_key(game_id, "created_time"))
            is_private = RedisHelper.get(RedisHelper.game_key(game_id, "is_private"))
            
            # Skip games with missing critical data
            if None in [game_phase, created_time]:
                continue
            
            # Get player seats
            t1p1_seat = RedisHelper.get(RedisHelper.game_key(game_id, "t1p1_seat")) or ""
            t1p2_seat = RedisHelper.get(RedisHelper.game_key(game_id, "t1p2_seat")) or ""
            t2p1_seat = RedisHelper.get(RedisHelper.game_key(game_id, "t2p1_seat")) or ""
            t2p2_seat = RedisHelper.get(RedisHelper.game_key(game_id, "t2p2_seat")) or ""
                        
            # Convert created_time to float
            created_time_float = float(created_time)
            
            # Check if game is available
            is_recent = (current_time - created_time_float) < 1200
            is_setup = game_phase == GamePhase.SETUP 
            is_private_game = is_private == "true"
            has_open_seats = not all([t1p1_seat, t1p2_seat, t2p1_seat, t2p2_seat])
            
            # For debugging: print time difference
            time_diff_minutes = (current_time - created_time_float) / 60
            
            if is_recent and is_setup and not is_private_game and has_open_seats:
                # Count occupied seats
                occupied_seat_count = sum(1 for seat in [t1p1_seat, t1p2_seat, t2p1_seat, t2p2_seat] if seat)
                
                available_games.append({
                    "game_id": game_id,
                    "created_time": created_time_float,
                    "occupied_seats": occupied_seat_count,
                    "phase": game_phase
                })
        
        # Sort games by creation time (newest first)
        available_games.sort(key=lambda g: g["created_time"], reverse=True)
        
        return JSONResponse(content={"games": available_games})
    
    except Exception as e:
        print(f"Error getting available games: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/games/stats")
async def get_game_stats():
    """Return game statistics from Supabase"""
    if not supabase:
        return JSONResponse(content={"error": "Game logging not configured"}, status_code=503)
    
    try:
        # Get basic stats
        all_games = supabase.table("game_logs").select("*").execute()
        
        if not all_games.data:
            return JSONResponse(content={
                "total_games": 0,
                "completed_games": 0,
                "in_progress_games": 0,
                "abandoned_games": 0,
                "average_moves": 0,
                "win_stats": {},
                "recent_games": []
            })
        
        games = all_games.data
        total_games = len(games)
        completed_games = len([g for g in games if g["game_status"] == "completed"])
        in_progress_games = len([g for g in games if g["game_status"] == "in_progress"])
        abandoned_games = len([g for g in games if g["game_status"] == "abandoned"])
        
        # Calculate average moves for completed games
        completed_with_moves = [g for g in games if g["game_status"] == "completed" and g["move_count"]]
        average_moves = sum(g["move_count"] for g in completed_with_moves) / len(completed_with_moves) if completed_with_moves else 0
        
        # Win statistics
        win_stats = {}
        for game in games:
            if game["game_status"] == "completed" and game["winner"]:
                winner = game["winner"]
                win_stats[winner] = win_stats.get(winner, 0) + 1
        
        # Recent games (last 10)
        recent_games = sorted(games, key=lambda x: x["started_at"], reverse=True)[:10]
        
        return JSONResponse(content={
            "total_games": total_games,
            "completed_games": completed_games,
            "in_progress_games": in_progress_games,
            "abandoned_games": abandoned_games,
            "average_moves": round(average_moves, 1),
            "win_stats": win_stats,
            "recent_games": recent_games
        })
    
    except Exception as e:
        print(f"Error getting game stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Run the app with uvicorn
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)