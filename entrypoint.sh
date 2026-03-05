#!/bin/bash
set -e

echo "Waiting for database to be ready..."
until python -c "import psycopg2; psycopg2.connect('$DATABASE_URL')" 2>/dev/null; do
    echo "Database is unavailable - sleeping"
    sleep 2
done

echo "Database is ready! Running database migrations..."
alembic upgrade head

echo "Running database initialization..."
python -m app.db.init_db

echo "Starting application..."
exec "$@"
