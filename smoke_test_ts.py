import requests
import json

def test_api_ts():
    url = "http://localhost:8000/design/enclosure"
    payload = {
        "diameter_inch": 12,
        "rms_power": 600,
        "fs": 32.0,
        "qts": 0.42,
        "vas": 45.0,
        "sd": 510.0,
        "xmax": 18.0,
        "re": 3.6,
        "vehicle": "Hatchback",
        "purpose": "Günlük Bass",
        "material_thickness_mm": 18,
        "enclosure_type": "aero"
    }
    headers = {"X-API-Key": "premium-dev"}
    
    try:
        print(f"Sending T/S request to {url}...")
        response = requests.post(url, json=payload, headers=headers, timeout=10)
        print(f"Status Code: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print("Success! Design ID:", data["design_id"])
            print("Mode:", data["mode"])
            print("Volume:", data["net_volume_l"], "L")
            print("Tuning:", data["tuning_hz"], "Hz")
            print("Expert Advice:", data["acoustic_advice"])
            return True
        else:
            print("Error:", response.text)
            return False
    except Exception as e:
        print("Failed to connect:", str(e))
        return False

if __name__ == "__main__":
    test_api_ts()
