"""
core/knowledge_engine.py
DD1 Bilgi Kütüphanesi Motoru v2
=====================================
NotebookLM benzeri yapılandırılmış bilgi erişim sistemi.

Mimari:
  knowledge/library/
    ├── arac_koleksiyonu.json      — Araç kasa, kapı, bagaj, motor
    ├── marka_koleksiyonu.json     — Ses sistemi markaları + parametreler
    ├── montaj_koleksiyonu.json    — Kurulum, harness, kasnak, Big3
    ├── piyasa_koleksiyonu.json    — Saha dili, SPL kültürü, pazar
    └── index.json                 — Meta-özet dizini

Kullanım:
    from core.knowledge_engine import query_library

    # Sadece marka + araç bilgisi — örn: "JBL Egea" konuşması
    result = query_library(
        keywords=["jbl", "egea"],
        collections=["marka_koleksiyonu", "arac_koleksiyonu"],
        max_chars=1200,
    )
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Optional

logger = logging.getLogger("dd1.knowledge")

# ── Sabitler ──────────────────────────────────────────────────────────────────

LIB_DIR = Path(__file__).resolve().parent.parent / "knowledge" / "library"

COLLECTION_NAMES = [
    "arac_koleksiyonu",
    "marka_koleksiyonu",
    "montaj_koleksiyonu",
    "piyasa_koleksiyonu",
]

# Koleksiyon seçimi için anahtar kelime sinyalleri
_ARAC_TRIGGERS = re.compile(
    r"\b(sedan|hatchback|suv|kasa|bagaj|kap[ıi]|clio|megane|egea|corolla|"
    r"golf|polo|i20|civic|octavia|duster|tucson|sportage|t.roc|yaris|"
    r"renault|fiat|toyota|volkswagen|vw|hyundai|peugeot|dacia|honda|"
    r"skoda|opel|togg|chery|bmw|mercedes|audi|ford|kia|nissan|citro)\b",
    re.IGNORECASE,
)

_MARKA_TRIGGERS = re.compile(
    r"\b(jbl|sundown|pioneer|rockford|alpine|hertz|focal|kicker|morel|"
    r"dd.?audio|carrozzeria|kenwood|sony|clarion|jl.?audio|polk|skar|"
    r"beyma|eminence|rcf|fane|peavey|qsc|subwoofer|hoparlör|tweeter|"
    r"amfi|amplifikatör|rms|ohm|empedans|xmax|woofer|mid.?range)\b",
    re.IGNORECASE,
)

_MONTAJ_TRIGGERS = re.compile(
    r"\b(kasnak|spacer|harness|soket|adapt[oö]r|per[cç]in|big.?3|big.?three|"
    r"kondansatör|kondansator|kapasite|ba[gğ]lant[ıi]|montaj|kablo|kurulum|"
    r"double.?baffle|mdf|port.?y[oö]n|alternator|alternatt?[oö]r|"
    r"big\s*three|voltaj|voltage.?drop|kablo.?kesme)\b",
    re.IGNORECASE,
)


# ── Kütüphane Yükleyici ───────────────────────────────────────────────────────

class _LibraryCache:
    """Koleksiyon dosyalarını bellekte tutan basit önbellek."""

    def __init__(self):
        self._cache: dict[str, dict] = {}
        self._mtimes: dict[str, float] = {}

    def get(self, collection: str) -> dict:
        path = LIB_DIR / f"{collection}.json"
        if not path.exists():
            return {"entries": []}
        mtime = path.stat().st_mtime
        if self._cache.get(collection) is None or self._mtimes.get(collection) != mtime:
            try:
                self._cache[collection] = json.loads(path.read_text(encoding="utf-8"))
                self._mtimes[collection] = mtime
                logger.debug("[LIBRARY] %s yeniden yüklendi (%d kayıt)",
                             collection, len(self._cache[collection].get("entries", [])))
            except Exception as e:
                logger.error("[LIBRARY] %s okunamadı: %s", collection, e)
                self._cache[collection] = {"entries": []}
        return self._cache[collection]

    def all_index_tags(self) -> dict[str, list[str]]:
        """index.json'dan her koleksiyonun top_tags listesini döner."""
        idx_path = LIB_DIR / "index.json"
        if not idx_path.exists():
            return {}
        try:
            idx = json.loads(idx_path.read_text(encoding="utf-8"))
            return {
                col: data.get("top_tags", [])
                for col, data in idx.get("collections", {}).items()
            }
        except Exception:
            return {}


_cache = _LibraryCache()


# ── Koleksiyon Otomatik Seçim ─────────────────────────────────────────────────

def _auto_select_collections(keywords: list[str]) -> list[str]:
    """
    Verilen anahtar kelimelere bakarak hangi koleksiyonların yükleneceğine karar verir.
    Her zaman piyasa_koleksiyonu düşük ağırlıkla eklenir (saha dili için).
    """
    text = " ".join(str(k) for k in keywords if k)
    selected = []

    if _ARAC_TRIGGERS.search(text):
        selected.append("arac_koleksiyonu")
    if _MARKA_TRIGGERS.search(text):
        selected.append("marka_koleksiyonu")
    if _MONTAJ_TRIGGERS.search(text):
        selected.append("montaj_koleksiyonu")

    # Hiçbiri tetiklenmediyse veya her halükarda saha dili için piyasa ekle
    if not selected:
        selected = ["piyasa_koleksiyonu", "marka_koleksiyonu"]
    elif "piyasa_koleksiyonu" not in selected and len(selected) < 3:
        selected.append("piyasa_koleksiyonu")

    return selected


# ── Puanlama ──────────────────────────────────────────────────────────────────

def _score_entry(entry: dict, keywords: list[str], collection: str = "") -> int:
    """
    Bir kütüphane kaydını anahtar kelimelere göre puanla.
    tag eslemesi: +5 / dump eslemesi: +1
    Montaj koleksiyonu: minimum 1 puan garantisi (tüm montaj verisi potansiyel ilgili).
    """
    if not keywords:
        return 1

    score = 0
    tags = set(entry.get("tags", []))
    dump = json.dumps(entry, ensure_ascii=False).lower()

    for kw in keywords:
        if not kw:
            continue
        kw_low = str(kw).lower().strip()
        if kw_low in tags:
            score += 5        # direkt tag eslemesi
        count = dump.count(kw_low)
        if count:
            score += count    # metinde gecme sayisi

    # Montaj koleksiyonu secilmisse: keyword eslesme olmasa bile tum kayitlar ilgili
    if collection == "montaj_koleksiyonu" and score == 0:
        score = 1  # minimum garantisi — montaj bilgisi her zaman yardimci olabilir

    return score


# ── Çıktı Üretici ─────────────────────────────────────────────────────────────

def _extract_tags_from_analiz(analiz: dict, ozet: str) -> list[str]:
    tags: set[str] = set()
    for key in ("markalar", "populer_markalar", "saha_dili", "jargon"):
        for item in (analiz.get(key) or []):
            for w in str(item).lower().split():
                w = re.sub(r"[^a-z0-9cçgğiıoösuüşz]", "", w)
                if len(w) > 2:
                    tags.add(w)
    for w in ozet[:200].lower().split():
        w = re.sub(r"[^a-z0-9cçgğiıoösuüşz]", "", w)
        if len(w) > 2:
            tags.add(w)

    # Teknik kritik kelimeler — regex ile tüm metinden zorla çıkar
    full_text = ozet + " ".join(
        str(x) for key in ("saha_dili", "jargon", "kronik_sorunlar", "teknik_sorular")
        for x in (analiz.get(key) or [])
    )
    _FORCED_TAGS = [
        (r"kasnak|spacer",          "kasnak"),
        (r"harness",                "harness"),
        (r"big.?3|big.?three",      "big3"),
        (r"alternatt?[oö]r",        "alternator"),
        (r"double.?baffle",         "doublebaffle"),
        (r"kondansatör|kondansator","kondansator"),
        (r"voltaj|voltage",         "voltaj"),
        (r"per[cç]in",              "percin"),
        (r"oval|6x9",              "oval"),
        (r"adapt[oö]r",             "adaptor"),
    ]
    for pattern, tag in _FORCED_TAGS:
        if re.search(pattern, full_text, re.IGNORECASE):
            tags.add(tag)

    return sorted(tags)[:40]

def _render_entry(entry: dict, ltype: str) -> str:
    """Tek bir kütüphane kaydını insan-okunabilir metne dönüştür."""
    parts = []

    if ltype == "arac":
        marka = entry.get("marka", "")
        model = entry.get("model", "")
        nesil = entry.get("nesil", "")
        kasa  = "/".join(entry.get("kasa_tipi", []))
        seg   = entry.get("segment", "")

        if marka and model:
            header = f"ARAÇ: {marka} {model}"
            if nesil:
                header += f" ({nesil})"
            parts.append(header)
            if kasa:
                parts.append(f"  Kasa: {kasa}  |  Segment: {seg}")
            if entry.get("kapi_hop_on_cm"):
                on_  = entry["kapi_hop_on_cm"]
                arka = entry.get("kapi_hop_arka_cm", "?")
                parts.append(f"  Kapı Hop: Ön {on_}cm / Arka {arka}cm")
            if entry.get("kapi_montaj_notu"):
                parts.append(f"  Montaj Notu: {entry['kapi_montaj_notu']}")
            if entry.get("bagaj_min_litre"):
                parts.append(f"  Bagaj: {entry['bagaj_min_litre']}–{entry.get('bagaj_max_litre', '?')}L")
            if entry.get("alternator_a"):
                parts.append(f"  Alternatör: {entry['alternator_a']}A")
        else:
            # analiz wrapper şeması
            if entry.get("kaynak"):
                parts.append(f"ARAÇ VERİSİ [{entry['kaynak'][:60]}]")
            if entry.get("ozet"):
                parts.append(entry["ozet"][:400])
            for j in (entry.get("jargon") or [])[:4]:
                parts.append(f"  • {j}")

    elif ltype == "marka":
        brandlist = ", ".join(entry.get("markalar", [])[:5])
        if brandlist:
            parts.append(f"MARKA: {brandlist}")
        if entry.get("ozet"):
            parts.append(entry["ozet"][:500])
        for s in (entry.get("saha_dili") or [])[:4]:
            parts.append(f"  - {s}")
        for k in (entry.get("kronik_sorunlar") or [])[:2]:
            parts.append(f"  ! {k}")

    elif ltype == "montaj":
        if entry.get("kaynak"):
            parts.append(f"MONTAJ [{entry['kaynak'][:50]}]")
        if entry.get("ozet"):
            parts.append(entry["ozet"][:400])
        for s in (entry.get("saha_dili") or [])[:4]:
            parts.append(f"  - {s}")
        for k in (entry.get("kronik_sorunlar") or [])[:2]:
            parts.append(f"  ! {k}")

    else:  # piyasa
        if entry.get("kaynak"):
            parts.append(f"PİYASA [{entry['kaynak'][:50]}]")
        if entry.get("ozet"):
            parts.append(entry["ozet"][:300])
        saha_items = (entry.get("saha_dili") or [])[:3]
        if saha_items:
            parts.append("  Saha Dili: " + " / ".join(saha_items))

    return "\n".join(parts)


# ── Ana API ───────────────────────────────────────────────────────────────────

def query_library(
    keywords: list[str | None],
    collections: Optional[list[str]] = None,
    max_chars: int = 1500,
    top_n: int = 6,
) -> str:
    """
    Kütüphaneden konuya özel, temiz ve sınırlı veri getirir.

    Parametreler:
        keywords    — Aranacak kelimeler (marka, araç adı, model, anahtar kelime)
                      None değerleri otomatik filtrelenir.
        collections — Hangi koleksiyonlardan aranacak. None ise otomatik seçilir.
        max_chars   — Dönen metnin maksimum karakter sayısı (token sınırı).
        top_n       — Her koleksiyondan en fazla kaç kayıt alınır.

    Döner: LLM'e aktarılacak temiz metin bloğu.
    """
    clean_keywords = [str(k).strip() for k in keywords if k and str(k).strip()]

    if not clean_keywords:
        return ""  # keyword yoksa sistem promptuna hiçbir şey ekleme

    selected = collections or _auto_select_collections(clean_keywords)

    sections: list[str] = []

    for col in selected:
        lib = _cache.get(col)
        entries = lib.get("entries", [])

        if not entries:
            logger.debug("[LIBRARY] %s boş, atlanıyor", col)
            continue

        # Puanla ve sirala
        scored = sorted(
            ((e, _score_entry(e, clean_keywords, col)) for e in entries),
            key=lambda x: x[1],
            reverse=True,
        )

        # Sadece skor > 0 olan kayıtları al
        relevant = [(e, s) for e, s in scored if s > 0][:top_n]

        if not relevant:
            # Koleksiyonda keyword eşleşmesi yok — bu koleksiyonu atla
            logger.debug("[LIBRARY] %s için eşleşen kayıt yok (kw=%s)", col, clean_keywords)
            continue

        col_label = {
            "arac_koleksiyonu":   "ARAÇ BİLGİSİ",
            "marka_koleksiyonu":  "SES SİSTEMİ MARKA BİLGİSİ",
            "montaj_koleksiyonu": "MONTAJ KURALLARI",
            "piyasa_koleksiyonu": "SAHA / PİYASA BİLGİSİ",
        }.get(col, col.upper())

        col_lines = [f"--- {col_label} ---"]
        for entry, score in relevant:
            ltype = entry.get("library_type", col.split("_")[0])
            rendered = _render_entry(entry, ltype)
            if rendered.strip():
                col_lines.append(rendered)
                col_lines.append("")  # boş satır ayraç

        if len(col_lines) > 1:
            sections.append("\n".join(col_lines))

    if not sections:
        return ""

    result = "\n\n".join(sections)

    # Karakter sınırı uygula (token güvenliği)
    if len(result) > max_chars:
        result = result[:max_chars] + "\n[...kütüphane bağlamı kısaltıldı]"

    return result


# ── Eski API — Geriye Dönük Uyumluluk ────────────────────────────────────────

def get_market_intelligence(
    query_keywords: list[str] | None = None,
) -> str:
    """
    Önceki API — geriye dönük uyumluluk için korundu.
    İçeride query_library'yi çağırır.
    """
    if not query_keywords:
        # Eski kullanım: keyword'süz çağrı — artık boş dön, LLM'i kirletme
        logger.debug("[LIBRARY] get_market_intelligence() keyword'süz çağrıldı — atlanıyor")
        return ""

    return query_library(
        keywords=query_keywords,
        collections=None,  # otomatik seç
        max_chars=1200,
        top_n=5,
    )


# Eski singleton — dokunma
class MarketIntelligence:
    """Geriye dönük uyumluluk için stub."""
    def build_context(self, query_keywords=None):
        return get_market_intelligence(query_keywords)


market_intel = MarketIntelligence()
