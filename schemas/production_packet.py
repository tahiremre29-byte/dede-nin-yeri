"""
schemas/production_packet.py
ProductionPacket — Lazer Ajanı'nın ürettiği çıktı paketi.

Lazer Ajanı yalnızca bu dosyadaki EK ALANLARI doldurabilir.
Akustik alanlara müdahale yasak — validator tarafından kontrol edilir.
"""
from __future__ import annotations
from pydantic import BaseModel, Field
from typing import Optional, Literal
from datetime import datetime
import uuid

from schemas.acoustic_design_packet import AcousticDesignPacket


ExportFormat = Literal["DXF", "SVG", "STL", "PDF", "DXF+STL"]

JointProfile = Literal[
    "standard_3mm",
    "standard_6mm",
    "reinforced_12mm",
    "none"
]


class NestingLayout(BaseModel):
    """Panel yerleşim optimizasyonu çıktısı."""
    sheet_width_mm:  float = 1200.0
    sheet_height_mm: float = 600.0
    panel_count:     int   = 0
    utilization_pct: float = 0.0
    panels:          list[dict] = Field(default_factory=list)


class ProductionFiles(BaseModel):
    """Üretilen dosya yolları."""
    dxf:  Optional[str] = None
    svg:  Optional[str] = None
    stl:  Optional[str] = None
    pdf:  Optional[str] = None


class ProductionPacket(BaseModel):
    """
    Lazer Ajanı çıktısı.
    Acoustic Design Packet referansını kırılamaz biçimde taşır.
    Lazer Ajanı buradaki acoustic_fingerprint'i değiştiremez.
    """
    production_id:  str = Field(default_factory=lambda: f"prd_{uuid.uuid4().hex[:8]}")
    timestamp:      str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    design_id:      str = ""          # AcousticDesignPacket.design_id

    # ── Akustik referans (kırılamaz) ──────────────────────────────
    acoustic_fingerprint: dict = Field(
        default_factory=dict,
        description="AcousticDesignPacket.immutable_fingerprint() çıktısı — değiştirilmez"
    )

    # ── Lazer Ajanı'nın EKLEYEBİLECEĞİ alanlar ──────────────────
    finger_joint_profile: JointProfile            = "standard_6mm"
    decorative_layers:    list[str]               = Field(default_factory=list)
    export_format:        ExportFormat            = "DXF"
    nesting_layout:       Optional[NestingLayout] = None
    production_notes:     str                     = ""

    # Material
    material_type:        str   = "MDF"
    material_thickness_mm: float = 18.0
    kerf_mm:              float = 0.15

    # Çıktı dosyaları
    files: ProductionFiles = Field(default_factory=ProductionFiles)

    # Doğrulama
    validation: dict = Field(default_factory=lambda: {
        "immutable_check": False,
        "volume_ok":       False,
        "port_ok":         False,
        "files_generated": False,
    })


def create_production_packet(
    acoustic: AcousticDesignPacket,
    joint:    JointProfile = "standard_6mm",
    fmt:      ExportFormat = "DXF",
    material: str = "MDF",
    thickness: float = 18.0,
) -> ProductionPacket:
    """ProductionPacket factory — Lazer Ajanı bu fonksiyonu çağırır."""
    return ProductionPacket(
        design_id=acoustic.design_id,
        acoustic_fingerprint=acoustic.immutable_fingerprint(),
        finger_joint_profile=joint,
        export_format=fmt,
        material_type=material,
        material_thickness_mm=thickness,
    )
