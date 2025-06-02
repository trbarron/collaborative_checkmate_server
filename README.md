# Collaborative Checkmate

A real-time collaborative chess application where teams of players work together to make the best moves. Built with FastAPI (backend), Remix (frontend), WebSockets, and Redis.

## Project Structure

This is a monorepo containing both the server and client applications:

```
collaborative-checkmate/
├── server/                 # FastAPI backend
│   ├── main.py
│   ├── requirements.txt
│   ├── Dockerfile
│   └── fly.toml
├── client/                 # Remix frontend  
│   ├── app/
│   │   ├── routes/
│   │   ├── components/
│   │   └── styles/
│   ├── package.json
│   └── remix.config.js
├── shared/                 # Shared types and constants
│   ├── types.ts
│   └── game-constants.ts
└── docker-compose.yml      # Local development
```

## Features

- **Team-based Chess**: 4 players split into 2 teams (2v2)
- **Real-time Collaboration**: Players submit moves and vote on the best option
- **Stockfish Integration**: AI analysis to select the optimal move when players disagree
- **Robust Reconnection**: 30-second grace period with state preservation
- **Automatic Seat Recovery**: Intelligent seat assignment recovery for synchronization issues
- **Game Logging**: Track games, players, and statistics with Supabase
- **WebSocket Communication**: Real-time updates for all players
- **Redis State Management**: Persistent game state and player sessions

## Quick Start

### Prerequisites

- Python 3.11+ (for server)
- Node.js 18+ (for client)
- Redis (cloud or local)
- Stockfish chess engine
- Supabase account (optional, for game logging)

### Development Setup

1. **Clone the repository:**
   ```bash
   git clone <repository-url>
   cd collaborative-checkmate
   ```

2. **Set up the server:**
   ```bash
   cd server
   cp env.example .env
   # Edit .env with your actual values
   pip install -r requirements.txt
   python main.py
   ```

3. **Set up the client (in a new terminal):**
   ```bash
   cd client
   npm install
   npm run dev
   ```

4. **Access the application:**
   - Frontend: `http://localhost:3000`
   - Backend API: `http://localhost:8000`

### Docker Development

```bash
# Run both server and client with hot reload
docker-compose up --build

# Or run individually
docker-compose up server
docker-compose up client
```

## Environment Variables

Create a `.env` file with these variables:

```env
# Required
REDIS_PASSWORD=your_redis_password

# Optional (defaults to /usr/games/stockfish)
STOCKFISH_PATH=/path/to/stockfish

# Optional (for game logging)
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=your_supabase_anon_key
```

## Game Logging (Optional)

The server can log detailed game statistics to Supabase:

### Setup

1. **Create a Supabase project** at [supabase.com](https://supabase.com)
2. **Run the database schema:**
   - Copy the contents of `supabase_schema.sql`
   - Paste and run in your Supabase SQL editor
3. **Add environment variables** (see above)

### What Gets Logged

- **Game Start**: Player names, lobby info, timestamp
- **During Game**: Move count tracking, team collaboration statistics
- **Game End**: Final statistics, winner, game result (checkmate/stalemate/draw), same-move counts

The server tracks when both players on a team submit identical moves

### View Statistics

Access game stats via the API endpoint:
```
GET /api/games/stats
```

## Deployment

### Fly.io (Recommended)

1. **Set secrets:**
   ```bash
   fly secrets set REDIS_PASSWORD=your_password
   fly secrets set SUPABASE_URL=your_supabase_url
   fly secrets set SUPABASE_ANON_KEY=your_supabase_key
   ```

2. **Deploy:**
   ```bash
   fly deploy
   ```

The `.dockerignore` file ensures sensitive files (like `.env`) are not included in deployments.

## API Endpoints

- `GET /api/games/available` - List joinable games
- `GET /api/games/stats` - Game statistics (requires Supabase)
- `GET /api/games/{game_id}/reconnection/{player_id}` - Check reconnection status
- `WS /ws/game/{game_id}/player/{player_id}` - WebSocket connection

## Reconnection System

The server includes a robust reconnection system to handle temporary disconnections:

### Features
- **Grace Period**: 30-second window for players to reconnect without losing their seat
- **State Preservation**: Player seats, ready status, and move selections are preserved during disconnections
- **Automatic Detection**: Server automatically detects reconnections vs new connections
- **Graceful Cleanup**: Expired disconnections are cleaned up automatically

### How It Works
1. When a player disconnects, their seat and game state are preserved for 30 seconds
2. Other players are notified of the temporary disconnection
3. If the player reconnects within the grace period, they resume their previous state
4. After the grace period expires, the seat is cleared and made available to new players

### API Support
- Check reconnection status: `GET /api/games/{game_id}/reconnection/{player_id}`
- Returns: reconnection eligibility, remaining grace time, player seat, and game phase

## Seat Recovery System

The server includes an intelligent seat recovery system to handle seat assignment synchronization issues:

### Features
- **Automatic Recovery**: Detects and fixes lost seat assignments automatically
- **Smart Assignment**: Prioritizes meaningful seat assignments based on game state
- **Race Condition Handling**: Resolves timing issues during connection and move submission
- **Graceful Fallback**: Provides clear error messages when recovery isn't possible

### When Recovery Triggers
- Player submits a move but has no seat assigned
- Player tries to lock in a move without a seat
- Player changes ready status but loses seat assignment
- WebSocket connection fails to assign seat properly

### Recovery Strategies
1. **Active Team Priority**: During selection phases, prioritize seats for the active team
2. **Single Seat Auto-assign**: If only one seat is available, assign automatically
3. **First Available**: Fallback to first available seat in consistent order

### Documentation
See [docs/SEAT_RECOVERY.md](docs/SEAT_RECOVERY.md) for detailed implementation and testing information.

## How It Works

1. **Setup Phase**: Players join a lobby and select seats (Team 1 or Team 2)
2. **Selection Phase**: Active team players submit their preferred moves
3. **Computing Phase**: Stockfish analyzes submissions and selects the best move
4. **Repeat**: Alternates between teams until game ends

## Game States

- `setup` - Waiting for players to join and ready up
- `team1_selection` / `team2_selection` - Teams selecting moves
- `team1_computing` / `team2_computing` - AI processing moves
- `cooldown` - Game finished

## Development

### Local Development

```bash
# Install dependencies
pip install -r requirements.txt

# Run with auto-reload
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### Docker

```bash
docker build -t collaborative-chess .
docker run -p 8000:8080 collaborative-chess
```

## Type Safety & Testing

### Type Safety

The server uses **Pydantic** for comprehensive type safety and validation:

#### Message Validation
All WebSocket messages are validated using Pydantic models defined in `shared/message_types.py`:

```python
# Client messages are automatically validated
validated_message = MessageValidator.validate_client_message(data)
seat = validated_message.seat  # Guaranteed to be valid SeatKey

# Server messages are type-safe
await validated_manager.send_validated_message(
    "game_state_update",
    game_id,
    player_id,
    fen="rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
    turn="white"
)
```

#### TypeScript Integration
Auto-generated TypeScript types keep client and server perfectly synchronized:

```bash
# Regenerate types after modifying Pydantic models
python3 generate_typescript_types.py
```

```typescript
import { TakeSeatMessage, GameStateUpdateMessage } from './shared/types_generated';

// Type-safe client code
const message: TakeSeatMessage = {
  type: 'take_seat',
  seat: 't1p1'  // Autocomplete and validation
};
```

#### Benefits
- **Runtime Safety**: Invalid messages are rejected with detailed error messages
- **Developer Experience**: Full IDE autocomplete and type checking
- **API Consistency**: Client and server types stay in sync automatically
- **Graceful Errors**: Validation failures provide clear feedback to clients

### Testing

#### Running Tests
```bash
# Unit tests for message validation
python -m pytest tests/test_message_validator.py -v

# Integration tests for WebSocket endpoints
python -m pytest tests/test_websocket.py -v

# Type validation tests
python -m pytest tests/test_types.py -v
```

#### Test Coverage
- **Message Validation**: All Pydantic models and validation logic
- **WebSocket Handlers**: End-to-end message processing
- **Type Generation**: TypeScript output verification
- **Error Handling**: Validation failure scenarios

#### Adding Tests
When adding new message types:

1. **Define Pydantic model** in `shared/message_types.py`
2. **Add validation tests** in `tests/test_message_validator.py`
3. **Test WebSocket handling** in `tests/test_websocket.py`
4. **Regenerate types** with `python3 generate_typescript_types.py`

## Dependencies

- **FastAPI** - Web framework
- **python-chess** - Chess logic and Stockfish integration
- **Redis** - State management
- **Supabase** - Game logging (optional)
- **WebSockets** - Real-time communication

## Architecture

```
Client (WebSocket) ↔ FastAPI Server ↔ Redis (Game State)
                        ↓
                   Stockfish Engine
                        ↓
                   Supabase (Logging)
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## License

[Add your license here] 