from datetime import datetime, timedelta, date, timezone
from app import create_app, db
from app.models import User, PatientProfile, DoctorProfile, HospitalProfile, MedicalProfile, DoctorSlot, Inventory

app = create_app()

with app.app_context():
    db.create_all()
    
    # 1. Patient Profile
    patient_user = User.query.filter_by(email='patient_demo@example.com').first()
    if not patient_user:
        patient_user = User(username='demo_patient', email='patient_demo@example.com', role='patient')
        patient_user.set_password('password123')
        db.session.add(patient_user)
        db.session.commit()
    
    if not patient_user.patient_profile:
        patient_profile = PatientProfile(
            user_id=patient_user.id,
            name='John Doe',
            dob=date(1990, 1, 1),
            gender='Male',
            phone='1234567890',
            address='123 Demo St, Cityville',
            blood_group='O+',
            height_cm=175.0,
            weight_kg=70.0
        )
        db.session.add(patient_profile)

    # 2. Doctor Profile (Cardiology)
    doctor_user = User.query.filter_by(email='doctor_demo@example.com').first()
    if not doctor_user:
        doctor_user = User(username='demo_doctor', email='doctor_demo@example.com', role='doctor')
        doctor_user.set_password('password123')
        db.session.add(doctor_user)
        db.session.commit()

    if not doctor_user.doctor_profile:
        doctor_profile = DoctorProfile(
            user_id=doctor_user.id,
            name='Jane Smith',
            specialty='Cardiology',
            experience_years=10,
            qualification='MD, DM Cardiology',
            clinic_address='456 Heart Clinic, Cityville',
            city='Cityville',
            consultation_fees=500.0,
            available_days='Mon, Wed, Fri',
            available_hours='09:00-17:00'
        )
        db.session.add(doctor_profile)
        db.session.commit()
        
        # Add slots for the doctor
        now = datetime.now(timezone.utc)
        for i in range(1, 4):
            # Slots for tomorrow, day after, etc.
            start_time = now.replace(hour=10, minute=0, second=0, microsecond=0) + timedelta(days=i)
            end_time = start_time + timedelta(minutes=30)
            slot1 = DoctorSlot(doctor_id=doctor_profile.id, start_time=start_time, end_time=end_time, is_booked=False)
            
            start_time2 = now.replace(hour=11, minute=0, second=0, microsecond=0) + timedelta(days=i)
            end_time2 = start_time2 + timedelta(minutes=30)
            slot2 = DoctorSlot(doctor_id=doctor_profile.id, start_time=start_time2, end_time=end_time2, is_booked=False)
            db.session.add_all([slot1, slot2])

    # 3. Hospital Profile
    hospital_user = User.query.filter_by(email='hospital_demo@example.com').first()
    if not hospital_user:
        hospital_user = User(username='demo_hospital', email='hospital_demo@example.com', role='hospital')
        hospital_user.set_password('password123')
        db.session.add(hospital_user)
        db.session.commit()

    if not hospital_user.hospital_profile:
        hospital_profile = HospitalProfile(
            user_id=hospital_user.id,
            name='Cityville General Hospital',
            email='hospital_demo@example.com',
            address='789 Health Ave, Cityville',
            city='Cityville',
            phone='0987654321'
        )
        db.session.add(hospital_profile)

    # 4. Medical / Pharmacy Profile
    medical_user = User.query.filter_by(email='medical_demo@example.com').first()
    if not medical_user:
        medical_user = User(username='demo_medical', email='medical_demo@example.com', role='medical')
        medical_user.set_password('password123')
        db.session.add(medical_user)
        db.session.commit()

    if not medical_user.medical_profile:
        medical_profile = MedicalProfile(
            user_id=medical_user.id,
            name='Cityville Community Pharmacy',
            email='medical_demo@example.com',
            address='101 Pharma Blvd, Cityville',
            city='Cityville',
            phone='1122334455'
        )
        db.session.add(medical_profile)

    # 5. Inventory Demo Data
    inv1 = Inventory.query.filter_by(medicine_name='Paracetamol 500mg').first()
    if not inv1:
        inv1 = Inventory(medicine_name='Paracetamol 500mg', stock=100, price=5.0, expiry_date=date(2027, 12, 31))
        db.session.add(inv1)
        
    inv2 = Inventory.query.filter_by(medicine_name='Amoxicillin 250mg').first()
    if not inv2:
        inv2 = Inventory(medicine_name='Amoxicillin 250mg', stock=50, price=15.0, expiry_date=date(2026, 6, 30))
        db.session.add(inv2)

    db.session.commit()
    print("Database seeded with demo data successfully!")
