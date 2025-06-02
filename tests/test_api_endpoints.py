"""
Tests for HTTP API endpoints
"""

import pytest
import time
from unittest.mock import patch, Mock
from fastapi.testclient import TestClient
from main import app, GameStateManager, RedisHelper, GamePhase

class TestAPIEndpoints:
    """Test HTTP API endpoints"""
    
    def test_get_available_games_empty(self, test_client, fake_redis):
        """Test getting available games when none exist"""
        response = test_client.get("/api/games/available")
        
        assert response.status_code == 200
        data = response.json()
        assert "games" in data
        assert len(data["games"]) == 0
    
    def test_get_available_games_with_games(self, test_client, fake_redis):
        """Test getting available games when some exist"""
        # Create some test games
        current_time = time.time()
        
        # Available game (recent, setup phase, not private, has open seats)
        game1_id = "available_game"
        RedisHelper.set_with_ttl(RedisHelper.game_key(game1_id, "game_phase"), GamePhase.SETUP)
        RedisHelper.set_with_ttl(RedisHelper.game_key(game1_id, "created_time"), str(current_time))
        RedisHelper.set_with_ttl(RedisHelper.game_key(game1_id, "is_private"), "false")
        RedisHelper.set_with_ttl(RedisHelper.game_key(game1_id, "t1p1_seat"), "player1")
        RedisHelper.set_with_ttl(RedisHelper.game_key(game1_id, "t1p2_seat"), "")
        RedisHelper.set_with_ttl(RedisHelper.game_key(game1_id, "t2p1_seat"), "")
        RedisHelper.set_with_ttl(RedisHelper.game_key(game1_id, "t2p2_seat"), "")
        
        # Private game (should not appear)
        game2_id = "private_game"
        RedisHelper.set_with_ttl(RedisHelper.game_key(game2_id, "game_phase"), GamePhase.SETUP)
        RedisHelper.set_with_ttl(RedisHelper.game_key(game2_id, "created_time"), str(current_time))
        RedisHelper.set_with_ttl(RedisHelper.game_key(game2_id, "is_private"), "true")
        RedisHelper.set_with_ttl(RedisHelper.game_key(game2_id, "t1p1_seat"), "player1")
        
        # Old game (should not appear)
        game3_id = "old_game"
        old_time = current_time - 2000  # More than 20 minutes old
        RedisHelper.set_with_ttl(RedisHelper.game_key(game3_id, "game_phase"), GamePhase.SETUP)
        RedisHelper.set_with_ttl(RedisHelper.game_key(game3_id, "created_time"), str(old_time))
        RedisHelper.set_with_ttl(RedisHelper.game_key(game3_id, "is_private"), "false")
        
        # In-progress game (should not appear)
        game4_id = "in_progress_game"
        RedisHelper.set_with_ttl(RedisHelper.game_key(game4_id, "game_phase"), GamePhase.TEAM1_SELECTION)
        RedisHelper.set_with_ttl(RedisHelper.game_key(game4_id, "created_time"), str(current_time))
        RedisHelper.set_with_ttl(RedisHelper.game_key(game4_id, "is_private"), "false")
        
        response = test_client.get("/api/games/available")
        
        assert response.status_code == 200
        data = response.json()
        assert "games" in data
        assert len(data["games"]) == 1
        
        game = data["games"][0]
        assert game["game_id"] == game1_id
        assert game["occupied_seats"] == 1
        assert game["phase"] == GamePhase.SETUP
    
    def test_check_reconnection_status_valid(self, test_client, fake_redis, clean_connection_manager):
        """Test checking reconnection status for a valid reconnection"""
        game_id = "test_game"
        player_id = "test_player"
        
        # Set up game state
        RedisHelper.set_with_ttl(RedisHelper.game_key(game_id, "game_phase"), GamePhase.TEAM1_SELECTION)
        RedisHelper.set_with_ttl(RedisHelper.game_key(game_id, "t1p1_seat"), player_id)
        
        # Simulate disconnection within grace period
        clean_connection_manager.disconnection_times[game_id] = {player_id: time.time() - 10}  # 10 seconds ago
        
        response = test_client.get(f"/api/games/{game_id}/reconnection/{player_id}")
        
        assert response.status_code == 200
        data = response.json()
        assert data["can_reconnect"] is True
        assert data["player_seat"] == "t1p1"
        assert data["game_phase"] == GamePhase.TEAM1_SELECTION
        assert data["remaining_grace_time"] > 0
    
    def test_check_reconnection_status_expired(self, test_client, fake_redis, clean_connection_manager):
        """Test checking reconnection status when grace period expired"""
        game_id = "test_game"
        player_id = "test_player"
        
        # Set up game state
        RedisHelper.set_with_ttl(RedisHelper.game_key(game_id, "game_phase"), GamePhase.TEAM1_SELECTION)
        RedisHelper.set_with_ttl(RedisHelper.game_key(game_id, "t1p1_seat"), player_id)
        
        # Simulate disconnection outside grace period
        clean_connection_manager.disconnection_times[game_id] = {player_id: time.time() - 100}  # 100 seconds ago
        
        response = test_client.get(f"/api/games/{game_id}/reconnection/{player_id}")
        
        assert response.status_code == 200
        data = response.json()
        assert data["can_reconnect"] is False
        assert data["remaining_grace_time"] == 0
    
    def test_check_reconnection_status_no_seat(self, test_client, fake_redis, clean_connection_manager):
        """Test checking reconnection status when player has no seat"""
        game_id = "test_game"
        player_id = "test_player"
        
        # Set up game state without player having a seat
        RedisHelper.set_with_ttl(RedisHelper.game_key(game_id, "game_phase"), GamePhase.TEAM1_SELECTION)
        
        response = test_client.get(f"/api/games/{game_id}/reconnection/{player_id}")
        
        assert response.status_code == 200
        data = response.json()
        assert data["can_reconnect"] is False
        assert data["player_seat"] is None
    
    @patch('main.get_supabase_client')
    def test_get_game_stats_no_supabase(self, mock_get_supabase, test_client):
        """Test getting game stats when Supabase is not available"""
        mock_get_supabase.return_value = None
        
        response = test_client.get("/api/games/stats")
        
        assert response.status_code == 503
        data = response.json()
        assert "error" in data
        assert "not configured" in data["error"]
    
    @patch('main.get_supabase_client')
    def test_get_game_stats_empty(self, mock_get_supabase, test_client):
        """Test getting game stats when no games exist"""
        # Mock Supabase client
        mock_client = Mock()
        mock_table = Mock()
        mock_client.table.return_value = mock_table
        mock_table.select.return_value.execute.return_value = Mock(data=[])
        mock_get_supabase.return_value = mock_client
        
        response = test_client.get("/api/games/stats")
        
        assert response.status_code == 200
        data = response.json()
        assert data["total_games"] == 0
        assert data["completed_games"] == 0
        assert data["in_progress_games"] == 0
        assert data["abandoned_games"] == 0
        assert data["average_moves"] == 0
        assert data["win_stats"] == {}
        assert data["recent_games"] == []
    
    @patch('main.get_supabase_client')
    def test_get_game_stats_with_data(self, mock_get_supabase, test_client):
        """Test getting game stats with actual data"""
        # Mock game data
        mock_games = [
            {
                "game_id": "game1",
                "game_status": "completed",
                "move_count": 20,
                "winner": "Team 1",
                "started_at": "2023-01-01T00:00:00"
            },
            {
                "game_id": "game2", 
                "game_status": "completed",
                "move_count": 30,
                "winner": "Team 2",
                "started_at": "2023-01-02T00:00:00"
            },
            {
                "game_id": "game3",
                "game_status": "in_progress",
                "move_count": 10,
                "winner": None,
                "started_at": "2023-01-03T00:00:00"
            },
            {
                "game_id": "game4",
                "game_status": "abandoned",
                "move_count": 5,
                "winner": None,
                "started_at": "2023-01-04T00:00:00"
            }
        ]
        
        # Mock Supabase client
        mock_client = Mock()
        mock_table = Mock()
        mock_client.table.return_value = mock_table
        mock_table.select.return_value.execute.return_value = Mock(data=mock_games)
        mock_get_supabase.return_value = mock_client
        
        response = test_client.get("/api/games/stats")
        
        assert response.status_code == 200
        data = response.json()
        assert data["total_games"] == 4
        assert data["completed_games"] == 2
        assert data["in_progress_games"] == 1
        assert data["abandoned_games"] == 1
        assert data["average_moves"] == 25.0  # (20 + 30) / 2
        assert data["win_stats"]["Team 1"] == 1
        assert data["win_stats"]["Team 2"] == 1
        assert len(data["recent_games"]) == 4

class TestAPIErrorHandling:
    """Test API error handling"""
    
    def test_get_available_games_redis_error(self, test_client):
        """Test handling Redis errors in available games endpoint"""
        with patch('main.redis') as mock_redis:
            mock_redis.keys.side_effect = Exception("Redis connection error")
            
            response = test_client.get("/api/games/available")
            
            assert response.status_code == 500
            data = response.json()
            assert "detail" in data
    
    def test_check_reconnection_status_error(self, test_client):
        """Test handling errors in reconnection status endpoint"""
        with patch('main.GameManager.get_player_seat') as mock_get_seat:
            mock_get_seat.side_effect = Exception("Database error")
            
            response = test_client.get("/api/games/test_game/reconnection/test_player")
            
            assert response.status_code == 500
            data = response.json()
            assert "detail" in data
    
    @patch('main.get_supabase_client')
    def test_get_game_stats_supabase_error(self, mock_get_supabase, test_client):
        """Test handling Supabase errors in game stats endpoint"""
        # Mock Supabase client that raises an error
        mock_client = Mock()
        mock_table = Mock()
        mock_client.table.return_value = mock_table
        mock_table.select.side_effect = Exception("Supabase error")
        mock_get_supabase.return_value = mock_client
        
        response = test_client.get("/api/games/stats")
        
        assert response.status_code == 500
        data = response.json()
        assert "detail" in data

class TestAPIValidation:
    """Test API input validation"""
    
    def test_reconnection_status_invalid_game_id(self, test_client, fake_redis):
        """Test reconnection status with invalid characters in game ID"""
        # This should still work as FastAPI path parameters are quite permissive
        response = test_client.get("/api/games/invalid-game-id/reconnection/player123")
        
        assert response.status_code == 200  # Should not fail on invalid game ID format
    
    def test_reconnection_status_empty_game_id(self, test_client):
        """Test reconnection status with empty game ID"""
        # This should result in a 404 as the path won't match
        response = test_client.get("/api/games//reconnection/player123")
        
        assert response.status_code == 404
    
    def test_available_games_query_parameters(self, test_client, fake_redis):
        """Test available games endpoint with query parameters"""
        # Should ignore unknown query parameters
        response = test_client.get("/api/games/available?unknown_param=value")
        
        assert response.status_code == 200
        data = response.json()
        assert "games" in data
