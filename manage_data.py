from app import create_app, db
from app.models import User, PatientProfile, DoctorProfile, Appointment, Prescription, PrescriptionItem, Order, Inventory, DoctorSlot, MedicalHistory, AuditLog, MedicationSchedule, MedicationLog, Notification
from datetime import datetime, timedelta, timezone, date
from werkzeug.security import generate_password_hash
import click
import sqlite3
import os

app = create_app()

@app.cli.command("init-roles")
def init_roles_command():
    """Initialize base users (Admin, Doctor, Pharmacy)."""
    # 1. Pharmacy
    if not User.query.filter_by(username='pharmacy').first():
        u = User(username='pharmacy', email='pharmacy@hospital.com', role='medical')
        u.set_password('pharmacy123')
        db.session.add(u)
        print("Created user: pharmacy")
    
    # 2. Doctor
    if not User.query.filter_by(username='doctor').first():
        u = User(username='doctor', email='doctor@hospital.com', role='doctor')
        u.set_password('doctor123')
        db.session.add(u)
        
        doc = DoctorProfile(user=u, name="Dr. Smith", specialty="Cardiology", 
                            city="Pune", consultation_fees=500.0, available_days="Mon,Wed,Fri")
        db.session.add(doc)
        print("Created user: doctor")

    # 3. Patient (Jinay)
    if not User.query.filter_by(username='jinay').first():
        u = User(username='jinay', email='jinay@example.com', role='patient')
        u.set_password('jinay123')
        db.session.add(u)
        
        pat = PatientProfile(user=u, name="Jinay", gender="Male", phone="9876543210")
        db.session.add(pat)
        print("Created user: jinay")
        
    db.session.commit()
    print("Base Roles Initialized.")

@app.cli.command("seed-inventory")
def seed_inventory_command():
    """Populate pharmacy inventory."""
    medicines = [
        {"name": "Cough Syrup", "price": 50.0, "stock": 50},
        {"name": "MultiVitamin", "price": 10.0, "stock": 100},
        {"name": "Calcium Sandoz", "price": 5.0, "stock": 100},
        {"name": "Paracetamol", "price": 2.0, "stock": 200},
        {"name": "Amoxicillin", "price": 15.0, "stock": 50},
        {"name": "Cetirizine", "price": 5.0, "stock": 100},
        {"name": "Vitamin C", "price": 3.0, "stock": 100}
    ]
    
    for med in medicines:
        item = Inventory.query.filter_by(medicine_name=med['name']).first()
        if not item:
            item = Inventory(medicine_name=med['name'], stock=med['stock'], price=med['price'])
            db.session.add(item)
            print(f"Added {med['name']}")
        else:
            item.stock = med['stock']
            print(f"Updated {med['name']}")
    db.session.commit()
    print("Inventory Populated.")

@app.cli.command("seed-demo")
def seed_demo_command():
    """Create demo appointments and prescriptions."""
    jinay = User.query.filter_by(username='jinay').first()
    doc = DoctorProfile.query.first()
    
    if not jinay or not doc:
        print("Run init-roles first.")
        return

    # Past Appt
    past_date = datetime.now(timezone.utc) - timedelta(days=10)
    appt1 = Appointment(
        patient_id=jinay.patient_profile.id,
        doctor_id=doc.id,
        status='completed',
        created_at=past_date
    )
    db.session.add(appt1)
    db.session.commit()
    
    presc1 = Prescription(appointment_id=appt1.id, instructions="Rest. Diagnosis: Seasonal Flu")
    db.session.add(presc1)
    db.session.commit()
    
    item1 = PrescriptionItem(
        prescription_id=presc1.id,
        medicine="Cough Syrup", dosage="10ml", frequency="0-0-1",
        timing="After Food", duration="5 days", quantity=1
    )
    db.session.add(item1)
    
    # Order for past appt
    order1 = Order(
        patient_id=jinay.patient_profile.id,
        items="Cough Syrup (x1)",
        total_amount=50.0,
        status='completed',
        delivery_type='delivery',
        created_at=past_date
    )
    db.session.add(order1)
    
    # Recent Appt
    appt2 = Appointment(
        patient_id=jinay.patient_profile.id,
        doctor_id=doc.id,
        status='completed',
        created_at=datetime.now(timezone.utc) - timedelta(hours=2)
    )
    
    # Set Fake Coordinates for Demo
    jinay.patient_profile.lat = 18.5913 # Wakad, Pune
    jinay.patient_profile.lng = 73.7742
    
    doc.lat = 18.5204 # Pune City
    doc.lng = 73.8567
    
    db.session.add(appt2)
    db.session.commit()
    
    presc2 = Prescription(appointment_id=appt2.id, instructions="Vitamins. Diagnosis: Weakness")
    db.session.add(presc2)
    db.session.commit()
    
    db.session.add(PrescriptionItem(prescription_id=presc2.id, medicine="MultiVitamin", 
                                    dosage="1 tab", frequency="1-0-0", timing="Morn", duration="30d", quantity=30))
                                    
    db.session.commit()
    print("Demo Data Added.")

@app.cli.command("fix-schema")
def fix_schema_command():
    """Ensure database schema is up to date."""
    db_path = os.path.join(app.instance_path, 'healthcare.db')
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Check Columns
        cursor.execute("PRAGMA table_info('patient_profile')")
        cols = [r[1] for r in cursor.fetchall()]
        if 'allergies' not in cols:
            cursor.execute("ALTER TABLE patient_profile ADD COLUMN allergies TEXT")
            print("Added allergies")
        if 'medical_conditions' not in cols:
            cursor.execute("ALTER TABLE patient_profile ADD COLUMN medical_conditions TEXT")
            print("Added medical_conditions")
            
        cursor.execute("PRAGMA table_info('doctor_profile')")
        cols = [r[1] for r in cursor.fetchall()]
        if 'education' not in cols:
            cursor.execute("ALTER TABLE doctor_profile ADD COLUMN education TEXT")
            print("Added education")
            
        cursor.execute("PRAGMA table_info('order')")
        cols = [r[1] for r in cursor.fetchall()]
        if 'delivery_type' not in cols:
            cursor.execute("ALTER TABLE `order` ADD COLUMN delivery_type VARCHAR(20) DEFAULT 'delivery'")
            print("Added delivery_type")
        if 'estimated_delivery' not in cols:
            cursor.execute("ALTER TABLE `order` ADD COLUMN estimated_delivery DATETIME")
            print("Added estimated_delivery")
        if 'delivery_lat' not in cols:
            cursor.execute("ALTER TABLE `order` ADD COLUMN delivery_lat FLOAT")
            print("Added delivery_lat")
        if 'delivery_lng' not in cols:
            cursor.execute("ALTER TABLE `order` ADD COLUMN delivery_lng FLOAT")
            print("Added delivery_lng")
        if 'delivery_agent' not in cols:
            cursor.execute("ALTER TABLE `order` ADD COLUMN delivery_agent VARCHAR(100)")
            print("Added delivery_agent")
        if 'eta' not in cols:
            cursor.execute("ALTER TABLE `order` ADD COLUMN eta VARCHAR(50)")
            print("Added eta")
            
        conn.commit()
        print("Schema Verified.")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        conn.close()

@app.cli.command("seed-medications")
def seed_medications_command():
    """Create demo medication schedules and logs for testing."""
    jinay = User.query.filter_by(username='jinay').first()
    
    if not jinay:
        print("Run init-roles first to create patient user.")
        return
    
    patient_id = jinay.patient_profile.id
    today = date.today()
    
    medications = [
        {
            "name": "Metformin",
            "dosage": "500mg",
            "frequency": "1-1-0",
            "times": "08:00, 20:00",
            "timing": "After Food",
            "start_offset": -5
        },
        {
            "name": "Amlodipine",
            "dosage": "5mg",
            "frequency": "1-0-0",
            "times": "08:00",
            "timing": "Morning",
            "start_offset": -3
        },
        {
            "name": "Vitamin D3",
            "dosage": "1000 IU",
            "frequency": "1-0-0",
            "times": "12:00",
            "timing": "With Food",
            "start_offset": -7
        },
        {
            "name": "Aspirin",
            "dosage": "75mg",
            "frequency": "0-0-1",
            "times": "21:00",
            "timing": "At Bedtime",
            "start_offset": -2
        }
    ]
    
    for med in medications:
        existing = MedicationSchedule.query.filter_by(
            patient_id=patient_id,
            medicine_name=med["name"],
            is_active=True
        ).first()
        
        if existing:
            print(f"Medication {med['name']} already exists, skipping.")
            continue
        
        start_date = today + timedelta(days=med["start_offset"])
        
        schedule = MedicationSchedule(
            patient_id=patient_id,
            medicine_name=med["name"],
            dosage=med["dosage"],
            frequency=med["frequency"],
            times=med["times"],
            timing=med["timing"],
            start_date=start_date,
            is_active=True
        )
        db.session.add(schedule)
        db.session.commit()
        
        generate_medication_logs(schedule, 14)
        print(f"Added medication: {med['name']}")
    
    notif = Notification(
        patient_id=patient_id,
        title="Welcome to Medication Tracker",
        message="Your medications have been set up. Track your daily doses here!",
        notification_type="general"
    )
    db.session.add(notif)
    
    for med in medications[:2]:
        notif2 = Notification(
            patient_id=patient_id,
            title=f"Medication Reminder: {med['name']}",
            message=f"It's time to take {med['name']} ({med['dosage']})",
            notification_type="medication_reminder",
            is_read=False
        )
        db.session.add(notif2)
    
    db.session.commit()
    print("Medication demo data created successfully!")

def generate_medication_logs(schedule, days_ahead=14):
    """Generate medication logs for the schedule"""
    if not schedule.times:
        return
    
    times_list = [t.strip() for t in schedule.times.split(',')]
    
    current_date = schedule.start_date
    end_date = schedule.end_date if schedule.end_date else (date.today() + timedelta(days=days_ahead))
    
    now = datetime.now()
    
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
                    if current_date < today:
                        status = 'taken' if scheduled_datetime.hour % 2 == 0 else 'missed'
                        taken_time = scheduled_datetime + timedelta(minutes=5) if status == 'taken' else None
                        log = MedicationLog(
                            schedule_id=schedule.id,
                            scheduled_time=scheduled_datetime,
                            date=current_date,
                            status=status,
                            taken_time=taken_time
                        )
                    elif current_date == today:
                        if scheduled_datetime < now:
                            status = 'taken'
                            taken_time = scheduled_datetime + timedelta(minutes=5)
                        else:
                            status = 'pending'
                            taken_time = None
                        log = MedicationLog(
                            schedule_id=schedule.id,
                            scheduled_time=scheduled_datetime,
                            date=current_date,
                            status=status,
                            taken_time=taken_time
                        )
                    else:
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

if __name__ == "__main__":
    app.run()
