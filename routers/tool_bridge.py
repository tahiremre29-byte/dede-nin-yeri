from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, validator
from typing import Literal
from pathlib import Path
from services.tool_bridge_service import calculate_acoustic_bridge, produce_dxf_bridge

router = APIRouter(prefix="/api/design", tags=["ToolBridge"])

class DesignRequest(BaseModel):
    session_id: str | None = None
    vehicle: Literal["Sedan", "SUV", "Truck", "Cabin"] = Field(..., description="Vehicle type")
    purpose: Literal["home", "studio", "car", "custom"] = Field(..., description="Intended use")
    diameter_inch: int = Field(..., gt=0, description="Speaker diameter in inches")
    rms_power: int = Field(..., gt=0, description="RMS power in watts")
    material_thickness_mm: int = Field(..., gt=0, le=30, description="Material thickness, realistic production range (1‑30 mm)")
    port_type: Literal["ported", "sealed", "bandpass"] = Field(...)

    @validator("purpose")
    def purpose_matches_vehicle(cls, v, values):
        # simple sanity: no contradictory combos (example rule)
        if values.get("vehicle") == "Cabin" and v != "custom":
            raise ValueError("Cabin vehicles must have purpose 'custom'")
        return v

class ProduceRequest(BaseModel):
    session_id: str | None = None
    design_id: str = Field(..., description="ID of the locked acoustic design")
    model_config = {"extra": "forbid"}

@router.post("/calculate")
async def calculate_endpoint(request: DesignRequest):
    """
    KİLİT KURAL UYGULAMASI: 
    Bu endpoint SADECE akustik hesaplamaları (kabin litresi, port vs.) yapar
    ve sonucu mühürleyerek kilitli AcousticPacket'i veri tabanına kaydeder.
    """
    try:
        result = calculate_acoustic_bridge(request.dict())
        return {
            "status": "ok",
            "design_id": result["design_id"],
            "summary": result.get("summary"),
            "message": result["message"],
            "net_volume_l": result.get("net_volume_l"),
            "tuning_hz": result.get("tuning_hz")
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/produce")
async def produce_endpoint(request: ProduceRequest):
    """
    KİLİT KURAL UYGULAMASI:
    Bu endpoint SADECE kilitlenmiş akustik paketi alır ve DXF/Üretim dosyasına 
    çevirir. Akustik değerlerde ASLA optimizasyon veya yorumlama yapamaz.
    """
    try:
        output_dir = Path(__file__).resolve().parents[2] / "output"
        output_dir.mkdir(parents=True, exist_ok=True)
        # Note: log_production inside bridge relies on session_id being passed or fallback
        result = produce_dxf_bridge(request.design_id, output_dir=output_dir, session_id=request.session_id)
        return {
            "status": "ok",
            "design_id": result["design_id"],
            "download_url": f"/api/design/download/{result['design_id']}?session_id={request.session_id or ''}",
            "message": result["message"]
        }
    except Exception as e:
        from services.history_service import history_db
        history_db.log_production(session_id=request.session_id, design_id=request.design_id, status="failed", error=str(e))
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/download/{design_id}")
async def download_endpoint(design_id: str, session_id: str = None):
    from fastapi.responses import FileResponse
    from services.history_service import history_db
    from core.config import cfg
    
    # 1. Access Control Logic
    access_mode = cfg.dxf_download_policy
    if access_mode != "open" and access_mode != "admin_free":
        history_db.log_download(session_id=session_id, design_id=design_id, status="failed:blocked", access_mode=access_mode)
        if access_mode == "paid_per_file":
            raise HTTPException(status_code=402, detail={"error": "Payment Required", "message": "Bu DXF dosyası tekil indirme ücretine tabidir. Lütfen ödeme adımına ilerleyin.", "code": "PAYMENT_NEEDED"})
        elif access_mode == "premium_subscription":
            raise HTTPException(status_code=403, detail={"error": "Forbidden", "message": "Bu işlem için Premium Üyelik gereklidir. Aboneliğinizi yükseltin.", "code": "UPGRADE_REQUIRED"})
        else:
            raise HTTPException(status_code=403, detail="Entitlement check failed.")
        
    output_dir = Path(__file__).resolve().parents[2] / "output"
    file_path = output_dir / f"{design_id}.dxf"
    if not file_path.is_file():
        history_db.log_download(session_id=session_id, design_id=design_id, status="failed:not_found", access_mode=access_mode)
        raise HTTPException(status_code=404, detail="DXF file not found")
        
    history_db.log_download(session_id=session_id, design_id=design_id, status="success", access_mode=access_mode)
    return FileResponse(file_path, media_type="application/dxf", filename=f"{design_id}.dxf")
