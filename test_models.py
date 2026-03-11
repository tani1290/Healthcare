import requests
import json

API_KEY = "AIzaSyDUyxGqc_KhBe68kmaV_WRIRVWm9PZQAAw"
URL = f"https://generativelanguage.googleapis.com/v1beta/models?key={API_KEY}"

try:
    response = requests.get(URL)
    print(f"Status Code: {response.status_code}")
    if response.status_code == 200:
        models = response.json().get('models', [])
        print("Available Models:")
        for m in models:
            if 'generateContent' in m.get('supportedGenerationMethods', []):
                print(f" - {m['name']}")
    else:
        print(f"Error: {response.text}")

except Exception as e:
    print(f"Exception: {e}")
