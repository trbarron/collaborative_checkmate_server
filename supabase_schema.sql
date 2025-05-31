-- Supabase table schema for game logging
-- Run this SQL in your Supabase SQL editor to create the game_logs table

CREATE TABLE IF NOT EXISTS game_logs (
    id BIGSERIAL PRIMARY KEY,
    game_id VARCHAR(255) UNIQUE NOT NULL,
    lobby_name VARCHAR(255) NOT NULL,
    started_at TIMESTAMP WITH TIME ZONE NOT NULL,
    ended_at TIMESTAMP WITH TIME ZONE,
    team1_player1 VARCHAR(255),
    team1_player2 VARCHAR(255),
    team2_player1 VARCHAR(255),
    team2_player2 VARCHAR(255),
    move_count INTEGER DEFAULT 0,
    game_result VARCHAR(50), -- 'checkmate', 'stalemate', 'draw', 'abandoned'
    winner VARCHAR(50), -- 'Team 1', 'Team 2', null for draws/stalemates
    game_status VARCHAR(20) DEFAULT 'in_progress', -- 'in_progress', 'completed', 'abandoned'
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create an index on game_id for faster lookups
CREATE INDEX IF NOT EXISTS idx_game_logs_game_id ON game_logs(game_id);

-- Create an index on started_at for time-based queries
CREATE INDEX IF NOT EXISTS idx_game_logs_started_at ON game_logs(started_at);

-- Create an index on game_status for filtering active games
CREATE INDEX IF NOT EXISTS idx_game_logs_status ON game_logs(game_status);

-- Enable Row Level Security (RLS) if needed
-- ALTER TABLE game_logs ENABLE ROW LEVEL SECURITY;

-- Create a policy for reading game logs (adjust as needed for your security requirements)
-- CREATE POLICY "Allow read access to game logs" ON game_logs FOR SELECT USING (true);

-- Function to automatically update the updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Trigger to automatically update updated_at on row updates
CREATE TRIGGER update_game_logs_updated_at 
    BEFORE UPDATE ON game_logs 
    FOR EACH ROW 
    EXECUTE FUNCTION update_updated_at_column(); 