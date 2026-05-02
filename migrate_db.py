from app import create_app
from models import db
from sqlalchemy import text

app = create_app()
with app.app_context():
    tables_columns = {
        "users": "admin_id",
        "products": "admin_id",
        "orders": "admin_id"
    }
    
    for table, column in tables_columns.items():
        try:
            with db.engine.connect() as conn:
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} INTEGER REFERENCES users(id)"))
                conn.commit()
                print(f"Successfully added {column} column to {table} table.")
        except Exception as e:
            print(f"Column {column} in {table} might already exist or error occurred: {e}")

    db.create_all()
    print("Database tables synchronized.")
