from flask import Blueprint, render_template, redirect, url_for
from flask_login import login_required, current_user
from app.models import DoctorProfile, PatientProfile, Appointment

hospital_bp = Blueprint('hospital', __name__, url_prefix='/hospital')

@hospital_bp.route('/dashboard')
@login_required
def dashboard():
    if current_user.role != 'hospital':
        return redirect(url_for('auth.login'))
        
    doc_count = DoctorProfile.query.count()
    patient_count = PatientProfile.query.count()
    appt_count = Appointment.query.count()
    
    return render_template('hospital/dashboard.html', title='Hospital Admin', 
                           doc_count=doc_count, patient_count=patient_count, appt_count=appt_count)
