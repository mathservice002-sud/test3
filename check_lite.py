import os
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv("OPENAI_API_KEY")
genai.configure(api_key=api_key)

models_to_test = [
    'models/gemini-2.0-flash-lite',
    'models/gemini-2.0-flash-lite-001'
]

print(f"--- Lite Models Diagnostic ---")

for model_name in models_to_test:
    print(f"\nTesting Model: {model_name}...")
    try:
        model = genai.GenerativeModel(model_name)
        response = model.generate_content("Hi", generation_config={"max_output_tokens": 5})
        print(f"Result: SUCCESS - Response: {response.text.strip()}")
    except Exception as e:
        print(f"Result: FAILED - Error: {e}")
