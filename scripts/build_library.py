"""
scripts/build_library.py
DD1 Bilgi Kutuphanesi Insa Scripti v2
==========================================
Gorev:
  desktop_apps/piyasa_ajani/arastirma/ klasoründeki TUM *.json dosyalarini
  okur, iceriklerine gore 4 koleksiyona kategorize eder ve
  knowledge/library/ altına normalize edilmiş kütüphane dosyaları yazar.

  ÖNEMLI KURALLAR:
    1. Kaynak dosyalar DOKUNULMAZ — sadece "__dd1_islendi" etiketi eklenir.
    2. Araç kaydı KAPSAMLIDIR — bir araçla ilgili tüm veriler (kapı, motor,
       bagaj, alternator, kasnak notu, cabin gain...) tek kayıtta toplanır.
    3. Birden fazla kaynaktan gelen aynı araç verileri MERGE edilir.

Çalıştır:
  python scripts/build_library.py              # tüm dosyaları işle
  python scripts/build_library.py --incremental # sadece yeni/değişen
  python scripts/build_library.py --watch      # otomatik izleme modu

Koleksiyonlar:
  arac_koleksiyonu    — Araç kapsamlı profil (kasa, kapı, motor, bagaj, kasnak...)
  marka_koleksiyonu   — Ses sistemi markaları, cihaz karakteri, parametreler
  montaj_koleksiyonu  — Kurulum, harness, kasnak, Big3, double baffle
  piyasa_koleksiyonu  — Saha dili, SPL kültürü, Türkiye pazar dinamikleri
"""

from __future__ import annotations
import json
import re
import sys
import time
import hashlib
import argparse
from pathlib import Path
from datetime import datetime
from typing import Any

# ── Yollar ────────────────────────────────────────────────────────────────────
ROOT    = Path(__file__).resolve().parent.parent
SRC_DIR = ROOT / "desktop_apps" / "piyasa_ajani" / "arastirma"
LIB_DIR = ROOT / "knowledge" / "library"
LIB_DIR.mkdir(parents=True, exist_ok=True)

COLLECTIONS = [
    "arac_koleksiyonu",
    "marka_koleksiyonu",
    "montaj_koleksiyonu",
    "piyasa_koleksiyonu",
]

# ── Kategori Tespit Sinyalleri ────────────────────────────────────────────────

_ARAC_SIGNALS = re.compile(
    r"kapi|kapı|kasa|segment|sedan|hatchback|suv|bagaj|turkiye_kasa|"
    r"odmd|auto.?data|otomobil.?com|motor.?analiz|fit.?guide|eu.?fit|"
    r"pioneer.?fit|hertz.?fit|populer.?arac|b_ve_c|katalog|segment_ve",
    re.IGNORECASE,
)
_MARKA_SIGNALS = re.compile(
    r"jbl|sundown|pioneer|rockford|carrozzeria|kicker|alpine|hertz|focal|"
    r"ddaudio|dd.?audio|sq.?jdm|american.?spl|spl.?brand|wikipedia.?brand|"
    r"jl.?audio|garmin|oldschool|regional.?brand|brazil|pancadao|japanese.?sq|"
    r"audiodesign|sescibaba",
    re.IGNORECASE,
)
_MONTAJ_SIGNALS = re.compile(
    r"kondansator|bigbang|the12volt|diyaudio|kabin.?sistem|omnicalc|"
    r"epey|donanim|veri.?standart",
    re.IGNORECASE,
)

# Kapı ölçüsü metininden cm çıkarıcı
_KAPI_CM_RE = re.compile(
    r"(ön|arka|on|\"front\"|\"rear\")\s*(?:kapı\s*)?[:\s]*"
    r"(\d{2}(?:[.,]\d)?)\s*(?:cm|\")",
    re.IGNORECASE,
)

# Araç adı tespiti için bilinen model tablosu
_BILINEN_ARACLAR = {
    "clio":      ("Renault", "Clio"),
    "megane":    ("Renault", "Megane"),
    "sandero":   ("Dacia",   "Sandero"),
    "duster":    ("Dacia",   "Duster"),
    "egea":      ("Fiat",    "Egea"),
    "tipo":      ("Fiat",    "Tipo"),
    "corolla":   ("Toyota",  "Corolla"),
    "yaris":     ("Toyota",  "Yaris"),
    "golf":      ("Volkswagen", "Golf"),
    "polo":      ("Volkswagen", "Polo"),
    "t-roc":     ("Volkswagen", "T-Roc"),
    "t-cross":   ("Volkswagen", "T-Cross"),
    "passat":    ("Volkswagen", "Passat"),
    "i20":       ("Hyundai", "i20"),
    "tucson":    ("Hyundai", "Tucson"),
    "bayon":     ("Hyundai", "Bayon"),
    "civic":     ("Honda",   "Civic"),
    "hr-v":      ("Honda",   "HR-V"),
    "208":       ("Peugeot", "208"),
    "2008":      ("Peugeot", "2008"),
    "3008":      ("Peugeot", "3008"),
    "corsa":     ("Opel",    "Corsa"),
    "octavia":   ("Skoda",   "Octavia"),
    "karoq":     ("Skoda",   "Karoq"),
    "sportage":  ("Kia",     "Sportage"),
    "tiggo":     ("Chery",   "Tiggo 7 Pro"),
    "t10x":      ("Togg",    "T10X"),
    "focus":     ("Ford",    "Focus"),
    "fiesta":    ("Ford",    "Fiesta"),
    "puma":      ("Ford",    "Puma"),
}


# ═══════════════════════════════════════════════════════════════════════════════
# BÖLÜM 1 — ŞEMA NORMALİZASYON FONKSİYONLARI
# ═══════════════════════════════════════════════════════════════════════════════

def _build_arac_tags(marka: str, model: str, nesil: str,
                     kasa: list[str], segment: str) -> list[str]:
    tags = {marka.lower(), model.lower()}
    if nesil:
        for w in re.split(r"[\s\(\)\/]+", nesil.lower()):
            if len(w) > 1:
                tags.add(w)
    tags.update(k.lower() for k in kasa)
    if segment:
        tags.add(segment.lower())
    return sorted(tags)


def _normalize_arac_direct(raw: dict, source_file: str) -> dict:
    """
    Doğrudan marka/model şemasından (b_ve_c listesi gibi) kapsamlı araç kaydı üretir.
    Motor, kapı, bagaj alanları şimdilik boş — consolidation adımında doldurulur.
    """
    kasa = raw.get("kasa_tipi", [])
    if isinstance(kasa, str):
        kasa = [kasa]
    marka = raw.get("marka", "")
    model = raw.get("model", "")
    nesil = raw.get("nesil", "")
    segment = raw.get("segment", "")

    return {
        "library_type":       "arac",
        "marka":              marka,
        "model":              model,
        "nesil":              nesil,
        "kasa_tipi":          kasa,
        "segment":            segment,
        "turkiye_statusu":    raw.get("turkiye_statusu", ""),
        # Kapı bilgileri — birden fazla kaynaktan gelebilir
        "kapi_hop_on_cm":     raw.get("kapi_hop_on_cm"),
        "kapi_hop_arka_cm":   raw.get("kapi_hop_arka_cm"),
        "kapi_sekli":         raw.get("kapi_sekli", ""),         # yuvarlak / oval / asimetrik
        "kapi_montaj_notu":   raw.get("kapi_montaj_notu", ""),   # kasnak, spacer, perçin vb.
        "kapi_harness_gerek": raw.get("kapi_harness_gerek"),     # True/False/None
        # Bagaj
        "bagaj_min_litre":    raw.get("bagaj_min_litre"),
        "bagaj_max_litre":    raw.get("bagaj_max_litre"),
        "bagaj_notu":         raw.get("bagaj_notu", ""),
        # Elektrik
        "alternator_a":       raw.get("alternator_a"),
        "aku_ah":             raw.get("aku_ah"),
        "motor_hacmi_cc":     raw.get("motor_hacmi_cc", ""),     # "1.0 TCe" vb.
        "big3_gerek":         raw.get("big3_gerek"),             # True/False/None
        # Akustik
        "cabin_gain_hz":      raw.get("cabin_gain_hz"),
        "akustik_notu":       raw.get("akustik_notu", ""),
        # Meta
        "usta_uyari":         raw.get("usta_uyari", ""),  # montajcıya özel uyarı
        "kaynaklar":          [source_file],
        "tags":               _build_arac_tags(marka, model, nesil, kasa, segment),
        "__library_type":     "arac_direct",
        "__source":           source_file,
    }


def _extract_tags_from_analiz(analiz: dict, ozet: str) -> list[str]:
    tags: set[str] = set()
    for key in ("markalar", "populer_markalar", "saha_dili", "jargon"):
        for item in (analiz.get(key) or []):
            for w in str(item).lower().split():
                w = re.sub(r"[^a-z0-9çğıöşü]", "", w)
                if len(w) > 2:
                    tags.add(w)
    for w in ozet[:200].lower().split():
        w = re.sub(r"[^a-z0-9çğıöşü]", "", w)
        if len(w) > 2:
            tags.add(w)
    return sorted(tags)[:30]


def _normalize_arac_analiz(raw: dict, source_file: str) -> dict:
    """Analiz-wrapper şemasından araç bağlam kaydı üretir (kapı/fit guide tipli)."""
    analiz = raw.get("analiz", {}) if isinstance(raw.get("analiz"), dict) else {}
    return {
        "library_type":    "arac",
        "kaynak":          raw.get("orneklem_kaynagi", source_file),
        "ozet":            analiz.get("ozet", ""),
        "saha_dili":       analiz.get("saha_dili", []),
        "jargon":          analiz.get("jargon", []),
        "kronik_sorunlar": analiz.get("kronik_sorunlar", []),
        "teknik_sorular":  analiz.get("teknik_sorular", []),
        "tags":            _extract_tags_from_analiz(analiz, analiz.get("ozet", "")),
        "__library_type":  "arac_context",
        "__source":        source_file,
    }


def _normalize_marka(raw: dict, source_file: str) -> dict:
    analiz = raw.get("analiz", {}) if isinstance(raw.get("analiz"), dict) else {}
    markalar = list(set(
        analiz.get("markalar", []) + analiz.get("populer_markalar", [])
    ))
    ozet = analiz.get("ozet", "")
    return {
        "library_type":    "marka",
        "kaynak":          raw.get("orneklem_kaynagi", source_file),
        "markalar":        markalar,
        "ozet":            ozet,
        "saha_dili":       analiz.get("saha_dili", []),
        "jargon":          analiz.get("jargon", []),
        "kronik_sorunlar": analiz.get("kronik_sorunlar", []),
        "teknik_sorular":  analiz.get("teknik_sorular", []),
        "tags":            _extract_tags_from_analiz(analiz, ozet),
        "__source":        source_file,
    }


def _normalize_montaj(raw: dict, source_file: str) -> dict:
    """
    Montaj dosyalarını normalize eder.
    Bu dosyalar çok çeşitli schema'lara sahip — standart ve özel key'lerin
    tamamını tarar, kritik teknik kelimeleri zorla tag olarak ekler.
    """
    # Tüm olası analiz bloklarını topla
    analiz   = raw.get("analiz", {}) if isinstance(raw.get("analiz"), dict) else {}
    icerik   = raw.get("icerik_analizi", {}) if isinstance(raw.get("icerik_analizi"), dict) else {}
    piyasa   = raw.get("piyasa_bulgulari", {}) if isinstance(raw.get("piyasa_bulgulari"), dict) else {}
    teknik   = raw.get("teknik_not_kondansator", {}) if isinstance(raw.get("teknik_not_kondansator"), dict) else {}
    dd1_icin = raw.get("dd1_icin", {}) if isinstance(raw.get("dd1_icin"), dict) else {}
    merged   = {**piyasa, **icerik, **teknik, **dd1_icin, **analiz}

    ozet = (
        merged.get("ozet")
        or raw.get("meta", {}).get("odak", "")
        or merged.get("egitim_acigi", "")
        or ""
    )
    saha  = list(set(merged.get("saha_dili", []) + merged.get("jargon", [])))
    sorun = merged.get("kronik_sorunlar", []) + merged.get("teknik_sorular", [])

    # Tüm raw veriyi tek string'e döküp kritik tag'leri zorla çıkar
    full_dump = json.dumps(raw, ensure_ascii=False).lower()
    tags: set[str] = set()

    _FORCED = [
        (r"kasnak|spacer",              "kasnak"),
        (r"harness",                    "harness"),
        (r"big.?3|big.?three",          "big3"),
        (r"alternatt?[oöo]r",           "alternator"),
        (r"double.?baffle",             "doublebaffle"),
        (r"kondansat[oö]r|kondansator", "kondansator"),
        (r"voltaj|voltage",             "voltaj"),
        (r"per[cç]in",                  "percin"),
        (r"oval|6x9",                   "oval"),
        (r"adapt[oö]r",                 "adaptor"),
        (r"soket|plug.?play",           "soket"),
        (r"crossover|high.?pass|hpf",   "crossover"),
        (r"for.?x",                     "forx"),
        (r"tweeter",                    "tweeter"),
        (r"kabin|enclosure",            "kabin"),
        (r"port|ported",                "port"),
        (r"amfi|amplif",                "amfi"),
        (r"diyaudio",                   "diyaudio"),
        (r"montaj",                     "montaj"),
        (r"kablo",                      "kablo"),
    ]

    for pattern, tag in _FORCED:
        if re.search(pattern, full_dump, re.IGNORECASE):
            tags.add(tag)

    # Kaynak key'ini belirle
    kaynak_val = (
        raw.get("orneklem_kaynagi")
        or raw.get("grup_url")
        or raw.get("meta", {}).get("kaynak", source_file)
        or source_file
    )

    return {
        "library_type":    "montaj",
        "kaynak":          kaynak_val,
        "ozet":            ozet,
        "saha_dili":       saha,
        "kronik_sorunlar": sorun,
        "tags":            sorted(tags),
        "__source":        source_file,
    }


def _normalize_piyasa(raw: dict, source_file: str) -> dict:
    analiz   = raw.get("analiz", {}) if isinstance(raw.get("analiz"), dict) else {}
    icerik   = raw.get("icerik_analizi", {}) if isinstance(raw.get("icerik_analizi"), dict) else {}
    pbulgular = raw.get("piyasa_bulgulari", {}) if isinstance(raw.get("piyasa_bulgulari"), dict) else {}
    merged   = {**pbulgular, **icerik, **analiz}
    ozet     = merged.get("ozet") or raw.get("meta", {}).get("odak", "")
    markalar = list(set(merged.get("markalar", []) + merged.get("populer_markalar", [])))
    saha     = list(set(merged.get("saha_dili", []) + merged.get("jargon", [])))
    sorun    = merged.get("kronik_sorunlar", []) + merged.get("teknik_sorular", [])
    return {
        "library_type":    "piyasa",
        "kaynak":          raw.get("orneklem_kaynagi") or raw.get("grup_url", source_file),
        "markalar":        markalar,
        "ozet":            ozet,
        "saha_dili":       saha,
        "kronik_sorunlar": sorun,
        "tags":            _extract_tags_from_analiz(merged, ozet),
        "__source":        source_file,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# BÖLÜM 2 — ARAÇ KONSOLİDASYONU (aynı araç → tek kapsamlı kayıt)
# ═══════════════════════════════════════════════════════════════════════════════

def _arac_key(marka: str, model: str) -> str:
    return f"{marka.strip().lower()}::{model.strip().lower()}"


def _extract_kapi_from_jargon(jargon_list: list[str], marka: str, model: str) -> dict:
    """
    Jargon / saha_dili metinlerinden kapı ölçüsü ve montaj notları çıkarır.
    Örn: "Fiat Egea: Ön 16.5cm, arka 16.5cm. Plastik kasnak şart."
    """
    result: dict[str, Any] = {}
    target_lower = f"{marka.lower()} {model.lower()}"

    for line in jargon_list:
        line_low = line.lower()
        if marka.lower() not in line_low and model.lower() not in line_low:
            continue

        # cm değerlerini çıkar
        cm_matches = re.findall(r"(\d{2}(?:[.,]\d)?)\s*cm", line_low)
        if cm_matches:
            # İlki genellikle ön, ikincisi arka
            if not result.get("kapi_hop_on_cm") and cm_matches:
                try:
                    result["kapi_hop_on_cm"] = float(cm_matches[0].replace(",", "."))
                except ValueError:
                    pass
            if not result.get("kapi_hop_arka_cm") and len(cm_matches) > 1:
                try:
                    result["kapi_hop_arka_cm"] = float(cm_matches[1].replace(",", "."))
                except ValueError:
                    pass

        # Oval/asimetrik yuva tespiti
        if re.search(r"oval|asimetrik|6x9|6.9", line_low):
            result["kapi_sekli"] = "oval/asimetrik"
        elif not result.get("kapi_sekli"):
            result["kapi_sekli"] = "yuvarlak"

        # Kasnak / spacer / perçin notu
        montaj_ipuclari = []
        if re.search(r"kasnak|spacer|perçin|adaptör|harness", line_low):
            montaj_ipuclari.append(line.strip()[:200])
        if montaj_ipuclari and not result.get("kapi_montaj_notu"):
            result["kapi_montaj_notu"] = " | ".join(montaj_ipuclari)

        # Harness gereksinimi
        if re.search(r"harness|kablo\s*kesme|soket\s*dönüştür", line_low):
            result["kapi_harness_gerek"] = True

    return result


def _extract_motor_from_context(ozet: str, jargon: list[str]) -> dict:
    """Genel motor/alternator bilgisini özet metinden çıkarır."""
    result = {}
    combined = ozet + " ".join(jargon)
    # Alternatör amper
    alt_m = re.search(r"(\d{2,3})\s*[Aa](?:mper|mp|\b)", combined)
    if alt_m and not result.get("alternator_a"):
        a = int(alt_m.group(1))
        if 50 <= a <= 200:
            result["alternator_a"] = a

    # Big 3 ihtiyacı
    if re.search(r"big.?3|big.?three|büyük\s*3", combined, re.IGNORECASE):
        result["big3_gerek"] = True

    return result


def _consolidate_vehicles(entries: list[dict]) -> list[dict]:
    """
    arac_koleksiyonu entries listesini alır.
    Aynı marka+model için birden fazla kayıt varsa hepsini tek kapsamlı kayıtta birleştirir.
    Eşleşmeyen context kayıtları ayrı entry olarak kalır.
    """
    # direct kayıtları (marka+model var) anahtara göre grupla
    direct_map: dict[str, dict] = {}
    context_records: list[dict] = []

    for e in entries:
        if e.get("__library_type") == "arac_direct" and e.get("marka") and e.get("model"):
            key = _arac_key(e["marka"], e["model"])
            if key not in direct_map:
                direct_map[key] = e
            else:
                # Aynı araç daha önce başka kaynaktan eklendi — alanları merge et
                existing = direct_map[key]
                for field in ("kapi_hop_on_cm", "kapi_hop_arka_cm", "kapi_sekli",
                              "kapi_montaj_notu", "kapi_harness_gerek",
                              "bagaj_min_litre", "bagaj_max_litre", "bagaj_notu",
                              "alternator_a", "aku_ah", "motor_hacmi_cc",
                              "big3_gerek", "cabin_gain_hz", "akustik_notu", "usta_uyari"):
                    if existing.get(field) is None and e.get(field) is not None:
                        existing[field] = e[field]
                # Kaynakları birleştir
                src = e.get("__source", "")
                if src and src not in existing.get("kaynaklar", []):
                    existing.setdefault("kaynaklar", []).append(src)
                # Tag'leri birleştir
                existing["tags"] = sorted(set(existing.get("tags", []) + e.get("tags", [])))
        else:
            context_records.append(e)

    # Context kayıtlarından araç bilgilerini direct_map'e aktar
    for ctx in context_records:
        jargon   = ctx.get("jargon", []) + ctx.get("saha_dili", [])
        ozet     = ctx.get("ozet", "")
        sorunlar = ctx.get("kronik_sorunlar", [])

        for key, vehicle in direct_map.items():
            marka = vehicle["marka"]
            model = vehicle["model"]

            # Bu context kaydı bu araçla ilgili mi?
            text = ozet + " ".join(jargon) + " ".join(sorunlar)
            if marka.lower() not in text.lower() and model.lower() not in text.lower():
                continue

            # Kapı bilgisi çıkar ve merge et
            kapi_info = _extract_kapi_from_jargon(jargon, marka, model)
            for field, val in kapi_info.items():
                if vehicle.get(field) is None and val is not None:
                    vehicle[field] = val

            # Motor/alternator bilgisi
            motor_info = _extract_motor_from_context(ozet, jargon)
            for field, val in motor_info.items():
                if vehicle.get(field) is None and val is not None:
                    vehicle[field] = val

            # Usta uyarısı — kronık sorunlardan ilk 2'si
            if not vehicle.get("usta_uyari") and sorunlar:
                vehicle["usta_uyari"] = " | ".join(sorunlar[:2])

            # Akustik notu
            if not vehicle.get("akustik_notu") and re.search(
                r"cabin.?gain|kabin.?kazan|rezonans", text, re.IGNORECASE
            ):
                m = re.search(r"~?(\d{2,3})\s*[Hh]z", text)
                if m:
                    vehicle["akustik_notu"] = f"Kabin rezonans ~{m.group(1)}Hz"

            # Kaynağı ekle
            src = ctx.get("__source", "")
            if src and src not in vehicle.get("kaynaklar", []):
                vehicle.setdefault("kaynaklar", []).append(src)

    # Sonuç: direct (kapsamlı) kayıtlar + bağlam kayıtları (eşleşmeyen)
    final: list[dict] = list(direct_map.values()) + context_records
    return final


# ═══════════════════════════════════════════════════════════════════════════════
# BÖLÜM 3 — DOSYA KATEGORI VE İŞLEME
# ═══════════════════════════════════════════════════════════════════════════════

def categorize_file(path: Path) -> str:
    name = path.stem.lower()
    if _ARAC_SIGNALS.search(name):
        return "arac_koleksiyonu"
    if _MARKA_SIGNALS.search(name):
        return "marka_koleksiyonu"
    if _MONTAJ_SIGNALS.search(name):
        return "montaj_koleksiyonu"
    # İçeriğe bak
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        dump = json.dumps(raw, ensure_ascii=False).lower()
        a = len(_ARAC_SIGNALS.findall(dump))
        m = len(_MARKA_SIGNALS.findall(dump))
        if a > m:
            return "arac_koleksiyonu"
        if m > 0:
            return "marka_koleksiyonu"
    except Exception:
        pass
    return "piyasa_koleksiyonu"


def process_file(path: Path) -> tuple[str, list[dict]]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"  [HATA] {path.name}: {e}")
        return "piyasa_koleksiyonu", []

    collection = categorize_file(path)
    fname = path.name

    def _dispatch(item: dict) -> dict:
        if collection == "arac_koleksiyonu":
            if item.get("marka") and item.get("model"):
                return _normalize_arac_direct(item, fname)
            return _normalize_arac_analiz(item, fname)
        if collection == "marka_koleksiyonu":
            return _normalize_marka(item, fname)
        if collection == "montaj_koleksiyonu":
            return _normalize_montaj(item, fname)
        return _normalize_piyasa(item, fname)

    if isinstance(raw, list):
        return collection, [_dispatch(i) for i in raw if isinstance(i, dict)]
    return collection, [_dispatch(raw)]


# ═══════════════════════════════════════════════════════════════════════════════
# BÖLÜM 4 — "İŞLENDİ" ETİKETLEME (kaynak dosyalar depoda kalır)
# ═══════════════════════════════════════════════════════════════════════════════

def _tag_source_file(path: Path, collection: str) -> None:
    """
    Kaynak JSON dosyasına "__dd1_islendi" etiketi ekler.
    Dosya YERINDE güncellenir, silinmez.
    Zaten etiketlenmişse dokunmaz.
    """
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        meta_key = "__dd1_islendi"

        if isinstance(raw, list):
            # Liste dosyası: meta bilgiyi dosyanın en üstüne wrapper ekleyerek mühürle
            # Ama listeyi bozmamak için ilk eleman zaten etiketli mi kontrol et
            if raw and isinstance(raw[0], dict) and raw[0].get(meta_key):
                return  # Zaten etiketli
            # Listeye dokunma — yanına ayrı bir meta dosyası yaz
            _write_meta_stamp(path, collection)
            return

        if isinstance(raw, dict):
            if raw.get(meta_key):
                return  # Zaten etiketli
            raw[meta_key]           = True
            raw["__dd1_koleksiyon"] = collection
            raw["__dd1_islendi_at"] = datetime.now().isoformat()
            path.write_text(
                json.dumps(raw, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
    except Exception as e:
        print(f"  [UYARI] Etiketleme başarısız {path.name}: {e}")


def _write_meta_stamp(path: Path, collection: str) -> None:
    """Liste tipli dosyalar için yan .meta.json dosyası yazar."""
    stamp_path = path.with_suffix(".meta.json")
    if stamp_path.exists():
        return
    stamp = {
        "__dd1_islendi":    True,
        "__dd1_koleksiyon": collection,
        "__dd1_islendi_at": datetime.now().isoformat(),
        "__dd1_kaynak":     path.name,
    }
    stamp_path.write_text(json.dumps(stamp, ensure_ascii=False, indent=2), encoding="utf-8")


# ═══════════════════════════════════════════════════════════════════════════════
# BÖLÜM 5 — ANA BUILD
# ═══════════════════════════════════════════════════════════════════════════════

def _load_existing(collection: str) -> dict:
    lib_path = LIB_DIR / f"{collection}.json"
    if lib_path.exists():
        try:
            return json.loads(lib_path.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"collection": collection, "version": 2, "entries": [], "source_hashes": {}}


def _file_hash(path: Path) -> str:
    return hashlib.md5(path.read_bytes()).hexdigest()


def build_library(incremental: bool = False, verbose: bool = True) -> dict[str, int]:
    if not SRC_DIR.exists():
        print(f"[HATA] Kaynak klasör bulunamadı: {SRC_DIR}")
        return {}

    # Meta stamp dosyalarını yoksay
    all_files = sorted(p for p in SRC_DIR.glob("*.json") if not p.name.endswith(".meta.json"))

    print(f"\n{'='*60}")
    print(f"  DD1 Bilgi Kutuphanesi Insa Ediliyor (v2)")
    print(f"  Kaynak : {len(all_files)} JSON dosyasi")
    print(f"  Hedef  : {LIB_DIR}")
    print(f"{'='*60}\n")

    libraries: dict[str, dict] = {col: _load_existing(col) for col in COLLECTIONS}
    stats    = {col: 0 for col in COLLECTIONS}
    skipped  = 0

    for path in all_files:
        fhash = _file_hash(path)

        if incremental:
            already = any(
                lib["source_hashes"].get(path.name) == fhash
                for lib in libraries.values()
            )
            if already:
                skipped += 1
                continue

        collection, entries = process_file(path)
        if not entries:
            continue

        lib = libraries[collection]

        # Eski kayıtları bu kaynaktan temizle (güncelleme durumu)
        lib["entries"] = [e for e in lib["entries"] if e.get("__source") != path.name]

        lib["entries"].extend(entries)
        lib["source_hashes"][path.name] = fhash
        stats[collection] += len(entries)

        # Kaynak dosyayı "işlendi" olarak etiketle (depoda kalsın)
        _tag_source_file(path, collection)

        if verbose:
            col_short = {"arac_koleksiyonu": "ARAÇ", "marka_koleksiyonu": "MARKA",
                         "montaj_koleksiyonu": "MONTAJ", "piyasa_koleksiyonu": "PİYASA"}.get(collection, "?")
            print(f"  [{col_short:6}] {path.name:<55} ->  {len(entries)} kayit")

    # -- Arac Konsolidasyonu
    print("\n  Arac kayitlari konsolide ediliyor...")
    before_count = len(libraries["arac_koleksiyonu"]["entries"])
    libraries["arac_koleksiyonu"]["entries"] = _consolidate_vehicles(
        libraries["arac_koleksiyonu"]["entries"]
    )
    after_count = len(libraries["arac_koleksiyonu"]["entries"])
    direct_count = sum(
        1 for e in libraries["arac_koleksiyonu"]["entries"]
        if e.get("__library_type") == "arac_direct"
    )
    print(f"  {before_count} kayit -> {after_count} kayit ({direct_count} kapsamli arac profili)")

    # ── Kütüphane Dosyalarını Yaz ────────────────────────────────────────────
    for col, lib in libraries.items():
        lib["updated_at"] = datetime.now().isoformat()
        (LIB_DIR / f"{col}.json").write_text(
            json.dumps(lib, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    _write_index(libraries)

    print(f"\n{'='*60}")
    print("  SONUC:")
    for col, count in stats.items():
        total = len(libraries[col]["entries"])
        print(f"  {col:<25}  +{count} yeni  |  toplam {total} kayit")
    if skipped:
        print(f"  {skipped} dosya atlandi (degismemis)")
    print(f"{'='*60}\n")
    return stats


def _write_index(libraries: dict[str, dict]) -> None:
    index = {
        "version":     2,
        "updated_at":  datetime.now().isoformat(),
        "collections": {}
    }
    for col, lib in libraries.items():
        entries = lib.get("entries", [])
        all_tags:   set[str] = set()
        all_brands: set[str] = set()
        all_models: set[str] = set()
        for e in entries:
            all_tags.update(e.get("tags", []))
            for b in e.get("markalar", []):
                all_brands.add(str(b).lower())
            if e.get("marka"):
                all_brands.add(str(e["marka"]).lower())
            if e.get("model"):
                all_models.add(f"{e.get('marka','')} {e['model']}".strip())

        index["collections"][col] = {
            "entry_count":  len(entries),
            "source_count": len(lib.get("source_hashes", {})),
            "top_tags":     sorted(all_tags)[:50],
            "brands":       sorted(all_brands)[:50],
            "models":       sorted(all_models)[:40],
        }

    (LIB_DIR / "index.json").write_text(
        json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"  [OK] index.json -> {LIB_DIR / 'index.json'}")


# ── Watch Modu ────────────────────────────────────────────────────────────────

def watch_mode(interval: int = 10) -> None:
    print(f"  Izleme modu acik (her {interval}s kontrol). Ctrl+C ile dur.\n")
    known = {p: _file_hash(p) for p in SRC_DIR.glob("*.json")
             if not p.name.endswith(".meta.json")}
    while True:
        time.sleep(interval)
        current = {p for p in SRC_DIR.glob("*.json") if not p.name.endswith(".meta.json")}
        changed = False
        for path in current:
            h = _file_hash(path)
            if known.get(path) != h:
                print(f"  [YENI/DEGISIKLIK] {path.name} isleniyor...")
                changed = True
        if changed:
            build_library(incremental=True, verbose=True)
            known = {p: _file_hash(p) for p in current}


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="DD1 Bilgi Kütüphanesi İnşa Scripti")
    parser.add_argument("--incremental", action="store_true",
                        help="Sadece değişen/yeni dosyaları işle")
    parser.add_argument("--watch", action="store_true",
                        help="arastirma/ klasörünü izle")
    parser.add_argument("--interval", type=int, default=10,
                        help="Watch mod kontrol aralığı (saniye)")
    args = parser.parse_args()

    if args.watch:
        try:
            build_library(incremental=False, verbose=True)
            watch_mode(args.interval)
        except KeyboardInterrupt:
            print("\n  İzleme modu kapatıldı.")
    else:
        build_library(incremental=args.incremental, verbose=True)
