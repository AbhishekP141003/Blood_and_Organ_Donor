#!/usr/bin/env bash
# Build script for Render

# Install dependencies
pip install -r requirements.txt

# Initialize database
python -c "from app import init_db; init_db()"
