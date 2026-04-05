from core.config import cfg
from google import genai

client = genai.Client(api_key=cfg.gemini_api_key)
prompt = (
    "JBL gt12 subwoofer (car audio) için fabrika T/S parametrelerinden "
    "Fs, Qts ve Vas değerlerini kesin olarak biliyor musun? Biliyorsan SADECE JSON formatında dön: "
    "{\"fs\": 30.0, \"qts\": 0.45, \"vas\": 55.0}. Emin değilsen veya bulamazsan "
    "SADECE 'BİLİNMİYOR' kelimesini dön. Başka hiçbir açıklama yazma."
)
res = client.models.generate_content(model="gemini-2.5-flash", contents=prompt)
print("RESPONSE:", res.text)
