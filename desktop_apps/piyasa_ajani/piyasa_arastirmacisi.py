"""
Piyasa Araştırmacısı — DD1 Platform
======================================
Görev: Türkiye araba ses piyasasını araştırır:
  - Saha dili / terminoloji
  - Popüler markalar & ürünler
  - Kullanıcı soruları & şikayetleri
  - Rakip analizi

Çalıştır:
    python piyasa_arastirmacisi.py
    python piyasa_arastirmacisi.py --konu "subwoofer markalar"

Sonuçlar: arastirma/ klasörüne kaydedilir.
"""

import os
import sys
import json
import time
import datetime
import argparse
import urllib.request
import urllib.parse
from pathlib import Path

# Windows terminali icin UTF-8
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

# Araştırma konuları ve arama sorguları
ARAMA_PLANI = {
    "saha_dili": [
        "araba ses sistemi kabin türkiye forum",
        "subwoofer kurulum usta dili türkiye",
        "car audio türkiye facebook grup kurulum",
        "woofer amplifikatör bağlantı türkiye",
    ],
    "markalar": [
        "türkiye en çok satan subwoofer markası 2024",
        "car audio amplifikatör türkiye fiyat 2024",
        "türkiye araba hoparlör marka karşılaştırma",
        "subwoofer fiyat türkiye trendyol n11",
    ],
    "musteri_sorulari": [
        "subwoofer kabin nasıl yapılır türkiye",
        "araba ses sistemi tavsiye türkiye forum",
        "ported kabin sealed kabin fark türkiye",
        "bass kabin ölçü türkiye soru",
    ],
    "rakip_analiz": [
        "araba ses sistemi hesaplama sitesi türkiye",
        "kabin hesaplama uygulaması türkiye",
        "car audio design app türkiye",
        "subwoofer box calculator türkçe",
    ],
}

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


def groq_analiz(sistem: str, mesaj: str) -> str:
    """Groq Llama ile analiz yap."""
    api_key = get_groq_key()
    if not api_key:
        return "[Groq key bulunamadı]"

    payload = json.dumps({
        "model": GROQ_MODEL,
        "messages": [
            {"role": "system", "content": sistem},
            {"role": "user",   "content": mesaj},
        ],
        "temperature": 0.4,
        "max_tokens": 2048,
    }).encode("utf-8")

    req = urllib.request.Request(
        GROQ_API_URL,
        data=payload,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (compatible; DDSOUND-Piyasa/1.0)",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data["choices"][0]["message"]["content"]
    except Exception as e:
        return f"[Groq hata: {e}]"


# ── DuckDuckGo Arama ──────────────────────────────────────────────────────────

def ddg_ara(sorgu: str, max_sonuc: int = 5) -> list[dict]:
    """DuckDuckGo Instant Answer API ile arama yap."""
    url = "https://api.duckduckgo.com/?q=" + urllib.parse.quote(sorgu) + "&format=json&no_redirect=1&no_html=1"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        sonuclar = []

        # Abstract
        if data.get("Abstract"):
            sonuclar.append({
                "baslik": data.get("Heading", sorgu),
                "ozet": data["Abstract"][:500],
                "url": data.get("AbstractURL", ""),
            })

        # Related Topics
        for item in data.get("RelatedTopics", [])[:max_sonuc]:
            if isinstance(item, dict) and item.get("Text"):
                sonuclar.append({
                    "baslik": item.get("Text", "")[:100],
                    "ozet": item.get("Text", "")[:300],
                    "url": item.get("FirstURL", ""),
                })

        return sonuclar[:max_sonuc]
    except Exception as e:
        print(f"  [Arama hata: {e}]")
        return []


def web_ara_genis(sorgu: str) -> str:
    """HTML arama sayfasından metin çek (backup)."""
    url = "https://html.duckduckgo.com/html/?q=" + urllib.parse.quote(sorgu)
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        })
        with urllib.request.urlopen(req, timeout=15) as resp:
            html = resp.read().decode("utf-8", errors="replace")

        # Basit metin çıkarma
        import re
        # result snippets
        snippets = re.findall(r'class="result__snippet"[^>]*>(.*?)</a>', html, re.DOTALL)
        titles   = re.findall(r'class="result__a"[^>]*>(.*?)</a>', html, re.DOTALL)

        # HTML etiketlerini temizle
        def strip_html(s):
            return re.sub(r'<[^>]+>', '', s).strip()

        combined = []
        for i, (t, s) in enumerate(zip(titles[:8], snippets[:8])):
            combined.append(f"{i+1}. {strip_html(t)}: {strip_html(s)}")

        return "\n".join(combined) if combined else "(sonuç bulunamadı)"
    except Exception as e:
        return f"(arama hatası: {e})"


# ── Araştırma Görevleri ───────────────────────────────────────────────────────

SISTEM_PROMPT = """
Sen DD1 araba ses platformu için piyasa araştırmacısısın.
Görevin: Türkiye araba ses piyasasını analiz et.
Çıktı formatı: JSON formatında, Türkçe, kısa ve öz.
Alan: subwoofer, kabin (speaker enclosure), amplifikatör, car audio Türkiye.
"""


def arastir_konu(konu: str, sorgular: list[str]) -> dict:
    """Bir konuyu araştır ve analiz et."""
    print(f"\n{'='*55}")
    print(f"  Konu: {konu.upper()}")
    print(f"{'='*55}")

    ham_veri = []
    for sorgu in sorgular:
        print(f"  Arıyor: {sorgu[:60]}...")
        metin = web_ara_genis(sorgu)
        if metin and len(metin) > 50:
            ham_veri.append(f"Sorgu: {sorgu}\n{metin}")
        time.sleep(1.5)  # Rate limit

    if not ham_veri:
        print("  [Veri bulunamadı]")
        return {"konu": konu, "sonuclar": [], "ozet": "Veri bulunamadı"}

    print(f"  Groq analiz yapıyor...")
    birlesik = "\n\n---\n".join(ham_veri[:4])

    analiz_promptu = f"""
Aşağıdaki ham arama sonuçlarını analiz et. Konu: {konu}

{birlesik[:3000]}

Şunları çıkar:
1. Öne çıkan markalar/ürünler (liste)
2. Sık kullanılan terimler/saha dili
3. Kullanıcıların en çok istediği/sorduğu şeyler
4. Rakipler / alternatif çözümler (varsa)
5. Genel piyasa özeti (2-3 cümle)

JSON formatında ver: {{"markalar": [], "terminoloji": [], "kullanici_istekleri": [], "rakipler": [], "ozet": ""}}
"""
    sonuc_str = groq_analiz(SISTEM_PROMPT, analiz_promptu)

    # JSON parse dene
    try:
        import re
        json_match = re.search(r'\{.*\}', sonuc_str, re.DOTALL)
        if json_match:
            analiz = json.loads(json_match.group())
        else:
            analiz = {"ham": sonuc_str}
    except Exception:
        analiz = {"ham": sonuc_str}

    analiz["konu"] = konu
    print(f"  [OK] {konu} analizi tamamlandi")
    return analiz


def rapor_yaz(sonuclar: dict, konu_filtre: str = None) -> Path:
    """Sonuçları dosyaya yaz."""
    tarih = datetime.datetime.now().strftime("%Y%m%d_%H%M")

    # JSON kaydet
    json_path = ARASTIRMA / f"piyasa_{tarih}.json"
    json_path.write_text(
        json.dumps(sonuclar, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

    # Markdown rapor
    md_path = ARASTIRMA / f"rapor_{tarih}.md"
    md = f"# Piyasa Araştırması Raporu\n"
    md += f"**Tarih:** {datetime.datetime.now().strftime('%d.%m.%Y %H:%M')}\n\n"

    for konu, veri in sonuclar.items():
        if not isinstance(veri, dict):
            continue
        md += f"## {konu.upper().replace('_', ' ')}\n\n"
        if veri.get("ozet"):
            md += f"**Özet:** {veri['ozet']}\n\n"
        if veri.get("markalar"):
            md += f"**Markalar:** {', '.join(str(m) for m in veri['markalar'][:10])}\n\n"
        if veri.get("terminoloji"):
            md += f"**Saha dili:** {', '.join(str(t) for t in veri['terminoloji'][:15])}\n\n"
        if veri.get("kullanici_istekleri"):
            md += "**Kullanıcı istekleri:**\n"
            for ist in veri["kullanici_istekleri"][:5]:
                md += f"- {ist}\n"
            md += "\n"
        if veri.get("rakipler"):
            md += f"**Rakipler:** {', '.join(str(r) for r in veri['rakipler'][:8])}\n\n"
        md += "---\n\n"

    md_path.write_text(md, encoding="utf-8")

    print(f"\n[OK] Rapor kaydedildi:")
    print(f"   JSON : {json_path}")
    print(f"   Rapor: {md_path}")

    return md_path


# ── Saha Dili Sözlüğü Güncelle ────────────────────────────────────────────────

def saha_dili_guncelle(yeni_terimler: list[str]):
    """Toplanan terimleri saha_dili.json'a ekle."""
    sozluk_path = ARASTIRMA / "saha_dili.json"
    if sozluk_path.exists():
        mevcut = json.loads(sozluk_path.read_text(encoding="utf-8"))
    else:
        mevcut = {"terimler": [], "son_guncelleme": ""}

    mevcut_set = set(mevcut.get("terimler", []))
    mevcut_set.update(yeni_terimler)
    mevcut["terimler"] = sorted(mevcut_set)
    mevcut["son_guncelleme"] = datetime.datetime.now().isoformat()

    sozluk_path.write_text(
        json.dumps(mevcut, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )
    print(f"  [*] Saha dili sozlugu guncellendi: {len(mevcut['terimler'])} terim")


# ── Ana ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Piyasa Araştırmacısı — DD1")
    parser.add_argument("--konu", help="Sadece bu konuyu araştır (saha_dili/markalar/musteri_sorulari/rakip_analiz)")
    parser.add_argument("--hizli", action="store_true", help="Her konuda 2 sorgu (hızlı mod)")
    args = parser.parse_args()

    print("=" * 55)
    print("  DDSOUND — Piyasa Araştırmacısı")
    print("  Türkiye Araba Ses Piyasası Analizi")
    print("=" * 55)

    api_key = get_groq_key()
    if not api_key:
        print("\n[!] GROQ_API_KEY bulunamadi!")
        print("   .env dosyasina GROQ_API_KEY=gsk_... ekle")
        sys.exit(1)
    print(f"\n[OK] Groq API hazir (key: ...{api_key[-6:]})")


    # Araştırılacak konuları seç
    if args.konu and args.konu in ARAMA_PLANI:
        plan = {args.konu: ARAMA_PLANI[args.konu]}
    else:
        plan = ARAMA_PLANI

    # Hızlı mod: her konuda 2 sorgu
    if args.hizli:
        plan = {k: v[:2] for k, v in plan.items()}

    sonuclar = {}
    for konu, sorgular in plan.items():
        sonuclar[konu] = arastir_konu(konu, sorgular)

        # Saha dili terimlerini sözlüğe ekle
        terminoloji = sonuclar[konu].get("terminoloji", [])
        if terminoloji:
            saha_dili_guncelle([str(t) for t in terminoloji])

        time.sleep(2)

    rapor_path = rapor_yaz(sonuclar)

    print("\n" + "=" * 55)
    print("  ARAŞTIRMA TAMAMLANDI")
    print(f"  {len(sonuclar)} konu analiz edildi")
    print(f"  Rapor: {rapor_path.name}")
    print("=" * 55)


if __name__ == "__main__":
    main()
