#!/bin/bash
# Run migrations on Railway using local venv

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

# Run migrations with Railway env vars
echo "Running migrations..."
railway run alembic upgrade head

echo "Seeding database..."
railway run python -m scripts.seed

echo "Done!"
