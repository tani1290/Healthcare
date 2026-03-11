# 🛠️ Development Setup Guide

This guide provides step-by-step instructions to set up the **National Healthcare System** backend on your local machine.

## 📋 Prerequisites

Ensure you have the following installed:
- **Python 3.8+**: [Download Here](https://www.python.org/downloads/)
- **Git**: [Download Here](https://git-scm.com/downloads)
- **SQLite**: (Usually pre-installed on macOS/Linux/Windows).

---

## 🚀 Step-by-Step Installation

### 1. Clone the Repository
Open your terminal and run:
```bash
git clone <your-repo-url>
cd patient_backend
```

### 2. Set Up a Virtual Environment
It's recommended to use a virtual environment to manage dependencies.

**macOS / Linux:**
```bash
python3 -m venv venv
source venv/bin/activate
```

**Windows:**
```bash
python -m venv venv
venv\Scripts\activate
```

### 3. Install Dependencies
Install all required Python packages from `requirements.txt`:
```bash
pip install -r requirements.txt
```

### 4. Initialize the Database
The application uses SQLite. You need to create the database tables and populate them with initial data.

**Run the following commands in order:**

1.  **Initialize Roles (Users)**:
    Creates default accounts for Pharmacy, Doctor, and Patient.
    ```bash
    export FLASK_APP=manage_data.py
    flask init-roles
    ```

2.  **Seed Inventory**:
    Adds sample medicines to the pharmacy inventory.
    ```bash
    flask seed-inventory
    ```

3.  **Fix Schema (Optional)**:
    Run this if you encounter "column not found" errors (useful after updates).
    ```bash
    flask fix-schema
    ```

### 5. Run the Application
Start the Flask development server:

**macOS / Linux:**
```bash
export FLASK_APP=run.py
export FLASK_DEBUG=1
flask run
```

**Windows (PowerShell):**
```powershell
$env:FLASK_APP = "run.py"
$env:FLASK_DEBUG = "1"
flask run
```

The server will start at `http://127.0.0.1:5000/`.

---

## 🧪 Testing the Setup

1.  Open your browser and navigate to `http://127.0.0.1:5000/`.
2.  Log in with the mock credentials:

| Role | Username | Password |
|------|----------|----------|
| **Patient** | `jinay` | `jinay123` |
| **Medical** | `pharmacy` | `pharmacy123` |
| **Doctor** | `doctor` | `doctor123` |

---

## ❓ Troubleshooting

### `ModuleNotFoundError: No module named 'app'`
Make sure you are in the root directory (`patient_backend`) and your virtual environment is activated.

### `sqlite3.OperationalError: no such table`
This means the database wasn't initialized. Run `flask init-roles` again.

### `Address already in use`
Another process is using port 5000. Kill it using:
```bash
# macOS/Linux
lsof -ti:5000 | xargs kill -9
```
Or run Flask on a different port:
```bash
flask run --port=5001
```
