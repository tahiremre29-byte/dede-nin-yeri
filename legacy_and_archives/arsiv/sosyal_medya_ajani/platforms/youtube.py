"""
tools/sosyal_medya_ajani/platforms/youtube.py
YouTube Data API v3 ile içerik paylaşımı.

Kurulum:
  pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib
  Google Cloud Console → YouTube Data API v3 aktif et → OAuth credentials indir
"""
from __future__ import annotations
import httpx
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from config import YOUTUBE_API_KEY, YOUTUBE_CHANNEL_ID, YOUTUBE_API_AKTIF


async def community_post_simule(baslik: str, aciklama: str) -> dict:
    """
    YouTube Community Post simülasyonu.
    Gerçek Community Post için OAuth2 gerekli.
    """
    print(f"\n[YOUTUBE Simulasyon]")
    print(f"   Baslik: {baslik[:60]}")
    print(f"   Aciklama ({len(aciklama)} karakter): {aciklama[:100]}...")
    return {"basari": True, "post_id": "yt_sim_001", "hata": None, "mod": "simulasyon"}


async def video_bilgisi_al(video_id: str) -> dict:
    """YouTube video istatistikleri."""
    if not YOUTUBE_API_AKTIF:
        return {"hata": "YOUTUBE_API_KEY tanımlı değil"}

    async with httpx.AsyncClient(timeout=10.0) as client:
        r = await client.get(
            "https://www.googleapis.com/youtube/v3/videos",
            params={
                "part": "statistics",
                "id": video_id,
                "key": YOUTUBE_API_KEY,
            }
        )
        if r.is_success:
            items = r.json().get("items", [])
            if items:
                return items[0].get("statistics", {})
    return {}
