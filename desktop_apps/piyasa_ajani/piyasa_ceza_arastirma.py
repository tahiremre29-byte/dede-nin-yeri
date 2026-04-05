"""
Piyasa Arayistirmaci — Ses Cezalari Ozel Arastirma
Calistir: python piyasa_ceza_arastirma.py
"""
import os, sys, json, time, datetime, urllib.request, urllib.parse
from pathlib import Path

if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

BASE      = Path(__file__).parent
ARASTIRMA = BASE / "arastirma"
ARASTIRMA.mkdir(exist_ok=True)

GROQ_MODEL   = "llama-3.3-70b-versatile"
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"

SORGULAR = [
    # Ses sistemi cezalari
    "turkiye araba ses sistemi ceza 2024 2025",
    "turkiye gurultu kirliligi arac ses ceza karakol",
    "trafik cezasi muzik ses yuksekligi turkiye",
    "modifiye ses sistemi ceza turkiye kanun",
    # Yetkili aciklamalar
    "emniyet mudurluğu gurultu ceza araba turkiye",
    "belediye gurultu ceza ses sistemi aciklama",
    "trafik polisi araba muzik ceza turkiye",
    # Piyasa etkisi
    "ses sistemi ceza piyasa etki turkiye esnaf",
    "car audio ceza yasak turkiye 2024",
    "subwoofer ceza turkiye yasal",
]

def get_groq_key():
    env_file = BASE / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            if line.startswith("GROQ_API_KEY="):
                k = line[len("GROQ_API_KEY="):].strip()
                if k:
                    return k
    return os.environ.get("GROQ_API_KEY", "").strip()

def groq_analiz(sistem, mesaj):
    api_key = get_groq_key()
    payload = json.dumps({
        "model": GROQ_MODEL,
        "messages": [
            {"role": "system", "content": sistem},
            {"role": "user",   "content": mesaj},
        ],
        "temperature": 0.3,
        "max_tokens": 2048,
    }).encode("utf-8")
    req = urllib.request.Request(
        GROQ_API_URL, data=payload,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (compatible; DDSOUND-Piyasa/1.0)",
        }, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))["choices"][0]["message"]["content"]
    except Exception as e:
        return f"[Groq hata: {e}]"

def web_ara(sorgu):
    url = "https://html.duckduckgo.com/html/?q=" + urllib.parse.quote(sorgu)
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            html = resp.read().decode("utf-8", errors="replace")
        import re
        snippets = re.findall(r'class="result__snippet"[^>]*>(.*?)</a>', html, re.DOTALL)
        titles   = re.findall(r'class="result__a"[^>]*>(.*?)</a>', html, re.DOTALL)
        def clean(s): return re.sub(r'<[^>]+>', '', s).strip()
        out = []
        for t, s in zip(titles[:6], snippets[:6]):
            out.append(f"- {clean(t)}: {clean(s)}")
        return "\n".join(out) or "(sonuc yok)"
    except Exception as e:
        return f"(hata: {e})"

def main():
    print("=" * 55)
    print("  Turkiye Araba Ses Ceza Arastirmasi")
    print("=" * 55)
    
    api_key = get_groq_key()
    if not api_key:
        print("[!] GROQ_API_KEY bulunamadi!")
        sys.exit(1)
    print(f"[OK] Groq hazir (...{api_key[-6:]})")

    ham = []
    for i, sorgu in enumerate(SORGULAR, 1):
        print(f"  [{i}/{len(SORGULAR)}] {sorgu[:60]}...")
        metin = web_ara(sorgu)
        if len(metin) > 50:
            ham.append(f"Sorgu: {sorgu}\n{metin}")
        time.sleep(1.5)

    print("\n  Groq analiz yapiyor...")
    birlesik = "\n\n---\n".join(ham[:8])
    anliz_promptu = f"""
Asagidaki arama sonuclari Turkiye'de araba ses sistemi cezalari hakkindadir.
Lutfen analiz et:

{birlesik[:4000]}

Su sorulara cevap ver:
1. Hangi cezalar var? (tur, miktar, kanun maddesi)
2. Kim aciklama yapti? (yetkili, kurum, tarih)
3. Piyasaya etkisi ne oldu?
4. Ses sistemi sahipleri/esnafi ne soyluyor?
5. Yasal durum nedir? (hangi sesler yasak, hangisi serbest)

JSON formatinda ver:
{{"cezalar": [], "aciklamalar": [], "piyasa_etkisi": "", "kullanici_tepkileri": [], "yasal_durum": "", "ozet": ""}}
"""
    sistem = "Sen Turkiye araba ses piyasasi uzmaninin arastirmacisinsin. Kisa, net, Turkce cevaplar ver."
    sonuc_str = groq_analiz(sistem, anliz_promptu)

    try:
        import re
        m = re.search(r'\{.*\}', sonuc_str, re.DOTALL)
        analiz = json.loads(m.group()) if m else {"ham": sonuc_str}
    except Exception:
        analiz = {"ham": sonuc_str}

    tarih = datetime.datetime.now().strftime("%Y%m%d_%H%M")
    out_json = ARASTIRMA / f"ceza_arastirma_{tarih}.json"
    out_md   = ARASTIRMA / f"ceza_rapor_{tarih}.md"

    analiz["tarih"] = tarih
    analiz["konu"]  = "turkiye_ses_cezalari"
    out_json.write_text(json.dumps(analiz, ensure_ascii=False, indent=2), encoding="utf-8")

    md  = f"# Turkiye Araba Ses Sistemi Ceza Raporu\n"
    md += f"**Tarih:** {datetime.datetime.now().strftime('%d.%m.%Y %H:%M')}\n\n"
    if analiz.get("ozet"):
        md += f"## Ozet\n{analiz['ozet']}\n\n"
    if analiz.get("cezalar"):
        md += "## Cezalar\n"
        for c in analiz["cezalar"]: md += f"- {c}\n"
        md += "\n"
    if analiz.get("aciklamalar"):
        md += "## Resmi Aciklamalar\n"
        for a in analiz["aciklamalar"]: md += f"- {a}\n"
        md += "\n"
    if analiz.get("yasal_durum"):
        md += f"## Yasal Durum\n{analiz['yasal_durum']}\n\n"
    if analiz.get("piyasa_etkisi"):
        md += f"## Piyasa Etkisi\n{analiz['piyasa_etkisi']}\n\n"
    if analiz.get("kullanici_tepkileri"):
        md += "## Kullanici/Esnaf Tepkileri\n"
        for t in analiz["kullanici_tepkileri"]: md += f"- {t}\n"
    out_md.write_text(md, encoding="utf-8")

    print(f"\n[OK] Rapor hazir: {out_md.name}")
    print("=" * 55)
    print("ARAŞTIRMA TAMAMLANDI")
    print("=" * 55)

    # Ozet ekrana bas
    print(f"\nOZET: {analiz.get('ozet', '(bos)')}")
    if analiz.get("cezalar"):
        print(f"CEZALAR: {analiz['cezalar']}")

if __name__ == "__main__":
    main()
