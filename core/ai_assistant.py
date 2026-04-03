"""
DD1 Platform — Gemini AI Asistan
Kullanıcıdan gelen serbest metin isteğini anlayıp
kabin parametrelerine dönüştürür.
"""
import os
import json
import google.generativeai as genai

# API anahtarını environment variable'dan al
_API_KEY = os.environ.get("GEMINI_API_KEY", "")

_SYSTEM_PROMPT = """Sen DD1 adlı bir ses sistemi uzmanı yapay zeka asistanısın.
Kullanıcılar sana Türkçe veya İngilizce olarak kabin tasarımı isteği gönderir.

Senin görevin:
1. Kullanıcının isteğini analiz et.
2. Eksik bilgileri sor (woofer modeli, kullanım amacı, hacim tercihi vs.).
3. Yeterli bilgi varsa JSON formatında kabin parametrelerini döndür.

Ürün Doğrulama ve Kutu Tip Kuralları:
- "JBL 1000", "Pioneer 1400" gibi muğlak model adları verildiğinde ASLA tahmin yürütüp kesin konuşma. Net model numarasını (örn: CS1214, TS-W311D4) sorarak teyit al.
- Müşterinin söylediği ürünün tipini belirle: "Loaded enclosure (kendinden kutulu hazır ürün)" mü yoksa "Driver-only (sadece hoparlör)" mü?
- Eğere ürün loaded enclosure (kendinden kutulu hazır ürün) ise, sistem kesinlikle yeni litre/tuning istemeyecek veya uydurmayacaktır. Şu yanıtı benimse: "Bu ürün fabrika çıkışı kutulu sistemdir. Buna yeniden litre/tuning uydurmak doğru değil. Yeni kutu tasarlanacaksa sürücünün tek başına modeliyle ilerleyelim."
- Eğer ürün driver-only ise, sealed/ported kararı asla "piyasada böyle deniyor" mantığıyla verilmeyecek. Karar ancak Thiele/Small (T/S) parametreleri, üretici tavsiyesi ve iç hesaplamalar sonucunda verilecek.
- Eğer aynı litre değeri hem sealed hem ported için uygunsa/karışıyorsa, bu durumu müşteriye açıkla: "Portlu tasarımlarda net hacmin üzerine tuning (frekans ayarı) ve fiziksel port alanının da (port hacmi) eklenmesi gerektiğini" belirterek farkı vurgula.

ÇIKTI FORMATI (JSON döndüreceğin zaman):
{
  "action": "design",
  "woofer_model": "Hertz HV 300",   // ya da null
  "woofer_hole_mm": 282,             // ya da null  
  "target_volume_l": 45.0,
  "target_freq_hz": 45.0,
  "enclosure_type": "aero",          // sealed | ported | aero
  "material_thickness_mm": 10.0
}

Eğer bilgi eksikse veya model muğlaksa:
{
  "action": "ask",
  "question": "JBL 1000 watt dediğiniz ürünün tam model kodu nedir? CS1214 gibi bir model kodu olması gerekir."
}

KURAL: Emin olmadığın hiçbir değeri tahmin etme. Sor.
Sadece kabin mühendisliği konularında cevap ver.
"""


def get_ai_response(user_message: str, history: list[dict] | None = None) -> dict:
    """
    Kullanıcı mesajını AIAdapter üzerinden gönderir.
    history: [{"role": "user"|"model", "parts": ["mesaj"]}]
    Döndürür: {"action": "design"|"ask"|"info", "content": ..., "raw": "..."}
    """
    from core.ai_adapter import AIAdapter
    
    adapter = AIAdapter()
    
    # Geçmişi dümdüz metin olarak prompta ekle (basit prompt engineering)
    history_context = ""
    if history:
        for turn in history:
            role_label = turn.get("role", "user")
            parts = turn.get("parts", [])
            for p in parts:
                history_context += f"{role_label.upper()}: {p}\n"
    
    full_prompt = f"GECMIS SOHBET:\n{history_context}\n\nKULLANICI: {user_message}\n" if history else user_message
    
    resp = adapter.generate(
        prompt=full_prompt,
        system_prompt=_SYSTEM_PROMPT,
    )
    
    if not resp.ok:
        return {"action": "error", "content": f"AI error: {resp.finish_reason}", "raw": ""}

    raw = resp.text.strip()

    # JSON blok varsa parse et
    if "```json" in raw:
        try:
            json_str = raw.split("```json")[1].split("```")[0].strip()
            parsed = json.loads(json_str)
            return {"action": parsed.get("action", "info"), "content": parsed, "raw": raw}
        except Exception:
            pass

    # Düz JSON dene
    if raw.startswith("{"):
        try:
            parsed = json.loads(raw)
            return {"action": parsed.get("action", "info"), "content": parsed, "raw": raw}
        except Exception:
            pass

    # Serbest metin yanıtı
    return {"action": "info", "content": raw, "raw": raw}
