"""
schemas/intake_packet.py
IntakePacket — Ses Ustası'nın Router'a ilettiği ilk paket.
Kullanıcının niyetini, araç bilgisini ve T/S durumunu içerir.
"""
from __future__ import annotations
from pydantic import BaseModel, Field
from typing import Optional, Literal
from datetime import datetime
import uuid


class TSParams(BaseModel):
    """Thiele-Small parametreleri opsiyonel blok."""
    fs:   Optional[float] = Field(None, ge=10, le=200, description="Rezonans frekansı (Hz)")
    qts:  Optional[float] = Field(None, ge=0.1, le=2.0)
    vas:  Optional[float] = Field(None, ge=1,   le=500, description="Eşdeğer hava hacmi (L)")
    xmax: Optional[float] = Field(None, ge=1,   le=100, description="Maks. sapma (mm)")
    re:   Optional[float] = Field(None, ge=0.5, le=20,  description="DC direnç (Ohm)")
    sd:   Optional[float] = Field(None, ge=50,  le=3000,description="Konik alanı (cm²)")

    @property
    def is_complete(self) -> bool:
        """Minimum hesap için fs, qts, vas üçlüsünün tam olup olmadığı."""
        return all(v is not None for v in [self.fs, self.qts, self.vas])


IntentType = Literal[
    "kabin_tasarim",    # Akustik hesap + kabin türü belirleme
    "uretim_dosyasi",   # DXF/STL üretimi (akustik paket hazır olmalı)
    "genel_tavsiye",    # Ses sistemi rehberliği
    "woofer_sorgu",     # Woofer veritabanı araması
    "feedback_gonder",  # Kullanıcı geri bildirimi
]


class IntakePacket(BaseModel):
    """
    Ses Ustası → Router → Kabin/Lazer Ajanı handoff paketi.
    Serbest metin handoff yapılmaz — tüm geçiş bu şema üzerinden olur.
    """
    intake_id:     str = Field(default_factory=lambda: f"in_{uuid.uuid4().hex[:8]}")
    timestamp:     str = Field(default_factory=lambda: datetime.utcnow().isoformat())

    # Kullanıcı niyeti
    user_intent:   IntentType = "kabin_tasarim"
    raw_message:   str = Field("", description="Orijinal kullanıcı mesajı")
    confidence:    float = Field(0.8, ge=0.0, le=1.0,
                                 description="Niyet sınıflama güven skoru")

    # Araç ve hedef
    vehicle:       str  = Field("Sedan", description="Araç tipi")
    purpose:       str  = Field("SQL",   description="SQL | SPL | LowBass | Daily")
    diameter_inch: int  = Field(12, ge=5, le=24)
    rms_power:     float = Field(500, ge=50, le=10000)

    # Woofer bilgisi
    woofer_model:  Optional[str]    = None
    has_ts_params: bool             = False
    ts_params:     Optional[TSParams] = None

    # Driver resolution meta — UI dürüstlük katmanı
    resolution_method: str  = "unknown"   # exact | fuzzy | fallback | manual | empirical
    driver_confidence: float = 0.0         # 0.0–1.0

    # Eksik alan takibi
    missing_fields: list[str]       = Field(default_factory=list,
        description="Hesap için eksik bilgiler")

    # Özel hedefler
    target_volume_l: Optional[float] = None
    target_freq_hz:  Optional[float] = None
    enclosure_type:  str             = "aero"

    # Kullanım alanı ve karakter (raw mesajdan çıkarılır)
    usage_domain:    str = Field(
        "car_audio",
        description="car_audio | outdoor | pro_audio | home_audio"
    )
    bass_char:       str = Field(
        "SQL",
        description="SQL | SPL | patlamalı | tok | günlük | flat"
    )

    def mark_complete(self) -> bool:
        """Paketin Kabin Ustası'na gönderilebilir olup olmadığı."""
        return (
            self.user_intent in ("kabin_tasarim", "uretim_dosyasi")
            and self.diameter_inch > 0
            and len(self.missing_fields) == 0
        )

    @property
    def driver_identity_confirmed(self) -> bool:
        """Driver tam teyit edildi mi? (READY badge için gerekli)"""
        return self.resolution_method in ("exact", "manual") and self.driver_confidence >= 0.8


def build_intake(
    raw_message: str,
    intent: IntentType = "kabin_tasarim",
    vehicle: str = "Sedan",
    purpose: str = "SQL",
    diameter_inch: int = 12,
    rms_power: float = 500,
    woofer_model: str | None = None,
    ts: TSParams | None = None,
    confidence: float = 0.8,
    resolution_method: str = "unknown",
    driver_confidence: float = 0.0,
    usage_domain: str = "car_audio",
    bass_char: str = "SQL",
    target_freq_hz: float | None = None,
    enclosure_type: str = "aero",
) -> IntakePacket:
    """IntakePacket factory — Ses Ustası bu fonksiyonu çağırır."""
    missing: list[str] = []
    if intent == "kabin_tasarim":
        if not woofer_model and (ts is None or not ts.is_complete):
            missing.append("woofer_model veya T/S parametreleri (fs, qts, vas)")
    # Eğer woofer model varsa ama resolution_method belirsizse
    if woofer_model and resolution_method == "unknown":
        resolution_method = "fuzzy"
        driver_confidence  = max(driver_confidence, 0.5)
    elif ts is not None and ts.is_complete and resolution_method == "unknown":
        resolution_method = "manual"
        driver_confidence  = max(driver_confidence, 0.95)
    elif resolution_method == "unknown":
        resolution_method = "empirical"
        driver_confidence  = max(driver_confidence, 0.3)
    return IntakePacket(
        raw_message=raw_message,
        user_intent=intent,
        vehicle=vehicle,
        purpose=purpose,
        diameter_inch=diameter_inch,
        rms_power=rms_power,
        woofer_model=woofer_model,
        has_ts_params=(ts is not None and ts.is_complete),
        ts_params=ts,
        confidence=confidence,
        resolution_method=resolution_method,
        driver_confidence=driver_confidence,
        missing_fields=missing,
        usage_domain=usage_domain,
        bass_char=bass_char,
        target_freq_hz=target_freq_hz,
        enclosure_type=enclosure_type,
    )
