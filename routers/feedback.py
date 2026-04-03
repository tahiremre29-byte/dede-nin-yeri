"""
DD1 Platform — Feedback Router
POST /feedback          — Tasarım değerlendir
GET  /feedback/report   — İstatistik raporu
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional
from core.learning_engine import save_feedback, get_feedback_report

router = APIRouter(prefix="/feedback", tags=["Feedback"])


class FeedbackRequest(BaseModel):
    design_id:     str
    rating:        int   = Field(..., ge=1, le=5, description="1 (kötü) — 5 (mükemmel)")
    comment:       Optional[str] = ""
    woofer_model:  Optional[str] = ""
    diameter_inch: Optional[int] = 0
    vehicle:       Optional[str] = ""
    purpose:       Optional[str] = ""


@router.post("")
def submit_feedback(req: FeedbackRequest):
    """Kullanıcının tasarım değerlendirmesini kaydet."""
    result = save_feedback(
        design_id     = req.design_id,
        rating        = req.rating,
        comment       = req.comment or "",
        woofer_model  = req.woofer_model or "",
        diameter_inch = req.diameter_inch or 0,
        vehicle       = req.vehicle or "",
        purpose       = req.purpose or "",
    )
    if not result["success"]:
        raise HTTPException(400, detail=result["error"])
    return result


@router.get("/report")
def feedback_report():
    """Tüm geri bildirimlerin istatistik özetini döner."""
    return get_feedback_report()
