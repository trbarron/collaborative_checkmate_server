import json
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from typing import Dict
import asyncio
import uuid
import chess
from redis import Redis
import os
from dotenv import load_dotenv

load_dotenv()

app = FastAPI()
redis = Redis(
    host='redis-18058.c89.us-east-1-3.ec2.redns.redis-cloud.com',
    port=18058,
    db=0,
    decode_responses=True,
    password=os.getenv("REDIS_PASSWORD")
)
players_ready = {}


# Store active connections
class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, Dict[str, WebSocket]] = {}  # game_id -> {player_id: websocket}

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

async def set_game_state(game_id: str,
                   phase: str,
                   fen: str,
                   t1p1_selection: str = None,
                   t1p2_selection: str = None,
                   t2p1_selection: str = None,
                   t2p2_selection: str = None
                   ):
    
    if phase:
        redis.set(f"game:{game_id}:phase", phase)
    
    if fen:
        redis.set(f"game:{game_id}:fen", fen)
    
    if t1p1_selection:
        redis.set(f"game:{game_id}:t1p1_selection", t1p1_selection)
    
    if t1p2_selection:
        redis.set(f"game:{game_id}:t1p2_selection", t1p2_selection)
    
    if t2p1_selection:
        redis.set(f"game:{game_id}:t2p1_selection", t2p1_selection)

    if t2p2_selection:
        redis.set(f"game:{game_id}:t2p2_selection", t2p2_selection)
    
    print(f"Game state set to {phase} for game {game_id}")

    await manager.broadcast(
        {"type": "game_state_set", "game_id": game_id, "phase": phase, "fen": fen},
        game_id
    )


async def startGame(game_id: str):
    board = chess.Board()
    print(board.fen())
    await set_game_state(
        game_id=game_id,
        phase="team1_selection",
        fen=board.fen()
    )

def set_up_table(game_id: str, player_id: str):
    player_seats = redis.get(f"game:{game_id}:player_seats")
    if player_seats:
        player_seats = json.loads(player_seats)
        # take the first seat with value of None
        for seat, player in player_seats.items():
            if player is None:
                player_seats[seat] = player_id
                break
        redis.set(f"game:{game_id}:player_seats", json.dumps(player_seats))
    
    else:
        player_seats = {
            "t1p1": player_id,
            "t1p2": None,
            "t2p1": None,
            "t2p2": None
        }

        redis.set(f"game:{game_id}:player_seats", json.dumps(player_seats))

    return player_seats


@app.websocket("/ws/game/{game_id}")
async def websocket_endpoint(websocket: WebSocket, game_id: str):
    player_id = str("James R.")
    
    await manager.connect(websocket, game_id, player_id)
    player_seats = set_up_table(game_id, player_id)
    
    # Send initial connection confirmation
    await manager.send_personal_message(
        {"type": "connection_established",
         "player_id": player_id
        },
        game_id, 
        player_id
    )

    # send player seats to all players
    await manager.broadcast(
        {"type": "player_seats",
         "player_seats": player_seats
        },
        game_id
    )

    print("Connection established")
    
    try:
        while True:
            # Receive message from client
            data = await websocket.receive_json()
            
            # Process the message based on its type
            if data["type"] == "submit_move":
                pass
                
                
                
            elif data["type"] == "join_game":
                # Handle player joining the game
                team = data.get("team")
                # Add player to game in Redis
                
                # Broadcast to all players
                await manager.broadcast(
                    {
                        "type": "player_joined",
                        "player_id": player_id,
                        "team": team
                    },
                    game_id
                )
            
            elif data["type"] == "ready":
                # Handle player being ready
                print("player ready")
                players_ready[player_id] = True
                await manager.broadcast(
                    {"type": "player_ready", "player_id": player_id},
                    game_id
                )
                if all(players_ready.values()):
                    await startGame(game_id)

            elif data["type"] == "take_seat":
                # Handle player taking a seat
                seat = data["seat"]
                print(f"player {player_id} taking seat {seat}")
                player_seats = redis.get(f"game:{game_id}:player_seats")
                if player_seats:
                    player_seats = json.loads(player_seats)
                    if player_seats[seat] == player_id:
                        player_seats[seat] = None
                    elif player_seats[seat] is None:
                        # make sure the player is not already in another seat
                        for temp_seat, temp_player in player_seats.items():
                            if temp_player == player_id:
                                player_seats[temp_seat] = None
                        player_seats[seat] = player_id
                    redis.set(f"game:{game_id}:player_seats", json.dumps(player_seats))
                    print(f"player_seats: {player_seats}")
                    
                    await manager.broadcast(
                        {"type": "player_seats",
                        "player_seats": player_seats
                        },
                        game_id
                    )


    except WebSocketDisconnect:
        # Handle disconnect
        manager.disconnect(game_id, player_id)
        await manager.broadcast(
            {"type": "player_disconnected", "player_id": player_id},
            game_id
        )

# Game timer coroutine example
async def game_timer(game_id: str):
    # This would run as a background task
    while True:
        # Check game state from Redis
        # Update timers
        # Broadcast timer updates
        await manager.broadcast(
            {
                "type": "timer_update",
                "phase": "team1_selection",
                "seconds_remaining": 3  # This would be calculated
            },
            game_id
        )
        
        await asyncio.sleep(1)  # Update every second