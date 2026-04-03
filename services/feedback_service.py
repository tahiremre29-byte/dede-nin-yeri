"""
services/feedback_service.py
DD1 Feedback Servisi

User feedback → FeedbackPacket → knowledge/feedback_log.json

Mevcut core/learning_engine.py'yi sarar (duplıkasyon yok).
"""
from __future__ import annotations
import json
import logging
from pathlib import Path
from datetime import datetime

from schemas.feedback_packet import FeedbackPacket, build_feedback

logger = logging.getLogger("dd1.feedback_service")

_KNOWLEDGE_DIR = Path(__file__).parent.parent / "knowledge"
_FEEDBACK_LOG  = _KNOWLEDGE_DIR / "feedback_log.json"


def _load_log() -> list[dict]:
    if _FEEDBACK_LOG.exists():
        try:
            with open(_FEEDBACK_LOG, encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return []
    return []


def _save_log(entries: list[dict]) -> None:
    _KNOWLEDGE_DIR.mkdir(parents=True, exist_ok=True)
    with open(_FEEDBACK_LOG, "w", encoding="utf-8") as f:
        json.dump(entries, f, ensure_ascii=False, indent=2)


def save_feedback(packet: FeedbackPacket) -> bool:
    """FeedbackPacket'i log dosyasına ekler. True → başarılı."""
    try:
        entries = _load_log()
        entries.append(packet.model_dump())
        _save_log(entries)
        logger.info(
            "[FEEDBACK_SERVICE] Kaydedildi: %s rating=%d/5",
            packet.feedback_id, packet.rating
        )
        return True
    except Exception as exc:
        logger.error("[FEEDBACK_SERVICE] Kayıt hatası: %s", exc)
        return False


def submit_feedback(
    design_id: str,
    rating: int,
    comment: str = "",
    **kwargs,
) -> dict:
    """
    FastAPI /feedback endpoint'i bu fonksiyonu çağırır.
    build_feedback → save_feedback → yanıt
    """
    packet = build_feedback(design_id=design_id, rating=rating,
                            comment=comment, **kwargs)
    ok = save_feedback(packet)
    return {
        "feedback_id": packet.feedback_id,
        "success": ok,
        "message": "Geri bildiriminiz kaydedildi." if ok
                   else "Kayıt sırasında hata oluştu.",
    }


def get_report() -> dict:
    """
    feedback_log.json'dan istatistik raporu üretir.
    Mevcut learning_engine.get_feedback_report() ile aynı mantık,
    tek kaynak burada.
    """
    entries = _load_log()
    if not entries:
        return {"total": 0, "average_rating": 0, "top_woofers": [], "top_vehicles": []}

    total = len(entries)
    avg   = sum(e.get("rating", 0) for e in entries) / total

    woofer_ratings: dict[str, list[float]] = {}
    vehicle_ratings: dict[str, list[float]] = {}

    for e in entries:
        wm = e.get("woofer_model") or "bilinmiyor"
        veh = e.get("vehicle") or "bilinmiyor"
        r = float(e.get("rating", 0))
        woofer_ratings.setdefault(wm, []).append(r)
        vehicle_ratings.setdefault(veh, []).append(r)

    top_woofers = sorted(
        [{"model": k, "avg": sum(v)/len(v)} for k, v in woofer_ratings.items()],
        key=lambda x: x["avg"], reverse=True
    )[:5]

    top_vehicles = sorted(
        [{"vehicle": k, "avg": sum(v)/len(v)} for k, v in vehicle_ratings.items()],
        key=lambda x: x["avg"], reverse=True
    )[:5]

    return {
        "total": total,
        "average_rating": round(avg, 2),
        "top_woofers": top_woofers,
        "top_vehicles": top_vehicles,
    }
