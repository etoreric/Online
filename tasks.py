from models import db, Order
from datetime import datetime, timedelta

def cleanup_old_orders(app):
    """Delete orders older than 7 days."""
    with app.app_context():
        cutoff_date = datetime.utcnow() - timedelta(days=7)
        old_orders = Order.query.filter(Order.created_at < cutoff_date).all()
        
        if old_orders:
            count = len(old_orders)
            for order in old_orders:
                db.session.delete(order)
            db.session.commit()
            print(f"[{datetime.utcnow()}] Cleaned up {count} old orders.")
        else:
            print(f"[{datetime.utcnow()}] No old orders to clean up.")
