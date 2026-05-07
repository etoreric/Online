import sqlite3

def fix_site_names():
    try:
        db_path = 'instance/styleshop.db'
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # 1. Update global settings (admin_id is NULL) to "StyleShop"
        cursor.execute("""
            UPDATE site_settings 
            SET site_name = 'StyleShop' 
            WHERE admin_id IS NULL
        """)
        
        # 2. Check if user 6 (Wiseman) has settings, if not create them with "Wiseman Business Connect"
        cursor.execute("SELECT id FROM site_settings WHERE admin_id = 6")
        if not cursor.fetchone():
            cursor.execute("""
                INSERT INTO site_settings (admin_id, site_name, hero_title, hero_bg_image)
                VALUES (6, 'Wiseman Business Connect', 'Wiseman Business Connect', 'hero_1777997022_131485.png')
            """)
        else:
            cursor.execute("""
                UPDATE site_settings 
                SET site_name = 'Wiseman Business Connect' 
                WHERE admin_id = 6
            """)
            
        conn.commit()
        print("Updated global site name to StyleShop.")
        print("Ensured Wiseman Business Connect is associated with admin_id 6.")
        
        conn.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == '__main__':
    fix_site_names()
