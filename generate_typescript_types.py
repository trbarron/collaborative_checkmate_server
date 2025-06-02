"""
Generate TypeScript types from Pydantic models
This keeps your Python and TypeScript types perfectly synchronized!
"""

import json
from typing import Dict, Any, List
from shared.message_types import (
    # Client messages
    TakeSeatMessage, ReadyMessage, NotReadyMessage, SubmitMoveMessage, 
    LockInMoveMessage, HeartbeatMessage,
    # Server messages  
    ConnectionEstablishedMessage, GameStateUpdateMessage, TimerUpdateMessage,
    PlayerReadyMessage, MoveSubmittedMessage, MoveSelectedMessage,
    PlayerDisconnectedMessage, PlayerReconnectedMessage, 
    PlayerPermanentlyDisconnectedMessage, PlayerSeatsMessage,
    ReconnectionStateSyncMessage, ReconnectionSuccessfulMessage,
    HeartbeatResponseMessage, GameOverMessage,
    # API types
    AvailableGame, AvailableGamesResponse, ReconnectionStatusResponse, GameStats,
    # Enums
    GamePhase
)

def pydantic_to_typescript_type(python_type: str) -> str:
    """Convert Python types to TypeScript types"""
    type_mapping = {
        'str': 'string',
        'int': 'number', 
        'float': 'number',
        'bool': 'boolean',
        'datetime': 'string',  # ISO string
        'Any': 'any',
        'Dict[str, str]': 'Record<string, string>',
        'Dict[str, int]': 'Record<string, number>',
        'Dict[str, Any]': 'Record<string, any>',
        'List[str]': 'string[]',
        'List[Any]': 'any[]',
    }
    return type_mapping.get(python_type, python_type)

def generate_typescript_interface(model_class, interface_name: str = None) -> str:
    """Generate TypeScript interface from Pydantic model"""
    if interface_name is None:
        interface_name = model_class.__name__
    
    # Get the JSON schema from Pydantic
    schema = model_class.model_json_schema()
    
    # Start building the interface
    lines = [f"export interface {interface_name} {{"]
    
    properties = schema.get('properties', {})
    required = schema.get('required', [])
    
    for field_name, field_info in properties.items():
        # Determine if field is optional
        is_optional = field_name not in required
        optional_marker = '?' if is_optional else ''
        
        # Get TypeScript type
        ts_type = get_typescript_type_from_schema(field_info)
        
        # Add field to interface
        lines.append(f"  {field_name}{optional_marker}: {ts_type};")
    
    lines.append("}")
    return "\n".join(lines)

def get_typescript_type_from_schema(field_info: Dict[str, Any]) -> str:
    """Convert JSON schema field info to TypeScript type"""
    field_type = field_info.get('type')
    
    if field_type == 'string':
        # Check for enum values (Literal types)
        if 'enum' in field_info:
            enum_values = [f'"{val}"' for val in field_info['enum']]
            return ' | '.join(enum_values)
        return 'string'
    elif field_type == 'integer':
        return 'number'
    elif field_type == 'number':
        return 'number'
    elif field_type == 'boolean':
        return 'boolean'
    elif field_type == 'array':
        item_type = get_typescript_type_from_schema(field_info.get('items', {}))
        return f'{item_type}[]'
    elif field_type == 'object':
        # Handle Record types
        if 'additionalProperties' in field_info:
            value_type = get_typescript_type_from_schema(field_info['additionalProperties'])
            return f'Record<string, {value_type}>'
        return 'object'
    elif 'anyOf' in field_info:
        # Handle union types (Optional fields)
        types = []
        for option in field_info['anyOf']:
            if option.get('type') != 'null':
                types.append(get_typescript_type_from_schema(option))
        return ' | '.join(types) if types else 'any'
    else:
        return 'any'

def generate_enum_from_pydantic(enum_class, enum_name: str = None) -> str:
    """Generate TypeScript enum from Python enum"""
    if enum_name is None:
        enum_name = enum_class.__name__
    
    lines = [f"export const {enum_name} = {{"]
    
    for member in enum_class:
        # Convert to uppercase constant style
        const_name = member.name.upper()
        lines.append(f"  {const_name}: '{member.value}',")
    
    lines.append("} as const;")
    lines.append("")
    lines.append(f"export type {enum_name}Type = typeof {enum_name}[keyof typeof {enum_name}];")
    
    return "\n".join(lines)

def generate_all_typescript_types() -> str:
    """Generate complete TypeScript definitions file"""
    
    typescript_content = [
        "// Auto-generated TypeScript types from Pydantic models",
        "// DO NOT EDIT MANUALLY - Run generate_typescript_types.py to update",
        "",
        "// ============================================================================",
        "// ENUMS",
        "// ============================================================================",
        "",
        generate_enum_from_pydantic(GamePhase),
        "",
        "// ============================================================================", 
        "// SEAT TYPES",
        "// ============================================================================",
        "",
        "export type SeatKey = 't1p1' | 't1p2' | 't2p1' | 't2p2';",
        "",
        "// ============================================================================",
        "// CLIENT → SERVER MESSAGES", 
        "// ============================================================================",
        "",
        generate_typescript_interface(TakeSeatMessage),
        "",
        generate_typescript_interface(ReadyMessage),
        "",
        generate_typescript_interface(NotReadyMessage),
        "",
        generate_typescript_interface(SubmitMoveMessage),
        "",
        generate_typescript_interface(LockInMoveMessage),
        "",
        generate_typescript_interface(HeartbeatMessage),
        "",
        "// Union type for all client messages",
        "export type ClientMessage = TakeSeatMessage | ReadyMessage | NotReadyMessage | SubmitMoveMessage | LockInMoveMessage | HeartbeatMessage;",
        "",
        "// ============================================================================",
        "// SERVER → CLIENT MESSAGES",
        "// ============================================================================", 
        "",
        generate_typescript_interface(ConnectionEstablishedMessage),
        "",
        generate_typescript_interface(GameStateUpdateMessage),
        "",
        generate_typescript_interface(TimerUpdateMessage),
        "",
        generate_typescript_interface(PlayerReadyMessage),
        "",
        generate_typescript_interface(MoveSubmittedMessage),
        "",
        generate_typescript_interface(MoveSelectedMessage),
        "",
        generate_typescript_interface(PlayerDisconnectedMessage),
        "",
        generate_typescript_interface(PlayerReconnectedMessage),
        "",
        generate_typescript_interface(PlayerPermanentlyDisconnectedMessage),
        "",
        generate_typescript_interface(PlayerSeatsMessage),
        "",
        generate_typescript_interface(ReconnectionStateSyncMessage),
        "",
        generate_typescript_interface(ReconnectionSuccessfulMessage),
        "",
        generate_typescript_interface(HeartbeatResponseMessage),
        "",
        generate_typescript_interface(GameOverMessage),
        "",
        "// Union type for all server messages",
        "export type ServerMessage = ConnectionEstablishedMessage | GameStateUpdateMessage | TimerUpdateMessage | PlayerReadyMessage | MoveSubmittedMessage | MoveSelectedMessage | PlayerDisconnectedMessage | PlayerReconnectedMessage | PlayerPermanentlyDisconnectedMessage | PlayerSeatsMessage | ReconnectionStateSyncMessage | ReconnectionSuccessfulMessage | HeartbeatResponseMessage | GameOverMessage;",
        "",
        "// ============================================================================",
        "// API RESPONSE TYPES",
        "// ============================================================================",
        "",
        generate_typescript_interface(AvailableGame),
        "",
        generate_typescript_interface(AvailableGamesResponse),
        "",
        generate_typescript_interface(ReconnectionStatusResponse),
        "",
        generate_typescript_interface(GameStats),
        "",
        "// ============================================================================",
        "// CONFIGURATION",
        "// ============================================================================",
        "",
        "export const CONFIG = {",
        "  SELECTION_TIME: 15,",
        "  RECONNECTION_GRACE_PERIOD: 30,", 
        "  HEARTBEAT_INTERVAL: 10000,",
        "  HEARTBEAT_TIMEOUT: 5000,",
        "  MAX_RECONNECT_ATTEMPTS: 10,",
        "  INITIAL_RECONNECT_DELAY: 1000,",
        "  MAX_RECONNECT_DELAY: 30000,",
        "} as const;",
    ]
    
    return "\n".join(typescript_content)

def main():
    """Generate TypeScript types and save to file"""
    typescript_content = generate_all_typescript_types()
    
    # Save to shared types file
    output_file = "shared/types_generated.ts"
    with open(output_file, 'w') as f:
        f.write(typescript_content)
    
    print(f"✅ Generated TypeScript types in {output_file}")
    print("📝 Import in your client with: import { ClientMessage, ServerMessage } from './shared/types_generated'")

if __name__ == "__main__":
    main() 