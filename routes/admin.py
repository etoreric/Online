from flask import Blueprint, render_template, redirect, url_for, flash, request, send_file, current_app
from flask_login import login_required, current_user
from models import db, User, Product, Category, Order, SiteSettings, AdminInvite, PasswordResetRequest
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash
from functools import wraps
from datetime import datetime, timedelta
import os
import uuid
import io
from fpdf import FPDF

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'static', 'uploads')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}


def admin_required(f):
    @wraps(f)
    @login_required
    def decorated(*args, **kwargs):
        if not current_user.is_admin and not current_user.is_superuser:
            flash('Access denied. Admin privileges required.', 'error')
            return redirect(url_for('store.home'))
        return f(*args, **kwargs)
    return decorated


def superuser_required(f):
    @wraps(f)
    @login_required
    def decorated(*args, **kwargs):
        if not getattr(current_user, 'is_superuser', False):
            flash('Access denied. Super User privileges required.', 'error')
            return redirect(url_for('admin.dashboard'))
        return f(*args, **kwargs)
    return decorated


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@admin_bp.route('/')
@admin_required
def dashboard():
    top_products = Product.query.filter_by(admin_id=current_user.id).order_by(Product.created_at.desc()).limit(5).all()
    
    total_admins = 0
    total_customers = 0

    if current_user.is_superuser:
        total_revenue = db.session.query(db.func.sum(Order.total)).scalar() or 0
        total_orders = Order.query.count()
        total_products = Product.query.count()
        total_users = User.query.count()
        total_admins = User.query.filter(User.is_admin == True).count()
        total_customers = User.query.filter((User.is_admin == False) | (User.is_admin == None)).count()
        recent_orders = Order.query.order_by(Order.created_at.desc()).limit(5).all()
        top_products = Product.query.order_by(Product.created_at.desc()).limit(5).all()
    else:
        total_revenue = db.session.query(db.func.sum(Order.total)).filter(Order.admin_id == current_user.id).scalar() or 0
        total_orders = Order.query.filter_by(admin_id=current_user.id).count()
        total_products = Product.query.filter_by(admin_id=current_user.id).count()
        total_users = User.query.filter_by(admin_id=current_user.id).count()
        total_customers = total_users
        recent_orders = Order.query.filter_by(admin_id=current_user.id).order_by(Order.created_at.desc()).limit(5).all()
        top_products = Product.query.filter_by(admin_id=current_user.id).order_by(Product.created_at.desc()).limit(5).all()

    # Calculate conversion rate (orders / products as a simple metric)
    conversion_rate = (total_orders / max(total_products, 1)) * 100 if total_products else 0

    return render_template('admin/dashboard.html',
                           total_revenue=total_revenue,
                           total_orders=total_orders,
                           total_products=total_products,
                           total_users=total_users,
                           total_admins=total_admins,
                           total_customers=total_customers,
                           conversion_rate=round(conversion_rate, 2),
                           recent_orders=recent_orders,
                           top_products=top_products)


import re

def slugify(text):
    text = text.lower()
    return re.sub(r'[\W_]+', '-', text).strip('-')


@admin_bp.route('/categories')
@admin_required
def categories():
    if current_user.is_superuser:
        all_categories = Category.query.order_by(Category.name).all()
    else:
        all_categories = Category.query.filter_by(admin_id=current_user.id).order_by(Category.name).all()
    return render_template('admin/categories.html', categories=all_categories)


@admin_bp.route('/categories/add', methods=['GET', 'POST'])
@admin_required
def add_category():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        if not name:
            flash('Category name is required.', 'error')
            return redirect(url_for('admin.add_category'))
            
        slug = slugify(name)
        if Category.query.filter_by(slug=slug, admin_id=current_user.id).first():
            flash('You already have a category with this name.', 'error')
            return redirect(url_for('admin.add_category'))
            
        category = Category(name=name, slug=slug, admin_id=current_user.id)
        db.session.add(category)
        db.session.commit()
        flash(f'Category "{name}" added successfully!', 'success')
        return redirect(url_for('admin.categories'))

    return render_template('admin/category_form.html', category=None)


@admin_bp.route('/categories/edit/<int:category_id>', methods=['GET', 'POST'])
@admin_required
def edit_category(category_id):
    category = db.get_or_404(Category, category_id)
    if not current_user.is_superuser and category.admin_id != current_user.id:
        flash('Permission denied. You can only edit your own categories.', 'error')
        return redirect(url_for('admin.categories'))

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        if not name:
            flash('Category name is required.', 'error')
            return redirect(url_for('admin.edit_category', category_id=category.id))

        slug = slugify(name)
        existing = Category.query.filter_by(slug=slug, admin_id=current_user.id).first()
        if existing and existing.id != category.id:
            flash('You already have another category with this name.', 'error')
            return redirect(url_for('admin.edit_category', category_id=category.id))

        category.name = name
        category.slug = slug
        db.session.commit()
        flash(f'Category updated to "{name}"!', 'success')
        return redirect(url_for('admin.categories'))

    return render_template('admin/category_form.html', category=category)


@admin_bp.route('/categories/delete/<int:category_id>', methods=['POST'])
@admin_required
def delete_category(category_id):
    category = db.get_or_404(Category, category_id)
    if not current_user.is_superuser and category.admin_id != current_user.id:
        flash('Permission denied. You can only delete your own categories.', 'error')
        return redirect(url_for('admin.categories'))
    if category.products:
        flash(f'Cannot delete category "{category.name}" because it has products associated with it.', 'error')
        return redirect(url_for('admin.categories'))
        
    db.session.delete(category)
    db.session.commit()
    flash('Category deleted.', 'success')
    return redirect(url_for('admin.categories'))


@admin_bp.route('/products')
@admin_required
def products():
    if current_user.is_superuser:
        all_products = Product.query.order_by(Product.created_at.desc()).all()
    else:
        all_products = Product.query.filter_by(admin_id=current_user.id).order_by(Product.created_at.desc()).all()
    return render_template('admin/products.html', products=all_products)


@admin_bp.route('/products/add', methods=['GET', 'POST'])
@admin_required
def add_product():
    if current_user.is_superuser:
        categories = Category.query.all()
    else:
        categories = Category.query.filter_by(admin_id=current_user.id).all()

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        description = request.form.get('description', '').strip()
        try:
            price = float(request.form.get('price', 0))
            category_id = int(request.form.get('category_id', 0))
            stock = int(request.form.get('stock', 0))
        except ValueError:
            flash('Invalid input for price, category, or stock.', 'error')
            return redirect(url_for('admin.add_product'))
        featured = request.form.get('featured') == 'on'

        image_filename = None
        if 'image' in request.files:
            file = request.files['image']
            if file and file.filename and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                # Add timestamp to avoid collisions
                import time
                filename = f"{int(time.time())}_{filename}"
                os.makedirs(UPLOAD_FOLDER, exist_ok=True)
                file.save(os.path.join(UPLOAD_FOLDER, filename))
                image_filename = filename

        product = Product(
            name=name,
            description=description,
            price=price,
            category_id=category_id if category_id else None,
            stock=stock,
            featured=featured,
            image=image_filename,
            admin_id=current_user.id
        )
        db.session.add(product)
        db.session.commit()
        flash(f'Product "{name}" added successfully!', 'success')
        return redirect(url_for('admin.products'))

    return render_template('admin/product_form.html', categories=categories, product=None)


@admin_bp.route('/products/edit/<int:product_id>', methods=['GET', 'POST'])
@admin_required
def edit_product(product_id):
    product = db.get_or_404(Product, product_id)
    if not current_user.is_superuser and product.admin_id != current_user.id:
        flash('Permission denied. You can only edit your own products.', 'error')
        return redirect(url_for('admin.products'))
    if current_user.is_superuser:
        categories = Category.query.all()
    else:
        categories = Category.query.filter_by(admin_id=current_user.id).all()

    if request.method == 'POST':
        product.name = request.form.get('name', '').strip()
        product.description = request.form.get('description', '').strip()
        try:
            product.price = float(request.form.get('price', 0))
            product.category_id = int(request.form.get('category_id', 0)) or None
            product.stock = int(request.form.get('stock', 0))
        except ValueError:
            flash('Invalid input for price, category, or stock.', 'error')
            return redirect(url_for('admin.edit_product', product_id=product.id))
        product.featured = request.form.get('featured') == 'on'

        if 'image' in request.files:
            file = request.files['image']
            if file and file.filename and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                import time
                filename = f"{int(time.time())}_{filename}"
                os.makedirs(UPLOAD_FOLDER, exist_ok=True)
                file.save(os.path.join(UPLOAD_FOLDER, filename))
                # Delete old image
                if product.image:
                    old_path = os.path.join(UPLOAD_FOLDER, product.image)
                    if os.path.exists(old_path):
                        os.remove(old_path)
                product.image = filename

        db.session.commit()
        flash(f'Product "{product.name}" updated!', 'success')
        return redirect(url_for('admin.products'))

    return render_template('admin/product_form.html', categories=categories, product=product)


@admin_bp.route('/products/delete/<int:product_id>', methods=['POST'])
@admin_required
def delete_product(product_id):
    product = db.get_or_404(Product, product_id)
    if not current_user.is_superuser and product.admin_id != current_user.id:
        flash('Permission denied. You can only delete your own products.', 'error')
        return redirect(url_for('admin.products'))
    if product.image:
        img_path = os.path.join(UPLOAD_FOLDER, product.image)
        if os.path.exists(img_path):
            os.remove(img_path)
    db.session.delete(product)
    db.session.commit()
    flash(f'Product deleted.', 'success')
    return redirect(url_for('admin.products'))


@admin_bp.route('/orders')
@admin_required
def orders():
    if current_user.is_superuser:
        all_orders = Order.query.order_by(Order.created_at.desc()).all()
        total_revenue = db.session.query(db.func.sum(Order.total)).scalar() or 0
    else:
        all_orders = Order.query.filter_by(admin_id=current_user.id).order_by(Order.created_at.desc()).all()
        total_revenue = db.session.query(db.func.sum(Order.total)).filter(Order.admin_id == current_user.id).scalar() or 0
    return render_template('admin/orders.html', orders=all_orders, total_revenue=total_revenue)


@admin_bp.route('/revenue')
@admin_required
def revenue():
    if current_user.is_superuser:
        orders = Order.query.order_by(Order.created_at.desc()).all()
        total_revenue = db.session.query(db.func.sum(Order.total)).scalar() or 0
    else:
        orders = Order.query.filter_by(admin_id=current_user.id).order_by(Order.created_at.desc()).all()
        total_revenue = db.session.query(db.func.sum(Order.total)).filter(Order.admin_id == current_user.id).scalar() or 0
    
    # Simple revenue by date
    revenue_by_date = {}
    for order in orders:
        date_str = order.created_at.strftime('%Y-%m-%d')
        revenue_by_date[date_str] = revenue_by_date.get(date_str, 0) + order.total
    
    sorted_revenue = sorted(revenue_by_date.items(), reverse=True)
    
    return render_template('admin/revenue.html', 
                           total_revenue=total_revenue, 
                           revenue_data=sorted_revenue)


@admin_bp.route('/revenue/export-pdf')
@admin_required
def export_revenue_pdf():
    if current_user.is_superuser:
        orders = Order.query.order_by(Order.created_at.desc()).all()
        total_revenue = db.session.query(db.func.sum(Order.total)).scalar() or 0
    else:
        orders = Order.query.filter_by(admin_id=current_user.id).order_by(Order.created_at.desc()).all()
        total_revenue = db.session.query(db.func.sum(Order.total)).filter(Order.admin_id == current_user.id).scalar() or 0
    
    # Group by date
    revenue_by_date = {}
    for order in orders:
        date_str = order.created_at.strftime('%Y-%m-%d')
        revenue_by_date[date_str] = revenue_by_date.get(date_str, 0) + order.total
    
    sorted_revenue = sorted(revenue_by_date.items(), reverse=True)

    # Generate PDF
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, "Revenue Report", ln=True, align="C")
    pdf.ln(5)
    
    pdf.set_font("Helvetica", "", 12)
    pdf.cell(0, 10, f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", ln=True)
    pdf.cell(0, 10, f"Total Revenue: GHS {total_revenue:,.2f}", ln=True)
    pdf.ln(5)
    
    # Table Header
    pdf.set_font("Helvetica", "B", 12)
    pdf.set_fill_color(240, 240, 240)
    pdf.cell(95, 10, "Date", 1, 0, "L", fill=True)
    pdf.cell(95, 10, "Revenue (GHS)", 1, 1, "R", fill=True)
    
    # Table Data
    pdf.set_font("Helvetica", "", 12)
    for date, amount in sorted_revenue:
        pdf.cell(95, 10, date, 1, 0, "L")
        pdf.cell(95, 10, f"{amount:,.2f}", 1, 1, "R")
    
    output = io.BytesIO()
    pdf.output(output)
    output.seek(0)
    
    return send_file(output, 
                     download_name=f"revenue_report_{datetime.now().strftime('%Y%m%d')}.pdf",
                     as_attachment=True,
                     mimetype='application/pdf')


@admin_bp.route('/orders/export-pdf')
@admin_required
def export_orders_pdf():
    if current_user.is_superuser:
        orders = Order.query.order_by(Order.created_at.desc()).all()
    else:
        orders = Order.query.filter_by(admin_id=current_user.id).order_by(Order.created_at.desc()).all()
    
    # Generate PDF
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, "Orders Report", ln=True, align="C")
    pdf.ln(5)
    
    pdf.set_font("Helvetica", "", 12)
    pdf.cell(0, 10, f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", ln=True)
    pdf.cell(0, 10, f"Total Orders: {len(orders)}", ln=True)
    pdf.ln(5)
    
    # Table Header
    pdf.set_font("Helvetica", "B", 10)
    pdf.set_fill_color(240, 240, 240)
    pdf.cell(40, 10, "Order #", 1, 0, "L", fill=True)
    pdf.cell(50, 10, "Customer", 1, 0, "L", fill=True)
    pdf.cell(30, 10, "Date", 1, 0, "L", fill=True)
    pdf.cell(30, 10, "Status", 1, 0, "L", fill=True)
    pdf.cell(40, 10, "Total (GHS)", 1, 1, "R", fill=True)
    
    # Table Data
    pdf.set_font("Helvetica", "", 10)
    for order in orders:
        pdf.cell(40, 10, order.order_number, 1, 0, "L")
        pdf.cell(50, 10, order.customer_name[:20], 1, 0, "L")
        pdf.cell(30, 10, order.created_at.strftime('%Y-%m-%d'), 1, 0, "L")
        pdf.cell(30, 10, order.status, 1, 0, "L")
        pdf.cell(40, 10, f"{order.total:,.2f}", 1, 1, "R")
    
    output = io.BytesIO()
    pdf.output(output)
    output.seek(0)
    
    return send_file(output, 
                     download_name=f"orders_report_{datetime.now().strftime('%Y%m%d')}.pdf",
                     as_attachment=True,
                     mimetype='application/pdf')


@admin_bp.route('/orders/update-status/<int:order_id>', methods=['POST'])
@admin_required
def update_order_status(order_id):
    order = db.get_or_404(Order, order_id)
    if not current_user.is_superuser and order.admin_id != current_user.id:
        flash('Permission denied. You can only update your own orders.', 'error')
        return redirect(url_for('admin.orders'))
    new_status = request.form.get('status')
    if new_status in ['Pending', 'Processing', 'Shipped', 'Delivered', 'Cancelled']:
        order.status = new_status
        db.session.commit()
        flash(f'Order {order.order_number} status updated to {new_status}.', 'success')
    return redirect(url_for('admin.orders'))


@admin_bp.route('/export-weekly-summary')
@admin_required
def export_weekly_summary():
    seven_days_ago = datetime.utcnow() - timedelta(days=7)
    
    if current_user.is_superuser:
        orders = Order.query.filter(Order.created_at >= seven_days_ago).all()
        new_customers = User.query.filter(User.created_at >= seven_days_ago, (User.is_admin == False) | (User.is_admin == None)).count()
    else:
        orders = Order.query.filter(Order.admin_id == current_user.id, Order.created_at >= seven_days_ago).all()
        new_customers = User.query.filter(User.admin_id == current_user.id, User.created_at >= seven_days_ago).count()
    
    total_revenue = sum(order.total for order in orders)
    total_orders = len(orders)
    
    # Daily breakdown for the week
    daily_revenue = {}
    for i in range(7):
        date = (datetime.utcnow() - timedelta(days=i)).strftime('%Y-%m-%d')
        daily_revenue[date] = 0
    
    for order in orders:
        date_str = order.created_at.strftime('%Y-%m-%d')
        if date_str in daily_revenue:
            daily_revenue[date_str] += order.total
    
    sorted_daily = sorted(daily_revenue.items())

    # Generate PDF
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 18)
    pdf.cell(0, 15, "Weekly Performance Summary", ln=True, align="C")
    pdf.set_font("Helvetica", "", 12)
    pdf.cell(0, 10, f"Period: {seven_days_ago.strftime('%b %d')} - {datetime.utcnow().strftime('%b %d, %Y')}", ln=True, align="C")
    pdf.ln(10)
    
    # Summary Box
    pdf.set_fill_color(245, 245, 245)
    pdf.set_font("Helvetica", "B", 14)
    pdf.cell(0, 12, " Key Metrics", 0, 1, "L", fill=True)
    pdf.set_font("Helvetica", "", 12)
    pdf.cell(90, 10, f"Total Revenue:", 0, 0)
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 10, f"GHS {total_revenue:,.2f}", 0, 1)
    
    pdf.set_font("Helvetica", "", 12)
    pdf.cell(90, 10, f"Total Orders:", 0, 0)
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 10, f"{total_orders}", 0, 1)
    
    pdf.set_font("Helvetica", "", 12)
    pdf.cell(90, 10, f"New Customers:", 0, 0)
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 10, f"{new_customers}", 0, 1)
    pdf.ln(10)
    
    # Daily Revenue Table
    pdf.set_font("Helvetica", "B", 14)
    pdf.cell(0, 12, " Daily Revenue Breakdown", 0, 1, "L", fill=True)
    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(95, 10, "Date", 1, 0, "C")
    pdf.cell(95, 10, "Revenue (GHS)", 1, 1, "C")
    
    pdf.set_font("Helvetica", "", 11)
    for date, amount in sorted_daily:
        pdf.cell(95, 10, date, 1, 0, "C")
        pdf.cell(95, 10, f"{amount:,.2f}", 1, 1, "R")
        
    pdf.ln(15)
    pdf.set_font("Helvetica", "I", 10)
    pdf.cell(0, 10, "Generated by Online Store Admin Portal", 0, 0, "C")
    
    output = io.BytesIO()
    pdf.output(output)
    output.seek(0)
    
    return send_file(output, 
                     download_name=f"weekly_summary_{datetime.now().strftime('%Y%m%d')}.pdf",
                     as_attachment=True,
                     mimetype='application/pdf')


@admin_bp.route('/orders/delete/<int:order_id>', methods=['POST'])
@admin_required
def delete_order(order_id):
    order = db.get_or_404(Order, order_id)
    if not current_user.is_superuser and order.admin_id != current_user.id:
        flash('Permission denied. You can only delete your own orders.', 'error')
        return redirect(url_for('admin.orders'))
    db.session.delete(order)
    db.session.commit()
    flash(f'Order {order.order_number} deleted successfully.', 'success')
    return redirect(url_for('admin.orders'))


@admin_bp.route('/users/delete/<int:user_id>', methods=['POST'])
@admin_required
def delete_user(user_id):
    redirect_url = request.referrer or url_for('admin.dashboard')
    
    if user_id == current_user.id:
        flash('You cannot delete your own account.', 'error')
        return redirect(redirect_url)
    
    user = db.get_or_404(User, user_id)
    
    # If not superuser, admin can only delete users registered under them
    if not current_user.is_superuser and user.admin_id != current_user.id:
        flash('Permission denied.', 'error')
        return redirect(redirect_url)
        
    username = user.username
    db.session.delete(user)
    db.session.commit()
    
    flash(f'User {username} deleted.', 'success')
    return redirect(redirect_url)


@admin_bp.route('/admins')
@superuser_required
def admins():
    superusers = User.query.filter_by(is_superuser=True).order_by(User.created_at.desc()).all()
    regular_admins = User.query.filter_by(is_admin=True, is_superuser=False).order_by(User.created_at.desc()).all()
    return render_template('admin/administrator.html', superusers=superusers, admins=regular_admins)


@admin_bp.route('/customers')
@admin_required
def customers():
    if current_user.is_superuser:
        all_customers = User.query.filter((User.is_admin == False) | (User.is_admin == None)).order_by(User.created_at.desc()).all()
    else:
        all_customers = User.query.filter_by(admin_id=current_user.id).order_by(User.created_at.desc()).all()
    return render_template('admin/customers.html', customers=all_customers)


@admin_bp.route('/settings', methods=['GET', 'POST'])
@admin_required
def settings():
    site_settings = SiteSettings.get_settings()
    
    if request.method == 'POST':
        site_settings.hero_title = request.form.get('hero_title', '').strip()
        site_settings.hero_subtitle = request.form.get('hero_subtitle', '').strip()
        site_settings.site_name = request.form.get('site_name', 'StyleShop').strip()
        site_settings.footer_about = request.form.get('footer_about', '').strip()
        site_settings.social_facebook = request.form.get('social_facebook', '#').strip() or '#'
        site_settings.social_tiktok = request.form.get('social_tiktok', '#').strip() or '#'
        site_settings.social_instagram = request.form.get('social_instagram', '#').strip() or '#'
        site_settings.promo_enabled = request.form.get('promo_enabled') == 'on'
        site_settings.promo_title = request.form.get('promo_title', 'Get 20% Off Your First Order').strip()
        site_settings.promo_subtitle = request.form.get('promo_subtitle', '').strip()
        
        if 'hero_bg_image' in request.files:
            file = request.files['hero_bg_image']
            if file and file.filename and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                import time
                filename = f"hero_{int(time.time())}_{filename}"
                os.makedirs(UPLOAD_FOLDER, exist_ok=True)
                file.save(os.path.join(UPLOAD_FOLDER, filename))
                
                # Delete old image if it exists
                if site_settings.hero_bg_image:
                    old_path = os.path.join(UPLOAD_FOLDER, site_settings.hero_bg_image)
                    if os.path.exists(old_path):
                        try:
                            os.remove(old_path)
                        except:
                            pass
                
                site_settings.hero_bg_image = filename
        
        db.session.commit()
        flash('Site settings updated successfully!', 'success')
        return redirect(url_for('admin.settings'))
        
    return render_template('admin/settings.html', settings=site_settings)


@admin_bp.route('/superuser')
@superuser_required
def superuser_dashboard():
    superusers = User.query.filter_by(is_superuser=True).order_by(User.created_at.desc()).all()
    regular_admins = User.query.filter_by(is_admin=True, is_superuser=False).order_by(User.created_at.desc()).all()
    invites = AdminInvite.query.filter_by(is_used=False).all()
    return render_template('admin/superuser.html',
                           superusers=superusers,
                           admins=regular_admins,
                           invites=invites)


@admin_bp.route('/password-resets')
@superuser_required
def password_resets():
    reset_requests = PasswordResetRequest.query.order_by(
        PasswordResetRequest.status.asc(),         # pending first
        PasswordResetRequest.requested_at.desc()   # newest first
    ).all()
    return render_template('admin/password_resets.html', reset_requests=reset_requests)


@admin_bp.route('/superuser/generate-invite', methods=['POST'])
@superuser_required
def generate_invite():
    token = AdminInvite.generate_token()
    invite = AdminInvite(
        token=token,
        expires_at=datetime.utcnow() + timedelta(days=7)
    )
    db.session.add(invite)
    db.session.commit()
    
    invite_url = url_for('auth.admin_register', token=token, _external=True)
    flash(f'New portal link generated: {invite_url}', 'success')
    return redirect(url_for('admin.superuser_dashboard'))


@admin_bp.route('/superuser/create-admin', methods=['POST'])
@superuser_required
def create_admin():
    username = request.form.get('username')
    email = request.form.get('email')
    phone = request.form.get('phone')
    if phone:
        phone = ''.join(c for c in phone if c.isdigit() or c == '+')
    password = request.form.get('password')
    
    if User.query.filter_by(username=username).first() or User.query.filter_by(email=email).first():
        flash('Username or email already exists.', 'error')
        return redirect(url_for('admin.superuser_dashboard'))
        
    new_admin = User(username=username, email=email, phone=phone, is_admin=True)
    new_admin.set_password(password)
    db.session.add(new_admin)
    db.session.commit()
    
    flash(f'Admin user {username} created successfully!', 'success')
    return redirect(url_for('admin.superuser_dashboard'))


@admin_bp.route('/superuser/delete-admin/<int:user_id>', methods=['POST'])
@superuser_required
def delete_admin(user_id):
    if user_id == current_user.id:
        flash('You cannot delete your own account.', 'error')
        return redirect(url_for('admin.admins'))
    
    user = db.get_or_404(User, user_id)
    username = user.username
    db.session.delete(user)
    db.session.commit()
    
    flash(f'Admin user {username} has been deleted.', 'success')
    return redirect(url_for('admin.admins'))


@admin_bp.route('/superuser/delete-invite/<int:invite_id>', methods=['POST'])
@superuser_required
def delete_invite(invite_id):
    invite = db.get_or_404(AdminInvite, invite_id)
    db.session.delete(invite)
    db.session.commit()
    flash('Portal link deleted.', 'success')
    return redirect(url_for('admin.superuser_dashboard'))


@admin_bp.route('/superuser/clear-all-invites', methods=['POST'])
@superuser_required
def clear_all_invites():
    AdminInvite.query.filter_by(is_used=False).delete()
    db.session.commit()
    flash('All pending portal links cleared.', 'success')
    return redirect(url_for('admin.superuser_dashboard'))


@admin_bp.route('/superuser/reset-password/<int:user_id>', methods=['POST'])
@superuser_required
def superuser_reset_password(user_id):
    user = db.get_or_404(User, user_id)
    new_password = request.form.get('new_password')
    if not new_password or len(new_password) < 6:
        flash('Password must be at least 6 characters.', 'error')
    else:
        user.set_password(new_password)
        db.session.commit()
        flash(f'Password for admin {user.username} has been reset.', 'success')
    return redirect(url_for('admin.admins'))


@admin_bp.route('/superuser/fulfill-reset/<int:req_id>', methods=['POST'])
@superuser_required
def fulfill_reset_request(req_id):
    """Superuser sets a new password for a user and notifies them via SMS."""
    reset_req = db.get_or_404(PasswordResetRequest, req_id)
    new_password = request.form.get('new_password', '').strip()

    if not new_password or len(new_password) < 6:
        flash('Password must be at least 6 characters.', 'error')
        return redirect(url_for('admin.password_resets'))

    user = reset_req.user
    user.set_password(new_password)

    # Mark the request as completed
    reset_req.status = 'completed'
    reset_req.resolved_at = datetime.utcnow()
    db.session.commit()

    # Send SMS via Twilio
    account_sid = os.getenv('TWILIO_ACCOUNT_SID')
    auth_token  = os.getenv('TWILIO_AUTH_TOKEN')
    twilio_number = os.getenv('TWILIO_PHONE_NUMBER')

    # Ensure E.164 format
    target_phone = user.phone
    if target_phone and not target_phone.startswith('+'):
        target_phone = ('+233' + target_phone[1:]) if target_phone.startswith('0') else ('+233' + target_phone)

    is_configured = all([account_sid, auth_token, twilio_number]) and 'your_' not in account_sid

    if is_configured:
        try:
            from twilio.rest import Client
            client = Client(account_sid, auth_token)
            client.messages.create(
                body=(f"Hello {user.username}, your StyleShop password has been reset by the administrator. "
                      f"Your new temporary password is: {new_password}  "
                      f"Please log in and change it immediately."),
                from_=twilio_number,
                to=target_phone
            )
            flash(f"Password reset and SMS sent to {user.username} ({user.phone}).", 'success')
            current_app.logger.info(f"Password reset SMS sent to {user.phone} for request #{req_id}")
        except Exception as e:
            current_app.logger.error(f"Twilio SMS error on fulfill-reset for {user.phone}: {e}")
            flash(f'Password reset for {user.username}, but SMS failed: {e}', 'warning')
    else:
        # Twilio not configured — log without revealing the password
        current_app.logger.warning(f"Twilio not configured. Password reset for {user.phone} (req #{req_id}), SMS not sent.")
        flash(f'Password reset for {user.username}. (SMS not sent — Twilio not configured.)', 'warning')

    return redirect(url_for('admin.password_resets'))


@admin_bp.route('/superuser/delete-reset/<int:req_id>', methods=['POST'])
@superuser_required
def delete_reset_request(req_id):
    reset_req = db.get_or_404(PasswordResetRequest, req_id)
    db.session.delete(reset_req)
    db.session.commit()
    flash('Password reset request deleted successfully.', 'success')
    return redirect(url_for('admin.password_resets'))


@admin_bp.route('/database-management')
@superuser_required
def database_management():
    return render_template('admin/database_management.html')


@admin_bp.route('/superuser/export-db')
@superuser_required
def export_db():
    db_uri = current_app.config.get('SQLALCHEMY_DATABASE_URI', '')
    if db_uri.startswith('sqlite:///'):
        db_path = db_uri.replace('sqlite:///', '')
        if not os.path.isabs(db_path):
            db_path = os.path.join(current_app.instance_path, db_path)
        if os.path.exists(db_path):
            return send_file(db_path, as_attachment=True, download_name='styleshop_backup.db')
    flash('Database export is only supported for SQLite.', 'error')
    return redirect(url_for('admin.database_management'))


@admin_bp.route('/superuser/import-db', methods=['POST'])
@superuser_required
def import_db():
    if 'db_file' not in request.files:
        flash('No file uploaded.', 'error')
        return redirect(url_for('admin.database_management'))
        
    file = request.files['db_file']
    if file.filename == '':
        flash('No selected file.', 'error')
        return redirect(url_for('admin.database_management'))
        
    if file and file.filename.endswith('.db'):
        db_uri = current_app.config.get('SQLALCHEMY_DATABASE_URI', '')
        if db_uri.startswith('sqlite:///'):
            db_path = db_uri.replace('sqlite:///', '')
            if not os.path.isabs(db_path):
                db_path = os.path.join(current_app.instance_path, db_path)
            try:
                # Dispose of SQLAlchemy engine to release file locks on Windows
                db.engine.dispose()
                # Save the uploaded file
                file.save(db_path)
                flash('Database imported successfully. The entire application state has been updated.', 'success')
            except Exception as e:
                flash(f'Error importing database: {str(e)}', 'error')
        else:
            flash('Database import is only supported for SQLite.', 'error')
    else:
        flash('Invalid file format. Please upload a valid .db SQLite database file.', 'error')
        
    return redirect(url_for('admin.database_management'))


@admin_bp.route('/profile', methods=['GET', 'POST'])
@admin_required
def profile():
    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'change_password':
            current_pass = request.form.get('current_password')
            new_pass = request.form.get('new_password')
            confirm_pass = request.form.get('confirm_password')
            
            if not current_user.check_password(current_pass):
                flash('Incorrect current password.', 'error')
            elif new_pass != confirm_pass:
                flash('New passwords do not match.', 'error')
            elif len(new_pass) < 6:
                flash('Password must be at least 6 characters.', 'error')
            else:
                current_user.set_password(new_pass)
                db.session.commit()
                flash('Your password has been changed successfully.', 'success')
            
            return redirect(url_for('admin.profile'))
            
        elif action == 'change_email':
            new_email = request.form.get('new_email', '').strip()
            if not new_email:
                flash('Email address cannot be empty.', 'error')
            elif User.query.filter(User.email == new_email, User.id != current_user.id).first():
                flash('This email is already in use by another account.', 'error')
            else:
                current_user.email = new_email
                db.session.commit()
                flash('Your email address has been updated successfully.', 'success')
                
            return redirect(url_for('admin.profile'))
            
    return render_template('admin/profile.html')
