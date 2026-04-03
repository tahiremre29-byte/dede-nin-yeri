"""
DD1 Platform — Woofer Arama Router
GET  /woofers/search?q=hertz
GET  /woofers/{model}
POST /woofers/add     — Manuel woofer ekle
POST /woofers/fetch   — URL'den öğren
"""
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Optional
from core.schemas import SearchResponse, WooferRecord
import core.thiele_small as ts_db
from core.learning_engine import add_woofer_manual, fetch_and_learn

router = APIRouter(prefix="/woofers", tags=["Woofer DB"])


# ── Request Modelleri ────────────────────────────────────────────────────────

class WooferAddRequest(BaseModel):
    model:    str
    brand:    str
    dia_mm:   float
    fs:       float
    qts:      float
    vas:      float
    xmax_mm:  float
    power_w:  int

class WooferFetchRequest(BaseModel):
    source_url: str
    key_map: Optional[dict] = None


# ── Mevcut Endpointler ───────────────────────────────────────────────────────

@router.get("/search", response_model=SearchResponse)
def search_woofers(q: str = Query(..., min_length=2, description="Marka veya model adı")):
    results = ts_db.search(q)
    if not results:
        raise HTTPException(404, detail=f"'{q}' için sonuç bulunamadı.")
    return SearchResponse(count=len(results), results=[WooferRecord(**w) for w in results])


@router.get("/{model}", response_model=WooferRecord)
def get_woofer(model: str):
    w = ts_db.get_by_model(model)
    if not w:
        raise HTTPException(404, detail=f"Model '{model}' bulunamadı.")
    return WooferRecord(**w)


# ── Yeni: Learning Engine Endpointleri ──────────────────────────────────────

@router.post("/add")
def add_woofer(req: WooferAddRequest):
    """Manuel woofer parametresi ekle — woofers.json'a kalıcı kaydeder."""
    result = add_woofer_manual(req.model_dump())
    if not result["success"]:
        raise HTTPException(400, detail=result["error"])
    return result


@router.post("/fetch")
def fetch_woofers(req: WooferFetchRequest):
    """
    Harici bir URL'den JSON formatında woofer listesi çek ve veritabanını güncelle.
    Duplicate kayıtlar otomatik atlanır.
    """
    result = fetch_and_learn(req.source_url, req.key_map)
    if not result.get("success"):
        raise HTTPException(502, detail=result.get("error", "Bilinmeyen hata"))
    return result

