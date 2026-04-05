import requests
import json
import time

URL = "http://127.0.0.1:9000/chat/"

print("--- DD1 SES USTASI TESTI (MUHENDIS MUSTERI) ---")

scenarios = [
    {
        "name": "TEST 1: SPL 15 INC (Rockford Fosgate T2D415) - 32Hz Hedefli",
        "message": "Selamın aleyküm. Elimde Rockford Fosgate T2D415 var 15 inç. 32Hz hedefli sert bas vuran bir SPL kabin tasarla."
    },
    {
        "name": "TEST 2: SQ 12 INC (Alpine Type-R) - Mühürlü Kalite",
        "message": "Ustam Alpine Type-R 12 inç için referans kalite SQ çalan mühürlü bir kutu yapalım."
    },
    {
        "name": "TEST 3: SPL 8 INC (GPL 8 inç SPL) - Küçük canavar",
        "message": "Usta 8 inç SPL bas var, araba sedan. Bu ufaklık için ciğer söken bir portlu kabin çıkar."
    }
]

context = {}

for s in scenarios:
    print(f"\n==============================================")
    print(f">>> {s['name']}")
    print(f"Müşteri: {s['message']}")
    
    payload = {
        "message": s["message"],
        "context": context
    }
    
    try:
        response = requests.post(URL, json=payload, timeout=30)
        print(f"Status Code: {response.status_code}")
        
        try:
            data = response.json()
        except Exception as json_e:
            print(f"Server Response (Not JSON): {response.text}")
            continue
            
        reply = data.get("reply", "")
        action = data.get("action", "")
        design = data.get("design")
        errors = data.get("errors", [])
        
        print(f"\nUstası (Action: {action}): {reply}")
        if errors:
            print(f"[!] Hatalar: {errors}")
            
        if design:
            print("\n[!] KABIN TASARIMI GELDI:")
            print(f" - Hacim (Net): {design.get('net_volume_l')} Litre")
            print(f" - Tuning (Frekans): {design.get('tuning_hz')} Hz")
            print(f" - Kutu Tipi: {design.get('enclosure_type')}")
            dims = design.get('dimensions', {})
            print(f" - Ebatlar: G={dims.get('w_mm')}mm Y={dims.get('h_mm')}mm D={dims.get('d_mm')}mm")
            
        ext_info = data.get("extracted_info", {})
        print(f"[*] CIkarilan Bilgiler:")
        for k, v in ext_info.items():
            print(f"    - {k}: {v}")

        # context update
        if data.get("extracted_info"):
            context.update(data["extracted_info"])
            
    except Exception as e:
        print(f"HATA: {e}")
        
    time.sleep(2)
