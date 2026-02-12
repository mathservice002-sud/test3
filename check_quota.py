import os
import google.generativeai as genai
from dotenv import load_dotenv
import time

load_dotenv()
api_key = os.getenv("OPENAI_API_KEY")
genai.configure(api_key=api_key)

models_to_test = [
    'gemini-1.5-flash',
    'gemini-2.0-flash',
    'gemini-2.5-flash'
]

print(f"--- Quota Diagnostic for Key: {api_key[:10]}... ---")

for model_name in models_to_test:
    print(f"\nTesting Model: {model_name}...")
    try:
        model = genai.GenerativeModel(model_name)
        response = model.generate_content("유닛 테스트입니다. 'OK'라고만 답해주세요.", generation_config={"max_output_tokens": 10})
        print(f"Result: SUCCESS - Response: {response.text.strip()}")
    except Exception as e:
        if "429" in str(e):
            print(f"Result: FAILED - Error: 429 Quota Exceeded")
        elif "404" in str(e):
            print(f"Result: FAILED - Error: 404 Model Not Found")
        else:
            print(f"Result: FAILED - Error: {e}")
    time.sleep(1) # Gap between tests
