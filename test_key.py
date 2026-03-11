import google.generativeai as genai
import os

API_KEY = "AIzaSyDUyxGqc_KhBe68kmaV_WRIRVWm9PZQAAw"
genai.configure(api_key=API_KEY)

try:
    model = genai.GenerativeModel('gemini-pro')
    response = model.generate_content("Hello, suggest a color for a hospital wall.")
    print(f"SUCCESS: {response.text}")
except Exception as e:
    print(f"FAILURE: {e}")
