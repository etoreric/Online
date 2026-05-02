from app import create_app
from models import db
from sqlalchemy import text

app = create_app()
with app.app_context():
    try:
        with db.engine.connect() as conn:
            # Recreate categories table without unique constraints on name and slug
            # 1. Rename existing table
            conn.execute(text("ALTER TABLE categories RENAME TO categories_old"))
            
            # 2. Create new table
            conn.execute(text("""
                CREATE TABLE categories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name VARCHAR(50) NOT NULL,
                    slug VARCHAR(50) NOT NULL,
                    admin_id INTEGER REFERENCES users(id)
                )
            """))
            
            # 3. Copy data
            conn.execute(text("INSERT INTO categories (id, name, slug, admin_id) SELECT id, name, slug, admin_id FROM categories_old"))
            
            # 4. Drop old table
            conn.execute(text("DROP TABLE categories_old"))
            
            conn.commit()
            print("Successfully updated category table constraints.")
    except Exception as e:
        print(f"Error updating category constraints: {e}")
        try:
            conn.execute(text("ROLLBACK"))
        except:
            pass

    db.create_all()
    print("Database synchronization complete.")
