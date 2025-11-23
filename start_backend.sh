#!/bin/bash

echo "Starting CSV Analyzer Backend..."
echo "================================"

# Activate virtual environment
source .hackathon_env_e2b/bin/activate

# Check if .env exists
if [ ! -f .env ]; then
    echo "Error: .env file not found!"
    echo "Please create a .env file with your API keys."
    echo "See .env.example for reference."
    exit 1
fi

# Export environment variables from .env
export $(cat .env | grep -v '^#' | xargs)

# Install/update dependencies
echo "Installing dependencies..."
pip install -r requirements.txt

# Start the Flask backend
echo "Starting Flask server on http://localhost:5000"
cd backend
python app.py

