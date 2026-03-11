import os
import secrets
from flask import Blueprint, render_template, redirect, url_for, flash, request, session
from flask_login import login_user, logout_user, current_user
from authlib.integrations.flask_client import OAuth
from app import db
from app.models import User, PatientProfile, DoctorProfile, HospitalProfile, MedicalProfile

auth_bp = Blueprint('auth', __name__)

# OAuth Setup
oauth = OAuth()

def init_oauth(app):
    """Initialize OAuth with the Flask app - call this from create_app()"""
    oauth.init_app(app)
    oauth.register(
        name='google',
        client_id=os.environ.get('GOOGLE_CLIENT_ID'),
        client_secret=os.environ.get('GOOGLE_CLIENT_SECRET'),
        server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
        client_kwargs={'scope': 'openid email profile'}
    )

@auth_bp.route('/', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        # Redirect based on role
        if current_user.role == 'patient': return redirect(url_for('patient.dashboard'))
        if current_user.role == 'doctor': return redirect(url_for('doctor.dashboard'))
        if current_user.role == 'hospital': return redirect(url_for('hospital.dashboard'))
        if current_user.role == 'medical': return redirect(url_for('medical.dashboard'))
        return redirect(url_for('auth.logout')) # Fallback

    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        user = User.query.filter_by(email=email).first()
        
        if user and user.check_password(password):
            login_user(user)
            if user.role == 'patient': return redirect(url_for('patient.dashboard'))
            if user.role == 'doctor': return redirect(url_for('doctor.dashboard'))
            if user.role == 'hospital': return redirect(url_for('hospital.dashboard'))
            if user.role == 'medical': return redirect(url_for('medical.dashboard'))
        else:
            flash('Invalid email or password.')
            
    return render_template('auth/login.html', title='Login')

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('auth.login'))
        
    if request.method == 'POST':
        role = request.form['role']
        email = request.form['email']
        username = request.form['username']
        password = request.form['password']
        
        if len(password) < 8:
            flash('Password must be at least 8 characters long.')
            return redirect(url_for('auth.register'))
        
        if User.query.filter_by(email=email).first():
            flash('Email already registered.')
            return redirect(url_for('auth.register'))
            
        if User.query.filter_by(username=username).first():
            flash('Username already taken. Please choose another.')
            return redirect(url_for('auth.register'))
            
        user = User(username=username, email=email, role=role)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        
        # Create specific profile based on role
        if role == 'patient':
            # Collect additional patient fields
            profile = PatientProfile(user_id=user.id, name=username, phone=request.form.get('phone'), gender=request.form.get('gender'))
            db.session.add(profile)
        elif role == 'doctor':
             # Collect additional doctor fields
            profile = DoctorProfile(user_id=user.id, name=username, specialty=request.form.get('specialty'), city=request.form.get('city'))
            db.session.add(profile)
            
        db.session.commit()
        flash('Registration successful! Please login.')
        return redirect(url_for('auth.login'))
        
    return render_template('auth/register.html', title='Register')

@auth_bp.route('/logout', methods=['GET', 'POST'])
def logout():
    if request.method == 'POST':
        logout_user()
        flash('Logged out successfully.')
        return redirect(url_for('auth.login'))
    
    # If GET, show confirmation page
    if not current_user.is_authenticated:
        return redirect(url_for('auth.login'))
        
    return render_template('auth/logout_confirm.html', title='Confirm Logout')

# ==================== Google OAuth Routes ====================

@auth_bp.route('/login/google')
def google_login():
    """Initiate Google OAuth login flow"""
    # Generate a nonce for security
    nonce = secrets.token_urlsafe(16)
    session['oauth_nonce'] = nonce
    session['oauth_role'] = 'patient'  # Default role for login
    
    redirect_uri = url_for('auth.google_callback', _external=True)
    return oauth.google.authorize_redirect(redirect_uri, nonce=nonce)

@auth_bp.route('/register/google')
def google_register():
    """Initiate Google OAuth registration flow with role selection"""
    role = request.args.get('role', 'patient')
    if role not in ['patient', 'doctor', 'hospital', 'medical']:
        role = 'patient'
    
    # Generate a nonce for security
    nonce = secrets.token_urlsafe(16)
    session['oauth_nonce'] = nonce
    session['oauth_role'] = role  # Store selected role
    
    redirect_uri = url_for('auth.google_callback', _external=True)
    return oauth.google.authorize_redirect(redirect_uri, nonce=nonce)

@auth_bp.route('/callback/google')
def google_callback():
    """Handle Google OAuth callback"""
    try:
        token = oauth.google.authorize_access_token()
        nonce = session.pop('oauth_nonce', None)
        role = session.pop('oauth_role', 'patient')
        
        user_info = oauth.google.parse_id_token(token, nonce=nonce)
        
        google_id = user_info.get('sub')
        email = user_info.get('email')
        name = user_info.get('name', email.split('@')[0])
        
        # Check if user exists by google_id
        user = User.query.filter_by(google_id=google_id).first()
        
        if not user:
            # Check if user exists by email (link Google account)
            user = User.query.filter_by(email=email).first()
            if user:
                # Link Google account to existing user
                user.google_id = google_id
                db.session.commit()
                flash('Google account linked to your existing account!')
            else:
                # Create new user
                # Generate unique username
                base_username = name.lower().replace(' ', '_')
                username = base_username
                counter = 1
                while User.query.filter_by(username=username).first():
                    username = f"{base_username}_{counter}"
                    counter += 1
                
                user = User(
                    username=username,
                    email=email,
                    role=role,
                    google_id=google_id
                )
                # No password for OAuth users
                db.session.add(user)
                db.session.commit()
                
                # Create profile based on role
                if role == 'patient':
                    profile = PatientProfile(user_id=user.id, name=name)
                    db.session.add(profile)
                elif role == 'doctor':
                    profile = DoctorProfile(user_id=user.id, name=name)
                    db.session.add(profile)
                elif role == 'hospital':
                    profile = HospitalProfile(user_id=user.id, name=name)
                    db.session.add(profile)
                elif role == 'medical':
                    profile = MedicalProfile(user_id=user.id, name=name)
                    db.session.add(profile)
                db.session.commit()
                
                flash(f'Account created successfully as {role}!')
        
        # Log the user in
        login_user(user)
        
        # Redirect based on role
        if user.role == 'patient':
            return redirect(url_for('patient.dashboard'))
        elif user.role == 'doctor':
            return redirect(url_for('doctor.dashboard'))
        elif user.role == 'hospital':
            return redirect(url_for('hospital.dashboard'))
        elif user.role == 'medical':
            return redirect(url_for('medical.dashboard'))
        
        return redirect(url_for('auth.login'))
        
    except Exception as e:
        flash(f'Google login failed: {str(e)}')
        return redirect(url_for('auth.login'))
