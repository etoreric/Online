import os
from flask import Flask
from flask_login import LoginManager
from flask_mail import Mail
from flask_apscheduler import APScheduler
from dotenv import load_dotenv
from models import db, User, SiteSettings

load_dotenv()


def create_app():
    app = Flask(__name__)

    # Configuration
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret-key')
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///styleshop.db'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max upload

    # Mail configuration
    app.config['MAIL_SERVER'] = os.getenv('MAIL_SERVER', 'smtp.gmail.com')
    app.config['MAIL_PORT'] = int(os.getenv('MAIL_PORT', 587))
    app.config['MAIL_USE_TLS'] = os.getenv('MAIL_USE_TLS', 'True').lower() == 'true'
    app.config['MAIL_USERNAME'] = os.getenv('MAIL_USERNAME')
    app.config['MAIL_PASSWORD'] = os.getenv('MAIL_PASSWORD')
    app.config['MAIL_DEFAULT_SENDER'] = os.getenv('MAIL_DEFAULT_SENDER', app.config['MAIL_USERNAME'])

    # Initialize extensions
    db.init_app(app)

    login_manager = LoginManager()
    login_manager.login_view = 'auth.login'
    login_manager.login_message_category = 'info'
    login_manager.init_app(app)

    mail = Mail(app)
    app.extensions['mail'] = mail

    # Initialize scheduler
    scheduler = APScheduler()
    
    # Schedule tasks
    from tasks import cleanup_old_orders
    scheduler.add_job(id='cleanup_orders', func=cleanup_old_orders, args=[app], trigger='interval', hours=24)
    
    scheduler.init_app(app)
    scheduler.start()

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))

    # Register blueprints
    from routes.auth import auth_bp
    from routes.store import store_bp
    from routes.admin import admin_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(store_bp)
    app.register_blueprint(admin_bp)

    # Create tables
    with app.app_context():
        db.create_all()

        # Create uploads directory
        uploads_dir = os.path.join(app.static_folder, 'uploads')
        os.makedirs(uploads_dir, exist_ok=True)

    # Context processor for cart count in templates
    @app.context_processor
    def cart_context():
        from flask_login import current_user
        from flask import session
        from models import Cart

        cart_count = 0
        try:
            if current_user.is_authenticated:
                cart = Cart.query.filter_by(user_id=current_user.id).first()
            else:
                session_id = session.get('cart_session_id')
                cart = Cart.query.filter_by(session_id=session_id).first() if session_id else None
            if cart:
                cart_count = cart.item_count
        except Exception:
            pass

        return {'cart_count': cart_count}

    @app.context_processor
    def settings_context():
        return {'settings': SiteSettings.get_settings()}

    @app.template_filter('from_json')
    def from_json_filter(value):
        import json
        return json.loads(value)

    return app


app = create_app()

if __name__ == '__main__':
    app.run(debug=True, port=5000)
