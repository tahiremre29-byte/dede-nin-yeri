"""
DD1 Platform — Thiele-Small Woofer Veritabanı
"""
import json
from pathlib import Path
from typing import Optional

_DB_PATH = Path(__file__).parent.parent / "data" / "woofers.json"
_woofers: list[dict] = []


def _load():
    global _woofers
    if not _woofers:
        with open(_DB_PATH, encoding="utf-8") as f:
            _woofers = json.load(f)


def search(query: str, limit: int = 10) -> list[dict]:
    """Marka veya model adına göre arama."""
    _load()
    q = query.lower()
    results = [
        w for w in _woofers
        if q in w["model"].lower() or q in w.get("brand", "").lower()
    ]
    return results[:limit]


def get_by_model(model: str) -> Optional[dict]:
    """Tam model adıyla getir."""
    _load()
    m = model.lower()
    for w in _woofers:
        if w["model"].lower() == m:
            return w
    return None


def infer_woofer_hole(dia_mm: float) -> float:
    """
    Standart kesim çapı tahmini (gerçek Thiele-Small'dan türetilir):
    12" → 282mm, 10" → 234mm, 15" → 358mm
    """
    ratio = 0.94  # kesim çapı / nominal çap
    return round(dia_mm * ratio, 0)
