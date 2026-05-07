import sqlite3
import os

def update_settings():
    try:
        db_path = 'instance/styleshop.db'
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Available image in static/uploads
        # hero_1777400561_Arrangement_of_black_friday_shopping_carts_with_copy_space___Free_Photo.jpg
        existing_image = 'hero_1777400561_Arrangement_of_black_friday_shopping_carts_with_copy_space___Free_Photo.jpg'
        
        cursor.execute("UPDATE site_settings SET hero_bg_image = ? WHERE admin_id IS NULL", (existing_image,))
        conn.commit()
        print(f"Updated global site settings to use {existing_image}")
        
        conn.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == '__main__':
    update_settings()
