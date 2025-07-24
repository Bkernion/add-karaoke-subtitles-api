#!/bin/bash

echo "🚀 Starting Karaoke Subtitle API..."

# Navigate to the project directory
cd "$(dirname "$0")"

# Activate virtual environment
source venv/bin/activate

# Create public directory if it doesn't exist
mkdir -p public

# Start the server
echo "Server starting on http://localhost:8000"
echo "Health check: http://localhost:8000/health"
echo "API docs: http://localhost:8000/docs"
echo ""
echo "Press Ctrl+C to stop the server"
echo ""

python main.py