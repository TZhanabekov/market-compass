#!/bin/bash
# Run migrations locally (for local development with docker-compose)

set -e

cd "$(dirname "$0")"

# Create venv if it doesn't exist
if [ ! -d ".venv" ]; then
    echo "Creating virtual environment..."
    python3.11 -m venv .venv
fi

# Activate venv
source .venv/bin/activate

# Install dependencies
echo "Installing dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

# Load local .env file
if [ -f ".env" ]; then
    echo "Loading .env file..."
    export $(cat .env | grep -v '^#' | xargs)
fi

# Run migrations locally
echo "Running migrations locally..."
alembic upgrade head

echo "Seeding database..."
python -m scripts.seed

echo "Done!"
