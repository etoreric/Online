from app import create_app
from models import db
from sqlalchemy import text

app = create_app()
with app.app_context():
    cols = [
        ("site_settings", "promo_enabled",  "BOOLEAN DEFAULT 1"),
        ("site_settings", "promo_title",    "VARCHAR(200) DEFAULT 'Get 20% Off Your First Order'"),
        ("site_settings", "promo_subtitle", "TEXT DEFAULT 'Sign up today and receive an exclusive discount on your first purchase.'"),
    ]
    for table, col, typedef in cols:
        try:
            with db.engine.connect() as conn:
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {col} {typedef}"))
                conn.commit()
                print(f"Added column '{col}' to '{table}'")
        except Exception as e:
            print(f"Skipped '{col}': {e}")
    db.create_all()
    print("Done.")
