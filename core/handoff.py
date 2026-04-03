"""
core/handoff.py
DD1 Ajan Geçiş Fabrikası

Ajanlar arası JSON paket oluşturma tek merkezde tutulur.
Serbest metin handoff yapılmaz — tüm geçişler bu modülden üretilen paketlerle olur.

API:
  handoff_to_acoustic(intake, engine_result) → AcousticDesignPacket
  handoff_to_production(acoustic)            → ProductionPacket (boş, doldurulacak)
  handoff_to_feedback(design_id, rating, ...)→ FeedbackPacket
"""
from __future__ import annotations
import logging
from typing import Any

from schemas.intake_packet         import IntakePacket
from schemas.acoustic_design_packet import (
    AcousticDesignPacket, DimensionSpec, PortSpec, InternalConstraints
)
from schemas.production_packet     import ProductionPacket, NestingLayout, create_production_packet
from schemas.feedback_packet       import FeedbackPacket, build_feedback

logger = logging.getLogger("dd1.handoff")


# ── 1. Kabin Ustası → Lazer Ajanı ────────────────────────────────────────────

def handoff_to_acoustic(
    intake: IntakePacket,
    engine_result: dict[str, Any],
) -> AcousticDesignPacket:
    """
    Motor çıktısını ve IntakePacket'i birleştirerek
    immutable AcousticDesignPacket üretir.

    engine_result: core/engine.py'nin döndürdüğü dict
    """
    dims = engine_result.get("dimensions", {})
    port = engine_result.get("port", {})

    dim_spec = DimensionSpec(
        w_mm=float(dims.get("w_mm", 500)),
        h_mm=float(dims.get("h_mm", 340)),
        d_mm=float(dims.get("d_mm", 400)),
    )

    port_spec = PortSpec(
        type=port.get("type", "aero"),
        dia_mm=port.get("dia_mm"),
        length_mm=float(port.get("length_mm", 200)),
        count=int(port.get("count", 1)),
        area_cm2=float(engine_result.get("port_area_cm2", 78.5)),
    )

    constraints = InternalConstraints(
        min_net_volume_l=float(engine_result.get("net_volume_l", 35)) * 0.90,
        max_net_volume_l=float(engine_result.get("net_volume_l", 35)) * 1.10,
        baffle_thickness_mm=float(intake.ts_params.re if intake.ts_params and intake.ts_params.re else 18),
        woofer_hole_mm=float(engine_result.get("woofer_hole_mm", 282)),
    )

    packet = AcousticDesignPacket(
        intake_id=intake.intake_id,
        mode=engine_result.get("mode", "MODE2_EMPIRICAL"),
        subwoofer_model=intake.woofer_model or "",
        diameter_inch=intake.diameter_inch,
        vehicle=intake.vehicle,
        purpose=intake.purpose,
        rms_power=intake.rms_power,
        # ── KİLİTLİ ALANLAR ────────────────────────────────────
        net_volume_l=float(engine_result["net_volume_l"]),
        tuning_hz=float(engine_result["tuning_hz"]),
        port_area_cm2=float(engine_result.get("port_area_cm2",
            port_spec.area_cm2)),
        port_length_cm=float(engine_result.get("port_length_cm",
            port_spec.length_mm / 10)),
        enclosure_type=intake.enclosure_type,
        internal_volume_constraints=constraints,
        acoustic_notes=engine_result.get("acoustic_advice", ""),
        # ── Ek bilgi ────────────────────────────────────────────
        dimensions=dim_spec,
        port=port_spec,
        f3_hz=float(engine_result.get("f3_hz", 0)),
        port_velocity_ms=float(engine_result.get("port_velocity_ms", 0)),
        peak_spl_db=float(engine_result.get("peak_spl_db", 0)),
        group_delay_ms=float(engine_result.get("group_delay_ms", 0)),
        cone_excursion_mm=float(engine_result.get("cone_excursion_mm", 0)),
        panel_list=engine_result.get("panel_list", []),
        validation_passed=engine_result.get("validation_passed", True),
        risk_notes=engine_result.get("notes", []),
    )

    logger.info(
        "[HANDOFF → ACOUSTIC] intake=%s design=%s vol=%.1fL tune=%.1fHz",
        intake.intake_id, packet.design_id,
        packet.net_volume_l, packet.tuning_hz,
    )
    return packet


# ── 2. Kabin Ustası → Lazer Ajanı (Boş Üretim Paketi) ───────────────────────

def handoff_to_production(
    acoustic: AcousticDesignPacket,
    joint: str = "standard_6mm",
    fmt: str = "DXF",
    material: str = "MDF",
    thickness: float = 18.0,
) -> ProductionPacket:
    """
    AcousticDesignPacket'ten boş ProductionPacket oluşturur.
    Lazer Ajanı bu paketi alır ve kendi alanlarını doldurur.
    acoustic_fingerprint burada kilitlenir.
    """
    packet = create_production_packet(
        acoustic=acoustic,
        joint=joint,
        fmt=fmt,
        material=material,
        thickness=thickness,
    )
    logger.info(
        "[HANDOFF → PRODUCTION] design=%s production=%s fmt=%s",
        acoustic.design_id, packet.production_id, fmt,
    )
    return packet


# ── 3. Feedback Handoff ───────────────────────────────────────────────────────

def handoff_to_feedback(
    design_id: str,
    rating: int,
    comment: str = "",
    **kwargs,
) -> FeedbackPacket:
    """FeedbackPacket factory — services/feedback_service bu fonksiyonu çağırır."""
    packet = build_feedback(
        design_id=design_id,
        rating=rating,
        comment=comment,
        **kwargs,
    )
    logger.info(
        "[HANDOFF → FEEDBACK] design=%s rating=%d/5",
        design_id, rating,
    )
    return packet


# ── 4. Handoff Özetleyici ─────────────────────────────────────────────────────

def handoff_summary(acoustic: AcousticDesignPacket) -> str:
    """
    Kabin Ustası→Lazer Ajanı geçişinde insana okunabilir özet.
    Log ve kullanıcı bilgilendirmesi için.
    """
    return (
        f"[Akustik Paket: {acoustic.design_id}]\n"
        f"  Mod:     {acoustic.mode}\n"
        f"  Woofer:  {acoustic.subwoofer_model or 'belirtilmedi'} {acoustic.diameter_inch}\"\n"
        f"  Hacim:   {acoustic.net_volume_l:.1f} L\n"
        f"  Tuning:  {acoustic.tuning_hz:.1f} Hz\n"
        f"  Port:    {acoustic.port_length_cm:.1f} cm  |  {acoustic.port_area_cm2:.1f} cm²\n"
        f"  Kabin:   {acoustic.enclosure_type}\n"
        f"  Hash:    {acoustic.packet_hash}\n"
    )
