import requests
import json
import os

# Configure API Key from environment variable
API_KEY = os.environ.get('GEMINI_API_KEY')
if not API_KEY:
    API_KEY = "demo_api_key_for_development"
    print("WARNING: GEMINI_API_KEY not set. AI features will not work properly.")

URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-flash-latest:generateContent?key={API_KEY}"

SYSTEM_INSTRUCTION = """
You are a clinical decision-support assistant. You analyze structured patient data and answer questions or suggest visualizations. You do NOT diagnose or replace a doctor.

Rules:
1. Use only provided patient data.
2. Do not hallucinate missing information.
3. If data is insufficient, respond with 'INSUFFICIENT_DATA'.
4. Keep answers concise and clinical.
5. Always include safety disclaimer.

Input Schema:
{
  "patient_profile": { "patient_id": "string", "age": "number", "sex": "string" },
  "medical_history": { "diagnoses": [], "medications": [], "allergies": [], "vitals": [], "lab_results": [] },
  "user_query": { "type": "string" }
}

Task Modes & Output Formats:

1. question_answering:
   {
     "answer": "string",
     "confidence_level": "LOW | MEDIUM | HIGH",
     "disclaimer": "string"
   }

2. patient_summary:
   {
     "summary": "string",
     "key_conditions": ["string"],
     "current_medications": ["string"],
     "disclaimer": "string"
   }

3. graph_instruction:
   {
     "chart_type": "line | bar",
     "title": "string",
     "x_axis": "string",
     "y_axis": "string",
     "reference_range": { "min": "number", "max": "number" },
     "interpretation": "string",
     "disclaimer": "string"
   }

Default Disclaimer: "AI-generated output for clinical support only. Final decision must be made by a licensed physician."
"""

def query_ai_service(patient_data, user_query):
    """
    Constructs the prompt and calls Gemini API via REST.
    """
    
    # Construct the Prompt
    prompt_text = f"""
    {SYSTEM_INSTRUCTION}

    Current Patient Data:
    {json.dumps(patient_data, indent=2)}

    User Query: "{user_query}"

    Based on the user query, determine the correct Task Mode and return ONLY the corresponding JSON object.
    IMPORTANT: Return ONLY valid JSON. No markdown formatting.
    """
    
    payload = {
        "contents": [{
            "parts": [{"text": prompt_text}]
        }]
    }
    
    try:
        response = requests.post(URL, headers={'Content-Type': 'application/json'}, json=payload)
        response.raise_for_status()
        
        result = response.json()
        
        # Extract text from Gemini response structure
        # { "candidates": [ { "content": { "parts": [ { "text": "..." } ] } } ] }
        try:
            generated_text = result['candidates'][0]['content']['parts'][0]['text']
        except (KeyError, IndexError):
            return {"error": "Invalid response structure from AI"}

        # specialized cleaning for json
        text = generated_text.strip()
        if text.startswith('```json'):
            text = text[7:-3]
        elif text.startswith('```'):
            text = text[3:-3]
            
        response_data = json.loads(text)
        
        # Post-processing: If graph_instruction, inject the actual data points from patient_data
        if "chart_type" in response_data:
             # Logic to find relevant lab results from patient_data based on title/axis
             # For this demo, we just pass back the full lab_results available
             # Note: patient_data structure might differ slightly depending on where it came from (dict vs obj)
             # In ai.py it is passed as a dict.
             # medical_history -> lab_results
             
             med_hist = patient_data.get("medical_history", {})
             lab_results = med_hist.get("lab_results", [])
             
             # Transform lab_results to chartjs format labels/data
             labels = [r.get("date") for r in lab_results]
             values = [r.get("value") for r in lab_results]
             
             response_data["graph_data"] = {
                 "labels": labels,
                 "datasets": [{
                     "label": response_data.get("title", "Trend"),
                     "data": values,
                     "borderColor": "rgb(75, 192, 192)",
                     "tension": 0.1
                 }]
             }
             
        return response_data

    except Exception as e:
        print(f"AI Error: {e}")
        return {
            "error": "Failed to generate AI response",
            "details": str(e)
        }

