from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_required, current_user
from app import db
from app.models import DoctorSlot, Appointment, Prescription, PrescriptionItem, MedicalHistory, PatientProfile, AuditLog
from datetime import datetime, timedelta, timezone

doctor_bp = Blueprint('doctor', __name__, url_prefix='/doctor')

@doctor_bp.route('/dashboard')
@login_required
def dashboard():
    if current_user.role != 'doctor':
        return redirect(url_for('auth.login'))
    
    doctor_profile = current_user.doctor_profile
    today = datetime.now(timezone.utc).replace(tzinfo=None).date()
    
    # Get all appointments for this doctor
    all_appointments = doctor_profile.appointments.all()
    
    # Today's appointments (for timeline)
    today_appointments = [a for a in all_appointments if a.slot and a.slot.start_time.date() == today]
    today_appointments.sort(key=lambda x: x.slot.start_time)
    
    # Pre-format appointment display data
    formatted_appointments = []
    for appt in today_appointments[:6]:
        formatted_appointments.append({
            'id': appt.id,
            'status': appt.status or '',
            'time_display': appt.slot.start_time.strftime('%I:%M %p') if appt.slot else 'N/A',
            'patient': appt.patient
        })
    
    # Statistics
    total_appointments = len(all_appointments)
    completed_visits = len([a for a in all_appointments if a.status == 'completed'])
    
    # Unique patients
    unique_patient_ids = set(a.patient_id for a in all_appointments)
    total_patients = len(unique_patient_ids)
    
    # New patients this month
    month_start = today.replace(day=1)
    new_patients_this_month = len([a for a in all_appointments 
        if a.created_at and a.created_at.date() >= month_start])
    
    # Revenue (consultation fees * completed appointments)
    consultation_fee = doctor_profile.consultation_fees or 500
    total_revenue = int(completed_visits * consultation_fee)
    
    # Recent patients for table - pre-format display values
    recent_patients = []
    seen_ids = set()
    for appt in sorted(all_appointments, key=lambda x: x.created_at or datetime.min, reverse=True):
        if appt.patient_id not in seen_ids and appt.patient:
            seen_ids.add(appt.patient_id)
            recent_patients.append({
                'name': appt.patient.name,
                'dob_display': appt.patient.dob.strftime('%d-%b-%y') if appt.patient.dob else 'N/A',
                'phone': appt.patient.phone or 'N/A',
                'last_visit': appt.created_at.strftime('%d-%b-%Y') if appt.created_at else 'N/A',
                'id': appt.patient_id
            })
            if len(recent_patients) >= 5:
                break
    
    return render_template('doctor/dashboard.html', 
        title='Doctor Dashboard',
        appointments=formatted_appointments,
        appointment_count=len(today_appointments),
        total_patients=total_patients,
        new_patients=new_patients_this_month,
        total_appointments=total_appointments,
        completed_visits=completed_visits,
        total_revenue=total_revenue,
        recent_patients=recent_patients
    )

@doctor_bp.route('/profile')
@login_required
def view_profile():
    return render_template('doctor/profile.html', title='My Professional Profile', profile=current_user.doctor_profile)

@doctor_bp.route('/profile/edit', methods=['GET', 'POST'])
@login_required
def edit_profile():
    if current_user.role != 'doctor':
        return redirect(url_for('auth.login'))
        
    profile = current_user.doctor_profile
    if request.method == 'POST':
        try:
            profile.consultation_fees = float(request.form.get('fees')) if request.form.get('fees') else 50.0
            profile.experience_years = int(request.form.get('experience')) if request.form.get('experience') else 0
        except ValueError:
            pass
            
        profile.bio = request.form.get('bio')
        profile.clinic_address = request.form.get('address')
        
        # Location
        if request.form.get('lat') and request.form.get('lng'):
            profile.lat = float(request.form.get('lat'))
            profile.lng = float(request.form.get('lng'))
            
        # Days: 'Mon', 'Tue' -> "Mon,Tue"
        days_list = request.form.getlist('days')
        profile.available_days = ",".join(days_list)
        
        # Hours: Combine start/end lists -> "09:00-12:00,14:00-18:00"
        starts = request.form.getlist('start_times')
        ends = request.form.getlist('end_times')
        hours_list = []
        for i in range(len(starts)):
            if starts[i] and ends[i]:
                hours_list.append(f"{starts[i]}-{ends[i]}")
        profile.available_hours = ",".join(hours_list)
        
        db.session.commit()
        flash('Profile updated successfully.')
        return redirect(url_for('doctor.view_profile'))
        
    return render_template('doctor/edit_profile.html', title='Edit Profile', profile=profile)

@doctor_bp.route('/slots/generate', methods=['POST'])
@login_required
def generate_slots():
    if current_user.role != 'doctor': return redirect(url_for('auth.login'))
    
    date_str = request.form['date']
    duration_mins = int(request.form['duration'])
    time_ranges = request.form.getlist('time_ranges')
    
    target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    
    count = 0
    for range_str in time_ranges:
        start_str, end_str = range_str.split('-')
        
        # Parse times
        start_t = datetime.strptime(start_str, '%H:%M').time()
        end_t = datetime.strptime(end_str, '%H:%M').time()
        
        # Create full datetime objects
        current_dt = datetime.combine(target_date, start_t)
        end_dt = datetime.combine(target_date, end_t)
        
        # Loop to create slots
        while current_dt + timedelta(minutes=duration_mins) <= end_dt:
            slot_end = current_dt + timedelta(minutes=duration_mins)
            
            # Create Slot
            slot = DoctorSlot(
                doctor_id=current_user.doctor_profile.id,
                start_time=current_dt,
                end_time=slot_end
            )
            db.session.add(slot)
            count += 1
            
            current_dt = slot_end
            
    db.session.commit()
    flash(f'Successfully generated {count} slots for {date_str}.')
    return redirect(url_for('doctor.manage_slots'))

@doctor_bp.route('/slots', methods=['GET', 'POST'])
@login_required
def manage_slots():
    if current_user.role != 'doctor':
        return redirect(url_for('auth.login'))
        
    if request.method == 'POST':
        start_time_str = request.form['start_time']
        duration = int(request.form['duration'])
        
        start_time = datetime.strptime(start_time_str, '%Y-%m-%dT%H:%M')
        end_time = start_time + timedelta(minutes=duration)
        
        slot = DoctorSlot(doctor_id=current_user.doctor_profile.id, start_time=start_time, end_time=end_time)
        db.session.add(slot)
        db.session.commit()
        flash('Slot added successfully.')
        return redirect(url_for('doctor.manage_slots'))
        
    slots = current_user.doctor_profile.slots.order_by(DoctorSlot.start_time.desc()).all()
    today_str = datetime.now(timezone.utc).replace(tzinfo=None).strftime('%Y-%m-%d')
    return render_template('doctor/slots.html', title='Manage Slots', slots=slots, min_date=today_str)

@doctor_bp.route('/slot/delete/<int:id>')
@login_required
def delete_slot(id):
    if current_user.role != 'doctor':
        return redirect(url_for('auth.login'))
    
    slot = DoctorSlot.query.get_or_404(id)
    if slot.doctor_id != current_user.doctor_profile.id:
        flash('Unauthorized.')
        return redirect(url_for('doctor.manage_slots'))
        
    if slot.is_booked:
        flash('Cannot delete a booked slot.')
        return redirect(url_for('doctor.manage_slots'))
        
    db.session.delete(slot)
    db.session.commit()
    flash('Slot deleted successfully.')
    return redirect(url_for('doctor.manage_slots'))

@doctor_bp.route('/slot/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_slot(id):
    if current_user.role != 'doctor':
        return redirect(url_for('auth.login'))
        
    slot = DoctorSlot.query.get_or_404(id)
    if slot.doctor_id != current_user.doctor_profile.id:
        flash('Unauthorized.')
        return redirect(url_for('doctor.manage_slots'))
        
    if slot.is_booked:
        flash('Cannot edit a booked slot.')
        return redirect(url_for('doctor.manage_slots'))
        
    if request.method == 'POST':
        start_time_str = request.form['start_time']
        duration = int(request.form['duration'])
        
        start_time = datetime.strptime(start_time_str, '%Y-%m-%dT%H:%M')
        end_time = start_time + timedelta(minutes=duration)
        
        slot.start_time = start_time
        slot.end_time = end_time
        db.session.commit()
        flash('Slot updated successfully.')
        return redirect(url_for('doctor.manage_slots'))
        
    return render_template('doctor/edit_slot.html', title='Edit Slot', slot=slot)

@doctor_bp.route('/appointment/<int:id>', methods=['GET', 'POST'])
@login_required
def appointment_details(id):
    if current_user.role != 'doctor':
        return redirect(url_for('auth.login'))
        
    appt = Appointment.query.get_or_404(id)
    if appt.doctor_id != current_user.doctor_profile.id:
        flash('Unauthorized access.')
        return redirect(url_for('doctor.dashboard'))
        
    if request.method == 'POST':
        medicines = request.form.getlist('medicines[]')
        dosages = request.form.getlist('dosages[]')
        frequencies = request.form.getlist('frequencies[]')
        timings = request.form.getlist('timings[]')
        durations = request.form.getlist('durations[]')
        quantities = request.form.getlist('quantities[]')
        instructions = request.form['instructions']
        
        presc = Prescription(appointment_id=appt.id, instructions=instructions)
        db.session.add(presc)
        db.session.commit() # Commit first to get ID
        
        for i in range(len(medicines)):
            if medicines[i]: # Only add if name exists
                item = PrescriptionItem(
                    prescription_id=presc.id,
                    medicine=medicines[i],
                    dosage=dosages[i] if i < len(dosages) else '',
                    frequency=frequencies[i] if i < len(frequencies) else '',
                    timing=timings[i] if i < len(timings) else '',
                    duration=durations[i] if i < len(durations) else '',
                    quantity=int(quantities[i]) if i < len(quantities) and quantities[i] else 0
                )
                db.session.add(item)
        
        appt.status = 'completed'
        
        # Log the action
        log = AuditLog(
            patient_id=appt.patient_id,
            action=f"Prescription added by Dr. {current_user.doctor_profile.name}",
            performed_by=f"Dr. {current_user.doctor_profile.name}"
        )
        db.session.add(log)
        
        db.session.commit()
        flash('Prescription sent successfully.')
        return redirect(url_for('doctor.appointment_details', id=id))
        
    return render_template('doctor/appointment.html', title='Appointment Details', appointment=appt)

@doctor_bp.route('/prescription/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_prescription(id):
    if current_user.role != 'doctor': return redirect(url_for('auth.login'))
    
    presc = Prescription.query.get_or_404(id)
    if presc.appointment.doctor_id != current_user.doctor_profile.id:
        flash('Unauthorized.')
        return redirect(url_for('doctor.dashboard'))
        
    if request.method == 'POST':
        # Clear old items
        for item in presc.items:
            db.session.delete(item)
            
        medicines = request.form.getlist('medicines[]')
        dosages = request.form.getlist('dosages[]')
        frequencies = request.form.getlist('frequencies[]')
        timings = request.form.getlist('timings[]')
        durations = request.form.getlist('durations[]')
        quantities = request.form.getlist('quantities[]')
        
        presc.instructions = request.form['instructions']
        
        for i in range(len(medicines)):
            if medicines[i]:
                item = PrescriptionItem(
                    prescription_id=presc.id,
                    medicine=medicines[i],
                    dosage=dosages[i] if i < len(dosages) else '',
                    frequency=frequencies[i] if i < len(frequencies) else '',
                    timing=timings[i] if i < len(timings) else '',
                    duration=durations[i] if i < len(durations) else '',
                    quantity=int(quantities[i]) if i < len(quantities) and quantities[i] else 0
                )
                db.session.add(item)
                
        db.session.commit()
        flash('Prescription updated.')
        return redirect(url_for('doctor.appointment_details', id=presc.appointment_id))
        
    return render_template('doctor/edit_prescription.html', title='Edit Prescription', prescription=presc)

@doctor_bp.route('/prescription/delete/<int:id>')
@login_required
def delete_prescription(id):
    if current_user.role != 'doctor': return redirect(url_for('auth.login'))
    
    presc = Prescription.query.get_or_404(id)
    if presc.appointment.doctor_id != current_user.doctor_profile.id:
        flash('Unauthorized.')
        return redirect(url_for('doctor.dashboard'))
        
    appt_id = presc.appointment_id
    db.session.delete(presc)
    db.session.commit()
    flash('Prescription deleted.')
    return redirect(url_for('doctor.appointment_details', id=appt_id))

@doctor_bp.route('/patient_history/<int:patient_id>')
@login_required
def view_patient_history(patient_id):
    if current_user.role != 'doctor': return redirect(url_for('auth.login'))
    
    # In a real app, check permission here
    patient = PatientProfile.query.get_or_404(patient_id)
    # Only show appointments related to the current doctor (Privacy)
    appointments = patient.appointments.filter_by(doctor_id=current_user.doctor_profile.id).order_by(Appointment.created_at.desc()).all()
    history_records = patient.medical_history.order_by(MedicalHistory.date.desc()).all()
    logs = patient.logs.order_by(AuditLog.timestamp.desc()).all()
    
    return render_template('doctor/history.html', title=f'History: {patient.name}', patient=patient, appointments=appointments, history_records=history_records, logs=logs)

@doctor_bp.route('/history/add/<int:patient_id>', methods=['POST'])
@login_required
def add_history_record(patient_id):
    if current_user.role != 'doctor': return redirect(url_for('auth.login'))
    
    title = request.form['title']
    description = request.form['description']
    date_str = request.form['date']
    date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
    
    history = MedicalHistory(
        patient_id=patient_id,
        title=title,
        description=description,
        date=date_obj
    )
    db.session.add(history)
    
    # Audit Log
    log = AuditLog(
        patient_id=patient_id,
        action=f"Added history record: {title}",
        performed_by=f"Dr. {current_user.doctor_profile.name}"
    )
    db.session.add(log)
    
    db.session.commit()
    flash('Medical history record added.')
    return redirect(url_for('doctor.view_patient_history', patient_id=patient_id))

