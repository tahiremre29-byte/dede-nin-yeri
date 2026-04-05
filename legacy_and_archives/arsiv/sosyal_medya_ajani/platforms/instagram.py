"""
tools/sosyal_medya_ajani/platforms/instagram.py
Instagram'a içerik yayınlar.

Öncelik sırası:
1. Meta Graph API (Business/Creator hesap + access_token varsa)
2. Playwright fallback (kişisel hesap — dikkatli kullan)
"""
from __future__ import annotations
import httpx
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from config import META_ACCESS_TOKEN, INSTAGRAM_USER_ID, USE_API


# ── Meta Graph API (Business hesap) ──────────────────────────────────────────

async def gorsel_paylasim_api(
    gorsel_url: str,
    caption: str,
) -> dict:
    """
    Meta Graph API ile Instagram'a görsel paylaşır.
    gorsel_url: Kamuya açık URL (CDN veya ngrok ile serve edilmiş yerel dosya)
    Döner: {basari: bool, post_id: str|None, hata: str|None}
    """
    if not USE_API:
        return {"basari": False, "hata": "META_ACCESS_TOKEN tanımlı değil — Playwright kullan"}

    async with httpx.AsyncClient(timeout=30.0) as client:
        # 1. Media container oluştur
        r1 = await client.post(
            f"https://graph.facebook.com/v19.0/{INSTAGRAM_USER_ID}/media",
            params={
                "image_url": gorsel_url,
                "caption": caption,
                "access_token": META_ACCESS_TOKEN,
            }
        )
        if not r1.is_success:
            return {"basari": False, "hata": r1.text}

        container_id = r1.json().get("id")

        # 2. Yayınla
        r2 = await client.post(
            f"https://graph.facebook.com/v19.0/{INSTAGRAM_USER_ID}/media_publish",
            params={
                "creation_id": container_id,
                "access_token": META_ACCESS_TOKEN,
            }
        )
        if r2.is_success:
            return {"basari": True, "post_id": r2.json().get("id"), "hata": None}
        else:
            return {"basari": False, "hata": r2.text}


async def video_paylasim_api(
    video_url: str,
    caption: str,
    thumb_url: str = "",
) -> dict:
    """Meta Reels API ile video paylaşır."""
    if not USE_API:
        return {"basari": False, "hata": "META_ACCESS_TOKEN tanımlı değil"}

    async with httpx.AsyncClient(timeout=60.0) as client:
        # 1. Reels container
        params = {
            "media_type": "REELS",
            "video_url": video_url,
            "caption": caption,
            "access_token": META_ACCESS_TOKEN,
        }
        if thumb_url:
            params["thumb_offset"] = "1000"

        r1 = await client.post(
            f"https://graph.facebook.com/v19.0/{INSTAGRAM_USER_ID}/media",
            params=params
        )
        if not r1.is_success:
            return {"basari": False, "hata": r1.text}

        container_id = r1.json().get("id")

        # 2. Yayınla
        r2 = await client.post(
            f"https://graph.facebook.com/v19.0/{INSTAGRAM_USER_ID}/media_publish",
            params={"creation_id": container_id, "access_token": META_ACCESS_TOKEN}
        )
        if r2.is_success:
            return {"basari": True, "post_id": r2.json().get("id"), "hata": None}
        else:
            return {"basari": False, "hata": r2.text}


# ── Simülasyon / Dry Run ──────────────────────────────────────────────────────

async def paylasim_simule(gorsel_yol: str, caption: str) -> dict:
    """
    Gerçek API olmadan paylaşımı simüle eder.
    Test amaçlı — caption ve görsel doğrulaması yapar.
    """
    p = Path(gorsel_yol)
    print(f"\n📸 Instagram Simülasyon")
    print(f"   Görsel: {p.name} ({'✅ mevcut' if p.exists() else '❌ yok'})")
    print(f"   Caption ({len(caption)} karakter):")
    print(f"   {caption[:200]}...")
    return {
        "basari": True,
        "post_id": "sim_12345",
        "hata": None,
        "mod": "simülasyon"
    }
