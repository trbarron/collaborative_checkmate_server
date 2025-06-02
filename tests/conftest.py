"""
Pytest configuration and fixtures for Collaborative Checkmate Server tests
"""

import pytest
import asyncio
import fakeredis
from unittest.mock import Mock, patch, MagicMock
from fastapi.testclient import TestClient
from fastapi import WebSocket

# Import your modules
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Mock the chess engine before importing main
with patch('chess.engine.SimpleEngine.popen_uci') as mock_engine:
    mock_engine.return_value = MagicMock()
    from main import app, manager, validated_manager
    from message_validator import MessageValidator, ValidatedConnectionManager
    import main

@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture
def fake_redis():
    """Create a fake Redis instance for testing"""
    fake_redis_instance = fakeredis.FakeRedis(decode_responses=True)
    
    # Enhance FakeRedis to properly handle set with nx=True
    original_set = fake_redis_instance.set
    def enhanced_set(key, value, nx=None, ex=None):
        if nx:
            # nx=True means set only if key doesn't exist
            if fake_redis_instance.exists(key):
                return False  # Key exists, don't set
            else:
                original_set(key, value, ex=ex)
                return True  # Key didn't exist, set successfully
        else:
            return original_set(key, value, ex=ex)
    
    fake_redis_instance.set = enhanced_set
    
    # Patch the redis instance in main module
    with patch.object(main, 'redis', fake_redis_instance):
        yield fake_redis_instance

@pytest.fixture
def test_client():
    """Create a test client for FastAPI"""
    return TestClient(app)

@pytest.fixture
def mock_supabase():
    """Mock Supabase client"""
    mock_client = Mock()
    mock_table = Mock()
    mock_client.table.return_value = mock_table
    mock_table.insert.return_value.execute.return_value = Mock(data=[])
    mock_table.update.return_value.eq.return_value.execute.return_value = Mock(data=[])
    mock_table.select.return_value.eq.return_value.execute.return_value = Mock(data=[])
    
    with patch('main.get_supabase_client', return_value=mock_client):
        yield mock_client

@pytest.fixture
def mock_chess_engine():
    """Mock chess engine for testing"""
    mock_engine = Mock()
    mock_info = Mock()
    mock_score = Mock()
    mock_score.white.return_value = 100
    mock_score.black.return_value = -100
    mock_info.__getitem__ = lambda self, key: mock_score if key == "score" else None
    mock_engine.analyse.return_value = mock_info
    
    # Mock chess.Board for move calculation tests
    with patch('main.chess') as mock_chess:
        # Mock Board class
        mock_board_class = Mock()
        mock_chess.Board = mock_board_class
        
        # Create mock board instances
        def create_mock_board(fen=None):
            mock_board = Mock()
            mock_board.fen.return_value = fen or "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
            
            # Mock legal moves for the starting position
            if fen == "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1":
                # Create a mock move object
                mock_move = Mock()
                mock_move.__str__ = lambda self: "e2e4"
                mock_board.legal_moves = [mock_move]
                
                # Mock push method
                def mock_push(move):
                    # After pushing e2e4, return the expected FEN
                    mock_board.fen.return_value = "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 1"
                
                mock_board.push = mock_push
            else:
                mock_board.legal_moves = []
            
            return mock_board
        
        mock_board_class.side_effect = create_mock_board
        
        with patch('main.engine', mock_engine):
            yield mock_engine

@pytest.fixture
def game_id():
    """Generate a test game ID"""
    return "test_game_123"

@pytest.fixture
def player_id():
    """Generate a test player ID"""
    return "test_player_456"

@pytest.fixture
def sample_client_messages():
    """Sample client messages for testing"""
    return {
        "take_seat": {
            "type": "take_seat",
            "seat": "t1p1"
        },
        "ready": {
            "type": "ready",
            "player_id": "test_player_456"
        },
        "submit_move": {
            "type": "submit_move",
            "player_id": "test_player_456",
            "move": "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 1"
        },
        "lock_in_move": {
            "type": "lock_in_move",
            "player_id": "test_player_456"
        },
        "heartbeat": {
            "type": "heartbeat",
            "timestamp": 1234567890.0,
            "connectionId": "test_connection_123"
        }
    }

@pytest.fixture
def sample_server_messages():
    """Sample server messages for testing"""
    return {
        "connection_established": {
            "type": "connection_established",
            "player_id": "test_player_456",
            "is_reconnection": False
        },
        "game_state_update": {
            "type": "game_state_update",
            "game_phase": "setup",
            "fen": "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
            "t1p1_seat": "test_player_456",
            "t1p1_ready": "true"
        },
        "player_disconnected": {
            "type": "player_disconnected",
            "player_id": "test_player_456",
            "grace_period": 30
        }
    }

@pytest.fixture
async def mock_websocket():
    """Create a mock WebSocket for testing"""
    websocket = Mock(spec=WebSocket)
    websocket.accept = Mock()
    websocket.send_json = Mock()
    websocket.receive_json = Mock()
    return websocket

@pytest.fixture
def clean_connection_manager():
    """Clean connection manager state between tests"""
    # Clear any existing connections
    manager.active_connections.clear()
    manager.disconnection_times.clear()
    yield manager
    # Clean up after test
    manager.active_connections.clear()
    manager.disconnection_times.clear() 