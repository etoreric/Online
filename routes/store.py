from flask import Blueprint, render_template, redirect, url_for, flash, request, session, jsonify
from flask_login import current_user
from models import db, Product, Category, Cart, CartItem, Order, OrderItem, User
import uuid

store_bp = Blueprint('store', __name__)


def get_or_create_cart():
    """Get existing cart or create a new one for the current user/session."""
    if current_user.is_authenticated:
        cart = Cart.query.filter_by(user_id=current_user.id).first()
        if not cart:
            # Check if there's a session cart to merge
            session_id = session.get('cart_session_id')
            if session_id:
                cart = Cart.query.filter_by(session_id=session_id).first()
                if cart:
                    cart.user_id = current_user.id
                    cart.session_id = None
                    db.session.commit()
            if not cart:
                cart = Cart(user_id=current_user.id)
                db.session.add(cart)
                db.session.commit()
    else:
        session_id = session.get('cart_session_id')
        if not session_id:
            session_id = str(uuid.uuid4())
            session['cart_session_id'] = session_id
        cart = Cart.query.filter_by(session_id=session_id).first()
        if not cart:
            cart = Cart(session_id=session_id)
            db.session.add(cart)
            db.session.commit()
    return cart


@store_bp.route('/')
def home():
    admin_id = session.get('active_admin_id')
    query = Product.query
    if admin_id:
        query = query.filter_by(admin_id=admin_id)
        
    featured = query.filter_by(featured=True).limit(8).all()
    categories = Category.query.all()
    latest = query.order_by(Product.created_at.desc()).limit(4).all()
    return render_template('store/home.html', featured=featured, categories=categories, latest=latest)


@store_bp.route('/portal/<int:admin_id>')
def portal(admin_id):
    admin = db.get_or_404(User, admin_id)
    if not admin.is_admin and not admin.is_superuser:
        flash('Invalid portal.', 'error')
        return redirect(url_for('store.home'))
    
    session['active_admin_id'] = admin_id
    flash(f'Welcome to {admin.username}\'s portal!', 'info')
    return redirect(url_for('store.home'))


@store_bp.route('/portal/exit')
def exit_portal():
    session.pop('active_admin_id', None)
    flash('You have exited the specialized portal.', 'info')
    return redirect(url_for('store.home'))


@store_bp.route('/shop')
def shop():
    category_slug = request.args.get('category', 'all')
    search = request.args.get('search', '').strip()
    categories = Category.query.all()

    admin_id = session.get('active_admin_id')
    query = Product.query
    if admin_id:
        query = query.filter_by(admin_id=admin_id)
        
    if category_slug and category_slug != 'all':
        cat = Category.query.filter_by(slug=category_slug).first()
        if cat:
            query = query.filter_by(category_id=cat.id)
    if search:
        query = query.filter(Product.name.ilike(f'%{search}%'))

    products = query.order_by(Product.created_at.desc()).all()
    return render_template('store/shop.html', products=products, categories=categories,
                           current_category=category_slug, search=search)


@store_bp.route('/product/<int:product_id>')
def product_detail(product_id):
    product = db.get_or_404(Product, product_id)
    related = Product.query.filter(
        Product.category_id == product.category_id,
        Product.id != product.id
    ).limit(4).all()
    return render_template('store/product.html', product=product, related=related)


@store_bp.route('/cart')
def cart():
    cart = get_or_create_cart()
    return render_template('store/cart.html', cart=cart)


@store_bp.route('/cart/add/<int:product_id>', methods=['POST'])
def add_to_cart(product_id):
    product = db.get_or_404(Product, product_id)
    try:
        quantity = int(request.form.get('quantity', 1))
    except ValueError:
        quantity = 1
    cart = get_or_create_cart()

    # Check if product already in cart
    item = CartItem.query.filter_by(cart_id=cart.id, product_id=product.id).first()
    if item:
        item.quantity += quantity
    else:
        item = CartItem(cart_id=cart.id, product_id=product.id, quantity=quantity)
        db.session.add(item)

    db.session.commit()

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({'success': True, 'cart_count': cart.item_count, 'message': f'{product.name} added to cart'})

    flash(f'{product.name} added to cart!', 'success')
    return redirect(request.referrer or url_for('store.shop'))


@store_bp.route('/cart/update/<int:item_id>', methods=['POST'])
def update_cart(item_id):
    item = db.get_or_404(CartItem, item_id)
    quantity = int(request.form.get('quantity', 1))

    if quantity <= 0:
        db.session.delete(item)
    else:
        item.quantity = quantity

    db.session.commit()

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        cart = get_or_create_cart()
        return jsonify({'success': True, 'cart_count': cart.item_count, 'cart_total': cart.total})

    return redirect(url_for('store.cart'))


@store_bp.route('/cart/remove/<int:item_id>', methods=['POST'])
def remove_from_cart(item_id):
    item = db.get_or_404(CartItem, item_id)
    db.session.delete(item)
    db.session.commit()
    flash('Item removed from cart.', 'info')
    return redirect(url_for('store.cart'))


@store_bp.route('/checkout', methods=['GET', 'POST'])
def checkout():
    cart = get_or_create_cart()
    if not cart.items:
        flash('Your cart is empty.', 'warning')
        return redirect(url_for('store.shop'))

    return render_template('store/checkout.html', cart=cart)


@store_bp.route('/place_order', methods=['POST'])
def place_order():
    customer_name = request.form.get('customer_name', '').strip()
    customer_email = request.form.get('customer_email', '').strip()
    customer_phone = request.form.get('customer_phone', '').strip()
    address = request.form.get('address', '').strip()

    if not customer_name or not customer_email or not customer_phone or not address:
        flash('Please fill in all required fields including delivery address.', 'error')
        return redirect(url_for('store.checkout'))

    cart = get_or_create_cart()
    if not cart or not cart.items:
        flash('Your cart is empty.', 'warning')
        return redirect(url_for('store.shop'))

    order = Order(
        order_number=Order.generate_order_number(),
        user_id=current_user.id if current_user.is_authenticated else None,
        admin_id=cart.items[0].product.admin_id if cart.items else session.get('active_admin_id'),
        customer_name=customer_name,
        customer_email=customer_email,
        customer_phone=customer_phone,
        address=address,
        total=cart.total,
        status='Pending',
        payment_method='Pay on Delivery'
    )
    db.session.add(order)
    db.session.flush()

    for cart_item in cart.items:
        order_item = OrderItem(
            order_id=order.id,
            product_id=cart_item.product_id,
            product_name=cart_item.product.name,
            price=cart_item.product.price,
            quantity=cart_item.quantity
        )
        db.session.add(order_item)
        cart_item.product.stock = max(0, cart_item.product.stock - cart_item.quantity)

    # Clear cart
    for item in cart.items:
        db.session.delete(item)

    db.session.commit()
    flash('Order placed successfully! We will contact you for delivery.', 'success')
    return redirect(url_for('store.order_success', order_number=order.order_number))


@store_bp.route('/order/success/<order_number>')
def order_success(order_number):
    order = Order.query.filter_by(order_number=order_number).first_or_404()
    return render_template('order_success.html', order=order)


@store_bp.route('/orders')
def my_orders():
    if not current_user.is_authenticated:
        flash('Please login to view your orders.', 'warning')
        return redirect(url_for('auth.login'))
    orders = Order.query.filter_by(user_id=current_user.id).order_by(Order.created_at.desc()).all()
    return render_template('store/my_orders.html', orders=orders)


@store_bp.route('/orders/delete/<int:order_id>', methods=['POST'])
def delete_order(order_id):
    if not current_user.is_authenticated:
        flash('Please login to manage your orders.', 'warning')
        return redirect(url_for('auth.login'))
        
    order = db.get_or_404(Order, order_id)
    
    # Ensure the user only deletes their own order
    if order.user_id != current_user.id:
        flash('Unauthorized action.', 'error')
        return redirect(url_for('store.my_orders'))
        
    db.session.delete(order)
    db.session.commit()
    flash(f'Order {order.order_number} has been deleted.', 'success')
    return redirect(url_for('store.my_orders'))


@store_bp.route('/cart/count')
def cart_count():
    cart = get_or_create_cart()
    return jsonify({'count': cart.item_count})


@store_bp.route('/messages')
def messages():
    if not current_user.is_authenticated:
        flash('Please login to view your messages.', 'warning')
        return redirect(url_for('auth.login'))
    
    user_messages = current_user.received_messages.all()
    return render_template('store/messages.html', messages=user_messages)


@store_bp.route('/messages/read/<int:msg_id>', methods=['POST'])
def mark_message_read(msg_id):
    if not current_user.is_authenticated:
        return jsonify({'success': False}), 401
    
    from models import Message
    msg = db.get_or_404(Message, msg_id)
    if msg.recipient_id == current_user.id:
        msg.is_read = True
        db.session.commit()
        return jsonify({'success': True})
    return jsonify({'success': False}), 403


@store_bp.route('/api/public-messages')
def get_public_messages():
    email = request.args.get('email', '').strip()
    if not email:
        return jsonify({'success': False, 'messages': []})
    
    from models import User, Message
    user = User.query.filter_by(email=email).first()
    if not user:
        return jsonify({'success': False, 'messages': []})
    
    # Return last 3 messages for this user (limited for demo purposes)
    msgs = Message.query.filter_by(recipient_id=user.id).order_by(Message.created_at.desc()).limit(3).all()
    
    return jsonify({
        'success': True,
        'messages': [{
            'subject': m.subject,
            'body': m.body,
            'date': m.created_at.strftime('%Y-%m-%d %H:%M')
        } for m in msgs]
    })
