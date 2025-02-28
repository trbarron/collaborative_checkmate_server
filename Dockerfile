FROM python:3.11-slim

WORKDIR /app

# Install Stockfish
RUN apt-get update && apt-get install -y stockfish && apt-get clean

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Update the Stockfish path in the code
ENV STOCKFISH_PATH="/usr/games/stockfish"

# Expose the port
EXPOSE 8080

# Command to run the application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]