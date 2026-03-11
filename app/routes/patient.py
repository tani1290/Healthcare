from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_required, current_user
from app import db
from app.models import DoctorProfile, DoctorSlot, Appointment, Prescription, Order, AuditLog, MedicalHistory, Inventory
from datetime import datetime, timezone

patient_bp = Blueprint('patient', __name__, url_prefix='/patient')

@patient_bp.route('/dashboard')
@login_required
def dashboard():
    if current_user.role != 'patient':
        return redirect(url_for('auth.login'))
    
    patient_profile = current_user.patient_profile
    today = datetime.now(timezone.utc).replace(tzinfo=None).date()
    
    # Get all appointments
    all_appointments = patient_profile.appointments.all()
    
    # Upcoming appointments (future, not cancelled)
    upcoming_appointments = [a for a in all_appointments 
        if a.slot and a.slot.start_time.date() >= today and a.status not in ['cancelled', 'completed']]
    upcoming_appointments.sort(key=lambda x: x.slot.start_time)
    
    # Statistics
    total_appointments = len(all_appointments)
    completed_visits = len([a for a in all_appointments if a.status == 'completed'])
    upcoming_count = len(upcoming_appointments)
    
    # Active prescriptions (from last 30 days)
    from datetime import timedelta
    thirty_days_ago = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=30)
    active_prescriptions = 0
    for appt in all_appointments:
        if appt.prescription and appt.created_at and appt.created_at >= thirty_days_ago:
            active_prescriptions += 1
    
    # Orders count
    orders = patient_profile.orders.all() if hasattr(patient_profile, 'orders') else []
    total_orders = len(orders)
    
    # Reminder Logic (same as before)
    reminders = []
    now_utc = datetime.now(timezone.utc).replace(tzinfo=None)
    hour = (now_utc.hour + 5) + (1 if now_utc.minute >= 30 else 0) 
    if hour >= 24: hour -= 24
    time_slot = 0  # Morning
    if 12 <= hour < 17: time_slot = 1
    if hour >= 17: time_slot = 2
    
    recent_appts = patient_profile.appointments.order_by(Appointment.created_at.desc()).limit(5).all()
    
    for appt in recent_appts:
        if appt.prescription:
            for item in appt.prescription.items:
                if not item.frequency: continue
                freq = item.frequency.strip()
                try:
                    parts = freq.split('-')
                    if len(parts) == 3 and parts[time_slot] == '1':
                        reminders.append({
                            'medicine': item.medicine,
                            'dosage': item.dosage,
                            'timing': item.timing,
                            'instruction': 'Take now'
                        })
                except Exception:
                    pass
    
    # Next appointment info
    next_appointment = upcoming_appointments[0] if upcoming_appointments else None
    
    return render_template('patient/dashboard.html', 
        title='Patient Dashboard',
        reminders=reminders,
        upcoming_appointments=upcoming_appointments[:5],
        total_appointments=total_appointments,
        completed_visits=completed_visits,
        upcoming_count=upcoming_count,
        active_prescriptions=active_prescriptions,
        total_orders=total_orders,
        next_appointment=next_appointment,
        profile=patient_profile
    )

@patient_bp.route('/profile')
@login_required
def profile():
    return render_template('patient/profile.html', title='My Health Profile', profile=current_user.patient_profile)

@patient_bp.route('/profile/edit', methods=['GET', 'POST'])
@login_required
def edit_profile():
    if current_user.role != 'patient':
        return redirect(url_for('auth.login'))
        
    profile = current_user.patient_profile
    if request.method == 'POST':
        profile.phone = request.form.get('phone')
        profile.address = request.form.get('address')
        
        try:
            profile.height_cm = float(request.form.get('height_cm')) if request.form.get('height_cm') else None
            profile.weight_kg = float(request.form.get('weight_kg')) if request.form.get('weight_kg') else None
        except ValueError:
            pass # Ignore invalid numbers
            
        profile.blood_group = request.form.get('blood_group')
        profile.allergies = request.form.get('allergies')
        profile.medical_conditions = request.form.get('conditions')
        
        db.session.commit()
        flash('Profile updated successfully.')
        return redirect(url_for('patient.profile'))
        
    return render_template('patient/edit_profile.html', title='Edit Profile', profile=profile)

@patient_bp.route('/doctors')
@login_required
def find_doctor():
    specialty = request.args.get('specialty')
    city = request.args.get('city')
    
    query = DoctorProfile.query
    if specialty:
        query = query.filter(DoctorProfile.specialty.ilike(f'%{specialty}%'))
    if city:
        query = query.filter(DoctorProfile.city.ilike(f'%{city}%'))
        
    doctors = query.all()
    return render_template('patient/doctors.html', title='Find Doctor', doctors=doctors)

@patient_bp.route('/book/<int:doctor_id>', methods=['GET', 'POST'])
@login_required
def book_appointment(doctor_id):
    doctor = DoctorProfile.query.get_or_404(doctor_id)
    
    if request.method == 'POST':
        slot_id = request.form['slot_id']
        symptoms = request.form['symptoms']
        
        slot = DoctorSlot.query.get(slot_id)
        if slot.is_booked:
            flash('Slot already booked. Please choose another.')
            return redirect(url_for('patient.book_appointment', doctor_id=doctor_id))
            
        # Check for overlapping appointments for this patient
        # Get all active appointments for the patient
        # We need to check if NewStart < ExistingEnd AND ExistingStart < NewEnd
        existing_appts = current_user.patient_profile.appointments.filter(
            Appointment.status.in_(['pending', 'confirmed', 'paid'])
        ).all()
        
        for existing in existing_appts:
            if existing.slot:
                # Check overlap
                if slot.start_time < existing.slot.end_time and existing.slot.start_time < slot.end_time:
                    flash(f'You already have an appointment with Dr. {existing.doctor.name} at this time ({existing.slot.start_time.strftime("%H:%M")}).')
                    return redirect(url_for('patient.book_appointment', doctor_id=doctor_id))
            
        # Create appointment
        appt = Appointment(patient_id=current_user.patient_profile.id, 
                           doctor_id=doctor_id, 
                           slot_id=slot_id, 
                           symptoms=symptoms)
        
        slot.is_booked = True
        db.session.add(appt)
        
        # Create Notification
        from app.models import Notification
        notif = Notification(
            patient_id=current_user.patient_profile.id,
            title="Appointment Pending Payment",
            message=f"Your appointment with Dr. {doctor.name} on {slot.start_time.strftime('%b %d at %I:%M %p')} is pending checkout.",
            notification_type='appointment'
        )
        db.session.add(notif)
        
        db.session.commit()
        
        return redirect(url_for('payment.checkout', type='appointment', id=appt.id))
    
    # Get available slots (simple filter: not booked and future time)
    # Using python filter for simplicity, in prod use SQL query
    slots = [s for s in doctor.slots if not s.is_booked and s.start_time > datetime.now(timezone.utc).replace(tzinfo=None)]
    return render_template('patient/book.html', title='Book Appointment', doctor=doctor, slots=slots)

@patient_bp.route('/appointments')
@login_required
def my_appointments():
    appointments = current_user.patient_profile.appointments.order_by(Appointment.created_at.desc()).all()
    return render_template('patient/appointments.html', title='My Appointments', appointments=appointments)

@patient_bp.route('/history')
@login_required
def history():
    # Show completed appointments as history
    appointments = current_user.patient_profile.appointments.filter(Appointment.status != 'pending').all()
    # General records
    history_records = current_user.patient_profile.medical_history.order_by(MedicalHistory.date.desc()).all()
    # Logs
    logs = current_user.patient_profile.logs.order_by(AuditLog.timestamp.desc()).all()
    
    return render_template('patient/history.html', title='Medical History', appointments=appointments, history_records=history_records, logs=logs)

@patient_bp.route('/my_orders')
@login_required
def my_orders():
    # Fetch patient's orders
    orders = Order.query.filter_by(patient_id=current_user.patient_profile.id).order_by(Order.created_at.desc()).all()
    return render_template('patient/my_orders.html', title='My Orders', orders=orders)

@patient_bp.route('/order/<int:prescription_id>', methods=['POST'])
@login_required
def order_medicines(prescription_id):
    presc = Prescription.query.get_or_404(prescription_id)
    if presc.appointment.patient_id != current_user.patient_profile.id:
        flash('Unauthorized.')
        return redirect(url_for('patient.dashboard'))
        
    delivery_type = request.form.get('delivery_type', 'delivery')
    
    # Handle Selected Items
    selected_ids = request.form.getlist('selected_items')
    
    selected_items = []
    if selected_ids:
        # Filter items
        try:
            ids_set = set(int(x) for x in selected_ids)
            selected_items = [i for i in presc.items if i.id in ids_set]
        except ValueError:
            selected_items = []
    else:
        # Fallback (if somehow called without selection, unlikely with new UI)
        # or maybe we should enforce selection
        pass 
        
    if not selected_items:
        flash('Please select at least one medicine to order.')
        return redirect(url_for('patient.view_prescription', id=prescription_id))

    today = datetime.now(timezone.utc).replace(tzinfo=None).date()
    
    for item in selected_items:
        # Check Inventory (Try exact match first)
        inv_item = Inventory.query.filter_by(medicine_name=item.medicine).first()
        
        # If not found, try robust search or create for demo
        if not inv_item:
            # Try splitting first word (e.g. "Amoxicillin 500mg" -> "Amoxicillin")
            simple_name = item.medicine.split(' ')[0]
            inv_item = Inventory.query.filter(Inventory.medicine_name.ilike(f"%{simple_name}%")).first()
            
            if not inv_item:
                print(f"DEBUG: Auto-creating inventory for {item.medicine}")
                inv_item = Inventory(medicine_name=item.medicine, stock=50, price=10.0)
                db.session.add(inv_item)
                db.session.commit() # Commit needed to get ID/use it
        
        if inv_item.stock < item.quantity:
            flash(f"Insufficient stock for '{item.medicine}'. Available: {inv_item.stock}, Requested: {item.quantity}")
            return redirect(url_for('patient.view_prescription', id=prescription_id))
            
        # Deduct Stock
        inv_item.stock -= item.quantity
        
    # Calculate Total (Using actual prices from inventory)
    total_price = 0
    for item in selected_items:
        inv_item = Inventory.query.filter_by(medicine_name=item.medicine).first()
        item_price = inv_item.price if inv_item else 0
        total_price += item_price * item.quantity

    # Create Order
    delivery_address = request.form.get('delivery_address')
    delivery_lat = request.form.get('lat')
    delivery_lng = request.form.get('lng')
    
    print(f"DEBUG: Order Location - Lat: {delivery_lat}, Lng: {delivery_lng}")
    
    order = Order(patient_id=current_user.patient_profile.id, 
                  items="", # Filled below
                  total_amount=total_price,
                  delivery_address=delivery_address if delivery_address else (current_user.patient_profile.address or "Default Address"),
                  delivery_lat=float(delivery_lat) if delivery_lat else None,
                  delivery_lng=float(delivery_lng) if delivery_lng else None,
                  delivery_type=delivery_type,
                  status='placed')
                  
    medicine_names = ", ".join([f"{i.medicine} (x{i.quantity})" for i in selected_items])
    order.items = medicine_names
    
    db.session.add(order)
    db.session.commit()
    return redirect(url_for('payment.checkout', type='order', id=order.id))

@patient_bp.route('/prescription/view/<int:id>')
@login_required
def view_prescription(id):
    presc = Prescription.query.get_or_404(id)
    if presc.appointment.patient_id != current_user.patient_profile.id:
        flash('Unauthorized.')
        return redirect(url_for('patient.dashboard'))
    return render_template('patient/view_prescription.html', title='View Prescription', prescription=presc)

@patient_bp.route('/prescriptions')
@login_required
def my_prescriptions():
    # Only appointments with prescriptions
    appts = current_user.patient_profile.appointments.join(Prescription).order_by(Appointment.created_at.desc()).all()
    return render_template('patient/my_prescriptions.html', title='My Prescriptions', appointments=appts)

@patient_bp.route('/history/add', methods=['POST'])
@login_required
def add_history_record():
    if current_user.role != 'patient': return redirect(url_for('auth.login'))
    
    title = request.form['title']
    description = request.form['description']
    date_str = request.form['date']
    date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
    
    history = MedicalHistory(
        patient_id=current_user.patient_profile.id,
        title=title,
        description=description,
        date=date_obj
    )
    db.session.add(history)
    
    # Audit Log
    log = AuditLog(
        patient_id=current_user.patient_profile.id,
        action=f"Self-Reported: {title}",
        performed_by=f"Patient {current_user.patient_profile.name}"
    )
    db.session.add(log)
    
    db.session.commit()
    flash('Medical record added successfully.')
    return redirect(url_for('patient.history'))
