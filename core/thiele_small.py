"""
DD1 Platform — Thiele-Small Woofer Veritabanı
"""
import json
import os
from pathlib import Path
from typing import Optional

_ROOT = Path(__file__).parent.parent
_DB_CANDIDATES = (
    Path(os.environ["DD1_WOOFER_DB"]) if os.environ.get("DD1_WOOFER_DB") else None,
    _ROOT / "data" / "woofers.json",
    _ROOT / "knowledge" / "woofers.json",
)
_woofers: list[dict] = []


def _load():
    global _woofers
    if _woofers:
        return

    db_path = next((p for p in _DB_CANDIDATES if p and p.exists()), None)
    if db_path is None:
        searched = ", ".join(str(p) for p in _DB_CANDIDATES if p)
        raise FileNotFoundError(f"Woofer veritabani bulunamadi. Aranan yollar: {searched}")

    with open(db_path, encoding="utf-8") as f:
        loaded = json.load(f)

    if not isinstance(loaded, list):
        raise ValueError(f"Woofer veritabani liste olmali: {db_path}")
    _woofers = loaded


def list_all() -> list[dict]:
    """Katalogdaki tüm doğrulanmış T/S kayıtlarının kopyasını döndürür."""
    _load()
    return [dict(item) for item in _woofers]


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
