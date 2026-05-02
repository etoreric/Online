import sys
import os
sys.path.append(os.getcwd())
from app import app
from models import db, User

def create_admin():
    with app.app_context():
        admin = User.query.filter_by(username='admin').first()
        if not admin:
            admin = User(username='admin', email='admin@example.com', is_admin=True)
            admin.set_password('admin123')
            db.session.add(admin)
            db.session.commit()
            print("Admin user created: admin / admin123")
        else:
            admin.is_admin = True
            admin.set_password('admin123')
            db.session.commit()
            print("User 'admin' already exists, updated password to admin123 and ensured admin privileges.")

if __name__ == '__main__':
    create_admin()
