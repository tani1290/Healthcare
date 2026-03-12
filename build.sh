#!/usr/bin/env bash
# Render build script

# Install Python dependencies
pip install -r requirements.txt

# Create database tables and seed demo data
python seed_db.py

# Ensure roles and inventory are initialized via CLI just in case
export FLASK_APP=manage_data.py
flask init-roles
flask seed-inventory
