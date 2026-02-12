import os
import google.generativeai as genai
from dotenv import load_dotenv
import time

load_dotenv()
api_key = os.getenv("OPENAI_API_KEY")
genai.configure(api_key=api_key)

models_to_test = [
    'models/gemini-1.5-flash',
    'models/gemini-1.5-flash-latest',
    'models/gemini-1.5-flash-8b',
    'models/gemini-flash-latest'
]

print(f"--- Second Diagnostic for Key: {api_key[:10]}... ---")

for model_name in models_to_test:
    print(f"\nTesting Model: {model_name}...")
    try:
        model = genai.GenerativeModel(model_name)
        response = model.generate_content("Hi", generation_config={"max_output_tokens": 5})
        print(f"Result: SUCCESS - Response: {response.text.strip()}")
    except Exception as e:
        print(f"Result: FAILED - Error: {e}")
    time.sleep(1)
