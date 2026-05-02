import sqlite3

def update_schema():
    try:
        conn = sqlite3.connect('instance/styleshop.db')
        cursor = conn.cursor()
        
        # Check current columns
        cursor.execute("PRAGMA table_info(users)")
        columns = [col[1] for col in cursor.fetchall()]
        
        if 'reset_token' not in columns:
            print("Adding reset_token column...")
            cursor.execute("ALTER TABLE users ADD COLUMN reset_token VARCHAR(100)")
            cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS ix_users_reset_token ON users (reset_token)")
            
        if 'reset_token_expiration' not in columns:
            print("Adding reset_token_expiration column...")
            cursor.execute("ALTER TABLE users ADD COLUMN reset_token_expiration DATETIME")
            
        conn.commit()
        print("Schema updated successfully.")
        conn.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == '__main__':
    update_schema()
