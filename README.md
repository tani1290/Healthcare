# 🏥 National Healthcare System

A comprehensive, full-stack web application for managing healthcare services, bridging the gap between Patients, Doctors, and Pharmacy services. Built with **Flask**, **SQLAlchemy**, and **Bootstrap 5**.

## 🚀 Features

### 👤 Patient Portal
- **Dashboard**: View upcoming appointments, medicine reminders, and health stats.
- **Find Doctors**: Search doctors by specialty and location.
- **Appointments**: Book, view, and manage appointments.
- **Prescriptions**: View digital prescriptions from doctors.
- **Order Medicines**: 
    - Order prescribed medicines directly from the app.
    - **Home Delivery**: Pin location on a map (`Leaflet.js`) for accurate delivery.
    - **Store Pickup**: Get directions to the nearest pharmacy.
    - **Live Tracking**: Visual stepper for order status (Placed → Packed → Out for Delivery → Delivered).
- **Medical History**: Access complete medical records and logs.
- **Profile**: Manage personal details, allergies, and medical conditions.

### 💊 Pharmacy / Medical Dashboard
- **Order Management**: View new, active, and completed medicine orders.
- **Inventory System**: Manage medicine stock, prices, and expiry dates.
- **Dispatch System**: 
    - Assign delivery agents and set ETAs.
    - **Smart Routing**: View patient location on a map.
    - **Share Route**: Copy route links or share directly via **WhatsApp** to delivery agents.

### 👨‍⚕️ Doctor Portal
- **Dashboard**: Manage daily appointments and patient queues.
- **Consultation**: Digital prescriptions and patient history review.

## 🛠️ Tech Stack
- **Backend**: Python, Flask, Flask-Login, Flask-SQLAlchemy.
- **Database**: SQLite.
- **Frontend**: HTML5, CSS3, Bootstrap 5, JavaScript.
- **Maps**: Leaflet.js, OpenStreetMap.
- **Payment**: Mock Payment Gateway (Supports Credit Card & **Cash on Delivery**).

## ⚙️ Installation & Setup

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd patient_backend
   ```

2. **Create a Virtual Environment**
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows use `venv\Scripts\activate`
   ```

3. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Initialize Database**
   The application uses a CLI utility to manage data.
   ```bash
   # Initialize and seed the database with mock data
   flask seed-db
   
   # Or to fix schema references if upgrading
   flask fix-schema
   ```

5. **Run the Application**
   ```bash
   export FLASK_APP=run.py
   export FLASK_DEBUG=1
   flask run
   ```

## 🔑 Default Credentials (Mock Data)

After running `flask seed-db`, the following users are available:

| Role | Email | Password |
|------|-------|----------|
| **Patient** | `patient@example.com` | `password` |
| **Doctor** | `doctor@test.com` | `password` |
| **Medical** | `medical@test.com` | `password` |

## 📱 Usage Guide

### Ordering Medicines
1. Go to **My Prescriptions**.
2. Click **Order Now**.
3. Select the medicines you need.
4. Choose **Home Delivery**.
5. Drag the map marker to your exact location.
6. Proceed to Checkout and select **Card** or **Cash on Delivery**.

### Dispatching Orders (Pharmacy)
1. Log in as **Medical**.
2. Go to the **Dashboard**.
3. Click **Route** to see the patient's location.
4. Click **Dispatch**, assign an agent (e.g., "Rahul"), and set an ETA (e.g., "20 mins").
5. Share the route via WhatsApp if needed.

## 🤝 Contributing
1. Fork the repo.
2. Create a feature branch (`git checkout -b feature/NewFeature`).
3. Commit changes (`git commit -m 'Add NewFeature'`).
4. Push to branch (`git push origin feature/NewFeature`).
5. Open a Pull Request.

---
*Built with ❤️ for better healthcare.*
