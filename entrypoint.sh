#!/bin/bash
# VECNA Container Entrypoint
# Initializes database and seeds demo data before starting the app

set -e

echo "=== VECNA Container Starting ==="

# Initialize database tables
echo "Initializing database..."
python -c "from app import init_db; init_db()"

# Seed demo data (always seed to ensure trucks exist)
echo "Seeding demo data..."
python -c "from app import seed_demo_data; seed_demo_data()"

echo "=== Database ready, starting application ==="

# Execute the CMD (gunicorn)
exec "$@"
