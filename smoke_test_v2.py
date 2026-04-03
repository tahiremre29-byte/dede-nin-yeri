import requests
import json

def test_api():
    url = "http://localhost:8000/design/enclosure"
    payload = {
        "diameter_inch": 12,
        "rms_power": 600,
        "vehicle": "Sedan",
        "purpose": "SQL",
        "bass_char": "Müzik Temiz Olsun",
        "sub_dir": "Arkaya baksın",
        "material_thickness_mm": 18,
        "enclosure_type": "aero"
    }
    headers = {"X-API-Key": "premium-dev"}
    
    try:
        print(f"Sending request to {url}...")
        response = requests.post(url, json=payload, headers=headers, timeout=10)
        print(f"Status Code: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print("Success! Design ID:", data["design_id"])
            print("Mode:", data["mode"])
            print("Tuning:", data["tuning_hz"], "Hz")
            print("Panels count:", len(data["panel_list"]))
            return True
        else:
            print("Error:", response.text)
            return False
    except Exception as e:
        print("Failed to connect:", str(e))
        return False

if __name__ == "__main__":
    test_api()
