"""
Tests for core game logic functionality
"""

import pytest
import time
from unittest.mock import patch, Mock, AsyncMock
from main import (
    GameManager, GameStateManager, PlayerActionHandler, 
    PhaseManager, MoveCalculator, GamePhase, RedisHelper
)

class TestGameManager:
    """Test GameManager functionality"""
    
    @pytest.mark.asyncio
    async def test_initialize_player_seats_new_game(self, fake_redis, game_id, player_id):
        """Test initializing player seats for a new game"""
        seat = GameManager.initialize_player_seats(game_id, player_id)
        
        assert seat == "t1p1"  # First player gets first seat
        
        # Check that game state was initialized
        assert GameStateManager.get_game_state(game_id, "t1p1_seat") == player_id
        assert GameStateManager.get_game_state(game_id, "game_phase") == GamePhase.SETUP
        assert GameStateManager.get_game_state(game_id, "move_count") == "0"
    
    @pytest.mark.asyncio
    async def test_initialize_player_seats_existing_game(self, fake_redis, game_id):
        """Test adding players to an existing game"""
        # Initialize first player
        player1 = "player1"
        seat1 = GameManager.initialize_player_seats(game_id, player1)
        assert seat1 == "t1p1"
        
        # Add second player
        player2 = "player2"
        seat2 = GameManager.initialize_player_seats(game_id, player2)
        assert seat2 == "t1p2"
        
        # Add third player
        player3 = "player3"
        seat3 = GameManager.initialize_player_seats(game_id, player3)
        assert seat3 == "t2p1"
        
        # Add fourth player
        player4 = "player4"
        seat4 = GameManager.initialize_player_seats(game_id, player4)
        assert seat4 == "t2p2"
    
    def test_get_player_seat(self, fake_redis, game_id, player_id):
        """Test getting a player's seat"""
        # Player not in game
        assert GameManager.get_player_seat(game_id, player_id) is None
        
        # Add player to game
        GameManager.initialize_player_seats(game_id, player_id)
        assert GameManager.get_player_seat(game_id, player_id) == "t1p1"
    
    def test_get_all_seats(self, fake_redis, game_id):
        """Test getting all seat assignments"""
        # Initialize some players
        GameManager.initialize_player_seats(game_id, "player1")
        GameManager.initialize_player_seats(game_id, "player2")
        
        seats = GameManager.get_all_seats(game_id)
        
        assert seats["t1p1"] == "player1"
        assert seats["t1p2"] == "player2"
        assert seats["t2p1"] == ""  # Empty seat
        assert seats["t2p2"] == ""  # Empty seat

class TestGameStateManager:
    """Test GameStateManager functionality"""
    
    @pytest.mark.asyncio
    async def test_update_game_state(self, fake_redis, game_id):
        """Test updating game state"""
        await GameStateManager.update_game_state(
            game_id=game_id,
            game_phase=GamePhase.TEAM1_SELECTION,
            fen="test_fen",
            t1p1_seat="player1"
        )
        
        # Check that values were stored
        assert GameStateManager.get_game_state(game_id, "game_phase") == GamePhase.TEAM1_SELECTION
        assert GameStateManager.get_game_state(game_id, "fen") == "test_fen"
        assert GameStateManager.get_game_state(game_id, "t1p1_seat") == "player1"
    
    def test_get_game_state(self, fake_redis, game_id):
        """Test getting individual game state values"""
        # Set a value
        RedisHelper.set_with_ttl(RedisHelper.game_key(game_id, "test_key"), "test_value")
        
        # Get the value
        assert GameStateManager.get_game_state(game_id, "test_key") == "test_value"
        assert GameStateManager.get_game_state(game_id, "nonexistent_key") is None
    
    def test_get_all_game_state(self, fake_redis, game_id):
        """Test getting all game state values"""
        # Set some values
        RedisHelper.set_with_ttl(RedisHelper.game_key(game_id, "fen"), "test_fen")
        RedisHelper.set_with_ttl(RedisHelper.game_key(game_id, "game_phase"), "setup")
        RedisHelper.set_with_ttl(RedisHelper.game_key(game_id, "t1p1_seat"), "player1")
        
        state = GameStateManager.get_all_game_state(game_id)
        
        assert state["fen"] == "test_fen"
        assert state["game_phase"] == "setup"
        assert state["t1p1_seat"] == "player1"
        # Other keys should be None
        assert state["t1p2_seat"] is None

class TestPlayerActionHandler:
    """Test PlayerActionHandler functionality"""
    
    @pytest.mark.asyncio
    async def test_change_seat(self, fake_redis, game_id):
        """Test changing player seats"""
        # Initialize players
        GameManager.initialize_player_seats(game_id, "player1")
        GameManager.initialize_player_seats(game_id, "player2")
        
        # Player1 is in t1p1, move to t2p1
        await PlayerActionHandler.change_seat(game_id, "player1", "t2p1")
        
        # Check seat assignments
        assert GameStateManager.get_game_state(game_id, "t1p1_seat") == ""  # Old seat empty
        assert GameStateManager.get_game_state(game_id, "t2p1_seat") == "player1"  # New seat occupied
        assert GameStateManager.get_game_state(game_id, "t1p2_seat") == "player2"  # Other player unchanged
    
    @pytest.mark.asyncio
    async def test_set_ready_status(self, fake_redis, game_id, mock_supabase):
        """Test setting player ready status"""
        # Initialize player
        GameManager.initialize_player_seats(game_id, "player1")
        
        # Set ready
        await PlayerActionHandler.set_ready_status(game_id, "player1", True)
        assert GameStateManager.get_game_state(game_id, "t1p1_ready") == "true"
        
        # Set not ready
        await PlayerActionHandler.set_ready_status(game_id, "player1", False)
        assert GameStateManager.get_game_state(game_id, "t1p1_ready") == "false"
    
    @pytest.mark.asyncio
    async def test_submit_move(self, fake_redis, game_id):
        """Test submitting a move"""
        # Initialize player and set game phase
        GameManager.initialize_player_seats(game_id, "player1")
        await GameStateManager.update_game_state(
            game_id=game_id,
            game_phase=GamePhase.TEAM1_SELECTION
        )
        
        # Submit move
        test_fen = "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 1"
        await PlayerActionHandler.submit_move(game_id, "player1", test_fen)
        
        # Check that move was recorded
        assert GameStateManager.get_game_state(game_id, "t1p1_selection") == test_fen
    
    @pytest.mark.asyncio
    async def test_submit_move_wrong_phase(self, fake_redis, game_id):
        """Test that moves can't be submitted in wrong phase"""
        # Initialize player and set wrong phase
        GameManager.initialize_player_seats(game_id, "player1")
        await GameStateManager.update_game_state(
            game_id=game_id,
            game_phase=GamePhase.TEAM2_SELECTION  # Team 1 player can't move
        )
        
        # Try to submit move
        test_fen = "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 1"
        await PlayerActionHandler.submit_move(game_id, "player1", test_fen)
        
        # Move should not be recorded
        assert GameStateManager.get_game_state(game_id, "t1p1_selection") != test_fen
    
    @pytest.mark.asyncio
    async def test_lock_in_move(self, fake_redis, game_id):
        """Test locking in a move"""
        # Initialize player
        GameManager.initialize_player_seats(game_id, "player1")
        
        # Lock in move
        await PlayerActionHandler.lock_in_move(game_id, "player1")
        
        # Check that move is locked
        assert GameStateManager.get_game_state(game_id, "t1p1_locked_in") == "true"

    @pytest.mark.asyncio
    async def test_seat_recovery_during_selection_phase(self, fake_redis, game_id):
        """Test automatic seat recovery during selection phase"""
        # Set up game with active team selection phase
        await GameStateManager.update_game_state(
            game_id=game_id,
            game_phase=GamePhase.TEAM1_SELECTION
        )
        
        # Create a scenario where only one team1 seat is available
        RedisHelper.set_with_ttl(RedisHelper.game_key(game_id, "t1p1_seat"), "existing_player")
        RedisHelper.set_with_ttl(RedisHelper.game_key(game_id, "t1p2_seat"), "")  # Empty
        RedisHelper.set_with_ttl(RedisHelper.game_key(game_id, "t2p1_seat"), "other_player1")
        RedisHelper.set_with_ttl(RedisHelper.game_key(game_id, "t2p2_seat"), "other_player2")
        
        # Attempt recovery for a player
        recovered_seat = await GameManager.attempt_seat_recovery(game_id, "test_player")
        
        # Should be assigned to the only available team1 seat
        assert recovered_seat == "t1p2"
        assert GameStateManager.get_game_state(game_id, "t1p2_seat") == "test_player"
    
    @pytest.mark.asyncio
    async def test_seat_recovery_one_seat_available(self, fake_redis, game_id):
        """Test seat recovery when only one seat is available in the entire game"""
        # Set up game with only one empty seat
        RedisHelper.set_with_ttl(RedisHelper.game_key(game_id, "t1p1_seat"), "player1")
        RedisHelper.set_with_ttl(RedisHelper.game_key(game_id, "t1p2_seat"), "player2")
        RedisHelper.set_with_ttl(RedisHelper.game_key(game_id, "t2p1_seat"), "")  # Empty
        RedisHelper.set_with_ttl(RedisHelper.game_key(game_id, "t2p2_seat"), "player4")
        
        # Attempt recovery
        recovered_seat = await GameManager.attempt_seat_recovery(game_id, "test_player")
        
        # Should be assigned to the only available seat
        assert recovered_seat == "t2p1"
        assert GameStateManager.get_game_state(game_id, "t2p1_seat") == "test_player"
    
    @pytest.mark.asyncio
    async def test_seat_recovery_no_seats_available(self, fake_redis, game_id):
        """Test seat recovery when no seats are available"""
        # Fill all seats
        RedisHelper.set_with_ttl(RedisHelper.game_key(game_id, "t1p1_seat"), "player1")
        RedisHelper.set_with_ttl(RedisHelper.game_key(game_id, "t1p2_seat"), "player2")
        RedisHelper.set_with_ttl(RedisHelper.game_key(game_id, "t2p1_seat"), "player3")
        RedisHelper.set_with_ttl(RedisHelper.game_key(game_id, "t2p2_seat"), "player4")
        
        # Attempt recovery
        recovered_seat = await GameManager.attempt_seat_recovery(game_id, "test_player")
        
        # Should return None
        assert recovered_seat is None
    
    @pytest.mark.asyncio
    async def test_submit_move_with_seat_recovery(self, fake_redis, game_id):
        """Test that submit_move can recover seats automatically"""
        # Set up game phase for team1 selection
        await GameStateManager.update_game_state(
            game_id=game_id,
            game_phase=GamePhase.TEAM1_SELECTION
        )
        
        # Set up scenario where player will need seat recovery
        RedisHelper.set_with_ttl(RedisHelper.game_key(game_id, "t1p1_seat"), "")  # Empty
        
        # Submit move (should trigger seat recovery)
        test_fen = "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 1"
        await PlayerActionHandler.submit_move(game_id, "test_player", test_fen)
        
        # Check that player was assigned a seat and move was recorded
        player_seat = GameManager.get_player_seat(game_id, "test_player")
        assert player_seat is not None
        assert GameStateManager.get_game_state(game_id, f"{player_seat}_selection") == test_fen

class TestPhaseManager:
    """Test PhaseManager functionality"""
    
    @pytest.mark.asyncio
    async def test_transition_phase_to_selection(self, fake_redis, game_id):
        """Test transitioning to selection phase"""
        with patch('main.manager') as mock_manager:
            mock_manager.broadcast = AsyncMock()
            
            await PhaseManager.transition_phase(game_id, GamePhase.TEAM1_SELECTION)
            
            # Check that phase was set
            assert GameStateManager.get_game_state(game_id, "game_phase") == GamePhase.TEAM1_SELECTION
            
            # Check that timer was broadcast (should be the first call)
            assert mock_manager.broadcast.call_count >= 1
            first_call_args = mock_manager.broadcast.call_args_list[0][0][0]
            assert first_call_args["type"] == "timer_update"
            assert first_call_args["seconds_remaining"] == 15  # SELECTION_TIME
    
    @pytest.mark.asyncio
    async def test_transition_phase_to_computing(self, fake_redis, game_id, mock_chess_engine):
        """Test transitioning to computing phase"""
        # Set up initial state
        await GameStateManager.update_game_state(
            game_id=game_id,
            fen="rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
        )
        
        with patch('main.MoveCalculator.compute_team_move') as mock_compute:
            mock_compute.return_value = AsyncMock()
            
            await PhaseManager.transition_phase(game_id, GamePhase.TEAM1_COMPUTING)
            
            # Check that phase was set
            assert GameStateManager.get_game_state(game_id, "game_phase") == GamePhase.TEAM1_COMPUTING
            
            # Check that move computation was triggered
            mock_compute.assert_called_with(game_id, 1)
    
    def test_check_team_ready(self, fake_redis, game_id):
        """Test checking if a team is ready"""
        # Set up team 1 with both players locked in
        RedisHelper.set_with_ttl(RedisHelper.game_key(game_id, "t1p1_locked_in"), "true")
        RedisHelper.set_with_ttl(RedisHelper.game_key(game_id, "t1p2_locked_in"), "true")
        RedisHelper.set_with_ttl(RedisHelper.game_key(game_id, "t1p1_ready"), "true")
        RedisHelper.set_with_ttl(RedisHelper.game_key(game_id, "t1p2_ready"), "true")
        
        assert PhaseManager._check_team_ready(game_id, 1) is True
        
        # Set one player not locked in
        RedisHelper.set_with_ttl(RedisHelper.game_key(game_id, "t1p2_locked_in"), "false")
        assert PhaseManager._check_team_ready(game_id, 1) is False

class TestMoveCalculator:
    """Test MoveCalculator functionality"""
    
    @pytest.mark.asyncio
    async def test_compute_team_move_both_selections(self, fake_redis, game_id, mock_chess_engine):
        """Test computing team move when both players have selections"""
        # Set up game state
        await GameStateManager.update_game_state(
            game_id=game_id,
            fen="rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
            t1p1_selection="rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 1",
            t1p2_selection="rnbqkbnr/pppppppp/8/8/3P4/8/PPP1PPPP/RNBQKBNR b KQkq d3 0 1"
        )
        
        with patch('main.manager') as mock_manager:
            mock_manager.broadcast = AsyncMock()
            
            await MoveCalculator.compute_team_move(game_id, 1)
            
            # Check that FEN was updated (should be one of the two selections)
            new_fen = GameStateManager.get_game_state(game_id, "fen")
            assert new_fen in [
                "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 1",
                "rnbqkbnr/pppppppp/8/8/3P4/8/PPP1PPPP/RNBQKBNR b KQkq d3 0 1"
            ]
            
            # Check that selections were cleared
            assert GameStateManager.get_game_state(game_id, "t1p1_selection") == ""
            assert GameStateManager.get_game_state(game_id, "t1p2_selection") == ""
            
            # Check that move count was incremented
            assert GameStateManager.get_game_state(game_id, "move_count") == "1"
    
    @pytest.mark.asyncio
    async def test_compute_team_move_one_selection(self, fake_redis, game_id, mock_chess_engine):
        """Test computing team move when only one player has a selection"""
        # Set up game state with only one selection
        await GameStateManager.update_game_state(
            game_id=game_id,
            fen="rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
            t1p1_selection="rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 1",
            t1p2_selection=""
        )
        
        with patch('main.manager') as mock_manager:
            mock_manager.broadcast = AsyncMock()
            
            await MoveCalculator.compute_team_move(game_id, 1)
            
            # Should use the only available selection
            new_fen = GameStateManager.get_game_state(game_id, "fen")
            assert new_fen == "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 1"
    
    @pytest.mark.asyncio
    async def test_compute_team_move_no_selections(self, fake_redis, game_id, mock_chess_engine):
        """Test computing team move when no players have selections"""
        # Set up game state with no selections
        await GameStateManager.update_game_state(
            game_id=game_id,
            fen="rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
            t1p1_selection="",
            t1p2_selection=""
        )
        
        with patch('main.manager') as mock_manager:
            mock_manager.broadcast = AsyncMock()
            
            await MoveCalculator.compute_team_move(game_id, 1)
            
            # Should make a random move (FEN should change)
            new_fen = GameStateManager.get_game_state(game_id, "fen")
            assert new_fen != "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
    
    def test_find_last_move(self):
        """Test finding the last move between two FENs"""
        old_fen = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
        new_fen = "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 1"
        
        # Mock chess.Board for this specific test
        with patch('main.chess.Board') as mock_board_class:
            # Create mock board instances
            def create_mock_board(fen):
                mock_board = Mock()
                mock_board.fen.return_value = fen
                
                if fen == old_fen:
                    # Mock legal moves for the starting position
                    mock_move = Mock()
                    mock_move.__str__ = lambda self: "e2e4"
                    mock_board.legal_moves = [mock_move]
                    
                    # Mock push method to simulate the move
                    def mock_push(move):
                        mock_board.fen.return_value = new_fen
                    mock_board.push = mock_push
                else:
                    mock_board.legal_moves = []
                
                return mock_board
            
            mock_board_class.side_effect = create_mock_board
            
            last_move = MoveCalculator._find_last_move(old_fen, new_fen)
            assert last_move == "e2e4"

class TestRedisHelper:
    """Test RedisHelper functionality"""
    
    def test_game_key(self):
        """Test game key generation"""
        key = RedisHelper.game_key("test_game", "test_field")
        assert key == "game:test_game:test_field"
    
    def test_set_and_get(self, fake_redis):
        """Test setting and getting values"""
        RedisHelper.set_with_ttl("test_key", "test_value")
        assert RedisHelper.get("test_key") == "test_value"
        
        # Test non-existent key
        assert RedisHelper.get("nonexistent") is None
    
    def test_set_multiple_and_get_multiple(self, fake_redis):
        """Test setting and getting multiple values"""
        key_values = {
            "key1": "value1",
            "key2": "value2",
            "key3": "value3"
        }
        
        RedisHelper.set_multiple(key_values)
        
        values = RedisHelper.get_multiple(["key1", "key2", "key3", "nonexistent"])
        assert values == ["value1", "value2", "value3", None]
    
    def test_set_if_not_exists(self, fake_redis):
        """Test conditional setting"""
        # Should succeed on first attempt
        assert RedisHelper.set_if_not_exists("test_key", "value1") is True
        assert RedisHelper.get("test_key") == "value1"
        
        # Should fail on second attempt
        assert RedisHelper.set_if_not_exists("test_key", "value2") is False
        assert RedisHelper.get("test_key") == "value1"  # Unchanged
    
    def test_delete(self, fake_redis):
        """Test deleting keys"""
        RedisHelper.set_with_ttl("test_key", "test_value")
        assert RedisHelper.get("test_key") == "test_value"
        
        RedisHelper.delete("test_key")
        assert RedisHelper.get("test_key") is None 