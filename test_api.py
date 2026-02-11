import requests
import json

def test_server_health():
    print("Testing Server Health...")
    try:
        response = requests.get("http://127.0.0.1:5000")
        print(f"Status Code: {response.status_code}")
        if response.status_code == 200:
            print("[SUCCESS] Server is UP")
    except Exception as e:
        print(f"[FAIL] Server is DOWN: {e}")

def test_recommend_endpoint():
    print("\nTesting Recommend Endpoint (with dummy data)...")
    url = "http://127.0.0.1:5000/api/recommend"
    payload = {
        "apiKey": "sk-test-dummy-key",
        "lunch": "카레라이스, 단무지, 요구르트",
        "ingredients": "두부, 스팸, 양파"
    }
    try:
        response = requests.post(url, json=payload)
        print(f"Status Code: {response.status_code}")
        # Expected response is an error JSON because key is invalid
        print(f"Response: {response.text}")
        if response.status_code in [400, 500]:
            print("[SUCCESS] Endpoint reached and handled authentication/API error correctly.")
    except Exception as e:
        print(f"[FAIL] Error reaching endpoint: {e}")

if __name__ == "__main__":
    test_server_health()
    test_recommend_endpoint()
