import requests
import json

url = "http://localhost:8000/download/instagram"
data = {
    "url": "https://www.instagram.com/p/DU51yg_kV70/?utm_source=ig_web_copy_link&igsh=NTc4MTIwNjQ2YQ==",
    "format": "mp4"
}

try:
    response = requests.post(url, json=data, timeout=60)
    print(f"Status Code: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
except Exception as e:
    print(f"Error: {e}")
