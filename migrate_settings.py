from app import create_app
from models import db
from sqlalchemy import text

app = create_app()
with app.app_context():
    try:
        with db.engine.connect() as conn:
            # Check if column exists first (optional, but good practice)
            # For simplicity, we'll try to add it and catch the error if it exists
            conn.execute(text("ALTER TABLE site_settings ADD COLUMN admin_id INTEGER REFERENCES users(id)"))
            conn.commit()
            print("Successfully added admin_id column to site_settings table.")
            
            # Since it's unique, we might want to add a unique constraint if the DB supports it via ALTER
            # But the model handles it.
    except Exception as e:
        print(f"admin_id column might already exist or error occurred: {e}")

    db.create_all()
    print("Database tables synchronized.")
