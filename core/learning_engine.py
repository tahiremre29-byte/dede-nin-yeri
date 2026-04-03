"""
learning_engine.py — DD1 Platform Öğrenme Motoru
İki görevi var:
  1. İnternetten / manuel girişten yeni woofer parametrelerini woofers.json'a kalıcı kaydet
  2. Kullanıcı tasarım geri bildirimlerini feedback_log.json'a kaydet ve raporla
"""

import json
import urllib.request
import urllib.error
from datetime import datetime
from pathlib import Path
from typing import Optional

BASE       = Path(__file__).parent.parent          # dd1_platform/
WOOFERS    = BASE / "data" / "woofers.json"
FEEDBACK   = BASE / "data" / "feedback_log.json"

# Woofer kaydında olması gereken alanlar ve tipleri
REQUIRED_FIELDS = {
    "model":    str,
    "brand":    str,
    "dia_mm":   (int, float),
    "fs":       (int, float),
    "qts":      (int, float),
    "vas":      (int, float),
    "xmax_mm":  (int, float),
    "power_w":  (int, float),
}


# ── Yardımcı Fonksiyonlar ────────────────────────────────────────────────────

def _load_woofers() -> list:
    try:
        return json.loads(WOOFERS.read_text(encoding="utf-8"))
    except Exception:
        return []

def _save_woofers(data: list) -> None:
    WOOFERS.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

def _load_feedback() -> list:
    try:
        return json.loads(FEEDBACK.read_text(encoding="utf-8"))
    except Exception:
        return []

def _save_feedback(data: list) -> None:
    FEEDBACK.parent.mkdir(parents=True, exist_ok=True)
    FEEDBACK.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

def _validate_woofer(params: dict) -> tuple[bool, str]:
    """Zorunlu alanları ve tiplerini kontrol eder."""
    for field, expected_type in REQUIRED_FIELDS.items():
        if field not in params:
            return False, f"Eksik alan: '{field}'"
        if not isinstance(params[field], expected_type):
            return False, f"'{field}' tipi yanlış: {type(params[field]).__name__} (beklenen: {expected_type})"
    return True, "OK"

def _model_exists(model_name: str, woofers: list) -> bool:
    """Model adına göre duplicate kontrolü (büyük/küçük harf duyarsız)."""
    name_lower = model_name.strip().lower()
    return any(w.get("model", "").strip().lower() == name_lower for w in woofers)

def _normalize_entry(params: dict) -> dict:
    """Kayıt formatını standartlaştırır."""
    return {
        "model":    str(params["model"]).strip(),
        "brand":    str(params["brand"]).strip(),
        "dia_mm":   round(float(params["dia_mm"]), 1),
        "fs":       round(float(params["fs"]), 1),
        "qts":      round(float(params["qts"]), 3),
        "vas":      round(float(params["vas"]), 1),
        "xmax_mm":  round(float(params["xmax_mm"]), 1),
        "power_w":  int(params["power_w"]),
    }


# ── Ana Fonksiyonlar ─────────────────────────────────────────────────────────

def add_woofer_manual(params: dict) -> dict:
    """
    Elle girilen woofer parametrelerini woofers.json'a kalıcı olarak ekler.
    Duplicate ise eklemez, hata döner.

    Örnek:
        add_woofer_manual({
            "model": "Hertz Mille Pro 12",
            "brand": "Hertz",
            "dia_mm": 300, "fs": 29.0, "qts": 0.27,
            "vas": 80.0, "xmax_mm": 13.5, "power_w": 900
        })
    """
    valid, msg = _validate_woofer(params)
    if not valid:
        return {"success": False, "error": msg}

    woofers = _load_woofers()

    if _model_exists(params["model"], woofers):
        return {"success": False, "error": f"Model zaten mevcut: '{params['model']}'"}

    entry = _normalize_entry(params)
    woofers.append(entry)
    _save_woofers(woofers)

    return {
        "success": True,
        "message": f"✅ Eklendi: {entry['brand']} {entry['model']}",
        "total_woofers": len(woofers),
    }


def fetch_and_learn(source_url: str, key_map: Optional[dict] = None) -> dict:
    """
    Bir URL'den JSON formatında woofer listesi çeker ve woofers.json'a ekler.
    Duplicate kayıtlar atlanır, sadece yeniler eklenir.

    Parametreler:
        source_url: JSON dizisi dönen URL
        key_map: Kaynak JSON'daki alan isimlerini DD1 formatına eşler.
                 Örnek: {"diameter": "dia_mm", "sensitivity": None}
                 None değerli alanlar atlanır.

    Varsayılan alan adları DD1 formatı ile aynıysa key_map gerekmez.
    """
    # Varsayılan key eşlemeleri (opsiyonel override)
    default_map = {
        "model":   "model",
        "brand":   "brand",
        "dia_mm":  "dia_mm",
        "fs":      "fs",
        "qts":     "qts",
        "vas":     "vas",
        "xmax_mm": "xmax_mm",
        "power_w": "power_w",
    }
    if key_map:
        default_map.update({k: v for k, v in key_map.items() if v is not None})

    # HTTP isteği
    try:
        req = urllib.request.Request(
            source_url,
            headers={"User-Agent": "DD1-LearningEngine/1.0"}
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            raw = json.loads(resp.read().decode("utf-8"))
    except urllib.error.URLError as e:
        return {"success": False, "error": f"Bağlantı hatası: {e.reason}"}
    except json.JSONDecodeError:
        return {"success": False, "error": "Geçersiz JSON formatı"}
    except Exception as e:
        return {"success": False, "error": str(e)}

    if not isinstance(raw, list):
        # Bazı API'ler -> {"data": [...]} gibi sarar
        raw = raw.get("data") or raw.get("woofers") or raw.get("results") or []

    # Alan yeniden adlandırma
    normalized_source = []
    for item in raw:
        mapped = {}
        for dd1_key, src_key in default_map.items():
            if src_key in item:
                mapped[dd1_key] = item[src_key]
        normalized_source.append(mapped)

    woofers = _load_woofers()
    added, skipped = 0, 0

    for item in normalized_source:
        valid, _ = _validate_woofer(item)
        if not valid:
            skipped += 1
            continue
        if _model_exists(item["model"], woofers):
            skipped += 1
            continue
        woofers.append(_normalize_entry(item))
        added += 1

    if added > 0:
        _save_woofers(woofers)

    return {
        "success": True,
        "added":   added,
        "skipped": skipped,
        "total_woofers": len(woofers),
        "source": source_url,
    }


def save_feedback(
    design_id: str,
    rating: int,
    comment: str = "",
    woofer_model: str = "",
    diameter_inch: int = 0,
    vehicle: str = "",
    purpose: str = "",
) -> dict:
    """
    Kullanıcının bir tasarım hakkındaki geri bildirimini kalıcı olarak kaydeder.

    rating: 1 (kötü) → 5 (mükemmel)
    """
    if not (1 <= rating <= 5):
        return {"success": False, "error": "rating 1-5 arasında olmalı"}

    feedback = _load_feedback()

    entry = {
        "id":           f"fb_{len(feedback)+1:04d}",
        "design_id":    design_id,
        "rating":       rating,
        "comment":      comment.strip(),
        "woofer_model": woofer_model.strip(),
        "diameter_inch": diameter_inch,
        "vehicle":      vehicle,
        "purpose":      purpose,
        "timestamp":    datetime.now().isoformat(timespec="seconds"),
    }

    feedback.append(entry)
    _save_feedback(feedback)

    return {
        "success": True,
        "feedback_id": entry["id"],
        "message": f"✅ Geri bildirim kaydedildi (Design: {design_id}, Puan: {rating}/5)",
    }


def get_feedback_report() -> dict:
    """
    Kayıtlı geri bildirimlerin istatistik özetini döner.
    En çok beğenilen woofer modelleri ve araç tipleri listelenir.
    """
    feedback = _load_feedback()
    if not feedback:
        return {"total": 0, "avg_rating": None, "top_woofers": [], "top_vehicles": []}

    total   = len(feedback)
    avg     = round(sum(f["rating"] for f in feedback) / total, 2)

    # Woofer bazlı ortalama puan
    woofer_scores: dict = {}
    for f in feedback:
        m = f.get("woofer_model") or "Bilinmiyor"
        woofer_scores.setdefault(m, []).append(f["rating"])

    top_woofers = sorted(
        [{"model": k, "avg": round(sum(v)/len(v), 2), "count": len(v)}
         for k, v in woofer_scores.items() if k],
        key=lambda x: x["avg"], reverse=True
    )[:5]

    # Araç bazlı ortalama puan
    vehicle_scores: dict = {}
    for f in feedback:
        v = f.get("vehicle") or "Bilinmiyor"
        vehicle_scores.setdefault(v, []).append(f["rating"])

    top_vehicles = sorted(
        [{"vehicle": k, "avg": round(sum(v)/len(v), 2), "count": len(v)}
         for k, v in vehicle_scores.items()],
        key=lambda x: x["avg"], reverse=True
    )[:5]

    # Puan dağılımı
    distribution = {str(i): sum(1 for f in feedback if f["rating"] == i) for i in range(1, 6)}

    return {
        "total":        total,
        "avg_rating":   avg,
        "distribution": distribution,
        "top_woofers":  top_woofers,
        "top_vehicles": top_vehicles,
        "last_feedback": feedback[-1]["timestamp"] if feedback else None,
    }
