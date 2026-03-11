from app import create_app, db
from app.models import User, DoctorProfile, PatientProfile

app = create_app()

@app.shell_context_processor
def make_shell_context():
    return {'db': db, 'User': User, 'DoctorProfile': DoctorProfile, 'PatientProfile': PatientProfile}

if __name__ == '__main__':
    app.run(debug=True, port=5005)
