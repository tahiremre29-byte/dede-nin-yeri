"""
tools/sosyal_medya_ajani/agent.py
Sosyal Medya Yönetim Ajanı — Ana Koordinatör

Özellikler:
- Caption + hashtag üretimi (GPT-4o-mini)
- Instagram/Facebook paylaşımı (Meta API veya simülasyon)
- DD1 proje entegrasyonu
- Video üretimi (MoviePy — opsiyonel)

Kullanım:
  python agent.py
"""
from __future__ import annotations
import asyncio
import json
from pathlib import Path
from typing import Optional
from datetime import datetime

import sys
sys.path.insert(0, str(Path(__file__).parent))
from config import AKTIF_PLATFORMLAR, OUTPUT_DIR, META_API_AKTIF, ONAY_ZORUNLU, ICERIK_MODU
from content.metin_uretici import caption_uret

# ── Ana Ajan ──────────────────────────────────────────────────────────────────

class SosyalMedyaAjani:
    """
    DDSOUND sosyal medya yönetim ajanı.
    Yatay mimaride bağımsız çalışır, DD1 ile entegre olabilir.
    """

    def __init__(self):
        self.log_dosya = OUTPUT_DIR / "paylasim_log.json"
        self._log_yukle()

    def _log_yukle(self):
        if self.log_dosya.exists():
            self.log = json.loads(self.log_dosya.read_text(encoding="utf-8"))
        else:
            self.log = []

    def _log_kaydet(self, kayit: dict):
        self.log.append({**kayit, "zaman": datetime.now().isoformat()})
        self.log_dosya.write_text(
            json.dumps(self.log, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    async def icerik_hazirla(
        self,
        konu: str,
        urun: Optional[str] = None,
        ek_bilgi: Optional[str] = None,
        ton: str = "usta",
    ) -> dict:
        """Icerik uretir, onay icin sunar."""
        print(f"\n[ICERIK] Hazirlaniyor: {konu}")

        # Her platform icin caption uret
        icerikler = {}
        for platform in AKTIF_PLATFORMLAR:
            sonuc = await caption_uret(konu, platform, ton, urun, ek_bilgi)
            icerikler[platform] = sonuc
            print(f"[OK] {platform.upper()} caption hazir ({len(sonuc['tam_caption'])} karakter)")

        return icerikler

    async def paylasim_yap(
        self,
        gorsel_yol: str,
        caption: str,
        platform: str = "instagram",
    ) -> dict:
        """
        Icerik paylasiyor. ONAY_ZORUNLU=True ise bu fonksiyon
        sadece onay sonrasi cagirilir — direkt cagirma.
        """
        print(f"\n[PAYLASIM] {platform.upper()} baslatiyor...")

        if platform in ("instagram", "facebook"):
            from platforms.instagram import paylasim_simule, gorsel_paylasim_api
            if META_API_AKTIF:
                sonuc = await gorsel_paylasim_api(gorsel_url=gorsel_yol, caption=caption)
            else:
                print("[UYARI] META_ACCESS_TOKEN yok — simulasyon modunda")
                sonuc = await paylasim_simule(gorsel_yol, caption)

        elif platform == "tiktok":
            from platforms.tiktok import paylasim_simule
            sonuc = await paylasim_simule(gorsel_yol, caption)

        elif platform == "youtube":
            from platforms.youtube import community_post_simule
            baslik = caption[:60]
            sonuc = await community_post_simule(baslik, caption)

        else:
            sonuc = {"basari": False, "hata": f"Bilinmeyen platform: {platform}"}

        self._log_kaydet({"platform": platform, "konu": caption[:60], "sonuc": sonuc})
        return sonuc

    async def dd1_proje_paylasim(
        self,
        proje_adi: str,
        arac: str,
        subwoofer: str,
        hacim: float,
        gorsel_listesi: Optional[list[str]] = None,
        video_uret: bool = False,
    ) -> dict:
        """
        DD1 proje tamamlaninca otomatik icerik uretir.

        KIRMIZI CIZGI: Onay her zaman zorunludur.
        ICERIK_MODU=resim: Video uretimi atlanir (kalitenin artmasi bekleniyor).
        """
        # Onay zorunlulugu — ONAY_ZORUNLU=True ise bypasslanamaz
        if not ONAY_ZORUNLU:
            raise RuntimeError("ONAY_ZORUNLU False olamaz — config.py kontrol edin")

        konu = f"{arac} - {subwoofer} montaji tamamlandi"
        ek_bilgi = f"Net hacim: {hacim:.1f}L kabin | DDSOUND"

        # 1. Caption uret
        icerikler = await self.icerik_hazirla(konu, subwoofer, ek_bilgi)

        # 2. Video (sadece ICERIK_MODU=reels ise)
        video_yol = None
        if video_uret and ICERIK_MODU == "reels":
            try:
                from content.video_uretici import dd1_proje_video_olustur
                video_yol = await dd1_proje_video_olustur(
                    proje_adi, arac, subwoofer, hacim, gorsel_listesi
                )
                print(f"[VIDEO] Olusturuldu: {video_yol}")
            except ImportError:
                print("[UYARI] moviepy kurulu degil — pip install moviepy")
            except Exception as e:
                print(f"[UYARI] Video hatasi: {e}")
        elif ICERIK_MODU == "resim":
            print("[MOD] Resim modu aktif — video uretimi atlaniyor")

        # 3. ZORUNLU ONAY — KIRMIZI CIZGI
        print("\n" + "="*60)
        print("*** ONAYI BEKLENIYOR — PAYLASIM YAPILMADI ***")
        print(f"Konu: {konu}")
        print("\nInstagram caption:")
        print(icerikler.get('instagram', {}).get('tam_caption', '')[:300])
        print("\nFacebook caption:")
        print(icerikler.get('facebook', {}).get('tam_caption', '')[:200])
        if video_yol:
            print(f"Video: {video_yol}")
        print("="*60)
        print("Platform secimi: instagram(i) / facebook(f) / tiktok(t) / youtube(y) / hepsi(h) / iptal(x)")
        secim = input("Seciminiz: ").strip().lower()

        if secim == 'x' or not secim:
            print("[IPTAL] Paylasim iptal edildi.")
            return {"basari": False, "sebep": "kullanici iptal etti"}

        # Platform secimi
        if secim == 'h':
            secili_platformlar = AKTIF_PLATFORMLAR
        else:
            harfler = {'i': 'instagram', 'f': 'facebook', 't': 'tiktok', 'y': 'youtube'}
            secili_platformlar = [harfler[c] for c in secim if c in harfler]

        if not secili_platformlar:
            print("[IPTAL] Gecersiz secim.")
            return {"basari": False, "sebep": "gecersiz secim"}

        # 4. Paylas
        sonuclar = {}
        for platform in secili_platformlar:
            caption = icerikler.get(platform, {}).get("tam_caption", "")
            gorsel = (gorsel_listesi[0] if gorsel_listesi else str(OUTPUT_DIR / "placeholder.png"))
            sonuclar[platform] = await self.paylasim_yap(gorsel, caption, platform)
            durum = "BASARILI" if sonuclar[platform].get("basari") else "BASARISIZ"
            print(f"[{durum}] {platform.upper()}")

        return sonuclar


# ── CLI Test ──────────────────────────────────────────────────────────────────

async def _test():
    ajan = SosyalMedyaAjani()

    print("DDSOUND Sosyal Medya Ajani Testi")
    print("="*40)

    # Caption uretimi testi
    icerikler = await ajan.icerik_hazirla(
        konu="Fiat Doblo D2 - 12 inc subwoofer kabin yapimi",
        urun="Hertz SV 300 D",
        ek_bilgi="SQL odakli proje, 40 litre kapali kutu",
        ton="usta"
    )

    print("\n[INSTAGRAM] Caption:")
    print(icerikler.get("instagram", {}).get("tam_caption", "")[:500])

    print("\n[FACEBOOK] Caption:")
    print(icerikler.get("facebook", {}).get("tam_caption", "")[:300])


if __name__ == "__main__":
    asyncio.run(_test())
