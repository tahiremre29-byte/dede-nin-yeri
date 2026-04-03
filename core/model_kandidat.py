"""
dd1_platform/core/model_kandidat.py
Model Aday Seçim Motoru

Görev:
  Marka, çap, RMS, kullanım profili bilgisine göre
  woofer_catalog.json'dan 2-4 model adayı seçer.

Eşleşme mantığı:
  1. Tam marka eşleşmesi öncelikli
  2. Çap uyumu (tam veya ±1 inç tolerans)
  3. RMS bant uyumu (%50-150 aralığı)
  4. qs_profile hedef profille örtüşmesi
  5. Çeşitlilik: karakter etiketleri farklı adaylar seçilir

Çıktı:
  list[dict] — sıralı aday listesi (max 4)
  Her aday: marka, model, çap, rms, character_tag, use_type, why_recommend, score

Test: tests/core/test_model_kandidat.py
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

_CATALOG_PATH = Path(__file__).parent.parent / "knowledge" / "woofer_catalog.json"
_CATALOG: list[dict] = []


def _load_catalog() -> list[dict]:
    global _CATALOG
    if not _CATALOG:
        with open(_CATALOG_PATH, encoding="utf-8") as f:
            _CATALOG = json.load(f)["catalog"]
    return _CATALOG


# ── Profil uyum matrisi ──────────────────────────────────────────────────────
# spl_vs_sq_profile değeri ile woofer qs_profile eşleştirmesi
_PROFILE_COMPAT: dict[str, set[str]] = {
    "sql":              {"sql", "sql_to_spl", "sq_sql", "spl_sql_border"},
    "sql_to_spl":       {"sql_to_spl", "spl_sql_border", "sql", "spl"},
    "spl":              {"spl", "spl_sql_border", "sql_to_spl"},
    "spl_sql_border":   {"spl_sql_border", "sql_to_spl", "spl", "sql"},
    "sq_sql":           {"sq_sql", "sql"},
    "spl_or_sql":       {"sql", "sql_to_spl", "spl_sql_border"},
    "unknown":          {"sql", "sq_sql", "sql_to_spl"},
}

MAX_CANDIDATES = 4
# RMS tolerans: kullanıcının gücünün %40 - %200 arası uygun
RMS_LOW_RATIO  = 0.40
RMS_HIGH_RATIO = 2.00


def _score_candidate(
    entry: dict,
    brand: str,
    diameter_inch: float,
    rms_power: float,
    spl_sq_profile: str,
) -> float:
    """Katalog girdisini verilen kriterlere göre puanla."""
    score = 0.0

    # 1. Marka eşleşmesi
    if brand and entry["brand"].lower().startswith(brand.lower()[:3]):
        score += 5.0
    elif brand and brand.lower() in entry["brand"].lower():
        score += 3.0

    # 2. Çap eşleşmesi
    diam_match = abs(entry["diameter_inch"] - diameter_inch)
    if diam_match == 0:
        score += 4.0
    elif diam_match == 1:
        score += 2.0
    elif diam_match == 2:
        score += 0.5
    else:
        return 0.0   # 3+ inç fark — aday değil

    # 3. RMS bant uyumu
    if rms_power > 0:
        low  = rms_power * RMS_LOW_RATIO
        high = rms_power * RMS_HIGH_RATIO
        entry_rms = entry["rms_w"]
        if low <= entry_rms <= high:
            # Kullanıcı gücüne ne kadar yakın?
            ratio = entry_rms / rms_power
            score += 3.0 * (1.0 - abs(1.0 - ratio))
        else:
            # Bant dışı ama çok uzak değilse yine de ekle
            if entry_rms < low * 0.5 or entry_rms > high * 2:
                return 0.0
            score += 0.5

    # 4. Profil uyumu
    compat = _PROFILE_COMPAT.get(spl_sq_profile, {"sql", "sq_sql"})
    if entry.get("qs_profile") in compat:
        score += 2.0

    return score


def get_model_candidates(
    brand: str = "",
    diameter_inch: float = 12,
    rms_power: float = 500,
    spl_sq_profile: str = "sql",
    max_count: int = MAX_CANDIDATES,
) -> list[dict]:
    """
    Verilen kriterlere göre model adaylarını seçer.

    Returns: Sıralı aday listesi (max max_count), her biri:
      {brand, model, diameter_inch, rms_w, character_tag, use_type, why_recommend, score}
    """
    catalog = _load_catalog()

    scored: list[tuple[float, dict]] = []
    for entry in catalog:
        s = _score_candidate(entry, brand, diameter_inch, rms_power, spl_sq_profile)
        if s > 0:
            scored.append((s, entry))

    if not scored:
        # Fallback: sadece çap eşleşmesi
        for entry in catalog:
            if abs(entry["diameter_inch"] - diameter_inch) <= 1:
                scored.append((1.0, entry))

    scored.sort(key=lambda x: x[0], reverse=True)

    # Çeşitlilik: farklı character_tag'li adaylar seç
    result: list[dict] = []
    seen_chars: set[str] = set()
    seen_brands: dict[str, int] = {}

    # 1. geçiş: en yüksek skoru al
    for score, entry in scored:
        if len(result) >= max_count:
            break
        ctag = entry.get("character_tag", "")
        brand_key = entry["brand"]
        # Aynı markadan max 2 aday
        if seen_brands.get(brand_key, 0) >= 2:
            continue
        result.append({
            "brand":         entry["brand"],
            "model":         entry["model"],
            "diameter_inch": entry["diameter_inch"],
            "rms_w":         entry["rms_w"],
            "character_tag": ctag,
            "use_type":      entry.get("use_type", ""),
            "why_recommend": entry.get("why_recommend", ""),
            "coil":          entry.get("coil", ""),
            "score":         round(score, 2),
        })
        seen_chars.add(ctag)
        seen_brands[brand_key] = seen_brands.get(brand_key, 0) + 1

    return result
