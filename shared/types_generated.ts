// Auto-generated TypeScript types from Pydantic models
// DO NOT EDIT MANUALLY - Run generate_typescript_types.py to update

// ============================================================================
// ENUMS
// ============================================================================

export const GamePhase = {
  SETUP: 'setup',
  TEAM1_SELECTION: 'team1_selection',
  TEAM1_COMPUTING: 'team1_computing',
  TEAM2_SELECTION: 'team2_selection',
  TEAM2_COMPUTING: 'team2_computing',
  COOLDOWN: 'cooldown',
} as const;

export type GamePhaseType = typeof GamePhase[keyof typeof GamePhase];

// ============================================================================
// SEAT TYPES
// ============================================================================

export type SeatKey = 't1p1' | 't1p2' | 't2p1' | 't2p2';

// ============================================================================
// CLIENT → SERVER MESSAGES
// ============================================================================

export interface TakeSeatMessage {
  type: string;
  seat: "t1p1" | "t1p2" | "t2p1" | "t2p2";
}

export interface ReadyMessage {
  type: string;
  player_id: string;
}

export interface NotReadyMessage {
  type: string;
  player_id: string;
}

export interface SubmitMoveMessage {
  type: string;
  player_id: string;
  move: string;
}

export interface LockInMoveMessage {
  type: string;
  player_id: string;
}

export interface HeartbeatMessage {
  type: string;
  timestamp: number;
  connectionId?: string;
}

// Union type for all client messages
export type ClientMessage = TakeSeatMessage | ReadyMessage | NotReadyMessage | SubmitMoveMessage | LockInMoveMessage | HeartbeatMessage;

// ============================================================================
// SERVER → CLIENT MESSAGES
// ============================================================================

export interface ConnectionEstablishedMessage {
  type: string;
  player_id: string;
  is_reconnection: boolean;
}

export interface GameStateUpdateMessage {
  type: string;
  game_phase?: any;
  duration?: number;
  fen?: string;
  last_move?: string;
  move_count?: string;
  t1_same_moves?: string;
  t2_same_moves?: string;
  next_relevant_time?: string;
  t1p1_seat?: string;
  t1p2_seat?: string;
  t2p1_seat?: string;
  t2p2_seat?: string;
  t1p1_ready?: string;
  t1p2_ready?: string;
  t2p1_ready?: string;
  t2p2_ready?: string;
  t1p1_locked_in?: string;
  t1p2_locked_in?: string;
  t2p1_locked_in?: string;
  t2p2_locked_in?: string;
  t1p1_selection?: string;
  t1p2_selection?: string;
  t2p1_selection?: string;
  t2p2_selection?: string;
}

export interface TimerUpdateMessage {
  type: string;
  seconds_remaining: number;
  key: string;
}

export interface PlayerReadyMessage {
  type: string;
  player_id: string;
}

export interface MoveSubmittedMessage {
  type: string;
  player_id: string;
  seat?: "t1p1" | "t1p2" | "t2p1" | "t2p2";
}

export interface MoveSelectedMessage {
  type: string;
  move: Record<string, string>;
}

export interface PlayerDisconnectedMessage {
  type: string;
  player_id: string;
  grace_period: number;
}

export interface PlayerReconnectedMessage {
  type: string;
  player_id: string;
  seat: "t1p1" | "t1p2" | "t2p1" | "t2p2";
}

export interface PlayerPermanentlyDisconnectedMessage {
  type: string;
  player_id: string;
}

export interface PlayerSeatsMessage {
  type: string;
  seats: Record<string, string>;
}

export interface ReconnectionStateSyncMessage {
  type: string;
  game_state: object;
  your_seat: "t1p1" | "t1p2" | "t2p1" | "t2p2";
}

export interface ReconnectionSuccessfulMessage {
  type: string;
  message: string;
}

export interface HeartbeatResponseMessage {
  type: string;
  timestamp: number;
}

export interface GameOverMessage {
  type: string;
  result: string;
  message: string;
  total_moves: number;
  team_coordination: Record<string, number>;
  final_position: string;
}

// Union type for all server messages
export type ServerMessage = ConnectionEstablishedMessage | GameStateUpdateMessage | TimerUpdateMessage | PlayerReadyMessage | MoveSubmittedMessage | MoveSelectedMessage | PlayerDisconnectedMessage | PlayerReconnectedMessage | PlayerPermanentlyDisconnectedMessage | PlayerSeatsMessage | ReconnectionStateSyncMessage | ReconnectionSuccessfulMessage | HeartbeatResponseMessage | GameOverMessage;

// ============================================================================
// API RESPONSE TYPES
// ============================================================================

export interface AvailableGame {
  game_id: string;
  created_time: number;
  occupied_seats: number;
  phase: any;
}

export interface AvailableGamesResponse {
  games: any[];
}

export interface ReconnectionStatusResponse {
  can_reconnect: boolean;
  player_seat?: string;
  game_phase?: any;
  remaining_grace_time: number;
  grace_period_total: number;
}

export interface GameStats {
  total_games: number;
  completed_games: number;
  in_progress_games: number;
  abandoned_games: number;
  average_moves: number;
  win_stats: Record<string, number>;
  recent_games: any[];
}

// ============================================================================
// CONFIGURATION
// ============================================================================

export const CONFIG = {
  SELECTION_TIME: 15,
  RECONNECTION_GRACE_PERIOD: 30,
  HEARTBEAT_INTERVAL: 10000,
  HEARTBEAT_TIMEOUT: 5000,
  MAX_RECONNECT_ATTEMPTS: 10,
  INITIAL_RECONNECT_DELAY: 1000,
  MAX_RECONNECT_DELAY: 30000,
} as const;