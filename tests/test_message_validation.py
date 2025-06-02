"""
Tests for Pydantic message validation
"""

import pytest
from pydantic import ValidationError
from message_validator import MessageValidator, ValidatedConnectionManager
from shared.message_types import TakeSeatMessage, ReadyMessage, GameStateUpdateMessage

class TestMessageValidator:
    """Test the MessageValidator class"""
    
    def test_validate_valid_client_messages(self, sample_client_messages):
        """Test validation of valid client messages"""
        for message_type, message_data in sample_client_messages.items():
            validated = MessageValidator.validate_client_message(message_data)
            assert validated.type == message_type
            
    def test_validate_invalid_client_message_type(self):
        """Test validation fails for unknown message type"""
        invalid_message = {
            "type": "unknown_message_type",
            "some_field": "value"
        }
        
        with pytest.raises(ValueError):
            MessageValidator.validate_client_message(invalid_message)
    
    def test_validate_invalid_seat_value(self):
        """Test validation fails for invalid seat value"""
        invalid_seat_message = {
            "type": "take_seat",
            "seat": "invalid_seat"
        }
        
        with pytest.raises(ValidationError) as exc_info:
            MessageValidator.validate_client_message(invalid_seat_message)
        
        # Check that the error mentions the valid seat options
        error_str = str(exc_info.value)
        assert "t1p1" in error_str or "literal_error" in error_str
    
    def test_validate_missing_required_field(self):
        """Test validation fails for missing required fields"""
        incomplete_message = {
            "type": "ready"
            # missing player_id
        }
        
        with pytest.raises(ValidationError) as exc_info:
            MessageValidator.validate_client_message(incomplete_message)
        
        # Check that the error mentions the missing field
        error_str = str(exc_info.value)
        assert "player_id" in error_str or "required" in error_str.lower()
    
    def test_create_valid_server_messages(self, sample_server_messages):
        """Test creation of valid server messages"""
        for message_type, expected_data in sample_server_messages.items():
            # Extract the type and create message with remaining data
            message_data = {k: v for k, v in expected_data.items() if k != "type"}
            
            created_message = MessageValidator.create_server_message(
                message_type, **message_data
            )
            
            assert created_message["type"] == message_type
            # Check that all expected fields are present
            for key, value in expected_data.items():
                assert created_message[key] == value
    
    def test_create_invalid_server_message_type(self):
        """Test creation fails for unknown server message type"""
        with pytest.raises(ValueError) as exc_info:
            MessageValidator.create_server_message(
                "unknown_server_message",
                some_field="value"
            )
        
        assert "Unknown server message type" in str(exc_info.value)
    
    def test_validate_and_extract_data(self, sample_client_messages):
        """Test message validation and data extraction"""
        for expected_type, message_data in sample_client_messages.items():
            message_type, validated_data = MessageValidator.validate_and_extract_data(message_data)
            
            assert message_type == expected_type
            assert validated_data["type"] == expected_type
            
            # Check that all original fields are preserved
            for key, value in message_data.items():
                assert validated_data[key] == value

class TestSpecificMessageTypes:
    """Test specific message type validations"""
    
    def test_take_seat_message_validation(self):
        """Test TakeSeatMessage validation"""
        # Valid seats
        valid_seats = ["t1p1", "t1p2", "t2p1", "t2p2"]
        for seat in valid_seats:
            message = {"type": "take_seat", "seat": seat}
            validated = MessageValidator.validate_client_message(message)
            assert isinstance(validated, TakeSeatMessage)
            assert validated.seat == seat
        
        # Invalid seat
        invalid_message = {"type": "take_seat", "seat": "invalid"}
        with pytest.raises(ValidationError):
            MessageValidator.validate_client_message(invalid_message)
    
    def test_ready_message_validation(self):
        """Test ReadyMessage validation"""
        # Valid message
        message = {"type": "ready", "player_id": "player123"}
        validated = MessageValidator.validate_client_message(message)
        assert isinstance(validated, ReadyMessage)
        assert validated.player_id == "player123"
        
        # Missing player_id
        invalid_message = {"type": "ready"}
        with pytest.raises(ValidationError):
            MessageValidator.validate_client_message(invalid_message)
    
    def test_game_state_update_message_creation(self):
        """Test GameStateUpdateMessage creation"""
        message_data = {
            "game_phase": "setup",
            "fen": "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
            "t1p1_seat": "player123"
        }
        
        created = MessageValidator.create_server_message(
            "game_state_update", **message_data
        )
        
        assert created["type"] == "game_state_update"
        assert created["game_phase"] == "setup"
        assert created["fen"] == message_data["fen"]
        assert created["t1p1_seat"] == "player123"
    
    def test_optional_fields_excluded_when_none(self):
        """Test that None values are excluded from server messages"""
        message_data = {
            "game_phase": "setup",
            "fen": None,  # This should be excluded
            "t1p1_seat": "player123"
        }
        
        created = MessageValidator.create_server_message(
            "game_state_update", **message_data
        )
        
        assert "fen" not in created  # None values should be excluded
        assert created["game_phase"] == "setup"
        assert created["t1p1_seat"] == "player123"

class TestValidatedConnectionManager:
    """Test the ValidatedConnectionManager wrapper"""
    
    @pytest.fixture
    def mock_base_manager(self):
        """Create a mock base connection manager"""
        from unittest.mock import Mock, AsyncMock
        mock_manager = Mock()
        mock_manager.send_personal_message = AsyncMock()
        mock_manager.broadcast = AsyncMock()
        return mock_manager
    
    @pytest.fixture
    def validated_manager_instance(self, mock_base_manager):
        """Create a ValidatedConnectionManager instance"""
        return ValidatedConnectionManager(mock_base_manager)
    
    @pytest.mark.asyncio
    async def test_send_validated_message(self, validated_manager_instance, mock_base_manager):
        """Test sending validated messages"""
        await validated_manager_instance.send_validated_message(
            "connection_established",
            "game123",
            "player456",
            is_reconnection=False
        )
        
        # Check that the base manager was called with a validated message
        mock_base_manager.send_personal_message.assert_called_once()
        call_args = mock_base_manager.send_personal_message.call_args
        
        sent_message = call_args[0][0]  # First argument is the message
        assert sent_message["type"] == "connection_established"
        assert sent_message["player_id"] == "player456"
        assert sent_message["is_reconnection"] is False
    
    @pytest.mark.asyncio
    async def test_broadcast_validated_message(self, validated_manager_instance, mock_base_manager):
        """Test broadcasting validated messages"""
        await validated_manager_instance.broadcast_validated_message(
            "player_disconnected",
            "game123",
            player_id="player456",
            grace_period=30
        )
        
        # Check that the base manager was called with a validated message
        mock_base_manager.broadcast.assert_called_once()
        call_args = mock_base_manager.broadcast.call_args
        
        sent_message = call_args[0][0]  # First argument is the message
        assert sent_message["type"] == "player_disconnected"
        assert sent_message["player_id"] == "player456"
        assert sent_message["grace_period"] == 30
    
    @pytest.mark.asyncio
    async def test_send_validation_error(self, validated_manager_instance, mock_base_manager):
        """Test sending validation errors"""
        # Create a mock ValidationError by trying to validate an invalid message
        try:
            MessageValidator.validate_client_message({"type": "invalid"})
        except ValueError:
            # Since we changed to ValueError, let's create a proper ValidationError for testing
            from pydantic import ValidationError
            # Create a ValidationError by trying to validate a message with missing required fields
            try:
                MessageValidator.validate_client_message({"type": "ready"})  # missing player_id
            except ValidationError as e:
                await validated_manager_instance.send_validation_error("game123", "player456", e)
        
        # Check that an error message was sent
        mock_base_manager.send_personal_message.assert_called_once()
        call_args = mock_base_manager.send_personal_message.call_args
        
        sent_message = call_args[0][0]
        assert sent_message["type"] == "validation_error"
        assert "errors" in sent_message
    
    @pytest.mark.asyncio
    async def test_send_error(self, validated_manager_instance, mock_base_manager):
        """Test sending general errors"""
        await validated_manager_instance.send_error("game123", "player456", "Test error message")
        
        # Check that an error message was sent
        mock_base_manager.send_personal_message.assert_called_once()
        call_args = mock_base_manager.send_personal_message.call_args
        
        sent_message = call_args[0][0]
        assert sent_message["type"] == "error"
        assert sent_message["message"] == "Test error message" 