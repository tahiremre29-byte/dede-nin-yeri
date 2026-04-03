"""
schemas/acoustic_design_packet.py
AcousticDesignPacket — Kabin Ustası'nın ürettiği İMMUTABLE akustik paket.

KURAL: locked=True olduğunda Lazer Ajanı aşağıdaki alanları DEĞİŞTİREMEZ:
  net_volume_l, tuning_hz, port_area_cm2, port_length_cm,
  internal_volume_constraints, acoustic_notes, enclosure_type

Lazer Ajanı yalnızca ek üretim alanları EKLEYEBİLİR.
"""
from __future__ import annotations
from pydantic import BaseModel, Field, model_validator
from typing import Optional, Literal
from datetime import datetime
import hashlib, json, uuid


DesignMode = Literal["MODE1_TS", "MODE2_EMPIRICAL"]


class DimensionSpec(BaseModel):
    w_mm: float
    h_mm: float
    d_mm: float


class PortSpec(BaseModel):
    type:              str   = "aero"
    dia_mm:            Optional[float] = None
    width_mm:          Optional[float] = None    # Slot port genışlık
    height_mm:         Optional[float] = None    # Slot port yükseklik
    length_mm:         float = 0.0
    count:             int   = 1
    area_cm2:          float = 0.0
    fold_direction:    str   = "single"           # single | folded_once | folded_twice
    mouth_orientation: str   = "front"            # front | side | rear
    fit_validated:     bool  = False              # Fiziksel sığma doğrulandı mı?


class InternalConstraints(BaseModel):
    """Lazer ajanının iç hacmi bozmaması için referans sınırları."""
    min_net_volume_l: float
    max_net_volume_l: float
    baffle_thickness_mm: float
    woofer_hole_mm: float


class AcousticDesignPacket(BaseModel):
    """
    Kabin Ustası çıktısı — KILITLI akustik paket.
    Bu paketin hash'i ProductionPacket içinde saklanır.
    Herhangi bir kilitli alana müdahale ProductionValidator tarafından engellenir.
    """
    design_id:    str  = Field(default_factory=lambda: f"dd1_{uuid.uuid4().hex[:8]}")
    timestamp:    str  = Field(default_factory=lambda: datetime.utcnow().isoformat())
    version:      str  = "1.0"
    locked:       bool = True       # Lazer Ajanı bu alanı False yapamaz

    # ── Kaynak izleme ─────────────────────────────────────────────
    intake_id:        str = ""
    mode:             DesignMode = "MODE1_TS"
    subwoofer_model:  str = ""
    diameter_inch:    int = 12
    vehicle:          str = "Sedan"
    purpose:          str = "SQL"
    rms_power:        float = 500.0

    # ── Driver Identity — Dürüstlük katmanı ─────────────────
    exact_driver_name: str   = ""     # Örn: "JBL GT-S12" veya "12\" ampirik"
    driver_source:     str   = ""     # db_exact | db_fuzzy | user_manual | empirical
    ts_source:         str   = ""     # user_manual | db | empirical_table
    ts_confidence:     float = 0.0    # 0.0–1.0
    fit_validation_summary: str = "" # Fiziksel montaj özeti

    # ── KİLİTLİ AKUSTİK ALANLAR ──────────────────────────────────
    # Lazer Ajanı bunlara dokunmaz
    net_volume_l:     float = Field(..., ge=5, le=600)
    tuning_hz:        float = Field(..., ge=15, le=120)
    port_area_cm2:    float = Field(..., ge=10)
    port_length_cm:   float = Field(..., ge=1)
    enclosure_type:   str   = "aero"
    internal_volume_constraints: InternalConstraints
    acoustic_notes:   str   = ""

    # ── Ek bilgi (kilitli değil ama Lazer değiştirmez) ───────────
    dimensions:        DimensionSpec
    port:              PortSpec
    f3_hz:             float = 0.0
    port_velocity_ms:  float = 0.0
    peak_spl_db:       float = 0.0
    group_delay_ms:    float = 0.0
    cone_excursion_mm: float = 0.0
    panel_list:        list[dict] = Field(default_factory=list)

    # ── Güven ─────────────────────────────────────────────────────
    confidence:        float = Field(0.9, ge=0.0, le=1.0)
    validation_passed: bool  = True
    risk_notes:        list[str] = Field(default_factory=list)

    # ── Paket bütünlük hash'i ─────────────────────────────────────
    packet_hash:       str  = ""

    # ── Çakışma Raporu ────────────────────────────────────────────
    conflict_report_dict: dict | None = None

    @model_validator(mode="after")
    def compute_hash(self) -> "AcousticDesignPacket":
        """
        Kilitli AKUSTİK alanların hash'i.
        design_id DAHIL DEĞİL — her çağrıda farklı UUID üretilir,
        hash yalnızca akustik değerlere bağlı olmalı.
        """
        if not self.packet_hash:
            locked_data = {
                "net_volume_l":   round(self.net_volume_l, 4),
                "tuning_hz":      round(self.tuning_hz, 4),
                "port_area_cm2":  round(self.port_area_cm2, 4),
                "port_length_cm": round(self.port_length_cm, 4),
                "enclosure_type": self.enclosure_type,
            }
            self.packet_hash = hashlib.sha256(
                json.dumps(locked_data, sort_keys=True).encode()
            ).hexdigest()[:16]
        return self


    def immutable_fingerprint(self) -> dict:
        """Kilitli alanların anlık görüntüsü — validator karşılaştırması için."""
        return {
            "net_volume_l":   self.net_volume_l,
            "tuning_hz":      self.tuning_hz,
            "port_area_cm2":  self.port_area_cm2,
            "port_length_cm": self.port_length_cm,
            "enclosure_type": self.enclosure_type,
            "packet_hash":    self.packet_hash,
        }
