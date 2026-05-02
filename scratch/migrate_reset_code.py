import sys
import os
sys.path.append(os.getcwd())
from app import create_app
from models import db
from sqlalchemy import text

app = create_app()
with app.app_context():
    # Columns to add to 'users' table
    columns_to_add = [
        ("reset_code", "VARCHAR(6)"),
        ("reset_code_expiration", "DATETIME")
    ]
    
    for column_name, column_type in columns_to_add:
        try:
            with db.engine.connect() as conn:
                conn.execute(text(f"ALTER TABLE users ADD COLUMN {column_name} {column_type}"))
                conn.commit()
                print(f"Successfully added {column_name} column to users table.")
        except Exception as e:
            if "duplicate column name" in str(e).lower():
                print(f"Column {column_name} already exists.")
            else:
                print(f"Error adding {column_name}: {e}")

    print("Migration complete.")
