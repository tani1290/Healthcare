from datetime import datetime, timedelta, timezone, date
from app import create_app, db
from app.models import User, Notification, MedicationSchedule, MedicationLog

app = create_app()

with app.app_context():
    # Get the demo patient
    patient_user = User.query.filter_by(email='patient_demo@example.com').first()
    if patient_user and patient_user.patient_profile:
        patient_id = patient_user.patient_profile.id
        
        # 1. Add some direct unread notifications
        notif1 = Notification(
            patient_id=patient_id,
            title="Welcome to HealthHub",
            message="Your account has been successfully set up. Please complete your health profile.",
            notification_type="general",
            is_read=False
        )
        notif2 = Notification(
            patient_id=patient_id,
            title="General Checkup Reminder",
            message="It's been a while since your last checkup. Consider booking an appointment.",
            notification_type="general",
            is_read=False
        )
        db.session.add(notif1)
        db.session.add(notif2)
        
        # 2. Add an active MedicationSchedule that should trigger a reminder immediately
        now = datetime.now(timezone.utc)
        today = now.date()
        
        # Create a schedule
        sched = MedicationSchedule(
            patient_id=patient_id,
            medicine_name="Vitamin D3",
            dosage="1 Capsule",
            frequency="1-0-0",
            timing="After Breakfast",
            start_date=today - timedelta(days=1),
            is_active=True
        )
        db.session.add(sched)
        db.session.commit() # commit to get sched.id
        
        # Add a log for right now + 5 minutes
        # check_and_create_reminders checks if time_diff <= 30 mins
        remind_time = now + timedelta(minutes=5)
        
        log = MedicationLog(
            schedule_id=sched.id,
            scheduled_time=remind_time,
            date=today,
            status='pending'
        )
        db.session.add(log)
        
        db.session.commit()
        print("Test notifications and medication schedule seeded successfully!")
    else:
        print("Demo patient not found. Run seed_db.py first.")
