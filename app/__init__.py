import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_migrate import Migrate
from flask_wtf.csrf import CSRFProtect
from config import Config

# Initialize extensions
db = SQLAlchemy()
login_manager = LoginManager()
login_manager.login_view = 'auth.login'
migrate = Migrate()
csrf = CSRFProtect()

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Initialize extensions with app
    db.init_app(app)
    login_manager.init_app(app)
    migrate.init_app(app)
    csrf.init_app(app)
    
    # Disable CSRF for API endpoints
    from app.routes.medication import api_bp
    csrf.exempt(api_bp)

    # Ensure upload folder exists
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

    # Register Blueprints
    from app.routes.auth import auth_bp, init_oauth
    app.register_blueprint(auth_bp)
    init_oauth(app)  # Initialize Google OAuth
    
    from app.routes.patient import patient_bp
    app.register_blueprint(patient_bp)
    
    from app.routes.doctor import doctor_bp
    app.register_blueprint(doctor_bp)
    
    from app.routes.hospital import hospital_bp
    app.register_blueprint(hospital_bp)
    
    from app.routes.medical import medical_bp
    app.register_blueprint(medical_bp)
    
    from app.routes.payment import payment_bp
    app.register_blueprint(payment_bp)

    from app.routes.ai import ai_bp
    app.register_blueprint(ai_bp)
    
    from app.routes.medication import medication_bp, api_bp
    app.register_blueprint(medication_bp)
    app.register_blueprint(api_bp)
    
    from datetime import datetime, timezone
    from flask_login import current_user
    
    @app.context_processor
    def inject_now():
        return {'now': lambda: datetime.now(timezone.utc).replace(tzinfo=None)}

    @app.context_processor
    def inject_notifications():
        if current_user.is_authenticated and current_user.role == 'patient':
            from app.models import Notification
            count = Notification.query.filter_by(
                patient_id=current_user.patient_profile.id, 
                is_read=False
            ).count()
            return dict(unread_notifications_count=count)
        return dict(unread_notifications_count=0)

    return app
