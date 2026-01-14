#!/bin/sh
# Startup script for Railway deployment
# Optionally runs migrations, then starts the API server

set -e

# Run migrations if AUTO_MIGRATE is set to "true"
if [ "${AUTO_MIGRATE:-false}" = "true" ]; then
    echo "Running database migrations (AUTO_MIGRATE=true)..."
    i=1
    max=8
    while [ $i -le $max ]; do
        if alembic upgrade head; then
            echo "Migrations applied successfully."
            break
        fi

        if [ $i -eq $max ]; then
            echo "Migration failed after ${max} attempts. Exiting."
            exit 1
        fi

        echo "Migration attempt ${i} failed; retrying in 2s..."
        sleep 2
        i=$((i+1))
    done
else
    echo "Skipping migrations (set AUTO_MIGRATE=true to enable)"
fi

echo "Starting API server..."
exec python -m uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080}
