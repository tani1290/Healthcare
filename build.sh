#!/usr/bin/env bash
# Render build script

# Install Python dependencies
pip install -r requirements.txt

# Initialize database and seed demo data
python seed_db.py
