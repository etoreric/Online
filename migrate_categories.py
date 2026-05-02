from app import create_app
from models import db
from sqlalchemy import text

app = create_app()
with app.app_context():
    try:
        with db.engine.connect() as conn:
            conn.execute(text("ALTER TABLE categories ADD COLUMN admin_id INTEGER REFERENCES users(id)"))
            conn.commit()
            print("Successfully added admin_id column to categories table.")
    except Exception as e:
        print(f"Error adding column or it already exists: {e}")

    db.create_all()
    print("Database synchronization complete.")
