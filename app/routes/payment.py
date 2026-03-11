from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app import db
from app.models import Appointment, Order
import uuid
import time

payment_bp = Blueprint('payment', __name__, url_prefix='/payment')

@payment_bp.route('/checkout/<string:type>/<int:id>', methods=['GET', 'POST'])
@login_required
def checkout(type, id):
    # type: 'appointment' or 'order'
    item = None
    amount = 0.0
    title = ""
    
    if type == 'appointment':
        item = Appointment.query.get_or_404(id)
        # Verify ownership
        if item.patient_id != current_user.patient_profile.id:
            flash("Unauthorized")
            return redirect(url_for('patient.dashboard'))
        amount = item.doctor.consultation_fees
        title = f"Consultation with {item.doctor.name}"
        
    elif type == 'order':
        item = Order.query.get_or_404(id)
        if item.patient_id != current_user.patient_profile.id:
            flash("Unauthorized")
            return redirect(url_for('patient.dashboard'))
        amount = item.total_amount
        title = "Medicine Order"
        
    else:
        return "Invalid payment type", 400

    if request.method == 'POST':
        method = request.form.get('payment_method', 'card')
        
        # Determine Status
        if method == 'cod':
            item.payment_status = 'pending_cod' if type == 'order' else 'unpaid' # COD usually pending
            transaction_id = f"COD-{uuid.uuid4().hex[:8].upper()}"
        else:
            # Simulate Card Payment
            time.sleep(1.5) 
            transaction_id = f"TXN-{uuid.uuid4().hex[:10].upper()}"
            item.payment_status = 'paid'
        
        item.transaction_id = transaction_id
        
        # If appointment, confirm it
        if type == 'appointment':
             item.status = 'confirmed'
        
        db.session.commit()
        
        return render_template('payment/success.html', transaction_id=transaction_id, type=type)

    return render_template('payment/checkout.html', item=item, type=type, amount=amount, title=title)
