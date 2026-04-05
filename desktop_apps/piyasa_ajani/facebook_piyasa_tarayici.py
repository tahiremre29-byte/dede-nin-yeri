"""
facebook_piyasa_tarayici.py
============================
DD1 Piyasa Ajanı — Facebook Grup Tarayıcı

Görev:
  Belirtilen Facebook gruplarına mevcut Chrome profilini kullanarak gir,
  sayfayı scroll yaparak post içeriklerini topla,
  Groq ile analiz et, arastirma/ klasörüne kaydet.

Çalıştır:
  python facebook_piyasa_tarayici.py
  python facebook_piyasa_tarayici.py --url https://www.facebook.com/groups/1336657139829613

NOT: Chrome kapalı olmalı! Tarayıcı açıkken profil kilitlenir.
"""

import os
import sys
import json
import time
import re
import datetime
import argparse
import urllib.request
import urllib.parse
from pathlib import Path

# Windows terminali UTF-8
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# ── Yapılandırma ──────────────────────────────────────────────────────────────

BASE       = Path(__file__).parent
ARASTIRMA  = BASE / "arastirma"
ARASTIRMA.mkdir(exist_ok=True)

GROQ_MODEL   = "llama-3.3-70b-versatile"
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"

# Chrome kullanıcı profili yolu (Windows default)
CHROME_PROFILE = os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\User Data")
CHROME_BINPATH = r"C:\Program Files\Google\Chrome\Application\chrome.exe"

# Taranacak Facebook grupları
FACEBOOK_GRUPLARI = [
    {
        "ad": "SPL Team Turkey",
        "url": "https://www.facebook.com/groups/1336657139829613",
        "odak": "SPL yarışma, yüksek güç sistemler, Türkiye ceza tartışması"
    },
    {
        "ad": "Big Bang Sounds",
        "url": "https://www.facebook.com/groups/1572668592895430",
        "odak": "SQ, head unit, DSP, montajcı ve hobici karışımı"
    },
]

# ── Groq API ──────────────────────────────────────────────────────────────────

def get_groq_key() -> str:
    env_file = BASE / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            if line.startswith("GROQ_API_KEY="):
                k = line[len("GROQ_API_KEY="):].strip()
                if k:
                    return k
    return os.environ.get("GROQ_API_KEY", "").strip()


def groq_analiz(icerik: str) -> str:
    api_key = get_groq_key()
    if not api_key:
        return "[Groq key bulunamadı]"

    sistem = """
Sen DD1 araba ses platformu için piyasa araştırmacısısın.
Türkiye car audio topluluk verilerini analiz ediyorsun.
Sonucu MUTLAKA JSON olarak ver.
"""
    prompt = f"""
Aşağıdaki Facebook grup post içeriklerini analiz et:

{icerik[:4000]}

Şunları çıkar:
1. Bahsedilen markalar (subwoofer, amfi, head unit, kablo vb.)
2. Saha dili / sokak terimleri (bagaj açtı, tok bas vb.)
3. Teknik sorular / şikayetler
4. Fiyat bilgileri (varsa)
5. Güncel tartışma konuları (ceza, 95 dB, vb.)
6. Genel özet (3 cümle)

JSON formatında ver:
{{
  "markalar": [],
  "saha_dili": [],
  "teknik_sorular": [],
  "fiyatlar": [],
  "guncel_konular": [],
  "ozet": ""
}}
"""
    payload = json.dumps({
        "model": GROQ_MODEL,
        "messages": [
            {"role": "system", "content": sistem},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.3,
        "max_tokens": 2048,
    }).encode("utf-8")

    req = urllib.request.Request(
        GROQ_API_URL,
        data=payload,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=45) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data["choices"][0]["message"]["content"]
    except Exception as e:
        return f"[Groq hata: {e}]"


# ── Selenium Facebook Tarayıcı ────────────────────────────────────────────────

def chrome_ac(headless: bool = False):
    """Mevcut Chrome profiliyle tarayıcı aç."""
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.chrome.service import Service
    from webdriver_manager.chrome import ChromeDriverManager

    opts = Options()
    opts.add_argument(f"--user-data-dir={CHROME_PROFILE}")
    opts.add_argument("--profile-directory=Default")
    opts.add_argument("--no-first-run")
    opts.add_argument("--no-default-browser-check")
    opts.add_argument("--disable-notifications")
    opts.add_argument("--disable-popup-blocking")
    opts.add_experimental_option("excludeSwitches", ["enable-automation"])
    opts.add_experimental_option("useAutomationExtension", False)

    if headless:
        opts.add_argument("--headless=new")

    if os.path.exists(CHROME_BINPATH):
        opts.binary_location = CHROME_BINPATH

    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=opts)
    driver.implicitly_wait(8)
    return driver


def facebook_grup_tara(driver, grup: dict, scroll_sayisi: int = 10) -> str:
    """
    Bir Facebook grubuna git, scroll yap, post metinlerini topla.
    Döner: Toplanan ham metin
    """
    from selenium.webdriver.common.by import By
    from selenium.webdriver.common.keys import Keys
    import time

    print(f"\n  → {grup['ad']} grubuna gidiliyor...")
    driver.get(grup["url"])
    time.sleep(5)  # Sayfa yüklensin

    # Giriş yapılmış mı kontrol
    if "login" in driver.current_url.lower() or "checkpoint" in driver.current_url.lower():
        print("  [!] Facebook girişi gerekiyor — Chrome profili yüklenmedi")
        return ""

    print(f"  [OK] Sayfa yüklendi: {driver.title[:60]}")

    # Scroll yaparak içerik topla
    toplanan = []
    son_yukseklik = 0

    for i in range(scroll_sayisi):
        # Sayfadaki post metinlerini çek
        try:
            from selenium.webdriver.common.by import By
            # Facebook post metin seçicileri
            post_elements = driver.find_elements(By.CSS_SELECTOR, 
                "div[data-ad-preview='message'], div[dir='auto']")
            
            for el in post_elements:
                metin = el.text.strip()
                if metin and len(metin) > 20 and metin not in toplanan:
                    toplanan.append(metin)
        except Exception as e:
            print(f"  [!] Element okuma: {e}")

        # Sayfayı aşağı kaydır
        driver.execute_script("window.scrollBy(0, 1200);")
        time.sleep(2.5)

        # Sayfa sonu kontrolü
        yeni_yukseklik = driver.execute_script("return document.body.scrollHeight")
        print(f"  Scroll {i+1}/{scroll_sayisi} — {len(toplanan)} metin toplandi")
        
        if yeni_yukseklik == son_yukseklik and i > 3:
            print("  [OK] Sayfa sonu — scroll duruyor")
            break
        son_yukseklik = yeni_yukseklik

    return "\n\n---\n".join(toplanan[:80])  # Max 80 metin parçası


# ── Ana Akış ─────────────────────────────────────────────────────────────────

def tara_ve_kaydet(grup_listesi: list, scroll_sayisi: int = 10):
    """Tüm grupları tara ve sonuçları kaydet."""
    
    print("\n" + "="*55)
    print("  DDSOUND — Facebook Piyasa Tarayıcısı")
    print("  Türkiye Car Audio Topluluk Analizi")
    print("="*55)

    api_key = get_groq_key()
    if not api_key:
        print("\n[!] GROQ_API_KEY bulunamadı! .env dosyasına ekle.")
        sys.exit(1)

    print("\n[!] ÖNEMLİ: Chrome tamamen kapalı olmalı!")
    print("    5 saniye içinde devam ediyor...")
    time.sleep(5)

    driver = None
    tum_sonuclar = []

    try:
        print("\n  Chrome başlatılıyor (mevcut profil)...")
        driver = chrome_ac(headless=False)
        print("  [OK] Chrome hazır")

        for grup in grup_listesi:
            print(f"\n{'─'*50}")
            print(f"  Grup: {grup['ad']}")
            print(f"  Odak: {grup['odak']}")
            print(f"{'─'*50}")

            # Sayfayı tara
            ham_metin = facebook_grup_tara(driver, grup, scroll_sayisi)

            if not ham_metin:
                print(f"  [!] {grup['ad']} için metin toplanamadı")
                continue

            print(f"\n  Groq analiz yapıyor ({len(ham_metin)} karakter)...")
            analiz_str = groq_analiz(ham_metin)

            # JSON parse
            try:
                json_match = re.search(r'\{.*\}', analiz_str, re.DOTALL)
                if json_match:
                    analiz = json.loads(json_match.group())
                else:
                    analiz = {"ham_analiz": analiz_str}
            except Exception:
                analiz = {"ham_analiz": analiz_str}

            sonuc = {
                "grup_adi": grup["ad"],
                "grup_url": grup["url"],
                "odak": grup["odak"],
                "tarih": datetime.datetime.now().isoformat(),
                "toplanan_metin_sayisi": ham_metin.count("---") + 1,
                "analiz": analiz,
                "ham_metin_snippet": ham_metin[:500],  # İlk 500 karakter
            }
            tum_sonuclar.append(sonuc)
            print(f"  [OK] {grup['ad']} analizi tamamlandı")
            time.sleep(3)

    finally:
        if driver:
            driver.quit()
            print("\n  [OK] Chrome kapatıldı")

    # Kaydet
    if tum_sonuclar:
        tarih = datetime.datetime.now().strftime("%Y%m%d_%H%M")
        kayit_yolu = ARASTIRMA / f"facebook_tarama_{tarih}.json"
        kayit_yolu.write_text(
            json.dumps(tum_sonuclar, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )
        print(f"\n[OK] Sonuç kaydedildi: {kayit_yolu}")

        # Özet yazdır
        print("\n" + "="*55)
        print("  TARAMA TAMAMLANDI")
        for s in tum_sonuclar:
            print(f"\n  {s['grup_adi']}:")
            a = s.get("analiz", {})
            if isinstance(a, dict):
                ozet = a.get("ozet", "")
                if ozet:
                    print(f"    Özet: {ozet[:120]}")
                markalar = a.get("markalar", [])
                if markalar:
                    print(f"    Markalar: {', '.join(str(m) for m in markalar[:6])}")
        print("="*55)
    else:
        print("\n[!] Hiç veri toplanamadı")

    return tum_sonuclar


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="DD1 Facebook Piyasa Tarayıcısı")
    parser.add_argument("--url", help="Sadece bu URL'yi tara")
    parser.add_argument("--scroll", type=int, default=10, help="Scroll sayısı (varsayılan: 10)")
    args = parser.parse_args()

    if args.url:
        gruplar = [{"ad": "Özel Grup", "url": args.url, "odak": "Genel tarama"}]
    else:
        gruplar = FACEBOOK_GRUPLARI

    tara_ve_kaydet(gruplar, scroll_sayisi=args.scroll)


if __name__ == "__main__":
    main()
