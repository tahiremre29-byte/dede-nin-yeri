"""
DD1 Box Agent — API İletişim Servisi
"""
import requests
from config import API_BASE_URL, DD1_PREMIUM_KEY

class ApiClient:
    @staticmethod
    def calculate_enclosure(params: dict) -> dict:
        """Kabin hesaplama isteğini sunucuya gönderir"""
        url = f"{API_BASE_URL}/design/enclosure"
        headers = {"X-API-Key": DD1_PREMIUM_KEY}
        
        # API beklediği parametre isimlerine çevir (isteğe bağlı, şu an uyumlu)
        # Sadece enclosure_type enum olduğu için stringe çevrilebilir
        payload = params.copy()
        
        # Boş olanları (0) None yap ki şema validation geçsin (Eğer opsiyonelse)
        for k in ["fs", "qts", "vas", "sd", "xmax", "re"]:
            if payload.get(k) == 0:
                payload[k] = None
                
        # API Parametre Eşleşmesi
        payload["material_thickness_mm"] = payload.pop("thickness")
        payload["enclosure_type"] = "aero" # Varsayılan
        payload["diameter_inch"] = payload.pop("diameter")
        
        response = requests.post(url, json=payload, headers=headers, timeout=15)
        response.raise_for_status()
        return response.json()

    @staticmethod
    def get_health() -> bool:
        """Sunucu durumunu kontrol et"""
        try:
            url = f"{API_BASE_URL}/health"
            r = requests.get(url, timeout=3)
            return r.status_code == 200
        except:
            return False
