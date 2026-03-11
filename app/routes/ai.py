from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from app.models import PatientProfile, MedicalHistory
from app.services.ai_service import query_ai_service
import json

ai_bp = Blueprint('ai', __name__, url_prefix='/ai')

@ai_bp.route('/insight', methods=['POST'])
@login_required
def get_insight():
    if current_user.role != 'doctor':
        return jsonify({"error": "Unauthorized"}), 403
        
    data = request.get_json()
    patient_id = data.get('patient_id')
    user_query = data.get('query')
    
    if not patient_id or not user_query:
        return jsonify({"error": "Missing parameters"}), 400
        
    # Fetch Patient Data
    patient = PatientProfile.query.get_or_404(patient_id)
    
    # Structure Data for AI
    # Note: parsing lifestyle_data from JSON string if exists
    lifestyle = {}
    if patient.lifestyle_data:
        try:
            lifestyle = json.loads(patient.lifestyle_data)
        except:
            lifestyle = patient.lifestyle_data

    import re
    
    # Serialize Medical History & Extract Lab Data
    history_list = []
    lab_results = []
    
    # Regex to find numbers in description (simple float matcher)
    val_regex = r"(\d+(\.\d+)?)"
    
    for h in patient.medical_history:
        # Add to text history
        history_list.append({
            "date": h.date.strftime('%Y-%m-%d'),
            "title": h.title,
            "details": h.description
        })
        
        # Try to extract numerical value for graphing
        # Helper: only extract if title matches query roughly or if we want all data available
        # checking if the record has a number
        match = re.search(val_regex, h.description)
        if match:
            try:
                val = float(match.group(1))
                lab_results.append({
                    "date": h.date.strftime('%Y-%m-%d'),
                    "test": h.title, # Use title as test name
                    "value": val
                })
            except:
                pass

    patient_payload = {
        "patient_profile": {
            "patient_id": str(patient.id),
            "name": patient.name,
            "age": patient.age or 30, # Default if not set
            "sex": patient.gender,
            "vitals": {
                "height": patient.height_cm,
                "weight": patient.weight_kg,
                "bmi": round(patient.weight_kg / ((patient.height_cm/100)**2), 1) if patient.height_cm and patient.weight_kg else None
            },
            "lifestyle": lifestyle
        },
        "medical_history": {
            "records": history_list,
            "lab_results": lab_results 
        }
    }
    
    # Call AI
    ai_response = query_ai_service(patient_payload, user_query)
    
    return jsonify(ai_response)
