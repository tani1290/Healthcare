from flask import Flask, request, redirect, session, send_from_directory
from werkzeug.utils import secure_filename
from datetime import datetime, timedelta
from functools import wraps
import hashlib, secrets, uuid, os

# ======================================================
# APP CONFIG
# ======================================================
app = Flask(__name__)
app.secret_key = secrets.token_hex(32)
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(hours=4)
app.config["UPLOAD_FOLDER"] = "uploads"
os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

# ======================================================
# UTILITIES
# ======================================================
def hash_password(p): return hashlib.sha256(p.encode()).hexdigest()
def now(): return datetime.now().strftime("%d %b %Y %H:%M")

def login_required(f):
    @wraps(f)
    def wrapper(*a, **k):
        if "patient" not in session:
            return redirect("/")
        return f(*a, **k)
    return wrapper

# ======================================================
# IN-MEMORY DATABASE (NATIONAL MOCK)
# ======================================================
patients = {
    "jinay@gmail.com": {
        "id":"P001","name":"Jinay","email":"jinay@gmail.com",
        "password":hash_password("jinay123"),
        "age":20,"city":"Pune","created":now()
    }
}

doctors = [
    {"id":"D01","name":"Dr. Mehta","specialty":"Cardiology","city":"Pune","lang":"English","exp":15,"rating":4.6},
    {"id":"D02","name":"Dr. Rao","specialty":"Orthopedic","city":"Mumbai","lang":"Hindi","exp":10,"rating":4.4},
    {"id":"D03","name":"Dr. Iyer","specialty":"Neurology","city":"Pune","lang":"English","exp":18,"rating":4.8}
]

appointments = []
reports = []
activity = []

# ======================================================
# ACTIVITY LOGGER (PATIENT SAFETY)
# ======================================================
def log(action):
    activity.append({
        "time": now(),
        "email": session.get("patient"),
        "action": action
    })

# ======================================================
# UI TEMPLATE (HOSPITAL-GRADE)
# ======================================================
def render(title, body, nav=True):
    navbar = ""
    if nav and "patient" in session:
        navbar = """
        <div class="nav">
            <b>🏥 National Patient Healthcare</b>
            <a href="/dashboard">Dashboard</a>
            <a href="/doctors">Find Doctor</a>
            <a href="/appointments">Appointments</a>
            <a href="/history">Medical History</a>
            <a href="/activity">Activity</a>
            <a href="/logout">Logout</a>
        </div>
        """
    return f"""
    <html>
    <head>
        <title>{title}</title>
        <style>
            body{{font-family:Segoe UI;background:#eef2ff;margin:0}}
            .nav{{background:#1e3a8a;color:white;padding:15px}}
            .nav a{{color:white;margin-left:15px;text-decoration:none}}
            .container{{padding:30px;max-width:1000px;margin:auto}}
            .card{{background:white;padding:25px;border-radius:12px;margin-bottom:20px;
                  box-shadow:0 6px 15px rgba(0,0,0,.1)}}
            input,select,button{{padding:10px;width:100%;margin-top:10px}}
            button{{background:#2563eb;color:white;border:none}}
            h2,h3{{color:#1e3a8a}}
            .badge{{background:#e0e7ff;padding:6px 14px;border-radius:20px}}
        </style>
    </head>
    <body>
        {navbar}
        <div class="container">{body}</div>
    </body>
    </html>
    """

# ======================================================
# LOGIN
# ======================================================
@app.route("/", methods=["GET","POST"])
def login():
    error=""
    if request.method=="POST":
        u=patients.get(request.form["email"])
        if u and u["password"]==hash_password(request.form["password"]):
            session["patient"]=u["email"]
            log("Logged in")
            return redirect("/dashboard")
        error="Invalid credentials"

    return render("Login",f"""
    <div class="card">
        <h2>Patient Login</h2>
        <form method="post">
            <input name="email" placeholder="Email" required>
            <input type="password" name="password" placeholder="Password" required>
            <button>Login</button>
        </form>
        <p style="color:red">{error}</p>
        <p><b>Demo:</b> jinay@gmail.com / jinay123</p>
    </div>
    """,False)

# ======================================================
# DASHBOARD
# ======================================================
@app.route("/dashboard")
@login_required
def dashboard():
    email=session["patient"]
    return render("Dashboard",f"""
    <div class="card">
        <h2>Welcome 👋</h2>
        <p>Total Appointments: {len([a for a in appointments if a["email"]==email])}</p>
        <p>Total Reports: {len([r for r in reports if r["email"]==email])}</p>
    </div>
    """)

# ======================================================
# DOCTOR SEARCH
# ======================================================
@app.route("/doctors", methods=["GET","POST"])
@login_required
def find_doctor():
    city=request.form.get("city","")
    spec=request.form.get("spec","")
    result=[d for d in doctors if city.lower() in d["city"].lower() and spec.lower() in d["specialty"].lower()]
    cards=""
    for d in result:
        cards+=f"""
        <div class="card">
            <h3>{d['name']}</h3>
            <p>{d['specialty']} | {d['city']}</p>
            <p>⭐ {d['rating']} | {d['exp']} yrs</p>
            <a href="/book/{d['id']}">Book Appointment</a>
        </div>
        """
    return render("Doctors",f"""
    <div class="card">
        <form method="post">
            <input name="city" placeholder="City">
            <input name="spec" placeholder="Specialty">
            <button>Search</button>
        </form>
    </div>
    {cards or "<p>No doctors found</p>"}
    """)

# ======================================================
# BOOK APPOINTMENT
# ======================================================
@app.route("/book/<doc_id>", methods=["GET","POST"])
@login_required
def book(doc_id):
    doc=[d for d in doctors if d["id"]==doc_id][0]
    if request.method=="POST":
        appointments.append({
            "id":str(uuid.uuid4())[:6],
            "email":session["patient"],
            "doctor":doc,
            "date":request.form["date"]
        })
        log("Booked appointment")
        return redirect("/appointments")
    return render("Book",f"""
    <div class="card">
        <h3>Book with {doc['name']}</h3>
        <form method="post">
            <input type="datetime-local" name="date" required>
            <button>Confirm</button>
        </form>
    </div>
    """)

# ======================================================
# APPOINTMENTS + REPORT UPLOAD
# ======================================================
@app.route("/appointments", methods=["GET","POST"])
@login_required
def appts():
    if request.method=="POST":
        f=request.files["file"]
        fname=secure_filename(f.filename)
        path=os.path.join(app.config["UPLOAD_FOLDER"],fname)
        f.save(path)
        reports.append({
            "email":session["patient"],
            "file":fname,
            "type":request.form["type"],
            "time":now()
        })
        log("Uploaded medical report")

    rows=""
    for a in appointments:
        if a["email"]==session["patient"]:
            rows+=f"<p>{a['date']} - {a['doctor']['name']}</p>"

    return render("Appointments",f"""
    <div class="card">{rows or "No appointments"}</div>
    <div class="card">
        <h3>Upload Medical Report</h3>
        <form method="post" enctype="multipart/form-data">
            <select name="type">
                <option>X-Ray</option><option>MRI</option><option>Blood Test</option>
            </select>
            <input type="file" name="file" required>
            <button>Upload</button>
        </form>
    </div>
    """)

# ======================================================
# MEDICAL HISTORY
# ======================================================
@app.route("/history")
@login_required
def history():
    rows=""
    for r in reports:
        if r["email"]==session["patient"]:
            rows+=f"<p>{r['time']} | {r['type']} | <a href='/download/{r['file']}'>Download</a></p>"
    return render("History",f"<div class='card'>{rows or 'No history yet'}</div>")

@app.route("/download/<name>")
@login_required
def download(name):
    log("Downloaded report")
    return send_from_directory(app.config["UPLOAD_FOLDER"],name)

# ======================================================
# ACTIVITY LOG
# ======================================================
@app.route("/activity")
@login_required
def act():
    rows=""
    for a in activity:
        if a["email"]==session["patient"]:
            rows+=f"<p>{a['time']} - {a['action']}</p>"
    return render("Activity",f"<div class='card'>{rows}</div>")

# ======================================================
# LOGOUT
# ======================================================
@app.route("/logout")
def logout():
    log("Logged out")
    session.clear()
    return redirect("/")

# ======================================================
# RUN
# ======================================================
if __name__=="__main__":
    print("GDG_VU_healthcare system → http://127.0.0.1:5000")
    app.run(debug=True)
