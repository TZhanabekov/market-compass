#!/bin/sh
# Startup script for Railway deployment
# Optionally runs migrations, then starts the API server

set -e

# Run migrations if AUTO_MIGRATE is set to "true"
if [ "${AUTO_MIGRATE:-false}" = "true" ]; then
    echo "Running database migrations (AUTO_MIGRATE=true)..."
    alembic upgrade head || {
        echo "Migration failed, but continuing..."
    }
else
    echo "Skipping migrations (set AUTO_MIGRATE=true to enable)"
fi

echo "Starting API server..."
exec python -m uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080}
