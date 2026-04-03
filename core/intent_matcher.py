"""
dd1_platform/core/intent_matcher.py
Sokak Dili Niyet Eşleştirici — JSON Tabanlı

Görev:
  Kullanıcının ham cümlesini alır → JSON sözlükteki en yakın intent'e eşler.
  Baskın intent + opsiyonel ikincil intent döner.
  Eşleşme bulunamasa None döner (upstream fallback devreye girer).

Eşleşme stratejisi (önem sırasına göre):
  1. Exact match — utterance tam eşleşmesi
  2. Keyword match — keywords listesindeki token'lar mesajda var mı?
  3. Skorlu arama — en yüksek skorlu entry seçilir
  Minimum eşleşme skoru: MIN_SCORE = 1 (en az 1 keyword eşleşmeli)

Kullanım:
  from core.intent_matcher import match_intent, IntentMatch

  result = match_intent("bagaj açsın")
  if result:
      print(result.user_intent)      # bagaj_acmak
      print(result.example_reply)    # Usta'nın cevap stili
      print(result.clarification_question_type)

Test: tests/core/test_intent_matcher.py
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

# JSON sözlük dosyası
_SOZLUK_PATH = Path(__file__).parent.parent / "knowledge" / "intent_sozluk.json"

# Lazy load — ilk çağrıda yükle
_SOZLUK: list[dict] = []


def _load_sozluk() -> list[dict]:
    global _SOZLUK
    if not _SOZLUK:
        with open(_SOZLUK_PATH, encoding="utf-8") as f:
            _SOZLUK = json.load(f)
    return _SOZLUK


# ── Veri sınıfı ───────────────────────────────────────────────────────────────

@dataclass
class IntentMatch:
    user_intent:               str
    normalized_meaning:        str
    listening_goal:            str
    system_style:              str
    inside_vs_outside_priority: str
    spl_vs_sq_profile:         str
    clarification_question_type: str
    example_reply:             str
    confidence:                float        # 0.0 – 1.0
    secondary_intent:          Optional[str] = None


# ── Normalizer ────────────────────────────────────────────────────────────────

def _normalize(text: str) -> str:
    """Küçük harf, Türkçe karakter koru, noktalama kaldır."""
    text = text.lower().strip()
    # Noktalama kaldır (harf ve boşluk bırak)
    text = re.sub(r"[^\w\s]", " ", text, flags=re.UNICODE)
    text = re.sub(r"\s+", " ", text)
    return text


def _tokenize(text: str) -> set[str]:
    return set(_normalize(text).split())


# ── Eşleştirici ───────────────────────────────────────────────────────────────

def _score_entry(entry: dict, msg_norm: str, msg_tokens: set[str]) -> float:
    """
    Bir sözlük entry'si için eşleşme skoru hesapla.
    Keyword eşleşmesi ağırlıklı. Utterance tam eşleşmesi bonus verir.
    """
    score = 0.0

    # 1. Utterance exact match (en güçlü sinyal)
    if _normalize(entry["utterance"]) == msg_norm:
        return 100.0

    # 2. Utterance partial match
    utterance_tokens = _tokenize(entry["utterance"])
    common_utt = utterance_tokens & msg_tokens
    if common_utt:
        # Oran: kaç utterance token'ı eşleşti
        score += len(common_utt) / max(len(utterance_tokens), 1) * 3.0

    # 3. Keywords eşleşmesi
    for kw in entry.get("keywords", []):
        kw_norm = _normalize(kw)
        if kw_norm in msg_norm:
            # Uzun keyword eşleşmesi daha değerli, ama baz olarak yeterince skor ver
            score += 4.0 + len(kw_norm.split()) * 1.0

    return score


MIN_SCORE = 0.5   # Bu skoru geçemeyene None


def match_intent(message: str) -> Optional[IntentMatch]:
    """
    Kullanıcı mesajını niyet sözlüğüne eşle.

    Returns: IntentMatch ya da None (eşleşme bulunamadı)
    """
    sozluk = _load_sozluk()
    msg_norm   = _normalize(message)
    msg_tokens = _tokenize(message)

    scored: list[tuple[float, dict]] = []
    for entry in sozluk:
        s = _score_entry(entry, msg_norm, msg_tokens)
        if s > 0:
            scored.append((s, entry))

    if not scored:
        return None

    # En yüksek skoru bul
    scored.sort(key=lambda x: x[0], reverse=True)
    best_score, best = scored[0]

    if best_score < MIN_SCORE:
        return None

    # İkincil intent: farklı user_intent, en az %50 yakınlıkta
    secondary = None
    if len(scored) >= 2:
        sec_score, sec = scored[1]
        if sec_score >= best_score * 0.5 and sec["user_intent"] != best["user_intent"]:
            secondary = sec["user_intent"]

    # Normalize confidence: 0–10 aralığını 0–1'e sıkıştır
    confidence = min(best_score / 10.0, 1.0)

    return IntentMatch(
        user_intent=best["user_intent"],
        normalized_meaning=best["normalized_meaning"],
        listening_goal=best["listening_goal"],
        system_style=best["system_style"],
        inside_vs_outside_priority=best["inside_vs_outside_priority"],
        spl_vs_sq_profile=best["spl_vs_sq_profile"],
        clarification_question_type=best["clarification_question_type"],
        example_reply=best["example_reply"],
        confidence=confidence,
        secondary_intent=secondary,
    )


def get_clarification_question(match: IntentMatch) -> Optional[str]:
    """
    Eşleşen intent'e göre Sözcü'nün sorması gereken netleştirici soru tipini döner.
    Sozcu bu tipi _question_message() fallback'i için kullanabilir.
    """
    q_map = {
        "daily_vs_park":              "Günlük kullanımda mı ağır, yoksa parkta açmak mı öncelik?",
        "inside_bass_vs_outside_stage": "İçeri bas mı, yoksa dışarı yüksek sahne mi ağır basıyor?",
        "outside_vs_inside":          "Dış ses mi öncelik, içeri bas mı?",
        "vehicle_info":               "Aracın ne?",
        "vehicle_model":              "Araç modelini ver.",
        "woofer_info":                "Elindeki woofer ne?",
        "vehicle_and_trunk":          "Araç nedir, bagaj ölçüsü ne kadar?",
        "character_preference":       "Tok karakter mi, sert vuruş mu?",
        "fatigue_vs_aggression":      "Temiz de kalsın mı, sert karakter sorun değil mi?",
        "long_drive_usage":           "Uzun yol dinlemesi var mı?",
        "bass_vs_mid_high_presence":  "Mid-tiz mi öne çıksın, bas dalga gibi önce o mu?",
        "existing_gear":              "Elindeki ekipman var mı, sıfırdan mı gidiyoruz?",
        "current_system_dump":        "Mevcut sistemi yaz, neyin boğulduğuna bakalım.",
        "taste_mapping":              "Hoşuna giden şey ne: içeri bas mı, dışarı sahne mi?",
        "park_vs_drive_priority":     "Öncelik park performansı mı, sürüşte içeri etki mi?",
        "inside_vs_outside":          "İçeri bas da olsun mu, dış ses mi öncelik?",
        "daily_importance":           "Günlük kullanım da önemliyse baştan söyle.",
        "vehicle_trunk_existing_gear": "Araç, bagaj ölçüsü ve elindeki ürünleri dök.",
    }
    return q_map.get(match.clarification_question_type)
