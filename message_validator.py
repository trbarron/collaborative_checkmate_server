"""
Message validation utility using Pydantic models
Integrates with the existing WebSocket handler in main.py
"""

from typing import Dict, Any, Union
from pydantic import ValidationError
from shared.message_types import (
    # Client message types
    ClientMessage, TakeSeatMessage, ReadyMessage, NotReadyMessage,
    SubmitMoveMessage, LockInMoveMessage, HeartbeatMessage,
    # Server message types  
    ConnectionEstablishedMessage, GameStateUpdateMessage, TimerUpdateMessage,
    PlayerReadyMessage, MoveSubmittedMessage, MoveSelectedMessage,
    PlayerDisconnectedMessage, PlayerReconnectedMessage,
    PlayerPermanentlyDisconnectedMessage, PlayerSeatsMessage,
    ReconnectionStateSyncMessage, ReconnectionSuccessfulMessage,
    HeartbeatResponseMessage, GameOverMessage
)

class MessageValidator:
    """Utility class for validating WebSocket messages using Pydantic models"""
    
    # Map client message types to their Pydantic models
    CLIENT_MESSAGE_TYPES = {
        "take_seat": TakeSeatMessage,
        "ready": ReadyMessage,
        "not_ready": NotReadyMessage,
        "submit_move": SubmitMoveMessage,
        "lock_in_move": LockInMoveMessage,
        "heartbeat": HeartbeatMessage,
    }
    
    # Map server message types to their Pydantic models
    SERVER_MESSAGE_TYPES = {
        "connection_established": ConnectionEstablishedMessage,
        "game_state_update": GameStateUpdateMessage,
        "timer_update": TimerUpdateMessage,
        "player_ready": PlayerReadyMessage,
        "move_submitted": MoveSubmittedMessage,
        "move_selected": MoveSelectedMessage,
        "player_disconnected": PlayerDisconnectedMessage,
        "player_reconnected": PlayerReconnectedMessage,
        "player_permanently_disconnected": PlayerPermanentlyDisconnectedMessage,
        "player_seats": PlayerSeatsMessage,
        "reconnection_state_sync": ReconnectionStateSyncMessage,
        "reconnection_successful": ReconnectionSuccessfulMessage,
        "heartbeat_response": HeartbeatResponseMessage,
        "game_over": GameOverMessage,
    }
    
    @classmethod
    def validate_client_message(cls, data: Dict[str, Any]) -> ClientMessage:
        """
        Validate incoming client message and return typed Pydantic model
        
        Args:
            data: Raw message data from WebSocket
            
        Returns:
            Validated Pydantic model instance
            
        Raises:
            ValueError: If message doesn't match any known client message type
        """
        message_type = data.get("type")
        
        if message_type not in cls.CLIENT_MESSAGE_TYPES:
            raise ValueError(f"Unknown client message type: {message_type}")
        
        model_class = cls.CLIENT_MESSAGE_TYPES[message_type]
        return model_class(**data)
    
    @classmethod
    def create_server_message(cls, message_type: str, **kwargs) -> Dict[str, Any]:
        """
        Create a validated server message
        
        Args:
            message_type: Type of message to create
            **kwargs: Message data
            
        Returns:
            Validated message as dictionary ready for JSON serialization
            
        Raises:
            ValueError: If message type is unknown
        """
        if message_type not in cls.SERVER_MESSAGE_TYPES:
            raise ValueError(f"Unknown server message type: {message_type}")
        
        model_class = cls.SERVER_MESSAGE_TYPES[message_type]
        message = model_class(type=message_type, **kwargs)
        return message.model_dump(exclude_none=True)
    
    @classmethod
    def validate_and_extract_data(cls, data: Dict[str, Any]) -> tuple[str, Dict[str, Any]]:
        """
        Validate client message and extract the data for processing
        
        Args:
            data: Raw message data from WebSocket
            
        Returns:
            Tuple of (message_type, validated_data_dict)
            
        Raises:
            ValidationError: If message validation fails
        """
        validated_message = cls.validate_client_message(data)
        message_type = validated_message.type
        
        # Convert back to dict for compatibility with existing handlers
        validated_data = validated_message.model_dump()
        
        return message_type, validated_data

# Enhanced connection manager with validation
class ValidatedConnectionManager:
    """Extension of ConnectionManager with message validation"""
    
    def __init__(self, base_manager):
        self.base_manager = base_manager
    
    async def send_validated_message(self, message_type: str, game_id: str, player_id: str, **kwargs):
        """Send a validated server message to a specific player"""
        try:
            # Only add player_id if the message type expects it
            model_class = MessageValidator.SERVER_MESSAGE_TYPES.get(message_type)
            if model_class and hasattr(model_class, '__annotations__') and 'player_id' in model_class.__annotations__:
                if 'player_id' not in kwargs:
                    kwargs['player_id'] = player_id
            
            validated_message = MessageValidator.create_server_message(message_type, **kwargs)
            print(f"📤 Sending {message_type} to {player_id}: {validated_message}")
            await self.base_manager.send_personal_message(validated_message, game_id, player_id)
        except Exception as e:
            print(f"Error sending validated message {message_type} to {player_id}: {e}")
    
    async def broadcast_validated_message(self, message_type: str, game_id: str, **kwargs):
        """Broadcast a validated server message to all players in a game"""
        try:
            validated_message = MessageValidator.create_server_message(message_type, **kwargs)
            await self.base_manager.broadcast(validated_message, game_id)
        except Exception as e:
            print(f"Error broadcasting validated message {message_type} to game {game_id}: {e}")
    
    async def send_validation_error(self, game_id: str, player_id: str, error: ValidationError):
        """Send validation error to client"""
        error_message = {
            "type": "validation_error",
            "message": "Invalid message format",
            "errors": error.errors()
        }
        await self.base_manager.send_personal_message(error_message, game_id, player_id)
    
    async def send_error(self, game_id: str, player_id: str, message: str):
        """Send general error to client"""
        error_message = {
            "type": "error",
            "message": message
        }
        await self.base_manager.send_personal_message(error_message, game_id, player_id)

# Message processing function for integration with existing WebSocket handler
async def process_validated_message(
    data: Dict[str, Any], 
    game_id: str, 
    player_id: str,
    validated_manager: ValidatedConnectionManager
) -> bool:
    """
    Process a validated WebSocket message
    
    Args:
        data: Raw message data from WebSocket
        game_id: Game identifier
        player_id: Player identifier
        validated_manager: ValidatedConnectionManager instance
        
    Returns:
        True if message was processed successfully, False otherwise
    """
    try:
        # Validate the message
        message_type, validated_data = MessageValidator.validate_and_extract_data(data)
        
        # Import here to avoid circular imports
        from main import PlayerActionHandler
        
        # Process based on message type (using existing handlers)
        if message_type == "submit_move":
            print(f"🎯 Received submit_move from {player_id}: {validated_data['move']}")
            await PlayerActionHandler.submit_move(
                game_id, validated_data["player_id"], validated_data["move"]
            )
            print(f"✅ Processed submit_move for {player_id}")
        
        elif message_type == "take_seat":
            await PlayerActionHandler.change_seat(
                game_id, player_id, validated_data["seat"]
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
                game_id, validated_data["player_id"]
            )
        
        elif message_type == "heartbeat":
            # Respond to heartbeat with validated message
            print(f"🔥 Received heartbeat from {player_id} with timestamp: {validated_data['timestamp']}")
            await validated_manager.send_validated_message(
                "heartbeat_response",
                game_id,
                player_id,
                timestamp=validated_data["timestamp"]
            )
            print(f"✅ Sent heartbeat_response to {player_id}")
        
        else:
            await validated_manager.send_error(
                game_id, player_id, f"Unknown message type: {message_type}"
            )
            return False
        
        return True
        
    except ValidationError as e:
        # Send validation error to client
        await validated_manager.send_validation_error(game_id, player_id, e)
        return False
    
    except Exception as e:
        # Send general error to client
        await validated_manager.send_error(
            game_id, player_id, f"Server error processing message: {str(e)}"
        )
        return False 