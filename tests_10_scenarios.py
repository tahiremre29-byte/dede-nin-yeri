import requests
import json
import time

TARGETS = [
    ("JBL bas var kabin istiyorum", "Tamam, bu işi halledebiliriz. JBL’in tam modelini yaz, sana uygun kabini çıkaralım."),
    ("Bas var kabin lazım", "Tamam, buna uygun kabin çıkarabiliriz. Basın marka ve tam modelini yaz, doğru yerden başlayalım."),
    ("JBL 1000 bas var", "Tamam, marka belli ama model daha net değil. Üstündeki tam kodu yaz, sana uygun kabini oradan çıkaralım."),
    ("Modeli bilmiyorum JBL 12", "Tamam, yine yürürüz. Üstündeki etikette yazan tam kodu söyleyebilirsen sağlıklı ilerleriz; kodu göremiyorsan üstündeki yazıları aynen yaz."),
    ("JBL CS1214 var", "Güzel, cihaz belli oldu. Şimdi aracına uygun litreli kabini kuralım. Aracı söyle, oradan devam edelim."),
    ("JBL CS1214 Corolla", "Tamam, cihaz ve araç belli oldu. Bu cihaza göre elimizde mantıklı kabin yolları var. Şimdi bagajda ne kadar yer ayırabileceğini söyle, sana uygun yapıyı netleştirelim."),
    ("Aracıma sistem yapmak istiyorum", "Tamam, doğru yerden girelim. Araç ne, bütçe ne civarda ve öncelik temiz dinlemek mi yoksa daha yüksek ses mi?"),
    ("Basım iyi vurmuyor", "Tamam, önce sorunun nerede olduğunu ayıralım. Basın modeli ne, mevcut kabin var mı, araç ne?"),
    ("Portlu mu kapalı mı yapsam", "Tamam, bunu cihaz ve araca göre netleştirmek lazım. Basın tam modeliyle aracı yaz, sana boş yorum değil net yol söyleyelim."),
    ("Bagaj küçük ama ses istiyorum", "Tamam, burada yer ve cihaz birlikte önemli. Aracı ve basın modelini yaz, bagajı öldürmeden nasıl yürüyeceğini netleştirelim.")
]

API_URL = "http://127.0.0.1:9000/chat/"

results = []
for i, (msg, expected) in enumerate(TARGETS):
    # Unique session ID to avoid context mixing
    sid = f"test_batch_10_{i}_{int(time.time())}"
    try:
        resp = requests.post(API_URL, json={"message": msg, "session_id": sid})
        data = resp.json()
        actual = data.get("reply", "").strip()
        results.append({
            "scenario_index": i+1,
            "message": msg,
            "expected": expected,
            "actual": actual
        })
    except Exception as e:
        results.append({
            "scenario_index": i+1,
            "message": msg,
            "expected": expected,
            "actual": f"ERROR: {str(e)}"
        })

print(json.dumps(results, indent=2, ensure_ascii=False))
