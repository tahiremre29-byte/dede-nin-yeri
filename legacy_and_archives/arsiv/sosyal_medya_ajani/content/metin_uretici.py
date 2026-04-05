"""
tools/sosyal_medya_ajani/content/metin_uretici.py
GPT-4o-mini ile caption, hashtag ve içerik metni üretir.
"""
import httpx
import json
from typing import Optional
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from config import OPENAI_KEY, DEFAULT_HASHTAGS, MAX_CAPTION_CHARS


async def caption_uret(
    konu: str,
    platform: str = "instagram",
    ton: str = "usta",
    urun: Optional[str] = None,
    ek_bilgi: Optional[str] = None
) -> dict:
    """
    Sosyal medya için caption üretir.
    
    Args:
        konu: İçerik konusu (örn: "Doblo'ya 12 inç subwoofer montajı")
        platform: instagram | facebook | youtube
        ton: usta | samimi | teknik | eglenceli
        urun: Ürün adı (varsa)
        ek_bilgi: Ekstra bağlam
    
    Returns:
        {caption, hashtags, cta, baslik}
    """
    ton_map = {
        "usta": "Tecrübeli araba ses ustası — teknik ama anlaşılır, samimi",
        "samimi": "Arkadaşça, enerjik, günlük dil",
        "teknik": "Teknik detay odaklı, spesifikasyonlar önemli",
        "eglenceli": "Eğlenceli, mizahi, emoji kullanır"
    }

    platform_talimat = {
        "instagram": "Instagram için max 2200 karakter, 3-5 paragraf, güçlü ilk cümle",
        "facebook": "Facebook için daha uzun açıklama olabilir, link paylaşım dostu",
        "youtube": "YouTube açıklaması — SEO odaklı, zaman damgaları için alan bırak"
    }

    prompt = f"""Sen bir araba ses uzmanısın. DDSOUND markası için sosyal medya içeriği yazıyorsun.

Konu: {konu}
Platform: {platform}
Ton: {ton_map.get(ton, ton_map['usta'])}
{f'Ürün: {urun}' if urun else ''}
{f'Ek bilgi: {ek_bilgi}' if ek_bilgi else ''}

{platform_talimat.get(platform, '')}

JSON formatında döndür:
{{
  "baslik": "kısa başlık (max 60 karakter, YouTube için SEO)",
  "caption": "ana metin (hashtag HARİÇ)",
  "cta": "harekete geçirici çağrı (1 cümle)",
  "hashtag_onerisi": ["#tag1", "#tag2", "#tag3"] (5-10 adet, Türkçe+İngilizce)
}}

Yasak: "şimdilik", "demo", "placeholder". Türkçe yaz."""

    async with httpx.AsyncClient(timeout=20.0) as client:
        resp = await client.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {OPENAI_KEY}"},
            json={
                "model": "gpt-4o-mini",
                "messages": [{"role": "user", "content": prompt}],
                "response_format": {"type": "json_object"},
                "max_tokens": 600,
                "temperature": 0.8,
            }
        )
        resp.raise_for_status()
        sonuc = json.loads(resp.json()["choices"][0]["message"]["content"])

    # Hashtag birleştir
    tum_hashtagler = list(set(
        sonuc.get("hashtag_onerisi", []) + DEFAULT_HASHTAGS[:5]
    ))[:15]

    # Caption + CTA + hashtag birleştir
    tam_caption = f"{sonuc.get('caption', '')}\n\n{sonuc.get('cta', '')}\n\n{' '.join(tum_hashtagler)}"
    tam_caption = tam_caption[:MAX_CAPTION_CHARS]

    return {
        "baslik": sonuc.get("baslik", konu[:60]),
        "caption": sonuc.get("caption", ""),
        "cta": sonuc.get("cta", ""),
        "hashtags": tum_hashtagler,
        "tam_caption": tam_caption,
        "platform": platform,
    }


def hashtag_sec(
    kategori: str = "genel",
    adet: int = 10
) -> list[str]:
    """Kategoriye göre hazır hashtag seti döndür."""
    hashtagler = {
        "genel": DEFAULT_HASHTAGS,
        "sql": ["#sql", "#soundqualityloud", "#basshead", "#sublow", "#loudcar"],
        "montaj": ["#montaj", "#caraudio", "#install", "#diy", "#workshop"],
        "subwoofer": ["#subwoofer", "#bass", "#woofer", "#deepbass", "#12inch"],
        "amplifier": ["#amplifier", "#amp", "#monoblock", "#4channel", "#power"],
    }
    secilen = hashtagler.get(kategori, DEFAULT_HASHTAGS)
    return secilen[:adet]
