#!/usr/bin/env python3
"""
VECNA Production Startup Script
Initializes database and starts the application.
"""
import os
import sys

# Add the app directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app, init_db, seed_demo_data

if __name__ == '__main__':
    # Initialize database
    print("Initializing database...")
    init_db()
    
    # Optionally seed demo data (set SEED_DEMO=true in environment)
    if os.environ.get('SEED_DEMO', '').lower() == 'true':
        print("Seeding demo data...")
        seed_demo_data()
    
    print("VECNA startup complete. Ready for gunicorn.")
