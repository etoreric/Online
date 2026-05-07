import sqlite3

def check_settings():
    try:
        conn = sqlite3.connect('instance/styleshop.db')
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM site_settings")
        rows = cursor.fetchall()
        print("Site Settings:")
        for row in rows:
            print(row)
        
        cursor.execute("PRAGMA table_info(site_settings)")
        columns = cursor.fetchall()
        print("\nSite Settings Columns:")
        for col in columns:
            print(col)
            
        conn.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == '__main__':
    check_settings()
