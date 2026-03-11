from app import create_app, db
import sqlite3
import os

app = create_app()

def add_column_if_not_exists(cursor, table, column, definition):
    try:
        cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
        print(f"Added column {column} to {table}")
    except sqlite3.OperationalError as e:
        if 'duplicate column name' in str(e):
            print(f"Column {column} already exists in {table}")
        else:
            print(f"Error adding {column}: {e}")

with app.app_context():
    db_path = os.path.join(app.instance_path, 'healthcare.db')
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Patient Profile
        add_column_if_not_exists(cursor, 'patient_profile', 'lat', 'FLOAT')
        add_column_if_not_exists(cursor, 'patient_profile', 'lng', 'FLOAT')
        
        # Doctor Profile
        add_column_if_not_exists(cursor, 'doctor_profile', 'lat', 'FLOAT')
        add_column_if_not_exists(cursor, 'doctor_profile', 'lng', 'FLOAT')
        
        # Pharmacy User? (Maybe later, hardcode for now)
        
        conn.commit()
        print("Geo columns added successfully.")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        conn.close()
