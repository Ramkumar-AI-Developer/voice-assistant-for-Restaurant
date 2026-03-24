import httpx

try:
    response = httpx.post(
        "http://localhost:8000/auth/login",
        json={"username": "admin", "password": "admin123"},
        headers={"Content-Type": "application/json"}
    )
    print(f"Status Code: {response.status_code}")
    print(f"Response: {response.json()}")
except Exception as e:
    print(f"Error: {e}")
