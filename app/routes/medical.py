from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app import db
from app.models import Order, Inventory
from datetime import datetime

medical_bp = Blueprint('medical', __name__, url_prefix='/medical')

@medical_bp.route('/dashboard')
@login_required
def dashboard():
    if current_user.role != 'medical':
        return redirect(url_for('auth.login'))
        
    new_orders = Order.query.filter_by(status='placed').order_by(Order.created_at.desc()).all()
    active_orders = Order.query.filter(Order.status.in_(['packed', 'dispatched'])).order_by(Order.created_at.desc()).all()
    completed_orders = Order.query.filter_by(status='delivered').order_by(Order.created_at.desc()).limit(10).all()
    
    return render_template('medical/dashboard.html', 
                          title='Pharmacy Dashboard', 
                          new_orders=new_orders, 
                          active_orders=active_orders,
                          completed_orders=completed_orders)

@medical_bp.route('/dispatch/<int:order_id>', methods=['GET', 'POST'])
@login_required
def dispatch_order(order_id):
    if current_user.role != 'medical': return redirect(url_for('auth.login'))
    
    order = Order.query.get_or_404(order_id)
    
    if request.method == 'POST':
        order.delivery_agent = request.form.get('agent_name')
        order.eta = request.form.get('eta')
        
    order.status = 'dispatched'
    db.session.commit()
    flash(f'Order #{order.id} dispatched with agent {order.delivery_agent}.')
    return redirect(url_for('medical.dashboard'))

@medical_bp.route('/deliver/<int:order_id>')
@login_required
def deliver_order(order_id):
    if current_user.role != 'medical': return redirect(url_for('auth.login'))
    
    order = Order.query.get_or_404(order_id)
    order.status = 'delivered'
    db.session.commit()
    flash(f'Order #{order.id} marked as Delivered.')
    return redirect(url_for('medical.dashboard'))

@medical_bp.route('/inventory', methods=['GET', 'POST'])
@login_required
def inventory():
    if current_user.role != 'medical': return redirect(url_for('auth.login'))
    
    if request.method == 'POST':
        name = request.form.get('name')
        stock = int(request.form.get('stock'))
        price = float(request.form.get('price'))
        expiry = request.form.get('expiry')
        expiry_date = datetime.strptime(expiry, '%Y-%m-%d').date() if expiry else None
        
        # Check existing
        item = Inventory.query.filter_by(medicine_name=name).first()
        if item:
            item.stock += stock # Add to stock
            item.price = price
            flash(f'Stock updated for {name}.')
        else:
            item = Inventory(medicine_name=name, stock=stock, price=price, expiry_date=expiry_date)
            db.session.add(item)
            flash(f'New medicine {name} added.')
            
        db.session.commit()
        return redirect(url_for('medical.inventory'))
        
    items = Inventory.query.all()
    return render_template('medical/inventory.html', title='Pharmacy Inventory', items=items)

@medical_bp.route('/mark_packed/<int:order_id>')
@login_required
def pack_order(order_id):
    if current_user.role != 'medical': return redirect(url_for('auth.login'))
    
    order = Order.query.get_or_404(order_id)
    order.status = 'packed'
    db.session.commit()
    flash(f'Order #{order.id} is packed.')
    return redirect(url_for('medical.dashboard'))

