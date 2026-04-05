"""
tools/sosyal_medya_ajani/platforms/tiktok.py
TikTok for Business API ile video paylaşımı.

NOT: TikTok Content Posting API (video) erişimi için TikTok for Business hesabı
     ve API approval süreci gereklidir.
     Şimdilik simülasyon modunda çalışır.
"""
from __future__ import annotations
import httpx
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from config import TIKTOK_ACCESS_TOKEN, TIKTOK_OPEN_ID, TIKTOK_API_AKTIF


async def video_paylasim_api(
    video_yol: str,
    caption: str,
) -> dict:
    """
    TikTok Content Posting API ile video paylaşır.
    Gereksinim: TikTok for Business hesap + API onayı
    """
    if not TIKTOK_API_AKTIF:
        return {"basari": False, "hata": "TIKTOK_ACCESS_TOKEN tanımlı değil — simülasyon kullan"}

    # TikTok Content Posting API v2
    async with httpx.AsyncClient(timeout=60.0) as client:
        # Adım 1: Upload init
        r1 = await client.post(
            "https://open.tiktokapis.com/v2/post/publish/inbox/video/init/",
            headers={
                "Authorization": f"Bearer {TIKTOK_ACCESS_TOKEN}",
                "Content-Type": "application/json; charset=UTF-8"
            },
            json={
                "post_info": {
                    "title": caption[:150],
                    "privacy_level": "PUBLIC_TO_EVERYONE",
                    "disable_duet": False,
                    "disable_comment": False,
                    "disable_stitch": False,
                },
                "source_info": {
                    "source": "FILE_UPLOAD",
                    "video_size": Path(video_yol).stat().st_size if Path(video_yol).exists() else 0,
                    "chunk_size": Path(video_yol).stat().st_size if Path(video_yol).exists() else 0,
                    "total_chunk_count": 1,
                }
            }
        )
        if not r1.is_success:
            return {"basari": False, "hata": r1.text}

        return {"basari": True, "publish_id": r1.json().get("data", {}).get("publish_id"), "hata": None}


async def paylasim_simule(video_yol: str, caption: str) -> dict:
    """TikTok paylaşımı simüle eder (API hazır olmadan test için)."""
    print(f"\n[TIKTOK Simulasyon]")
    print(f"   Video: {Path(video_yol).name if video_yol else 'belirtilmedi'}")
    print(f"   Caption ({len(caption)} karakter): {caption[:100]}...")
    return {"basari": True, "post_id": "tiktok_sim_001", "hata": None, "mod": "simulasyon"}
