# Collaborative Checkmate Server

A real-time collaborative chess server where teams of players work together to make the best moves. Built with FastAPI, WebSockets, and Redis.

## Features

- **Team-based Chess**: 4 players split into 2 teams (2v2)
- **Real-time Collaboration**: Players submit moves and vote on the best option
- **Stockfish Integration**: AI analysis to select the optimal move when players disagree
- **Game Logging**: Track games, players, and statistics with Supabase
- **WebSocket Communication**: Real-time updates for all players
- **Redis State Management**: Persistent game state and player sessions

## Quick Start

### Prerequisites

- Python 3.11+
- Redis (cloud or local)
- Stockfish chess engine
- Supabase account (optional, for game logging)

### Installation

1. **Clone and install dependencies:**
   ```bash
   git clone <repository-url>
   cd collaborative_checkmate_server
   pip install -r requirements.txt
   ```

2. **Set up environment variables:**
   ```bash
   cp env.example .env
   # Edit .env with your actual values
   ```

3. **Run the server:**
   ```bash
   python main.py
   ```

The server will start on `http://localhost:8000`

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
- `WS /ws/game/{game_id}/player/{player_id}` - WebSocket connection

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