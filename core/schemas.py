"""
DD1 Platform — API Schemas (Pydantic v2)
"""
from pydantic import BaseModel, Field
from typing import Optional, Literal
from enum import Enum


class EnclosureType(str, Enum):
    sealed  = "sealed"
    ported  = "ported"
    aero    = "aero"


# ── Request Models ──────────────────────────────────────────────────────────

class DesignRequest(BaseModel):
    # Woofer — either model name OR manual TS params (optional for Empirical)
    woofer_model: Optional[str] = Field(None, example="Hertz HV 300")
    fs:  Optional[float] = Field(None, ge=10, le=200, description="Resonance freq (Hz)")
    qts: Optional[float] = Field(None, ge=0.1, le=2.0)
    vas: Optional[float] = Field(None, ge=1, le=500, description="Equivalent air vol (L)")
    sd:  Optional[float] = Field(None, ge=50, le=3000)
    xmax: Optional[float] = Field(None, ge=1, le=100)
    re:  Optional[float] = Field(None, ge=0.5, le=20)

    # Basic Info
    diameter_inch: int = Field(12, ge=5, le=24)
    rms_power: float = Field(500, ge=50, le=10000)
    vehicle: str = Field("Sedan")
    purpose: str = Field("SQL")
    bass_char: str = Field("Müzik Temiz Olsun")
    sub_dir: str = Field("Arkaya baksın")

    # Acoustic targets
    target_volume_l:  Optional[float] = Field(None, ge=5,  le=500, example=45.0)
    target_freq_hz:   Optional[float] = Field(None, ge=20, le=200, example=45.0)
    enclosure_type:   EnclosureType = EnclosureType.aero

    # Build params
    material_thickness_mm: float = Field(18.0, ge=6, le=40)
    kerf_mm: float = Field(0.15, ge=0.0, le=1.0)
    woofer_hole_mm: Optional[float] = Field(None, description="Manual override")


class ValidateRequest(BaseModel):
    w_mm: float
    h_mm: float
    d_mm: float
    port_dia_mm: float
    port_len_mm: float
    thickness_mm: float = 10.0
    enc_type: EnclosureType = EnclosureType.aero


# ── Response Models ──────────────────────────────────────────────────────────

class PortSpec(BaseModel):
    type: str
    dia_mm: Optional[float] = None
    length_mm: float
    count: int = 1


class Dimensions(BaseModel):
    w_mm: float
    h_mm: float
    d_mm: float


class DesignResponse(BaseModel):
    design_id: str
    mode: str
    dimensions: Dimensions
    port: PortSpec
    net_volume_l: float
    tuning_hz: float
    f3_hz: float
    port_velocity_ms: float
    peak_spl_db: float
    cone_excursion_mm: float
    group_delay_ms: float
    validation_passed: bool
    acoustic_advice: str
    expert_comment: str
    notes: list[str] = []
    panel_list: list[dict] = []
    dxf_url: Optional[str] = None   # Populated for premium users
    stl_url: str


class WooferRecord(BaseModel):
    model: str
    brand: str
    dia_mm: float
    fs: float
    qts: float
    vas: float
    xmax_mm: Optional[float] = None
    power_w: Optional[float] = None


class SearchResponse(BaseModel):
    count: int
    results: list[WooferRecord]
