from flask import Blueprint, render_template, redirect, url_for, request, flash, jsonify
from flask_login import login_required, current_user
from app import db
from app.models import MedicationSchedule, MedicationLog, Notification, PrescriptionItem, Prescription, PatientProfile, Appointment, User
from datetime import datetime, timezone, timedelta, date
import calendar

medication_bp = Blueprint('medication', __name__, url_prefix='/medication')

api_bp = Blueprint('api', __name__, url_prefix='/api')

@api_bp.route('/profiles', methods=['GET'])
def get_profiles():
    patients = PatientProfile.query.all()
    profiles = []
    for p in patients:
        profiles.append({
            'id': p.id,
            'name': p.name or f'Patient {p.id}',
            'avatar_color': f'#{hash(str(p.id)) % 0xFFFFFF:06x}'
        })
    return jsonify(profiles)

@api_bp.route('/profiles', methods=['POST'])
def create_profile():
    data = request.get_json()
    name = data.get('name', f'Patient {data.get("id", 1)}')
    avatar_color = data.get('avatar_color', '#6366F1')
    
    user = User(username=name.lower().replace(' ', '_'), email=f'{name.lower().replace(" ", "")}@example.com', role='patient')
    user.set_password('password123')
    db.session.add(user)
    db.session.commit()
    
    patient = PatientProfile(user_id=user.id, name=name)
    db.session.add(patient)
    db.session.commit()
    
    return jsonify({
        'id': patient.id,
        'name': patient.name,
        'avatar_color': avatar_color
    }), 201

@api_bp.route('/profiles/<int:profile_id>', methods=['PUT'])
def update_profile(profile_id):
    data = request.get_json()
    patient = PatientProfile.query.get_or_404(profile_id)
    patient.name = data.get('name', patient.name)
    db.session.commit()
    return jsonify({'success': True})

@api_bp.route('/profiles/<int:profile_id>', methods=['DELETE'])
def delete_profile(profile_id):
    patient = PatientProfile.query.get_or_404(profile_id)
    if patient.user_id:
        user = User.query.get(patient.user_id)
        if user:
            db.session.delete(user)
    schedules = MedicationSchedule.query.filter_by(patient_id=profile_id).all()
    for s in schedules:
        MedicationLog.query.filter_by(schedule_id=s.id).delete()
        db.session.delete(s)
    db.session.delete(patient)
    db.session.commit()
    return jsonify({'success': True})

@api_bp.route('/medications', methods=['GET'])
def get_medications():
    profile_id = request.args.get('profile_id')
    if not profile_id:
        return jsonify([])
    medications = MedicationSchedule.query.filter_by(patient_id=profile_id, is_active=True).all()
    return jsonify([{
        'id': m.id,
        'profile_id': m.patient_id,
        'name': m.medicine_name,
        'dose': m.dosage,
        'time': m.times.split(',')[0].strip() if m.times else '08:00',
        'frequency': m.frequency or 'daily',
        'notes': m.timing
    } for m in medications])

@api_bp.route('/medications', methods=['POST'])
def create_medication():
    data = request.get_json()
    schedule = MedicationSchedule(
        patient_id=data.get('profile_id'),
        medicine_name=data.get('name'),
        dosage=data.get('dose'),
        times=data.get('time', '08:00'),
        frequency=data.get('frequency', 'daily'),
        timing=data.get('notes', ''),
        start_date=date.today(),
        is_active=True
    )
    db.session.add(schedule)
    db.session.commit()
    generate_medication_logs(schedule, 30)
    return jsonify({'id': schedule.id, **data}), 201

@api_bp.route('/medications/<int:med_id>', methods=['PUT'])
def update_medication(med_id):
    data = request.get_json()
    schedule = MedicationSchedule.query.get_or_404(med_id)
    schedule.medicine_name = data.get('name', schedule.medicine_name)
    schedule.dosage = data.get('dose', schedule.dosage)
    schedule.times = data.get('time', schedule.times)
    schedule.frequency = data.get('frequency', schedule.frequency)
    schedule.timing = data.get('notes', schedule.timing)
    db.session.commit()
    MedicationLog.query.filter_by(schedule_id=schedule.id).delete()
    db.session.commit()
    generate_medication_logs(schedule, 30)
    return jsonify({'success': True})

@api_bp.route('/medications/<int:med_id>', methods=['DELETE'])
def delete_medication(med_id):
    schedule = MedicationSchedule.query.get_or_404(med_id)
    MedicationLog.query.filter_by(schedule_id=schedule.id).delete()
    db.session.delete(schedule)
    db.session.commit()
    return jsonify({'success': True})

@api_bp.route('/logs', methods=['GET'])
def get_logs():
    profile_id = request.args.get('profile_id')
    log_date = request.args.get('date', date.today().isoformat())
    if not profile_id:
        return jsonify([])
    
    selected_date = datetime.strptime(log_date, '%Y-%m-%d').date()
    
    logs = MedicationLog.query.filter(
        MedicationLog.schedule.has(patient_id=profile_id),
        MedicationLog.date == selected_date
    ).all()
    
    return jsonify([{
        'id': log.id,
        'medication_id': log.schedule_id,
        'date': log.date.isoformat(),
        'taken': 1 if log.status == 'taken' else 0,
        'taken_at': log.taken_time.strftime('%H:%M') if log.taken_time else None
    } for log in logs])

@api_bp.route('/logs', methods=['POST'])
def toggle_log():
    data = request.get_json()
    medication_id = data.get('medication_id')
    log_date = data.get('date', date.today().isoformat())
    taken = data.get('taken', True)
    
    selected_date = datetime.strptime(log_date, '%Y-%m-%d').date()
    
    log = MedicationLog.query.filter_by(
        schedule_id=medication_id,
        date=selected_date
    ).first()
    
    if log:
        if log.status == 'taken':
            return jsonify({'success': False, 'error': 'Already taken'}), 400
        log.status = 'taken' if taken else 'skipped'
        log.taken_time = datetime.now(timezone.utc).replace(tzinfo=None) if taken else None
    else:
        schedule = MedicationSchedule.query.get(medication_id)
        if schedule and schedule.times:
            times_list = [t.strip() for t in schedule.times.split(',')]
            for time_str in times_list:
                try:
                    hour, minute = map(int, time_str.split(':'))
                    log = MedicationLog(
                        schedule_id=medication_id,
                        scheduled_time=datetime.combine(selected_date, datetime.min.time().replace(hour=hour, minute=minute)),
                        date=selected_date,
                        status='taken' if taken else 'skipped',
                        taken_time=datetime.now(timezone.utc).replace(tzinfo=None) if taken else None
                    )
                    db.session.add(log)
                    break
                except:
                    continue
    
    db.session.commit()
    return jsonify({'success': True})

@api_bp.route('/stats', methods=['GET'])
def get_stats():
    profile_id = request.args.get('profile_id')
    if not profile_id:
        return jsonify({'adherence_rate': 0, 'streak': 0})
    
    all_logs = MedicationLog.query.filter(
        MedicationLog.schedule.has(patient_id=profile_id)
    ).all()
    
    if not all_logs:
        return jsonify({'adherence_rate': 0, 'streak': 0})
    
    from collections import defaultdict
    logs_by_date = defaultdict(lambda: {'total': 0, 'taken': 0})
    
    for log in all_logs:
        date_key = log.date.isoformat()
        logs_by_date[date_key]['total'] += 1
        if log.status == 'taken':
            logs_by_date[date_key]['taken'] += 1
    
    total = sum(d['total'] for d in logs_by_date.values())
    taken = sum(d['taken'] for d in logs_by_date.values())
    adherence_rate = (taken / total * 100) if total > 0 else 0
    
    streak = 0
    sorted_dates = sorted(logs_by_date.keys(), reverse=True)
    for date_key in sorted_dates:
        if logs_by_date[date_key]['total'] == logs_by_date[date_key]['taken']:
            streak += 1
        else:
            break
    
    return jsonify({'adherence_rate': round(adherence_rate, 1), 'streak': streak})

@api_bp.route('/history', methods=['GET'])
def get_history():
    profile_id = request.args.get('profile_id')
    days = int(request.args.get('days', 7))
    
    if not profile_id:
        return jsonify([])
    
    history = []
    for i in range(days):
        d = date.today() - timedelta(days=i)
        logs = MedicationLog.query.filter(
            MedicationLog.schedule.has(patient_id=profile_id),
            MedicationLog.date == d
        ).all()
        
        history.append({
            'date': d.isoformat(),
            'medications': [{
                'id': log.id,
                'name': log.schedule.medicine_name,
                'dose': log.schedule.dosage,
                'time': log.scheduled_time.strftime('%H:%M') if log.scheduled_time else '',
                'taken': 1 if log.status == 'taken' else 0,
                'taken_at': log.taken_time.strftime('%H:%M') if log.taken_time else None
            } for log in logs]
        })
    
    return jsonify(history)

@medication_bp.route('/dashboard')
@login_required
def dashboard():
    if current_user.role != 'patient':
        return redirect(url_for('auth.login'))
    
    patient_profile = current_user.patient_profile
    today = date.today()
    
    # Get active schedules
    schedules = MedicationSchedule.query.filter_by(
        patient_id=patient_profile.id, 
        is_active=True
    ).all()
    
    # Get today's pending medications
    today_logs = MedicationLog.query.filter(
        MedicationLog.schedule.has(patient_id=patient_profile.id),
        MedicationLog.date == today
    ).order_by(MedicationLog.scheduled_time).all()
    
    pending_today = [log for log in today_logs if log.status == 'pending']
    taken_today = [log for log in today_logs if log.status == 'taken']
    missed_today = [log for log in today_logs if log.status == 'missed']
    
    # Unread notifications count
    notifications_count = Notification.query.filter_by(
        patient_id=patient_profile.id,
        is_read=False
    ).count()
    
    # Get recent notifications
    recent_notifications = Notification.query.filter_by(
        patient_id=patient_profile.id
    ).order_by(Notification.created_at.desc()).limit(10).all()
    
    return render_template(
        'medication/dashboard.html',
        title='Medication Tracker',
        schedules=schedules,
        pending_today=pending_today,
        taken_today=taken_today,
        missed_today=missed_today,
        today=today,
        notifications_count=notifications_count,
        recent_notifications=recent_notifications
    )

@medication_bp.route('/calendar')
@login_required
def medication_calendar():
    if current_user.role != 'patient':
        return redirect(url_for('auth.login'))
    
    patient_profile = current_user.patient_profile
    year = request.args.get('year', type=int)
    month = request.args.get('month', type=int)
    
    today = date.today()
    if not year:
        year = today.year
    if not month:
        month = today.month
    
    # Get all logs for the month
    start_date = date(year, month, 1)
    if month == 12:
        end_date = date(year + 1, 1, 1)
    else:
        end_date = date(year, month + 1, 1)
    
    logs = MedicationLog.query.filter(
        MedicationLog.schedule.has(patient_id=patient_profile.id),
        MedicationLog.date >= start_date,
        MedicationLog.date < end_date
    ).all()
    
    # Organize logs by date
    logs_by_date = {}
    for log in logs:
        date_key = log.date.isoformat()
        if date_key not in logs_by_date:
            logs_by_date[date_key] = {'taken': 0, 'missed': 0, 'pending': 0, 'skipped': 0}
        logs_by_date[date_key][log.status] += 1
    
    # Get calendar data
    import calendar
    cal = calendar.Calendar(firstweekday=0)
    month_days = cal.monthdayscalendar(year, month)
    
    month_name = calendar.month_name[month]
    
    prev_month = month - 1 if month > 1 else 12
    prev_year = year if month > 1 else year - 1
    next_month = month + 1 if month < 12 else 1
    next_year = year if month < 12 else year + 1
    
    return render_template(
        'medication/calendar.html',
        title='Medication Calendar',
        year=year,
        month=month,
        month_name=month_name,
        month_days=month_days,
        logs_by_date=logs_by_date,
        today=today,
        prev_month=prev_month,
        prev_year=prev_year,
        next_month=next_month,
        next_year=next_year
    )

@medication_bp.route('/calendar/<date>')
@login_required
def calendar_day(date):
    if current_user.role != 'patient':
        return redirect(url_for('auth.login'))
    
    try:
        selected_date = datetime.strptime(date, '%Y-%m-%d').date()
    except ValueError:
        flash('Invalid date format')
        return redirect(url_for('medication.medication_calendar'))
    
    logs = MedicationLog.query.filter(
        MedicationLog.schedule.has(patient_id=current_user.patient_profile.id),
        MedicationLog.date == selected_date
    ).order_by(MedicationLog.scheduled_time).all()
    
    return render_template(
        'medication/calendar_day.html',
        title=f'Medications for {selected_date.strftime("%B %d, %Y")}',
        date=selected_date,
        logs=logs
    )

@medication_bp.route('/add', methods=['GET', 'POST'])
@login_required
def add_medication():
    if current_user.role != 'patient':
        return redirect(url_for('auth.login'))
    
    patient_profile = current_user.patient_profile
    
    if request.method == 'POST':
        medicine_name = request.form.get('medicine_name')
        dosage = request.form.get('dosage')
        frequency = request.form.get('frequency')
        times = request.form.get('times')
        timing = request.form.get('timing')
        start_date = datetime.strptime(request.form.get('start_date'), '%Y-%m-%d').date()
        end_date_str = request.form.get('end_date')
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date() if end_date_str else None
        
        schedule = MedicationSchedule(
            patient_id=patient_profile.id,
            medicine_name=medicine_name,
            dosage=dosage,
            frequency=frequency,
            times=times,
            timing=timing,
            start_date=start_date,
            end_date=end_date
        )
        db.session.add(schedule)
        db.session.commit()
        
        # Generate logs for the schedule (30 days ahead)
        generate_medication_logs(schedule, 30)
        
        flash('Medication added successfully!')
        return redirect(url_for('medication.dashboard'))
    
    return render_template('medication/add.html', title='Add Medication', today=date.today())

@medication_bp.route('/import_from_prescription/<int:prescription_id>')
@login_required
def import_from_prescription(prescription_id):
    if current_user.role != 'patient':
        return redirect(url_for('auth.login'))
    
    prescription = Prescription.query.get_or_404(prescription_id)
    if prescription.appointment.patient_id != current_user.patient_profile.id:
        flash('Unauthorized.')
        return redirect(url_for('patient.dashboard'))
    
    imported_count = 0
    for item in prescription.items:
        existing = MedicationSchedule.query.filter_by(
            patient_id=current_user.patient_profile.id,
            medicine_name=item.medicine,
            is_active=True
        ).first()
        
        if not existing:
            schedule = MedicationSchedule(
                patient_id=current_user.patient_profile.id,
                prescription_item_id=item.id,
                medicine_name=item.medicine,
                dosage=item.dosage,
                frequency=item.frequency,
                timing=item.timing,
                start_date=date.today()
            )
            db.session.add(schedule)
            db.session.commit()
            generate_medication_logs(schedule, 30)
            imported_count += 1
    
    if imported_count > 0:
        flash(f'Successfully imported {imported_count} medication(s) from prescription!')
    else:
        flash('No new medications to import (already exist in your list).')
    
    return redirect(url_for('medication.dashboard'))

@medication_bp.route('/log/<int:log_id>/take', methods=['POST'])
@login_required
def take_medication(log_id):
    log = MedicationLog.query.get_or_404(log_id)
    if log.schedule.patient_id != current_user.patient_profile.id:
        return jsonify({'error': 'Unauthorized'}), 403
    
    if log.status == 'taken':
        return jsonify({'error': 'Already taken'}), 400
    
    log.status = 'taken'
    log.taken_time = datetime.now(timezone.utc).replace(tzinfo=None)
    db.session.commit()
    
    return jsonify({'success': True, 'status': 'taken'})

@medication_bp.route('/log/<int:log_id>/skip', methods=['POST'])
@login_required
def skip_medication(log_id):
    log = MedicationLog.query.get_or_404(log_id)
    if log.schedule.patient_id != current_user.patient_profile.id:
        return jsonify({'error': 'Unauthorized'}), 403
    
    log.status = 'skipped'
    db.session.commit()
    
    return jsonify({'success': True, 'status': 'skipped'})

@medication_bp.route('/log/<int:log_id>/undo', methods=['POST'])
@login_required
def undo_medication(log_id):
    log = MedicationLog.query.get_or_404(log_id)
    if log.schedule.patient_id != current_user.patient_profile.id:
        return jsonify({'error': 'Unauthorized'}), 403
    
    log.status = 'pending'
    log.taken_time = None
    db.session.commit()
    
    return jsonify({'success': True, 'status': 'pending'})

@medication_bp.route('/schedule/<int:schedule_id>/deactivate', methods=['POST'])
@login_required
def deactivate_schedule(schedule_id):
    schedule = MedicationSchedule.query.get_or_404(schedule_id)
    if schedule.patient_id != current_user.patient_profile.id:
        return jsonify({'error': 'Unauthorized'}), 403
    
    schedule.is_active = False
    db.session.commit()
    
    flash('Medication deactivated.')
    return redirect(url_for('medication.dashboard'))

@medication_bp.route('/schedule/<int:schedule_id>/activate', methods=['POST'])
@login_required
def activate_schedule(schedule_id):
    schedule = MedicationSchedule.query.get_or_404(schedule_id)
    if schedule.patient_id != current_user.patient_profile.id:
        return jsonify({'error': 'Unauthorized'}), 403
    
    schedule.is_active = True
    db.session.commit()
    
    flash('Medication activated.')
    return redirect(url_for('medication.dashboard'))

@medication_bp.route('/schedule/<int:schedule_id>/delete', methods=['POST'])
@login_required
def delete_schedule(schedule_id):
    schedule = MedicationSchedule.query.get_or_404(schedule_id)
    if schedule.patient_id != current_user.patient_profile.id:
        return jsonify({'error': 'Unauthorized'}), 403
    
    db.session.delete(schedule)
    db.session.commit()
    
    flash('Medication deleted.')
    return redirect(url_for('medication.dashboard'))

@medication_bp.route('/edit/<int:schedule_id>', methods=['GET', 'POST'])
@login_required
def edit_medication(schedule_id):
    if current_user.role != 'patient':
        return redirect(url_for('auth.login'))
    
    schedule = MedicationSchedule.query.get_or_404(schedule_id)
    if schedule.patient_id != current_user.patient_profile.id:
        flash('Unauthorized.')
        return redirect(url_for('medication.dashboard'))
    
    if request.method == 'POST':
        schedule.medicine_name = request.form.get('medicine_name')
        schedule.dosage = request.form.get('dosage')
        schedule.frequency = request.form.get('frequency')
        schedule.times = request.form.get('times')
        schedule.timing = request.form.get('timing')
        
        start_date_str = request.form.get('start_date')
        if start_date_str:
            schedule.start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        
        end_date_str = request.form.get('end_date')
        schedule.end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date() if end_date_str else None
        
        db.session.commit()
        
        MedicationLog.query.filter_by(schedule_id=schedule.id).delete()
        db.session.commit()
        generate_medication_logs(schedule, 30)
        
        flash('Medication updated successfully!')
        return redirect(url_for('medication.dashboard'))
    
    return render_template('medication/edit.html', title='Edit Medication', schedule=schedule)

@medication_bp.route('/schedule/<int:schedule_id>/regenerate_logs', methods=['POST'])
@login_required
def regenerate_logs(schedule_id):
    schedule = MedicationSchedule.query.get_or_404(schedule_id)
    if schedule.patient_id != current_user.patient_profile.id:
        return jsonify({'error': 'Unauthorized'}), 403
    
    MedicationLog.query.filter_by(schedule_id=schedule.id).delete()
    db.session.commit()
    generate_medication_logs(schedule, 30)
    
    flash('Medication logs regenerated.')
    return redirect(url_for('medication.dashboard'))

@medication_bp.route('/notifications')
@login_required
def notifications():
    if current_user.role != 'patient':
        return redirect(url_for('auth.login'))
    
    notifications = Notification.query.filter_by(
        patient_id=current_user.patient_profile.id
    ).order_by(Notification.created_at.desc()).all()
    
    return render_template('medication/notifications.html', title='Notifications', notifications=notifications)

@medication_bp.route('/notifications/mark_read/<int:notification_id>', methods=['POST'])
@login_required
def mark_notification_read(notification_id):
    notification = Notification.query.get_or_404(notification_id)
    if notification.patient_id != current_user.patient_profile.id:
        return jsonify({'error': 'Unauthorized'}), 403
    
    notification.is_read = True
    notification.read_at = datetime.now(timezone.utc).replace(tzinfo=None)
    db.session.commit()
    
    return redirect(url_for('medication.notifications'))

@medication_bp.route('/notifications/mark_all_read', methods=['POST'])
@login_required
def mark_all_notifications_read():
    if current_user.role != 'patient':
        return jsonify({'error': 'Unauthorized'}), 403
    
    Notification.query.filter_by(
        patient_id=current_user.patient_profile.id,
        is_read=False
    ).update({'is_read': True, 'read_at': datetime.now(timezone.utc).replace(tzinfo=None)})
    db.session.commit()
    
    return redirect(url_for('medication.notifications'))

@medication_bp.route('/notification/<int:notification_id>/checklist', methods=['POST'])
@login_required
def checklist_medication(notification_id):
    if current_user.role != 'patient':
        return redirect(url_for('auth.login'))
        
    notification = Notification.query.get_or_404(notification_id)
    if notification.patient_id != current_user.patient_profile.id:
        flash('Unauthorized.')
        return redirect(url_for('medication.dashboard'))
        
    # Example Title: "Medication Reminder: Vitamin D3"
    import re
    match = re.search(r'Reminder:\s*(.+)', notification.title)
    if match:
        medicine_name = match.group(1).strip()
        
        # Try to find an active schedule for this medicine
        schedule = MedicationSchedule.query.filter(
            MedicationSchedule.patient_id == current_user.patient_profile.id,
            MedicationSchedule.medicine_name == medicine_name,
            MedicationSchedule.is_active == True
        ).first()
        
        if schedule:
            today = datetime.now(timezone.utc).replace(tzinfo=None).date()
            # Find today's pending log
            log = MedicationLog.query.filter(
                MedicationLog.schedule_id == schedule.id,
                MedicationLog.date == today,
                MedicationLog.status == 'pending'
            ).first()
            
            if log:
                # Mark as taken
                log.status = 'taken'
                log.taken_time = datetime.now(timezone.utc).replace(tzinfo=None)
                
                # Add to history
                from app.models import MedicalHistory, AuditLog
                history = MedicalHistory(
                    patient_id=current_user.patient_profile.id,
                    title=f"Took Medication: {medicine_name}",
                    description=f"Checked off via notification. Dosage: {schedule.dosage}",
                    date=today
                )
                db.session.add(history)
                
                audit = AuditLog(
                    patient_id=current_user.patient_profile.id,
                    action=f"Self-Reported: Took {medicine_name}",
                    performed_by=f"Patient {current_user.patient_profile.name}"
                )
                db.session.add(audit)
                flash(f"Successfully recorded taking {medicine_name} in your Medical History.", 'success')
            else:
                flash(f"Could not find a pending log for {medicine_name} today.", 'warning')
        else:
            flash(f"Could not find an active schedule for {medicine_name}.", 'danger')
            
    # Always mark notification as read
    notification.is_read = True
    notification.read_at = datetime.now(timezone.utc).replace(tzinfo=None)
    db.session.commit()
    
    # Check if this was a redirect from bell or notifications page
    # Since we use this primarily from the notifications page, we redirect back there
    return redirect(url_for('medication.notifications'))

@medication_bp.route('/api/today_logs')
@login_required
def api_today_logs():
    if current_user.role != 'patient':
        return jsonify({'error': 'Unauthorized'}), 403
    
    today = date.today()
    logs = MedicationLog.query.filter(
        MedicationLog.schedule.has(patient_id=current_user.patient_profile.id),
        MedicationLog.date == today
    ).order_by(MedicationLog.scheduled_time).all()
    
    data = [{
        'id': log.id,
        'medicine': log.schedule.medicine_name,
        'dosage': log.schedule.dosage,
        'scheduled_time': log.scheduled_time.strftime('%H:%M') if log.scheduled_time else '',
        'taken_time': log.taken_time.strftime('%H:%M') if log.taken_time else None,
        'status': log.status,
        'timing': log.schedule.timing
    } for log in logs]
    
    return jsonify(data)

def generate_medication_logs(schedule, days_ahead=30):
    """Generate medication logs for the schedule"""
    if not schedule.times:
        return
    
    times_list = [t.strip() for t in schedule.times.split(',')]
    
    current_date = schedule.start_date
    end_date = schedule.end_date if schedule.end_date else (date.today() + timedelta(days=days_ahead))
    
    while current_date <= end_date:
        for time_str in times_list:
            try:
                hour, minute = map(int, time_str.split(':'))
                scheduled_datetime = datetime.combine(current_date, datetime.min.time().replace(hour=hour, minute=minute))
                
                existing_log = MedicationLog.query.filter_by(
                    schedule_id=schedule.id,
                    date=current_date,
                    scheduled_time=scheduled_datetime
                ).first()
                
                if not existing_log:
                    log = MedicationLog(
                        schedule_id=schedule.id,
                        scheduled_time=scheduled_datetime,
                        date=current_date,
                        status='pending'
                    )
                    db.session.add(log)
            except ValueError:
                continue
        
        current_date += timedelta(days=1)
    
    db.session.commit()

def check_and_create_reminders():
    """Background task to check for upcoming medications and create notifications"""
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    today = now.date()
    
    schedules = MedicationSchedule.query.filter_by(is_active=True).all()
    
    for schedule in schedules:
        logs = MedicationLog.query.filter(
            MedicationLog.schedule == schedule,
            MedicationLog.date == today,
            MedicationLog.status == 'pending'
        ).all()
        
        for log in logs:
            scheduled_naive = log.scheduled_time.replace(tzinfo=None) if log.scheduled_time.tzinfo else log.scheduled_time
            time_diff = (scheduled_naive - now.replace(tzinfo=None)).total_seconds() / 60
            
            if 0 < time_diff <= 30:
                thirty_mins_ago = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(minutes=30)
                existing_notification = Notification.query.filter(
                    Notification.patient_id == schedule.patient_id,
                    Notification.title == f"Medication Reminder: {schedule.medicine_name}",
                    Notification.created_at >= thirty_mins_ago
                ).first()
                
                if not existing_notification:
                    notification = Notification(
                        patient_id=schedule.patient_id,
                        title=f"Medication Reminder: {schedule.medicine_name}",
                        message=f"It's time to take {schedule.medicine_name} ({schedule.dosage})",
                        notification_type='medication_reminder'
                    )
                    db.session.add(notification)
    
    db.session.commit()

from flask_login import current_user
from datetime import timedelta

@api_bp.route('/reminders/check', methods=['POST'])
def trigger_reminders():
    """API endpoint to check and create medication reminders. Can be called by a scheduler."""
    check_and_create_reminders()
    
    new_notifs = []
    if current_user.is_authenticated and current_user.role == 'patient':
        one_min_ago = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(seconds=65)
        recent = Notification.query.filter(
            Notification.patient_id == current_user.patient_profile.id,
            Notification.is_read == False,
            Notification.created_at >= one_min_ago
        ).all()
        
        for n in recent:
            new_notifs.append({
                'id': n.id,
                'title': n.title,
                'message': n.message,
                'type': n.notification_type
            })
            
    return jsonify({'success': True, 'new_notifications': new_notifs})

@medication_bp.route('/doctor/patients')
@login_required
def doctor_patients():
    if current_user.role != 'doctor':
        return redirect(url_for('auth.login'))
    
    doctor = current_user.doctor_profile
    appointments = Appointment.query.filter_by(doctor_id=doctor.id).all()
    patient_ids = list(set([a.patient_id for a in appointments]))
    patients = PatientProfile.query.filter(PatientProfile.id.in_(patient_ids)).all()
    
    return render_template('medication/doctor_patients.html', title='Patient Medications', patients=patients)

@medication_bp.route('/doctor/patient/<int:patient_id>')
@login_required
def doctor_patient_medications(patient_id):
    if current_user.role != 'doctor':
        return redirect(url_for('auth.login'))
    
    patient = PatientProfile.query.get_or_404(patient_id)
    schedules = MedicationSchedule.query.filter_by(patient_id=patient_id).all()
    
    today = date.today()
    logs_today = MedicationLog.query.filter(
        MedicationLog.schedule.has(patient_id=patient_id),
        MedicationLog.date == today
    ).all()
    
    taken_count = len([l for l in logs_today if l.status == 'taken'])
    missed_count = len([l for l in logs_today if l.status == 'missed'])
    pending_count = len([l for l in logs_today if l.status == 'pending'])
    
    return render_template(
        'medication/doctor_patient_meds.html',
        title=f'{patient.name}\'s Medications',
        patient=patient,
        schedules=schedules,
        today=today,
        taken_count=taken_count,
        missed_count=missed_count,
        pending_count=pending_count
    )

@medication_bp.route('/doctor/medication/add/<int:patient_id>', methods=['GET', 'POST'])
@login_required
def doctor_add_medication(patient_id):
    if current_user.role != 'doctor':
        return redirect(url_for('auth.login'))
    
    patient = PatientProfile.query.get_or_404(patient_id)
    
    if request.method == 'POST':
        medicine_name = request.form.get('medicine_name')
        dosage = request.form.get('dosage')
        frequency = request.form.get('frequency')
        times = request.form.get('times')
        timing = request.form.get('timing')
        start_date = datetime.strptime(request.form.get('start_date'), '%Y-%m-%d').date()
        end_date_str = request.form.get('end_date')
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date() if end_date_str else None
        
        schedule = MedicationSchedule(
            patient_id=patient.id,
            medicine_name=medicine_name,
            dosage=dosage,
            frequency=frequency,
            times=times,
            timing=timing,
            start_date=start_date,
            end_date=end_date,
            is_active=True
        )
        db.session.add(schedule)
        db.session.commit()
        
        generate_medication_logs(schedule, 30)
        
        notification = Notification(
            patient_id=patient.id,
            title=f'Doctor Added: {medicine_name}',
            message=f'Dr. {current_user.doctor_profile.name} has added {medicine_name} to your medication schedule.',
            notification_type='medication_reminder'
        )
        db.session.add(notification)
        db.session.commit()
        
        flash(f'Medication added for {patient.name}')
        return redirect(url_for('medication.doctor_patient_medications', patient_id=patient.id))
    
    return render_template('medication/doctor_add_medication.html', title='Add Medication', patient=patient)

@medication_bp.route('/doctor/medication/edit/<int:schedule_id>', methods=['GET', 'POST'])
@login_required
def doctor_edit_medication(schedule_id):
    if current_user.role != 'doctor':
        return redirect(url_for('auth.login'))
    
    schedule = MedicationSchedule.query.get_or_404(schedule_id)
    
    if request.method == 'POST':
        schedule.medicine_name = request.form.get('medicine_name')
        schedule.dosage = request.form.get('dosage')
        schedule.frequency = request.form.get('frequency')
        schedule.times = request.form.get('times')
        schedule.timing = request.form.get('timing')
        
        start_date_str = request.form.get('start_date')
        if start_date_str:
            schedule.start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        
        end_date_str = request.form.get('end_date')
        schedule.end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date() if end_date_str else None
        
        db.session.commit()
        
        MedicationLog.query.filter_by(schedule_id=schedule.id).delete()
        db.session.commit()
        generate_medication_logs(schedule, 30)
        
        notification = Notification(
            patient_id=schedule.patient_id,
            title=f'Doctor Updated: {schedule.medicine_name}',
            message=f'Dr. {current_user.doctor_profile.name} has updated your {schedule.medicine_name} prescription.',
            notification_type='medication_reminder'
        )
        db.session.add(notification)
        db.session.commit()
        
        flash('Medication updated successfully!')
        return redirect(url_for('medication.doctor_patient_medications', patient_id=schedule.patient_id))
    
    return render_template('medication/doctor_edit_medication.html', title='Edit Medication', schedule=schedule)

@medication_bp.route('/doctor/medication/delete/<int:schedule_id>', methods=['POST'])
@login_required
def doctor_delete_medication(schedule_id):
    if current_user.role != 'doctor':
        return jsonify({'error': 'Unauthorized'}), 403
    
    schedule = MedicationSchedule.query.get_or_404(schedule_id)
    patient_id = schedule.patient_id
    
    notification = Notification(
        patient_id=patient_id,
        title=f'Doctor Removed: {schedule.medicine_name}',
        message=f'Dr. {current_user.doctor_profile.name} has removed {schedule.medicine_name} from your medication schedule.',
        notification_type='general'
    )
    db.session.add(notification)
    
    db.session.delete(schedule)
    db.session.commit()
    
    flash('Medication removed.')
    return redirect(url_for('medication.doctor_patient_medications', patient_id=patient_id))


@medication_bp.route('/api/patient/schedules', methods=['GET'])
@login_required
def api_patient_schedules():
    if current_user.role != 'patient':
        return jsonify({'error': 'Unauthorized'}), 403
    
    patient_profile = current_user.patient_profile
    schedules = MedicationSchedule.query.filter_by(
        patient_id=patient_profile.id,
        is_active=True
    ).all()
    
    data = [{
        'id': s.id,
        'medicine_name': s.medicine_name,
        'dosage': s.dosage,
        'frequency': s.frequency,
        'times': s.times,
        'timing': s.timing,
        'start_date': s.start_date.isoformat() if s.start_date else None,
        'end_date': s.end_date.isoformat() if s.end_date else None,
        'is_active': s.is_active
    } for s in schedules]
    
    return jsonify(data)

@medication_bp.route('/api/patient/schedules', methods=['POST'])
@login_required
def api_create_schedule():
    if current_user.role != 'patient':
        return jsonify({'error': 'Unauthorized'}), 403
    
    data = request.get_json()
    patient_profile = current_user.patient_profile
    
    schedule = MedicationSchedule(
        patient_id=patient_profile.id,
        medicine_name=data.get('medicine_name'),
        dosage=data.get('dosage'),
        frequency=data.get('frequency'),
        times=data.get('times'),
        timing=data.get('timing'),
        start_date=datetime.strptime(data.get('start_date'), '%Y-%m-%d').date() if data.get('start_date') else date.today(),
        end_date=datetime.strptime(data['end_date'], '%Y-%m-%d').date() if data.get('end_date') else None
    )
    db.session.add(schedule)
    db.session.commit()
    
    generate_medication_logs(schedule, 30)
    
    return jsonify({
        'id': schedule.id,
        'medicine_name': schedule.medicine_name,
        'dosage': schedule.dosage,
        'frequency': schedule.frequency,
        'times': schedule.times,
        'timing': schedule.timing,
        'start_date': schedule.start_date.isoformat() if schedule.start_date else None,
        'end_date': schedule.end_date.isoformat() if schedule.end_date else None,
        'is_active': schedule.is_active
    }), 201

@medication_bp.route('/api/patient/schedules/<int:schedule_id>', methods=['GET'])
@login_required
def api_get_schedule(schedule_id):
    if current_user.role != 'patient':
        return jsonify({'error': 'Unauthorized'}), 403
    
    schedule = MedicationSchedule.query.get_or_404(schedule_id)
    if schedule.patient_id != current_user.patient_profile.id:
        return jsonify({'error': 'Unauthorized'}), 403
    
    return jsonify({
        'id': schedule.id,
        'medicine_name': schedule.medicine_name,
        'dosage': schedule.dosage,
        'frequency': schedule.frequency,
        'times': schedule.times,
        'timing': schedule.timing,
        'start_date': schedule.start_date.isoformat() if schedule.start_date else None,
        'end_date': schedule.end_date.isoformat() if schedule.end_date else None,
        'is_active': schedule.is_active
    })

@medication_bp.route('/api/patient/schedules/<int:schedule_id>', methods=['PUT'])
@login_required
def api_update_schedule(schedule_id):
    if current_user.role != 'patient':
        return jsonify({'error': 'Unauthorized'}), 403
    
    schedule = MedicationSchedule.query.get_or_404(schedule_id)
    if schedule.patient_id != current_user.patient_profile.id:
        return jsonify({'error': 'Unauthorized'}), 403
    
    data = request.get_json()
    schedule.medicine_name = data.get('medicine_name', schedule.medicine_name)
    schedule.dosage = data.get('dosage', schedule.dosage)
    schedule.frequency = data.get('frequency', schedule.frequency)
    schedule.times = data.get('times', schedule.times)
    schedule.timing = data.get('timing', schedule.timing)
    
    if data.get('start_date'):
        schedule.start_date = datetime.strptime(data['start_date'], '%Y-%m-%d').date()
    if data.get('end_date'):
        schedule.end_date = datetime.strptime(data['end_date'], '%Y-%m-%d').date()
    
    db.session.commit()
    
    MedicationLog.query.filter_by(schedule_id=schedule.id).delete()
    db.session.commit()
    generate_medication_logs(schedule, 30)
    
    return jsonify({'success': True})

@medication_bp.route('/api/patient/schedules/<int:schedule_id>', methods=['DELETE'])
@login_required
def api_delete_schedule(schedule_id):
    if current_user.role != 'patient':
        return jsonify({'error': 'Unauthorized'}), 403
    
    schedule = MedicationSchedule.query.get_or_404(schedule_id)
    if schedule.patient_id != current_user.patient_profile.id:
        return jsonify({'error': 'Unauthorized'}), 403
    
    db.session.delete(schedule)
    db.session.commit()
    
    return jsonify({'success': True})

@medication_bp.route('/api/patient/logs', methods=['GET'])
@login_required
def api_patient_logs():
    if current_user.role != 'patient':
        return jsonify({'error': 'Unauthorized'}), 403
    
    patient_profile = current_user.patient_profile
    date_str = request.args.get('date', date.today().isoformat())
    selected_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    
    logs = MedicationLog.query.filter(
        MedicationLog.schedule.has(patient_id=patient_profile.id),
        MedicationLog.date == selected_date
    ).order_by(MedicationLog.scheduled_time).all()
    
    data = [{
        'id': log.id,
        'schedule_id': log.schedule_id,
        'medicine_name': log.schedule.medicine_name,
        'dosage': log.schedule.dosage,
        'scheduled_time': log.scheduled_time.strftime('%H:%M') if log.scheduled_time else '',
        'taken_time': log.taken_time.strftime('%H:%M') if log.taken_time else None,
        'status': log.status,
        'date': log.date.isoformat()
    } for log in logs]
    
    return jsonify(data)

@medication_bp.route('/api/patient/logs/<int:log_id>/take', methods=['POST'])
@login_required
def api_take_medication(log_id):
    if current_user.role != 'patient':
        return jsonify({'error': 'Unauthorized'}), 403
    
    log = MedicationLog.query.get_or_404(log_id)
    if log.schedule.patient_id != current_user.patient_profile.id:
        return jsonify({'error': 'Unauthorized'}), 403
    
    if log.status == 'taken':
        return jsonify({'error': 'Already taken'}), 400
    
    log.status = 'taken'
    log.taken_time = datetime.now(timezone.utc).replace(tzinfo=None)
    db.session.commit()
    
    return jsonify({'success': True, 'status': 'taken'})

@medication_bp.route('/api/patient/logs/<int:log_id>/skip', methods=['POST'])
@login_required
def api_skip_medication(log_id):
    if current_user.role != 'patient':
        return jsonify({'error': 'Unauthorized'}), 403
    
    log = MedicationLog.query.get_or_404(log_id)
    if log.schedule.patient_id != current_user.patient_profile.id:
        return jsonify({'error': 'Unauthorized'}), 403
    
    log.status = 'skipped'
    db.session.commit()
    
    return jsonify({'success': True, 'status': 'skipped'})

@medication_bp.route('/api/patient/stats', methods=['GET'])
@login_required
def api_patient_stats():
    if current_user.role != 'patient':
        return jsonify({'error': 'Unauthorized'}), 403
    
    patient_profile = current_user.patient_profile
    
    all_logs = MedicationLog.query.filter(
        MedicationLog.schedule.has(patient_id=patient_profile.id)
    ).all()
    
    if not all_logs:
        return jsonify({'adherence_rate': 0, 'streak': 0, 'total_medications': 0, 'taken_count': 0, 'missed_count': 0})
    
    from collections import defaultdict
    logs_by_date = defaultdict(lambda: {'total': 0, 'taken': 0})
    
    for log in all_logs:
        date_key = log.date.isoformat()
        logs_by_date[date_key]['total'] += 1
        if log.status == 'taken':
            logs_by_date[date_key]['taken'] += 1
    
    total = sum(d['total'] for d in logs_by_date.values())
    taken = sum(d['taken'] for d in logs_by_date.values())
    adherence_rate = (taken / total * 100) if total > 0 else 0
    
    streak = 0
    sorted_dates = sorted(logs_by_date.keys(), reverse=True)
    for date_key in sorted_dates:
        if logs_by_date[date_key]['total'] == logs_by_date[date_key]['taken']:
            streak += 1
        else:
            break
    
    return jsonify({
        'adherence_rate': round(adherence_rate, 1),
        'streak': streak,
        'total_medications': total,
        'taken_count': taken,
        'missed_count': total - taken
    })

@medication_bp.route('/api/patient/history', methods=['GET'])
@login_required
def api_patient_history():
    if current_user.role != 'patient':
        return jsonify({'error': 'Unauthorized'}), 403
    
    patient_profile = current_user.patient_profile
    days = int(request.args.get('days', 7))
    
    from datetime import timedelta
    dates = [(date.today() - timedelta(days=i)).isoformat() for i in range(days)]
    
    history = []
    for date_str in dates:
        selected_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        logs = MedicationLog.query.filter(
            MedicationLog.schedule.has(patient_id=patient_profile.id),
            MedicationLog.date == selected_date
        ).all()
        
        day_data = {
            'date': date_str,
            'medications': [{
                'id': log.id,
                'schedule_id': log.schedule_id,
                'name': log.schedule.medicine_name,
                'dose': log.schedule.dosage,
                'time': log.scheduled_time.strftime('%H:%M') if log.scheduled_time else '',
                'taken': 1 if log.status == 'taken' else 0,
                'taken_at': log.taken_time.strftime('%H:%M') if log.taken_time and log.status == 'taken' else None,
                'status': log.status
            } for log in logs]
        }
        history.append(day_data)
    
    return jsonify(history)


@medication_bp.route('/api/doctor/patients', methods=['GET'])
@login_required
def api_doctor_patients():
    if current_user.role != 'doctor':
        return jsonify({'error': 'Unauthorized'}), 403
    
    doctor = current_user.doctor_profile
    appointments = Appointment.query.filter_by(doctor_id=doctor.id).all()
    patient_ids = list(set([a.patient_id for a in appointments]))
    patients = PatientProfile.query.filter(PatientProfile.id.in_(patient_ids)).all()
    
    data = [{
        'id': p.id,
        'name': p.name,
        'gender': p.gender,
        'age': p.age
    } for p in patients]
    
    return jsonify(data)

@medication_bp.route('/api/doctor/patient/<int:patient_id>/schedules', methods=['GET'])
@login_required
def api_doctor_patient_schedules(patient_id):
    if current_user.role != 'doctor':
        return jsonify({'error': 'Unauthorized'}), 403
    
    schedules = MedicationSchedule.query.filter_by(patient_id=patient_id).all()
    
    data = [{
        'id': s.id,
        'medicine_name': s.medicine_name,
        'dosage': s.dosage,
        'frequency': s.frequency,
        'times': s.times,
        'timing': s.timing,
        'start_date': s.start_date.isoformat() if s.start_date else None,
        'end_date': s.end_date.isoformat() if s.end_date else None,
        'is_active': s.is_active
    } for s in schedules]
    
    return jsonify(data)

@medication_bp.route('/api/doctor/patient/<int:patient_id>/schedules', methods=['POST'])
@login_required
def api_doctor_create_schedule(patient_id):
    if current_user.role != 'doctor':
        return jsonify({'error': 'Unauthorized'}), 403
    
    patient = PatientProfile.query.get_or_404(patient_id)
    data = request.get_json()
    
    schedule = MedicationSchedule(
        patient_id=patient.id,
        medicine_name=data.get('medicine_name'),
        dosage=data.get('dosage'),
        frequency=data.get('frequency'),
        times=data.get('times'),
        timing=data.get('timing'),
        start_date=datetime.strptime(data.get('start_date'), '%Y-%m-%d').date() if data.get('start_date') else date.today(),
        end_date=datetime.strptime(data['end_date'], '%Y-%m-%d').date() if data.get('end_date') else None,
        is_active=True
    )
    db.session.add(schedule)
    db.session.commit()
    
    generate_medication_logs(schedule, 30)
    
    notification = Notification(
        patient_id=patient.id,
        title=f'Doctor Added: {schedule.medicine_name}',
        message=f'Dr. {current_user.doctor_profile.name} has added {schedule.medicine_name} to your medication schedule.',
        notification_type='medication_reminder'
    )
    db.session.add(notification)
    db.session.commit()
    
    return jsonify({
        'id': schedule.id,
        'medicine_name': schedule.medicine_name,
        'dosage': schedule.dosage
    }), 201

@medication_bp.route('/api/doctor/schedules/<int:schedule_id>', methods=['PUT'])
@login_required
def api_doctor_update_schedule(schedule_id):
    if current_user.role != 'doctor':
        return jsonify({'error': 'Unauthorized'}), 403
    
    schedule = MedicationSchedule.query.get_or_404(schedule_id)
    data = request.get_json()
    
    schedule.medicine_name = data.get('medicine_name', schedule.medicine_name)
    schedule.dosage = data.get('dosage', schedule.dosage)
    schedule.frequency = data.get('frequency', schedule.frequency)
    schedule.times = data.get('times', schedule.times)
    schedule.timing = data.get('timing', schedule.timing)
    
    if data.get('start_date'):
        schedule.start_date = datetime.strptime(data['start_date'], '%Y-%m-%d').date()
    if data.get('end_date'):
        schedule.end_date = datetime.strptime(data['end_date'], '%Y-%m-%d').date()
    
    db.session.commit()
    
    MedicationLog.query.filter_by(schedule_id=schedule.id).delete()
    db.session.commit()
    generate_medication_logs(schedule, 30)
    
    notification = Notification(
        patient_id=schedule.patient_id,
        title=f'Doctor Updated: {schedule.medicine_name}',
        message=f'Dr. {current_user.doctor_profile.name} has updated your {schedule.medicine_name} prescription.',
        notification_type='medication_reminder'
    )
    db.session.add(notification)
    db.session.commit()
    
    return jsonify({'success': True})

@medication_bp.route('/api/doctor/schedules/<int:schedule_id>', methods=['DELETE'])
@login_required
def api_doctor_delete_schedule(schedule_id):
    if current_user.role != 'doctor':
        return jsonify({'error': 'Unauthorized'}), 403
    
    schedule = MedicationSchedule.query.get_or_404(schedule_id)
    patient_id = schedule.patient_id
    
    notification = Notification(
        patient_id=patient_id,
        title=f'Doctor Removed: {schedule.medicine_name}',
        message=f'Dr. {current_user.doctor_profile.name} has removed {schedule.medicine_name} from your medication schedule.',
        notification_type='general'
    )
    db.session.add(notification)
    
    db.session.delete(schedule)
    db.session.commit()
    
    return jsonify({'success': True})

@medication_bp.route('/api/doctor/patient/<int:patient_id>/logs', methods=['GET'])
@login_required
def api_doctor_patient_logs(patient_id):
    if current_user.role != 'doctor':
        return jsonify({'error': 'Unauthorized'}), 403
    
    date_str = request.args.get('date', date.today().isoformat())
    selected_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    
    logs = MedicationLog.query.filter(
        MedicationLog.schedule.has(patient_id=patient_id),
        MedicationLog.date == selected_date
    ).order_by(MedicationLog.scheduled_time).all()
    
    data = [{
        'id': log.id,
        'schedule_id': log.schedule_id,
        'medicine_name': log.schedule.medicine_name,
        'dosage': log.schedule.dosage,
        'scheduled_time': log.scheduled_time.strftime('%H:%M') if log.scheduled_time else '',
        'taken_time': log.taken_time.strftime('%H:%M') if log.taken_time else None,
        'status': log.status,
        'date': log.date.isoformat()
    } for log in logs]
    
    return jsonify(data)

@medication_bp.route('/api/notifications', methods=['GET'])
@login_required
def api_notifications():
    if current_user.role != 'patient':
        return jsonify({'error': 'Unauthorized'}), 403
    
    notifications = Notification.query.filter_by(
        patient_id=current_user.patient_profile.id
    ).order_by(Notification.created_at.desc()).limit(50).all()
    
    data = [{
        'id': n.id,
        'title': n.title,
        'message': n.message,
        'notification_type': n.notification_type,
        'is_read': n.is_read,
        'created_at': n.created_at.isoformat()
    } for n in notifications]
    
    return jsonify(data)

@medication_bp.route('/api/notifications/<int:notification_id>/read', methods=['POST'])
@login_required
def api_mark_notification_read(notification_id):
    if current_user.role != 'patient':
        return jsonify({'error': 'Unauthorized'}), 403
    
    notification = Notification.query.get_or_404(notification_id)
    if notification.patient_id != current_user.patient_profile.id:
        return jsonify({'error': 'Unauthorized'}), 403
    
    notification.is_read = True
    notification.read_at = datetime.now(timezone.utc).replace(tzinfo=None)
    db.session.commit()
    
    return jsonify({'success': True})

@medication_bp.route('/api/notifications/unread_count', methods=['GET'])
@login_required
def api_unread_notifications_count():
    if current_user.role != 'patient':
        return jsonify({'error': 'Unauthorized'}), 403
    
    count = Notification.query.filter_by(
        patient_id=current_user.patient_profile.id,
        is_read=False
    ).count()
    
    return jsonify({'count': count})

@medication_bp.route('/api/notifications/ping', methods=['POST'])
@login_required
def api_notification_ping():
    if current_user.role != 'patient':
        return jsonify({'error': 'Unauthorized'}), 403
    
    patient_profile = current_user.patient_profile
    
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    today = now.date()
    
    upcoming_logs = MedicationLog.query.filter(
        MedicationLog.schedule.has(patient_id=patient_profile.id),
        MedicationLog.date == today,
        MedicationLog.status == 'pending'
    ).order_by(MedicationLog.scheduled_time).all()
    
    upcoming = []
    for log in upcoming_logs:
        if log.scheduled_time:
            scheduled_naive = log.scheduled_time.replace(tzinfo=None) if log.scheduled_time.tzinfo else log.scheduled_time
            time_diff = (scheduled_naive - now.replace(tzinfo=None)).total_seconds() / 60
            
            if -5 <= time_diff <= 30:
                upcoming.append({
                    'id': log.id,
                    'medicine_name': log.schedule.medicine_name,
                    'dosage': log.schedule.dosage,
                    'scheduled_time': log.scheduled_time.strftime('%H:%M'),
                    'status': log.status
                })
    
    unread_count = Notification.query.filter_by(
        patient_id=patient_profile.id,
        is_read=False
    ).count()
    
    return jsonify({
        'ping': True,
        'upcoming_medications': upcoming,
        'unread_notifications': unread_count
    })
