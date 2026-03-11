from datetime import datetime, timedelta, timezone, date
import random
from app import create_app, db
from app.models import User, PatientProfile, MedicalHistory, Order, Prescription, PrescriptionItem, DoctorProfile, Appointment, MedicationSchedule, MedicationLog, Notification

app = create_app()

with app.app_context():
    patient_user = User.query.filter_by(email='patient_demo@example.com').first()
    doctor_user = User.query.filter_by(email='doctor_demo@example.com').first()
    
    if not patient_user or not doctor_user:
        print("Required demo users not found. Run seed_db.py first.")
        exit(1)
        
    patient_id = patient_user.patient_profile.id
    doctor_id = doctor_user.doctor_profile.id
    now = datetime.now(timezone.utc)
    today = now.date()
    
    print("Seeding comprehensive data for patient...")

    # 1. Update Health Profile Stats
    profile = patient_user.patient_profile
    profile.height_cm = 175.5
    profile.weight_kg = 72.3
    profile.blood_group = "O+"
    
    # 2. Add Medical History Records
    history1 = MedicalHistory(
        patient_id=patient_id,
        title="Annual Physical Examination",
        description="Routine checkup. All vitals normal. Blood pressure 120/80. Advised to increase daily water intake.",
        date=today - timedelta(days=180)
    )
    history2 = MedicalHistory(
        patient_id=patient_id,
        title="Diagnosed with Mild Hypertension",
        description="Prescribed mild beta-blockers and recommended dietary changes (reduce sodium).",
        date=today - timedelta(days=90)
    )
    db.session.add_all([history1, history2])
    
    # 3. Add Orders
    order1 = Order(
        patient_id=patient_id,
        items="Vitamin C supplements x2, Bandages x1",
        total_amount=45.50,
        delivery_address="123 Demo St, Health City",
        status="delivered",
        payment_status="paid",
        created_at=now - timedelta(days=5)
    )
    order2 = Order(
        patient_id=patient_id,
        items="Blood Pressure Monitor",
        total_amount=120.00,
        delivery_address="123 Demo St, Health City",
        status="out_for_delivery",
        payment_status="paid",
        created_at=now - timedelta(hours=3),
        eta="Today, 4:00 PM"
    )
    db.session.add_all([order1, order2])

    # 4. Add Past and Upcoming Appointments with Prescriptions
    past_appt = Appointment(
        patient_id=patient_id,
        doctor_id=doctor_id,
        slot_id=1,  # Assuming slot 1 exists from previous seed
        status='completed',
        symptoms="Frequent headaches, slight dizziness.",
        created_at=now - timedelta(days=10)
    )
    db.session.add(past_appt)
    db.session.flush() # Get past_appt.id
    
    presc1 = Prescription(
        appointment_id=past_appt.id,
        instructions="Take medication after meals. Monitor BP weekly."
    )
    db.session.add(presc1)
    db.session.flush()
    
    p_item1 = PrescriptionItem(
        prescription_id=presc1.id,
        medicine="Amlodipine",
        dosage="5mg",
        frequency="1-0-0",
        timing="After Breakfast",
        duration="30 days",
        quantity=30
    )
    p_item2 = PrescriptionItem(
        prescription_id=presc1.id,
        medicine="Paracetamol",
        dosage="500mg",
        frequency="1-0-1",
        timing="After Food",
        duration="5 days",
        quantity=10
    )
    db.session.add_all([p_item1, p_item2])
    
    # 5. Add Past Medication Logs for Calendar Stats
    # We already have active Vitamin D3 from seed_notifications.
    # Let's add an active Amlodipine schedule and fill the calendar for the last 5 days
    sched_bp = MedicationSchedule(
        patient_id=patient_id,
        medicine_name="Amlodipine",
        dosage="5mg",
        frequency="1-0-0",
        timing="After Breakfast",
        start_date=today - timedelta(days=10),
        is_active=True
    )
    db.session.add(sched_bp)
    db.session.flush()
    
    for i in range(1, 6):
        past_date = today - timedelta(days=i)
        scheduled = datetime.combine(past_date, datetime.min.time()).replace(hour=8, tzinfo=timezone.utc)
        
        # Randomly mix taken, missed, pending
        status = random.choice(['taken', 'taken', 'taken', 'missed', 'skipped'])
        taken_time = scheduled + timedelta(minutes=random.randint(5, 60)) if status == 'taken' else None
        
        log = MedicationLog(
            schedule_id=sched_bp.id,
            scheduled_time=scheduled,
            taken_time=taken_time,
            date=past_date,
            status=status
        )
        db.session.add(log)
        
    # Also add a pending log for today for Amlodipine
    today_bp_log = MedicationLog(
        schedule_id=sched_bp.id,
        scheduled_time=now - timedelta(hours=1), # Missed the 1 hr ago slot, now pending
        date=today,
        status='pending'
    )
    db.session.add(today_bp_log)
    
    # 6. More diverse Notifications
    notif_order = Notification(
        patient_id=patient_id,
        title="Order Out for Delivery",
        message="Your Blood Pressure Monitor is out for delivery. ETA: Today, 4:00 PM.",
        notification_type="order",
        is_read=False
    )
    notif_appt = Notification(
        patient_id=patient_id,
        title="Appointment Follow-up",
        message="Please leave a review for your recent visit with Dr. Jane Smith.",
        notification_type="general",
        is_read=False
    )
    db.session.add_all([notif_order, notif_appt])

    try:
        db.session.commit()
        print("Successfully seeded all additional profile, history, prescription, order, and calendar data!")
    except Exception as e:
        db.session.rollback()
        print(f"Error seeding data: {e}")
