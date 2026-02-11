import requests
import json

def test_api_config():
    print("Testing /api/config Endpoint...")
    try:
        response = requests.get("http://127.0.0.1:5000/api/config")
        print(f"Status Code: {response.status_code}")
        print(f"Response Body: {response.text}")
        data = response.json()
        if "hasServerKey" in data:
            print(f"[SUCCESS] Server reported hasServerKey correctly: {data['hasServerKey']}")
    except Exception as e:
        print(f"[FAIL] Error: {e}")

def test_analyze_without_key():
    print("\nTesting /api/analyze without client-side key (expecting server key to take over)...")
    # This test will still fail with 400/500 if NO server key is set, 
    # but it verifies the route is reachable.
    try:
        response = requests.post("http://127.0.0.1:5000/api/analyze", json={
            "apiKey": "",
            "image": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8/5+hHgAHggJ/PchI7wAAAABJRU5ErkJggg=="
        })
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.text}")
    except Exception as e:
        print(f"[FAIL] Error: {e}")

if __name__ == "__main__":
    test_api_config()
    test_analyze_without_key()
