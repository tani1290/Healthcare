from datetime import datetime, timezone
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from app import db, login_manager

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, index=True)
    email = db.Column(db.String(120), unique=True, index=True)
    password_hash = db.Column(db.String(128))
    role = db.Column(db.String(20)) # 'patient', 'doctor', 'hospital', 'medical'
    google_id = db.Column(db.String(100), unique=True, nullable=True)  # For Google OAuth
    
    # Relationships
    patient_profile = db.relationship('PatientProfile', backref='user', uselist=False, cascade="all, delete-orphan")
    doctor_profile = db.relationship('DoctorProfile', backref='user', uselist=False, cascade="all, delete-orphan")
    hospital_profile = db.relationship('HospitalProfile', backref='user', uselist=False, cascade="all, delete-orphan")
    medical_profile = db.relationship('MedicalProfile', backref='user', uselist=False, cascade="all, delete-orphan")

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class PatientProfile(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), unique=True)
    name = db.Column(db.String(100))
    dob = db.Column(db.Date) # For age calculation
    gender = db.Column(db.String(20))
    phone = db.Column(db.String(20))
    address = db.Column(db.String(200))
    
    # Vitals & Lifestyle
    age = db.Column(db.Integer) # Derived or stored
    height_cm = db.Column(db.Float)
    weight_kg = db.Column(db.Float)
    blood_group = db.Column(db.String(10))
    allergies = db.Column(db.Text) # JSON string or comma-separated list
    medical_conditions = db.Column(db.Text) # Chronic conditions
    lifestyle_data = db.Column(db.Text) # JSON string for smoker, alcoholic, activity_level
    
    # Location
    lat = db.Column(db.Float)
    lng = db.Column(db.Float)
    
    medical_history = db.relationship('MedicalHistory', backref='patient', lazy='dynamic')
    appointments = db.relationship('Appointment', backref='patient', lazy='dynamic', foreign_keys='Appointment.patient_id')
    orders = db.relationship('Order', backref='patient', lazy='dynamic')
    logs = db.relationship('AuditLog', backref='patient', lazy='dynamic')

class DoctorProfile(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), unique=True)
    name = db.Column(db.String(100))
    specialty = db.Column(db.String(100))
    experience_years = db.Column(db.Integer)
    qualification = db.Column(db.String(100))
    clinic_address = db.Column(db.String(200))
    city = db.Column(db.String(100))
    consultation_fees = db.Column(db.Float)
    rating = db.Column(db.Float, default=0.0)
    education = db.Column(db.Text) # Detailed education background
    
    # Enhanced Info
    medical_license = db.Column(db.String(50))
    bio = db.Column(db.Text)
    available_days = db.Column(db.String(100)) # e.g. "Mon, Wed, Fri"
    available_hours = db.Column(db.String(50)) # e.g. "10:00-16:00"
    
    # Location
    lat = db.Column(db.Float)
    lng = db.Column(db.Float)
    
    appointments = db.relationship('Appointment', backref='doctor', lazy='dynamic', foreign_keys='Appointment.doctor_id')
    slots = db.relationship('DoctorSlot', backref='doctor', lazy='dynamic')

class DoctorSlot(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    doctor_id = db.Column(db.Integer, db.ForeignKey('doctor_profile.id'))
    start_time = db.Column(db.DateTime)
    end_time = db.Column(db.DateTime)
    is_booked = db.Column(db.Boolean, default=False)

class Appointment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patient_profile.id'))
    doctor_id = db.Column(db.Integer, db.ForeignKey('doctor_profile.id'))
    slot_id = db.Column(db.Integer, db.ForeignKey('doctor_slot.id'))
    
    # Relationships
    slot = db.relationship('DoctorSlot', backref='appointments_list')
    
    status = db.Column(db.String(20), default='pending') # pending, confirmed, completed, cancelled
    payment_status = db.Column(db.String(20), default='unpaid') # unpaid, paid
    transaction_id = db.Column(db.String(50))
    symptoms = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
    
    # Prescription linked to appointment
    prescription = db.relationship('Prescription', backref='appointment', uselist=False)

class Prescription(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    appointment_id = db.Column(db.Integer, db.ForeignKey('appointment.id'), unique=True)
    instructions = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
    
    items = db.relationship('PrescriptionItem', backref='prescription', lazy='dynamic', cascade="all, delete-orphan")

class PrescriptionItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    prescription_id = db.Column(db.Integer, db.ForeignKey('prescription.id'))
    medicine = db.Column(db.String(100))
    dosage = db.Column(db.String(50)) # e.g. 500mg
    frequency = db.Column(db.String(50)) # e.g. 1-0-1
    timing = db.Column(db.String(50)) # e.g. Before Food, After Food
    duration = db.Column(db.String(50)) # e.g. 5 days
    quantity = db.Column(db.Integer)

class MedicalHistory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patient_profile.id'))
    title = db.Column(db.String(100))
    description = db.Column(db.Text)
    date = db.Column(db.Date)
    
    # Permissions
    # Simplification: Comma separated list of doctor IDs who have access
    doctor_access_ids = db.Column(db.String(200), default="") 

class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patient_profile.id'))
    items = db.Column(db.Text)
    total_amount = db.Column(db.Float)
    delivery_address = db.Column(db.String(200))
    delivery_lat = db.Column(db.Float)
    delivery_lng = db.Column(db.Float)
    delivery_type = db.Column(db.String(20), default='delivery') # 'delivery' or 'pickup'
    estimated_delivery = db.Column(db.DateTime)
    delivery_agent = db.Column(db.String(100))
    eta = db.Column(db.String(50)) # e.g. "30 mins", "2:00 PM"
    status = db.Column(db.String(20), default='placed') # placed, packed, out_for_delivery, delivered
    payment_status = db.Column(db.String(20), default='unpaid') # unpaid, paid
    transaction_id = db.Column(db.String(50))
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))

class AuditLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patient_profile.id'))
    action = db.Column(db.String(255)) # Description of change
    performed_by = db.Column(db.String(100)) # Name of user who performed it
    timestamp = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
    
    # Relationship
    # Backref 'logs' will be accessible from patient_profile

class Inventory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    medicine_name = db.Column(db.String(100), unique=True)
    stock = db.Column(db.Integer, default=0)
    price = db.Column(db.Float)
    expiry_date = db.Column(db.Date)
    
    # Optional: Link to pharmacy user if multi-vendor

class MedicationSchedule(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patient_profile.id'))
    prescription_item_id = db.Column(db.Integer, db.ForeignKey('prescription_item.id'), nullable=True)
    medicine_name = db.Column(db.String(100), nullable=False)
    dosage = db.Column(db.String(50))
    frequency = db.Column(db.String(50))  # e.g. "1-0-1" for morning-noon-evening
    times = db.Column(db.String(100))  # e.g. "08:00,14:00,20:00" - specific times
    timing = db.Column(db.String(50))  # Before Food, After Food
    start_date = db.Column(db.Date)
    end_date = db.Column(db.Date, nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
    
    logs = db.relationship('MedicationLog', backref='schedule', lazy='dynamic', cascade="all, delete-orphan")

class MedicationLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    schedule_id = db.Column(db.Integer, db.ForeignKey('medication_schedule.id'))
    scheduled_time = db.Column(db.DateTime)
    taken_time = db.Column(db.DateTime, nullable=True)
    status = db.Column(db.String(20), default='pending')  # pending, taken, missed, skipped
    date = db.Column(db.Date, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))

class Notification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patient_profile.id'))
    title = db.Column(db.String(100), nullable=False)
    message = db.Column(db.Text)
    notification_type = db.Column(db.String(30))  # medication_reminder, appointment, order, general
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
    read_at = db.Column(db.DateTime, nullable=True)

class HospitalProfile(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), unique=True)
    name = db.Column(db.String(100))
    address = db.Column(db.String(200))
    city = db.Column(db.String(100))
    phone = db.Column(db.String(20))
    email = db.Column(db.String(120))
    lat = db.Column(db.Float)
    lng = db.Column(db.Float)

class MedicalProfile(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), unique=True)
    name = db.Column(db.String(100))
    address = db.Column(db.String(200))
    city = db.Column(db.String(100))
    phone = db.Column(db.String(20))
    email = db.Column(db.String(120))
    lat = db.Column(db.Float)
    lng = db.Column(db.Float)

