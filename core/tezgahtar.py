"""
dd1_platform/core/tezgahtar.py
Tezgahtar Sunum Katmanı

Görev:
  model_kandidat.py'den gelen aday listesini kullanıcıya
  usta/tezgahtar dilinde sunar.

Mod ayrımı:
  - usta: teknik doğruluk (validator çıktısı)
  - tezgahtar: ürün sunumu (bu modül)
  - ticari: marka anlaşmalı ürünler görünür (gelecek faz)

Ticari etik kuralı:
  Sponsorlu / anlaşmalı ürün varsa sadece teknik uygunsa öne alınır.
  Uygun değilse zorla önerilmez.
  Sistem güveni satıştan önce gelir.

Çıktı:
  {
    "reply": str,              ← Kullanıcıya gönderilecek metin (usta dili)
    "candidates": list[dict],  ← UI card listesi
    "question": str,           ← Tek kapanış sorusu
    "mode": "tezgahtar"
  }

Test: tests/core/test_tezgahtar.py
"""
from __future__ import annotations

from typing import Optional


# ── Karakter etiketi → kısa açıklama haritası ────────────────────────────────
_CHAR_DESC: dict[str, str] = {
    "giriş seviye":   "Bütçe dostu, günlük başlangıç kurgusu",
    "günlük tok":     "Kontrollü tok bas, sürekli dinlemeye dayanıklı",
    "dengeli":        "Ne çok sert ne çok yumuşak, ortada güvenli",
    "sert karakter":  "Güçlü ve agresif, cadde / SPL için",
    "güçlü":          "Yüksek watt kapasiteli, büyük hacim gerektirir",
    "dışa dönük":     "Bagaj sahne ve show için tasarlanmış",
    "dengeli güçlü":  "Hem güçlü hem kontrollü, SUV / panelvan için",
}


def _char_line(candidate: dict) -> str:
    ctag = candidate.get("character_tag", "")
    desc = _CHAR_DESC.get(ctag, ctag)
    return desc


def _format_candidate_text(idx: int, candidate: dict) -> str:
    """Tek bir aday için tezgahtar dili metin satırı."""
    labels = {0: "En uygun", 1: "Karakter alternatifi", 2: "Bütçe alternatifi", 3: "Ekstra alternatif"}
    label = labels.get(idx, f"Seçenek {idx+1}")

    brand  = candidate["brand"]
    model  = candidate["model"]
    diam   = candidate["diameter_inch"]
    rms    = candidate["rms_w"]
    ctag   = candidate.get("character_tag", "")
    why    = candidate.get("why_recommend", "")
    char_desc = _char_line(candidate)

    return (
        f"  [{label}] {brand} {model} — {diam}\" / {rms}W RMS\n"
        f"   Karakter: {ctag} → {char_desc}\n"
        f"   {why}"
    )


def _build_reply(
    intro: str,
    candidates: list[dict],
    closing_question: str,
) -> str:
    """Tezgahtar metni birleştir."""
    lines = [intro, ""]
    for i, cand in enumerate(candidates):
        lines.append(_format_candidate_text(i, cand))
        lines.append("")
    lines.append(closing_question)
    return "\n".join(lines)


# ── Ana API ───────────────────────────────────────────────────────────────────

def present_candidates(
    candidates: list[dict],
    brand: str = "",
    diameter_inch: float = 12,
    rms_power: float = 500,
    spl_sq_profile: str = "sql",
    user_intent: str = "",
    sponsored_models: Optional[list[str]] = None,  # gelecek: ticari ürünler
) -> dict:
    """
    Aday listesini tezgahtar diliyle sun.

    sponsored_models: teknik uygunsa öne alınacak anlaşmalı model adları.
    Returns: {reply, candidates, question, mode, ui_cards}
    """
    if not candidates:
        return {
            "reply":      "Bu ölçü ve güç için uygun aday bulunamadı. Farklı çap veya marka deneyelim.",
            "candidates": [],
            "question":   "Çap veya güç için alternatif bakalım mı?",
            "mode":       "tezgahtar",
            "ui_cards":   [],
        }

    # Sponsorlu ürünü öne al (teknik uygunsa)
    if sponsored_models:
        ordered: list[dict] = []
        rest: list[dict] = []
        for cand in candidates:
            if cand["model"] in sponsored_models:
                ordered.insert(0, cand)   # öne al
            else:
                rest.append(cand)
        candidates = ordered + rest

    # Intro cümle — niyet + marka + çap bilgisinden üret
    brand_str = f"{brand} " if brand else ""
    diam_str  = f"{int(diameter_inch)}\"" if diameter_inch else ""
    rms_str   = f"{int(rms_power)}W" if rms_power else ""

    intent_intro = _intent_to_intro(user_intent, spl_sq_profile)

    intro = (
        f"{intent_intro} "
        f"{brand_str}{diam_str}{' ' if diam_str and rms_str else ''}{rms_str} "
        f"çizgisinde birkaç aday çıkarayım. "
        f"Elindeki ürün hangisine yakın?"
    ).strip()

    # Kapanış sorusu
    closing = "Senin cihaz listelediklerimden hangisi? Seçersen o cihaza özel kabin hesabına girebiliriz."

    reply = _build_reply(intro, candidates, closing)

    # UI card listesi (frontend için yapılandırılmış)
    ui_cards = [_to_ui_card(i, c) for i, c in enumerate(candidates)]

    return {
        "reply":      reply,
        "candidates": candidates,
        "question":   closing,
        "mode":       "tezgahtar",
        "ui_cards":   ui_cards,
    }


def _intent_to_intro(user_intent: str, spl_sq_profile: str) -> str:
    """Niyet ve profile göre giriş cümlesi üret."""
    intent_map = {
        "tight_bass":            "Tok bas istiyorsun,",
        "inside_bass_priority":  "Kabin içi bas öncelikli,",
        "sql_request":           "SQL hedefin var,",
        "bagaj_acmak":           "Bagaj açma niyetin var,",
        "street_mode_build":     "Cadde mod kuruyor olacaksın,",
        "aggressive_loudness":   "Sert karakter istiyorsun,",
        "show_effect":           "Show / dışa dönük kurgu istiyorsun,",
        "balanced_inside_outside": "İki taraflı dengeli istiyorsun,",
        "non_fatiguing_loud":    "Yormayan ama sesli bir kurgu istiyorsun,",
    }
    return intent_map.get(user_intent) or (
        "SQL çizgisinde," if "sql" in spl_sq_profile
        else "SPL çizgisinde," if spl_sq_profile == "spl"
        else "Günlük kullanım için,"
    )


def _to_ui_card(idx: int, candidate: dict) -> dict:
    """Frontend için yapılandırılmış model kartı."""
    labels = ["best_match", "character_alt", "budget_alt", "extra_alt"]
    return {
        "card_type":     labels[idx] if idx < len(labels) else "extra_alt",
        "brand":         candidate["brand"],
        "model":         candidate["model"],
        "diameter_inch": candidate["diameter_inch"],
        "rms_w":         candidate["rms_w"],
        "character_tag": candidate.get("character_tag", ""),
        "character_desc": _char_line(candidate),
        "use_type":      candidate.get("use_type", ""),
        "why_recommend": candidate.get("why_recommend", ""),
        "coil":          candidate.get("coil", ""),
        "score":         candidate.get("score", 0),
        "image_url":     None,   # gelecek: ürün görseli
        "is_sponsored":  False,  # gelecek: ticari anlaşma
    }


__all__ = ["present_candidates"]
