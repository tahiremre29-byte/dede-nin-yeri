"""DD1 halka acik beta icin dar ve guvenli API yuzeyi."""
from __future__ import annotations

import os
from itertools import permutations
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field, model_validator

from core.learning_engine import save_feedback
from core.public_catalog import approved_model_names, approved_record, public_product_records
from services.design_service import design_from_params


router = APIRouter(prefix="/api/public", tags=["Halka Acik Beta"])


class PublicDesignRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    woofer_model: str = Field(..., min_length=1, max_length=120)
    vehicle: Literal["Sedan", "Hatchback", "SUV", "Van", "Pickup"] = "Sedan"
    purpose: Literal["SQL", "SPL", "Günlük Bass"] = "SQL"
    max_width_mm: float | None = Field(None, ge=200, le=2500)
    max_height_mm: float | None = Field(None, ge=200, le=1800)
    max_depth_mm: float | None = Field(None, ge=200, le=2500)

    @model_validator(mode="after")
    def complete_space_dimensions(self):
        values = (self.max_width_mm, self.max_height_mm, self.max_depth_mm)
        if any(value is not None for value in values) and not all(value is not None for value in values):
            raise ValueError("Alan kontrolu icin uc olcu de birlikte girilmeli.")
        return self


class PublicFeedbackRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    design_id: str = Field(..., min_length=1, max_length=80)
    rating: int = Field(..., ge=1, le=5)
    comment: str = Field("", max_length=500)
    woofer_model: str = Field("", max_length=120)
    vehicle: str = Field("", max_length=80)
    purpose: str = Field("", max_length=80)


def _production_standard() -> tuple[float, float]:
    try:
        material = float(os.environ.get("DD1_PUBLIC_MATERIAL_MM", "10"))
        kerf = float(os.environ.get("DD1_PUBLIC_KERF_MM", "0.15"))
    except ValueError as exc:
        raise HTTPException(503, detail="Uretim standardi yapilandirilamadi.") from exc

    if not 6 <= material <= 40 or not 0 <= kerf <= 1:
        raise HTTPException(503, detail="Uretim standardi yapilandirilamadi.")
    return material, kerf


def _geometry_review_required(acoustic) -> bool:
    report = acoustic.conflict_report_dict or {}
    options = report.get("options", [])
    return not any(bool(option.get("production_ready")) for option in options)


def _public_panel_list(panels: list[dict]) -> list[dict]:
    public_panels = []
    for panel in panels or []:
        public_panels.append({
            "name": panel.get("name") or panel.get("ad") or "Panel",
            "qty": panel.get("qty") or panel.get("adet") or 1,
            "w_mm": panel.get("w") or panel.get("w_mm") or panel.get("en_mm"),
            "h_mm": panel.get("h") or panel.get("h_mm") or panel.get("boy_mm"),
        })
    return public_panels


def _fit_check(req: PublicDesignRequest, acoustic) -> dict:
    available = (req.max_width_mm, req.max_height_mm, req.max_depth_mm)
    if any(value is None for value in available):
        return {"status": "not_checked"}

    box = (
        float(acoustic.dimensions.w_mm),
        float(acoustic.dimensions.h_mm),
        float(acoustic.dimensions.d_mm),
    )
    matching_rotation = next(
        (
            rotation for rotation in permutations(box)
            if all(value <= available[index] for index, value in enumerate(rotation))
        ),
        None,
    )
    if matching_rotation:
        return {
            "status": "fits",
            "orientation_mm": {
                "w": matching_rotation[0],
                "h": matching_rotation[1],
                "d": matching_rotation[2],
            },
        }
    return {"status": "does_not_fit"}


@router.get("/products")
def products():
    approved = approved_model_names()
    results = public_product_records()
    return {
        "configured": bool(approved),
        "count": len(results),
        "results": results,
    }


@router.post("/design")
def design(req: PublicDesignRequest):
    record = approved_record(req.woofer_model)
    if record is None:
        raise HTTPException(400, detail="Bu urun halka acik beta katalogunda onayli degil.")

    material, kerf = _production_standard()
    try:
        diameter_inch = max(5, round(float(record["dia_mm"]) / 25.4))
        fs = float(record["fs"])
        qts = float(record["qts"])
        vas = float(record["vas"])
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(422, detail="Bu urunun teknik verisi henuz tamamlanmadi.") from exc

    result = design_from_params(
        diameter_inch=diameter_inch,
        rms_power=float(record.get("power_w") or 500),
        vehicle=req.vehicle,
        purpose=req.purpose,
        woofer_model=req.woofer_model,
        fs=fs,
        qts=qts,
        vas=vas,
        xmax=float(record.get("xmax_mm") or 0) or None,
        sd=float(record.get("sd") or 0) or None,
        re=float(record.get("re") or 0) or None,
        enclosure_type="ported",
        usage_domain="car_audio",
        bass_char=req.purpose,
        material_thickness_mm=material,
        kerf_mm=kerf,
        resolution_method="exact",
        driver_confidence=1.0,
    )

    if not result["success"] or result.get("acoustic_packet") is None:
        raise HTTPException(422, detail="Bu urun icin guvenli bir akustik taslak olusturulamadi.")

    acoustic = result["acoustic_packet"]
    return {
        "design_id": acoustic.design_id,
        "woofer_model": req.woofer_model,
        "net_volume_l": acoustic.net_volume_l,
        "tuning_hz": acoustic.tuning_hz,
        "port": {
            "area_cm2": acoustic.port_area_cm2,
            "length_cm": acoustic.port_length_cm,
            "count": acoustic.port.count if acoustic.port else 1,
        },
        "dimensions": acoustic.dimensions.model_dump(),
        "material_thickness_mm": acoustic.material_thickness_mm,
        "kerf_mm": acoustic.kerf_mm,
        "panel_list": _public_panel_list(acoustic.panel_list),
        "fit_check": _fit_check(req, acoustic),
        "geometry_review_required": _geometry_review_required(acoustic),
    }


@router.post("/feedback")
def feedback(req: PublicFeedbackRequest):
    result = save_feedback(
        design_id=req.design_id,
        rating=req.rating,
        comment=req.comment,
        woofer_model=req.woofer_model,
        vehicle=req.vehicle,
        purpose=req.purpose,
    )
    if not result.get("success"):
        raise HTTPException(400, detail="Geri bildirim kaydedilemedi.")
    return {"success": True, "feedback_id": result.get("feedback_id")}
