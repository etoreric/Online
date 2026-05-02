from flask import Blueprint, render_template, redirect, url_for, flash, request, session, current_app
from flask_login import login_user, logout_user, login_required, current_user
from flask_mail import Message
from twilio.rest import Client
import os
from models import db, User, AdminInvite, PasswordResetRequest
from datetime import datetime

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('store.home'))

    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')

        user = User.query.filter_by(email=email).first()
        if user and user.check_password(password):
            login_user(user)
            flash('Welcome back!', 'success')
            next_page = request.args.get('next')
            if next_page:
                return redirect(next_page)
            if user.is_admin:
                return redirect(url_for('admin.dashboard'))
            return redirect(url_for('store.home'))
        else:
            flash('Invalid email or password.', 'error')

    return render_template('auth/login.html')


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('store.home'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip()
        phone = request.form.get('phone', '').strip()
        if phone:
            phone = ''.join(c for c in phone if c.isdigit() or c == '+')
        password = request.form.get('password', '')
        confirm = request.form.get('confirm_password', '')

        if not email:
            flash('Email address is required.', 'error')
            return render_template('auth/register.html')

        if password != confirm:
            flash('Passwords do not match.', 'error')
            return render_template('auth/register.html')

        if User.query.filter_by(email=email).first():
            flash('Email already registered.', 'error')
            return render_template('auth/register.html')

        if User.query.filter_by(username=username).first():
            flash('Username already taken.', 'error')
            return render_template('auth/register.html')

        user = User(
            username=username, 
            email=email,
            phone=phone,
            admin_id=session.get('active_admin_id')
        )
        user.set_password(password)
        db.session.add(user)
        db.session.commit()

        login_user(user)
        flash('Account created successfully!', 'success')
        return redirect(url_for('store.home'))

    return render_template('auth/register.html')


@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('store.home'))


@auth_bp.route('/request-password-reset', methods=['GET', 'POST'])
def request_password_reset():
    """User submits a request for superuser to reset their password."""
    if current_user.is_authenticated:
        return redirect(url_for('store.home'))

    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        user = User.query.filter_by(email=email).first()

        if not user:
            flash('No account found with that email address.', 'error')
            return render_template('auth/request_password_reset.html')

        # Check if there is already a pending request for this user
        existing = PasswordResetRequest.query.filter_by(
            user_id=user.id, status='pending'
        ).first()
        if existing:
            flash('You already have a pending reset request. Please wait for the superuser to process it.', 'info')
            return render_template('auth/request_password_reset.html')

        message = request.form.get('message', '').strip()
        req = PasswordResetRequest(user_id=user.id, message=message)
        db.session.add(req)
        db.session.commit()
        flash('Your request has been submitted. The superuser will reset your password and notify you via SMS.', 'success')
        return redirect(url_for('auth.login'))

    return render_template('auth/request_password_reset.html')




@auth_bp.route('/admin-register/<token>', methods=['GET', 'POST'])
def admin_register(token):
    invite = AdminInvite.query.filter_by(token=token, is_used=False).first()
    if not invite or (invite.expires_at and invite.expires_at < datetime.utcnow()):
        flash('Invalid or expired invite link.', 'error')
        return redirect(url_for('auth.login'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip()
        phone = request.form.get('phone', '').strip()
        if phone:
            phone = ''.join(c for c in phone if c.isdigit() or c == '+')
        password = request.form.get('password', '')
        confirm = request.form.get('confirm_password', '')

        if not email:
            flash('Email address is required.', 'error')
            return render_template('auth/admin_register.html', token=token)

        if password != confirm:
            flash('Passwords do not match.', 'error')
            return render_template('auth/admin_register.html', token=token)

        if User.query.filter_by(email=email).first() or User.query.filter_by(username=username).first():
            flash('Username or email already exists.', 'error')
            return render_template('auth/admin_register.html', token=token)

        new_admin = User(username=username, email=email, phone=phone, is_admin=True)
        new_admin.set_password(password)
        db.session.add(new_admin)
        
        invite.is_used = True
        db.session.commit()

        login_user(new_admin)
        flash('Admin account created successfully! Welcome to the portal.', 'success')
        return redirect(url_for('admin.dashboard'))

    return render_template('auth/admin_register.html', token=token)
