"""
tools/sosyal_medya_ajani/content/video_uretici.py
MoviePy + Pillow ile Reels/Short formatında video üretir.
Slaytlardan veya tek görselden otomatik video oluşturur.

Kurulum:
  pip install moviepy pillow
  FFmpeg binary: https://ffmpeg.org/ (PATH'e ekle)
"""
from __future__ import annotations
import os
import asyncio
from pathlib import Path
from typing import Optional
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from config import VIDEO_FPS, VIDEO_RESOLUTION, REELS_RESOLUTION, OUTPUT_DIR


def _pillow_mevcutmu() -> bool:
    try:
        import PIL
        return True
    except ImportError:
        return False


def _moviepy_mevcutmu() -> bool:
    try:
        import moviepy
        return True
    except ImportError:
        return False


def gorsel_slide_olustur(
    metin: str,
    alt_metin: str = "",
    bg_renk: tuple = (15, 23, 42),      # Koyu lacivert
    yazi_renk: tuple = (226, 232, 240),  # Açık gri
    vurgu_renk: tuple = (125, 211, 252), # Mavi
    boyut: tuple = REELS_RESOLUTION,
    cikti_yol: Optional[str] = None
) -> str:
    """
    Pillow ile tek slayt görsel oluşturur.
    Döner: Kayıt yolu (str)
    """
    if not _pillow_mevcutmu():
        raise ImportError("pip install pillow gerekli")

    from PIL import Image, ImageDraw, ImageFont

    img = Image.new("RGB", boyut, bg_renk)
    draw = ImageDraw.Draw(img)

    # Font (sistem fontları)
    try:
        font_buyuk = ImageFont.truetype("arial.ttf", 72)
        font_kucuk = ImageFont.truetype("arial.ttf", 42)
    except Exception:
        font_buyuk = ImageFont.load_default()
        font_kucuk = ImageFont.load_default()

    # Ana metin — ortala
    w, h = boyut
    draw.text((w // 2, h // 3), metin, font=font_buyuk, fill=vurgu_renk, anchor="mm")
    if alt_metin:
        draw.text((w // 2, h // 2), alt_metin, font=font_kucuk, fill=yazi_renk, anchor="mm")

    # Logo alanı alt kısım
    draw.text((w // 2, h - 100), "DDSOUND", font=font_kucuk, fill=vurgu_renk, anchor="mm")

    cikti = cikti_yol or str(OUTPUT_DIR / "slide.png")
    img.save(cikti)
    return cikti


def slaytlardan_video_olustur(
    slayt_listesi: list[dict],
    cikti_adi: str = "reels.mp4",
    her_slayt_sure: float = 3.0,
    format: str = "reels",    # reels (1080x1920) veya kare (1080x1080)
    muzik_yol: Optional[str] = None,
) -> str:
    """
    Slayt listesinden video üretir.
    
    slayt_listesi: [{"metin": "...", "alt_metin": "...", "gorsel_yol": "..." (opsiyonel)}]
    Döner: Video dosya yolu
    """
    if not _moviepy_mevcutmu():
        raise ImportError("pip install moviepy gerekli — ayrıca FFmpeg kurulu olmalı")

    from moviepy.editor import (
        ImageClip, concatenate_videoclips, AudioFileClip, CompositeAudioClip
    )

    boyut = REELS_RESOLUTION if format == "reels" else VIDEO_RESOLUTION
    klipler = []

    for slayt in slayt_listesi:
        # Görsel yok → Pillow ile oluştur
        if "gorsel_yol" not in slayt or not Path(slayt["gorsel_yol"]).exists():
            tmp_yol = str(OUTPUT_DIR / f"slayt_{len(klipler)}.png")
            gorsel_slide_olustur(
                metin=slayt.get("metin", ""),
                alt_metin=slayt.get("alt_metin", ""),
                boyut=boyut,
                cikti_yol=tmp_yol
            )
            gorsel_yol = tmp_yol
        else:
            gorsel_yol = slayt["gorsel_yol"]

        klip = ImageClip(gorsel_yol, duration=her_slayt_sure)
        klipler.append(klip)

    # Birleştir
    final = concatenate_videoclips(klipler, method="compose")

    # Müzik ekle (opsiyonel)
    if muzik_yol and Path(muzik_yol).exists():
        muzik = AudioFileClip(muzik_yol).subclip(0, final.duration)
        final = final.set_audio(muzik)

    cikti_yol = str(OUTPUT_DIR / cikti_adi)
    final.write_videofile(
        cikti_yol,
        fps=VIDEO_FPS,
        codec="libx264",
        audio_codec="aac",
        verbose=False,
        logger=None
    )
    return cikti_yol


async def dd1_proje_video_olustur(
    proje_adi: str,
    arac: str,
    subwoofer: str,
    hacim: float,
    gorsel_listesi: Optional[list[str]] = None
) -> str:
    """
    DD1 proje sonucundan otomatik Reels videosu üretir.
    
    Args:
        proje_adi: Projenin adı
        arac: Araç modeli
        subwoofer: Subwoofer modeli
        hacim: Net hacim (litre)
        gorsel_listesi: Montaj fotoğrafları (varsa)
    """
    slaytlar = [
        {"metin": proje_adi.upper(), "alt_metin": f"{arac} | DDSOUND"},
        {"metin": subwoofer, "alt_metin": f"Net Hacim: {hacim:.1f}L"},
        {"metin": "TAMAMLANDI", "alt_metin": "Kaliteli ses, kaliteli işçilik"},
    ]

    # Fotoğraf varsa ekle
    if gorsel_listesi:
        for g in gorsel_listesi[:3]:  # Max 3 fotoğraf
            slaytlar.insert(2, {"metin": "", "gorsel_yol": g})

    cikti = await asyncio.to_thread(
        slaytlardan_video_olustur,
        slaytlar,
        f"dd1_{proje_adi.replace(' ', '_')}.mp4",
        format="reels"
    )
    return cikti
