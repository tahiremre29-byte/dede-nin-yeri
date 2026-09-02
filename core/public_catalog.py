"""Halka acik betada gorunmesine izin verilen urun kataloğu."""
from __future__ import annotations

import json
import os
from pathlib import Path

import core.thiele_small as ts_db

_APPROVED_FILE = Path(__file__).parent.parent / "knowledge" / "approved_products.json"


def approved_model_names() -> set[str]:
    """
    Yalniz acikca onaylanan model adlarini dondurur.

    Oncelik:
      1. DD1_APPROVED_MODELS="Model A|Model B"
      2. knowledge/approved_products.json icindeki model listesi

    Hicbiri yoksa genel katalogdan urun sizdirmaz; bos set dondurur.
    """
    raw = os.environ.get("DD1_APPROVED_MODELS", "").strip()
    if raw:
        return {item.strip().casefold() for item in raw.split("|") if item.strip()}

    if not _APPROVED_FILE.exists():
        return set()

    try:
        data = json.loads(_APPROVED_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return set()

    if isinstance(data, dict):
        data = data.get("models", [])
    if not isinstance(data, list):
        return set()
    return {str(item).strip().casefold() for item in data if str(item).strip()}


def approved_records(query: str | None = None) -> list[dict]:
    approved = approved_model_names()
    results = [
        w for w in ts_db.list_all()
        if w.get("model", "").casefold() in approved
    ]
    if query:
        q = query.casefold()
        results = [
            w for w in results
            if q in w.get("model", "").casefold()
            or q in w.get("brand", "").casefold()
        ]
    return results


def public_product_records(query: str | None = None) -> list[dict]:
    """Tarayiciya yalniz urun kimligi ve temel vitrin bilgisini gonderir."""
    return [
        {
            "model": record.get("model", ""),
            "brand": record.get("brand", ""),
            "dia_mm": record.get("dia_mm"),
            "power_w": record.get("power_w"),
        }
        for record in approved_records(query)
    ]


def approved_record(model: str | None) -> dict | None:
    if not model or model.casefold() not in approved_model_names():
        return None
    return ts_db.get_by_model(model)
