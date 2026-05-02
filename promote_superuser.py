import sys
from app import create_app
from models import db, User

def promote_user(username):
    app = create_app()
    with app.app_context():
        user = User.query.filter_by(username=username).first()
        if not user:
            print(f"User '{username}' not found.")
            return
        
        user.is_admin = True
        user.is_superuser = True
        db.session.commit()
        print(f"User '{username}' has been promoted to Super User.")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        promote_user(sys.argv[1])
    else:
        print("Usage: python promote_superuser.py <username>")
