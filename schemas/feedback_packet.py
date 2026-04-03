"""
schemas/feedback_packet.py
FeedbackPacket — Kullanıcı geri bildirimi.
Hem tasarım kalitesi hem de saha gerçekliği izlenir.
"""
from __future__ import annotations
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
import uuid


class FeedbackPacket(BaseModel):
    """
    Kullanıcı tasarım sonrası geri bildirimi.
    Öğrenen sistem bu veriyi feedback_log.json'a yazar.
    """
    feedback_id:       str  = Field(default_factory=lambda: f"fb_{uuid.uuid4().hex[:8]}")
    timestamp:         str  = Field(default_factory=lambda: datetime.utcnow().isoformat())

    # Hangi tasarım
    design_id:         str  = ""
    production_id:     Optional[str] = None

    # Kullanıcı puanı
    rating:            int  = Field(..., ge=1, le=5)
    comment:           str  = ""

    # Tasarım bağlamı (raporlama için)
    user_goal:         str  = ""       # SQL / SPL / Daily / LowBass
    vehicle:           str  = ""
    woofer_model:      str  = ""
    diameter_inch:     Optional[int]   = None
    proposed_volume_l: Optional[float] = None
    proposed_tuning_hz: Optional[float] = None

    # Saha gerçekliği
    actual_built:      bool = False    # Gerçekten üretildi mi?
    revision_needed:   bool = False    # Revizyon gerekti mi?
    field_note:        str  = ""       # Atölye notu

    # Sistem meta
    mode_used:         str  = ""       # MODE1_TS | MODE2_EMPIRICAL
    confidence_was:    Optional[float] = None


def build_feedback(
    design_id: str,
    rating: int,
    comment: str = "",
    user_goal: str = "",
    vehicle: str = "",
    woofer_model: str = "",
    diameter_inch: int | None = None,
    volume_l: float | None = None,
    tuning_hz: float | None = None,
    actual_built: bool = False,
    revision_needed: bool = False,
    field_note: str = "",
    mode_used: str = "",
) -> FeedbackPacket:
    """FeedbackPacket factory."""
    return FeedbackPacket(
        design_id=design_id,
        rating=rating,
        comment=comment,
        user_goal=user_goal,
        vehicle=vehicle,
        woofer_model=woofer_model,
        diameter_inch=diameter_inch,
        proposed_volume_l=volume_l,
        proposed_tuning_hz=tuning_hz,
        actual_built=actual_built,
        revision_needed=revision_needed,
        field_note=field_note,
        mode_used=mode_used,
    )
