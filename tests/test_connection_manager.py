"""
Tests for WebSocket connection management
"""

import pytest
import time
from unittest.mock import Mock, AsyncMock
from main import ConnectionManager, GameConfig

class TestConnectionManager:
    """Test ConnectionManager functionality"""
    
    @pytest.fixture
    def connection_manager(self):
        """Create a fresh ConnectionManager instance"""
        return ConnectionManager()
    
    @pytest.fixture
    def mock_websocket(self):
        """Create a mock WebSocket"""
        websocket = Mock()
        websocket.accept = AsyncMock()
        websocket.send_json = AsyncMock()
        return websocket
    
    @pytest.mark.asyncio
    async def test_connect_new_game(self, connection_manager, mock_websocket):
        """Test connecting to a new game"""
        game_id = "test_game"
        player_id = "test_player"
        
        await connection_manager.connect(mock_websocket, game_id, player_id)
        
        # Check that websocket was accepted
        mock_websocket.accept.assert_called_once()
        
        # Check that connection was stored
        assert game_id in connection_manager.active_connections
        assert player_id in connection_manager.active_connections[game_id]
        assert connection_manager.active_connections[game_id][player_id] == mock_websocket
    
    @pytest.mark.asyncio
    async def test_connect_existing_game(self, connection_manager, mock_websocket):
        """Test connecting to an existing game"""
        game_id = "test_game"
        player1_id = "player1"
        player2_id = "player2"
        
        # Connect first player
        websocket1 = Mock()
        websocket1.accept = AsyncMock()
        await connection_manager.connect(websocket1, game_id, player1_id)
        
        # Connect second player to same game
        await connection_manager.connect(mock_websocket, game_id, player2_id)
        
        # Check that both connections are stored
        assert len(connection_manager.active_connections[game_id]) == 2
        assert connection_manager.active_connections[game_id][player1_id] == websocket1
        assert connection_manager.active_connections[game_id][player2_id] == mock_websocket
    
    @pytest.mark.asyncio
    async def test_connect_clears_disconnection_time(self, connection_manager, mock_websocket):
        """Test that connecting clears any existing disconnection time"""
        game_id = "test_game"
        player_id = "test_player"
        
        # Set up disconnection time
        connection_manager.disconnection_times[game_id] = {player_id: time.time() - 10}
        
        await connection_manager.connect(mock_websocket, game_id, player_id)
        
        # Check that disconnection time was cleared
        assert game_id not in connection_manager.disconnection_times or \
               player_id not in connection_manager.disconnection_times[game_id]
    
    def test_disconnect_single_player(self, connection_manager, mock_websocket):
        """Test disconnecting a single player"""
        game_id = "test_game"
        player_id = "test_player"
        
        # Set up connection
        connection_manager.active_connections[game_id] = {player_id: mock_websocket}
        
        connection_manager.disconnect(game_id, player_id)
        
        # Check that connection was removed
        assert game_id not in connection_manager.active_connections
        
        # Check that disconnection time was recorded
        assert game_id in connection_manager.disconnection_times
        assert player_id in connection_manager.disconnection_times[game_id]
        assert isinstance(connection_manager.disconnection_times[game_id][player_id], float)
    
    def test_disconnect_multiple_players(self, connection_manager):
        """Test disconnecting one player when multiple are connected"""
        game_id = "test_game"
        player1_id = "player1"
        player2_id = "player2"
        
        websocket1 = Mock()
        websocket2 = Mock()
        
        # Set up connections
        connection_manager.active_connections[game_id] = {
            player1_id: websocket1,
            player2_id: websocket2
        }
        
        connection_manager.disconnect(game_id, player1_id)
        
        # Check that only player1 was removed
        assert game_id in connection_manager.active_connections
        assert player1_id not in connection_manager.active_connections[game_id]
        assert player2_id in connection_manager.active_connections[game_id]
        
        # Check disconnection time was recorded
        assert player1_id in connection_manager.disconnection_times[game_id]
    
    def test_is_within_grace_period_true(self, connection_manager):
        """Test grace period check when within period"""
        game_id = "test_game"
        player_id = "test_player"
        
        # Set disconnection time to 10 seconds ago
        connection_manager.disconnection_times[game_id] = {
            player_id: time.time() - 10
        }
        
        assert connection_manager.is_within_grace_period(game_id, player_id) is True
    
    def test_is_within_grace_period_false(self, connection_manager):
        """Test grace period check when outside period"""
        game_id = "test_game"
        player_id = "test_player"
        
        # Set disconnection time to more than grace period ago
        connection_manager.disconnection_times[game_id] = {
            player_id: time.time() - (GameConfig.RECONNECTION_GRACE_PERIOD + 10)
        }
        
        assert connection_manager.is_within_grace_period(game_id, player_id) is False
    
    def test_is_within_grace_period_no_record(self, connection_manager):
        """Test grace period check when no disconnection record exists"""
        game_id = "test_game"
        player_id = "test_player"
        
        assert connection_manager.is_within_grace_period(game_id, player_id) is False
    
    def test_cleanup_expired_disconnections(self, connection_manager):
        """Test cleaning up expired disconnection records"""
        game_id = "test_game"
        current_time = time.time()
        
        # Set up disconnection times - one expired, one not
        connection_manager.disconnection_times[game_id] = {
            "expired_player": current_time - (GameConfig.RECONNECTION_GRACE_PERIOD + 10),
            "active_player": current_time - 10
        }
        
        connection_manager.cleanup_expired_disconnections(game_id)
        
        # Check that expired record was removed
        assert "expired_player" not in connection_manager.disconnection_times[game_id]
        assert "active_player" in connection_manager.disconnection_times[game_id]
    
    def test_cleanup_expired_disconnections_empty_game(self, connection_manager):
        """Test cleanup when all disconnections are expired"""
        game_id = "test_game"
        current_time = time.time()
        
        # Set up all expired disconnections
        connection_manager.disconnection_times[game_id] = {
            "player1": current_time - (GameConfig.RECONNECTION_GRACE_PERIOD + 10),
            "player2": current_time - (GameConfig.RECONNECTION_GRACE_PERIOD + 20)
        }
        
        connection_manager.cleanup_expired_disconnections(game_id)
        
        # Check that entire game record was removed
        assert game_id not in connection_manager.disconnection_times
    
    @pytest.mark.asyncio
    async def test_send_personal_message_success(self, connection_manager, mock_websocket):
        """Test sending a personal message successfully"""
        game_id = "test_game"
        player_id = "test_player"
        message = {"type": "test", "data": "hello"}
        
        # Set up connection
        connection_manager.active_connections[game_id] = {player_id: mock_websocket}
        
        await connection_manager.send_personal_message(message, game_id, player_id)
        
        # Check that message was sent
        mock_websocket.send_json.assert_called_once_with(message)
    
    @pytest.mark.asyncio
    async def test_send_personal_message_connection_failed(self, connection_manager, mock_websocket):
        """Test handling failed message sending"""
        game_id = "test_game"
        player_id = "test_player"
        message = {"type": "test", "data": "hello"}
        
        # Set up connection with failing websocket
        mock_websocket.send_json.side_effect = Exception("Connection failed")
        connection_manager.active_connections[game_id] = {player_id: mock_websocket}
        
        await connection_manager.send_personal_message(message, game_id, player_id)
        
        # Check that connection was removed after failure
        assert game_id not in connection_manager.active_connections
        
        # Check that disconnection time was recorded
        assert game_id in connection_manager.disconnection_times
        assert player_id in connection_manager.disconnection_times[game_id]
    
    @pytest.mark.asyncio
    async def test_send_personal_message_no_connection(self, connection_manager):
        """Test sending message when no connection exists"""
        game_id = "test_game"
        player_id = "test_player"
        message = {"type": "test", "data": "hello"}
        
        # Should not raise an exception
        await connection_manager.send_personal_message(message, game_id, player_id)
    
    @pytest.mark.asyncio
    async def test_broadcast_success(self, connection_manager):
        """Test broadcasting to multiple players successfully"""
        game_id = "test_game"
        message = {"type": "broadcast", "data": "hello all"}
        
        # Set up multiple connections
        websocket1 = Mock()
        websocket1.send_json = AsyncMock()
        websocket2 = Mock()
        websocket2.send_json = AsyncMock()
        
        connection_manager.active_connections[game_id] = {
            "player1": websocket1,
            "player2": websocket2
        }
        
        await connection_manager.broadcast(message, game_id)
        
        # Check that message was sent to all players
        websocket1.send_json.assert_called_once_with(message)
        websocket2.send_json.assert_called_once_with(message)
    
    @pytest.mark.asyncio
    async def test_broadcast_with_failed_connection(self, connection_manager):
        """Test broadcasting when one connection fails"""
        game_id = "test_game"
        message = {"type": "broadcast", "data": "hello all"}
        
        # Set up connections - one working, one failing
        websocket1 = Mock()
        websocket1.send_json = AsyncMock()
        websocket2 = Mock()
        websocket2.send_json = AsyncMock(side_effect=Exception("Connection failed"))
        
        connection_manager.active_connections[game_id] = {
            "player1": websocket1,
            "player2": websocket2
        }
        
        await connection_manager.broadcast(message, game_id)
        
        # Check that working connection still received message
        websocket1.send_json.assert_called_once_with(message)
        
        # Check that failed connection was removed
        assert "player2" not in connection_manager.active_connections[game_id]
        assert "player1" in connection_manager.active_connections[game_id]
        
        # Check that disconnection time was recorded for failed connection
        assert "player2" in connection_manager.disconnection_times[game_id]
    
    @pytest.mark.asyncio
    async def test_broadcast_no_game(self, connection_manager):
        """Test broadcasting when game doesn't exist"""
        game_id = "nonexistent_game"
        message = {"type": "broadcast", "data": "hello"}
        
        # Should not raise an exception
        await connection_manager.broadcast(message, game_id) 