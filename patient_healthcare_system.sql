j-- =====================================================
-- NATIONAL PATIENT HEALTHCARE SYSTEM (FULL DATABASE)
-- =====================================================

CREATE DATABASE IF NOT EXISTS patient_healthcare_system
CHARACTER SET utf8mb4
COLLATE utf8mb4_unicode_ci;

USE patient_healthcare_system;

-- =========================
-- PATIENTS
-- =========================
CREATE TABLE patients (
    id INT AUTO_INCREMENT PRIMARY KEY,
    patient_code VARCHAR(10) UNIQUE NOT NULL,
    name VARCHAR(100) NOT NULL,
    email VARCHAR(120) UNIQUE NOT NULL,
    password_hash VARCHAR(256) NOT NULL,
    age INT,
    gender VARCHAR(20),
    city VARCHAR(100),
    phone VARCHAR(20),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    last_login DATETIME
);

-- =========================
-- DOCTORS (READ-ONLY FOR PATIENT)
-- =========================
CREATE TABLE doctors (
    id INT AUTO_INCREMENT PRIMARY KEY,
    doctor_code VARCHAR(10) UNIQUE NOT NULL,
    name VARCHAR(100) NOT NULL,
    specialty VARCHAR(100),
    city VARCHAR(100),
    language VARCHAR(50),
    experience_years INT,
    rating DECIMAL(2,1),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- =========================
-- APPOINTMENTS
-- =========================
CREATE TABLE appointments (
    id INT AUTO_INCREMENT PRIMARY KEY,
    appointment_code VARCHAR(12) UNIQUE NOT NULL,
    patient_email VARCHAR(120) NOT NULL,
    doctor_code VARCHAR(10) NOT NULL,
    appointment_datetime DATETIME,
    reason TEXT,
    status VARCHAR(30) DEFAULT 'Booked',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (patient_email) REFERENCES patients(email) ON DELETE CASCADE,
    FOREIGN KEY (doctor_code) REFERENCES doctors(doctor_code) ON DELETE CASCADE
);

-- =========================
-- PATIENT FILE UPLOADS
-- =========================
CREATE TABLE patient_files (
    id INT AUTO_INCREMENT PRIMARY KEY,
    file_code VARCHAR(12) UNIQUE NOT NULL,
    patient_email VARCHAR(120) NOT NULL,
    appointment_code VARCHAR(12),
    file_category VARCHAR(50),
    file_type VARCHAR(20),
    original_filename VARCHAR(255),
    stored_filename VARCHAR(255),
    file_path VARCHAR(255),
    uploaded_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (patient_email) REFERENCES patients(email) ON DELETE CASCADE,
    FOREIGN KEY (appointment_code) REFERENCES appointments(appointment_code) ON DELETE SET NULL
);

-- =========================
-- MEDICAL HISTORY (LIFETIME)
-- =========================
CREATE TABLE medical_history (
    id INT AUTO_INCREMENT PRIMARY KEY,
    history_code VARCHAR(12) UNIQUE NOT NULL,
    patient_email VARCHAR(120) NOT NULL,
    title VARCHAR(150),
    description TEXT,
    related_file_code VARCHAR(12),
    event_date DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (patient_email) REFERENCES patients(email) ON DELETE CASCADE,
    FOREIGN KEY (related_file_code) REFERENCES patient_files(file_code) ON DELETE SET NULL
);

-- =========================
-- ACTIVITY LOGS (AUDIT)
-- =========================
CREATE TABLE activity_logs (
    id INT AUTO_INCREMENT PRIMARY KEY,
    patient_email VARCHAR(120) NOT NULL,
    action VARCHAR(255),
    ip_address VARCHAR(50),
    action_time DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (patient_email) REFERENCES patients(email) ON DELETE CASCADE
);

-- =========================
-- INDEXES
-- =========================
CREATE INDEX idx_patient_email ON patients(email);
CREATE INDEX idx_doctor_city ON doctors(city);
CREATE INDEX idx_doctor_specialty ON doctors(specialty);
CREATE INDEX idx_appointment_patient ON appointments(patient_email);
CREATE INDEX idx_file_patient ON patient_files(patient_email);
CREATE INDEX idx_history_patient ON medical_history(patient_email);

-- =========================
-- SAMPLE PATIENT DATA
-- =========================
INSERT INTO patients
(patient_code, name, email, password_hash, age, gender, city, phone)
VALUES
('P001','Jinay','jinay@gmail.com',SHA2('jinay123',256),20,'Male','Pune','9999991111'),
('P002','Ashish','ashish@gmail.com',SHA2('ashish123',256),21,'Male','Mumbai','9999992222'),
('P003','Partha','partha@gmail.com',SHA2('partha123',256),22,'Male','Delhi','9999993333'),
('P004','Tanishq','tanishq@gmail.com',SHA2('tanishq123',256),21,'Male','Pune','9999994444');

-- =========================
-- SAMPLE DOCTOR DATA
-- =========================
INSERT INTO doctors
(doctor_code, name, specialty, city, language, experience_years, rating)
VALUES
('D01','Dr. Mehta','Cardiology','Pune','English',15,4.6),
('D02','Dr. Rao','Orthopedic','Mumbai','Hindi',10,4.4),
('D03','Dr. Iyer','Neurology','Pune','English',18,4.8);
