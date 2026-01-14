#!/bin/bash
# Run migrations on Railway
# 
# IMPORTANT: Railway uses internal domains (postgres.railway.internal) 
# which are not accessible from local machine.
# 
# Options:
# 1. Use AUTO_MIGRATE=true in Railway (recommended) - migrations run automatically on deploy
# 2. Use Railway Shell (if available) to run migrations inside the container
# 3. Use this script with Railway CLI (may not work due to internal domains)

set -e

cd "$(dirname "$0")"

echo "⚠️  WARNING: Railway uses internal database domains that may not be accessible locally."
echo ""
echo "Recommended approach:"
echo "1. Set AUTO_MIGRATE=true in Railway Dashboard → Variables"
echo "2. Migrations will run automatically on each deploy"
echo ""
echo "Alternative: Run migrations inside Railway container"
echo "1. Go to Railway Dashboard → your service → Deployments"
echo "2. Click on latest deployment → Shell (if available)"
echo "3. Run: alembic upgrade head && python -m scripts.seed"
echo ""
read -p "Continue with local attempt? (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    exit 0
fi

# Check if Railway CLI is installed and connected
if ! command -v railway &> /dev/null; then
    echo "Error: Railway CLI is not installed."
    echo "Install it with: npm install -g @railway/cli"
    exit 1
fi

# Check if connected to Railway project
if ! railway status &> /dev/null; then
    echo "Error: Not connected to Railway project."
    echo "Run: railway link"
    exit 1
fi

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

# Try to run migrations with Railway env vars
echo "Attempting to run migrations with Railway environment..."
echo "Note: This may fail if DATABASE_URL uses internal Railway domains."
echo ""

if railway run alembic upgrade head; then
    echo "✓ Migrations successful!"
    echo "Seeding database..."
    railway run python -m scripts.seed
    echo "✓ Done!"
else
    echo ""
    echo "❌ Migration failed. This is expected if DATABASE_URL uses internal domains."
    echo ""
    echo "Please use one of these alternatives:"
    echo "1. Set AUTO_MIGRATE=true in Railway Dashboard → Variables"
    echo "2. Use Railway Shell to run migrations inside the container"
    echo "3. Use Railway's 'Run Command' feature if available"
    exit 1
fi
