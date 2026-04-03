"""
agents/kabin_ustasi.py
DD1 Kabin Ustası — Akustik Karar Ajanı

YETKİ SINIRI:
- DXF/STL üretimi YAPAMAZ
- IntakePacket'i alır, engine.py çağırır, AcousticDesignPacket döner
- Çıktı immutable — Lazer Ajanı değiştiremez
"""
from __future__ import annotations
import logging
from pathlib import Path
from typing import Any

from schemas.intake_packet import IntakePacket
from schemas.acoustic_design_packet import AcousticDesignPacket
from core.handoff import handoff_to_acoustic, handoff_summary
from core.validators import validate_intake, validate_acoustic

logger = logging.getLogger("dd1.kabin_ustasi")

_PROMPT_PATH = Path(__file__).parent / "prompts" / "kabin_ustasi.txt"
_SYSTEM_PROMPT: str = _PROMPT_PATH.read_text(encoding="utf-8")


class KabinUstasi:
    """
    DD1 Akustik Karar Ajanı.
    Yalnızca akustik hesap ve kabin tipi kararı verir.
    DXF/üretim kararı VERMEZ.
    """

    def __init__(self, api_key: str | None = None):
        logger.info("[KABIN USTASI] Başlatıldı")

    # ── Ana Giriş Noktası ─────────────────────────────────────────

    def design(self, intake: IntakePacket) -> dict:
        """
        IntakePacket → AcousticDesignPacket

        Döner:
          {
            "acoustic_packet": AcousticDesignPacket,
            "summary": str,
            "advice": str,
            "validation_passed": bool,
            "errors": list[str],
            "warnings": list[str],
          }
        """
        # 1. Intake doğrula
        val_in = validate_intake(intake)
        if not val_in.passed:
            return {
                "acoustic_packet": None,
                "summary": "",
                "advice": "",
                "validation_passed": False,
                "errors": val_in.errors,
                "warnings": val_in.warnings,
            }

        # 2. Motor çağrısı (core/engine.py — tek akustik kaynak)
        engine_result = self._call_engine(intake)

        # 3. AcousticDesignPacket oluştur (handoff.py fabrikası)
        packet = handoff_to_acoustic(intake, engine_result)

        # 4. Akustik paketi doğrula
        val_ac = validate_acoustic(packet)

        # 5. AI tavsiye (sadece insan yorumu — hesap DEĞIL)
        advice = self._ai_advice(packet)

        summary = handoff_summary(packet)
        logger.info("[KABIN USTASI] Tasarım tamamlandı: %s", packet.design_id)

        return {
            "acoustic_packet": packet,
            "summary": summary,
            "advice": advice,
            "validation_passed": val_ac.passed,
            "errors": val_ac.errors,
            "warnings": val_ac.warnings,
        }

    # ── Engine Çağrısı ────────────────────────────────────────────

    def _call_engine(self, intake: IntakePacket) -> dict[str, Any]:
        """
        core/engine.py'yi çağırır — tek akustik hesap merkezi.
        Bu modülde akustik matematik YOK.
        """
        # Geç import — döngüsel bağımlılığı önler
        from core.engine import design_enclosure as calculate_enclosure
        from core.schemas import DesignRequest

        params: dict[str, Any] = {
            "diameter_inch": intake.diameter_inch,
            "rms_power": intake.rms_power,
            "vehicle": intake.vehicle,
            "purpose": intake.purpose,
            "enclosure_type": intake.enclosure_type,
            "bass_char": getattr(intake, "bass_char", "SQL"),
        }

        if intake.has_ts_params and intake.ts_params and intake.ts_params.is_complete:
            ts = intake.ts_params
            params.update({
                "fs": ts.fs,
                "qts": ts.qts,
                "vas": ts.vas,
                "xmax": ts.xmax,
                "re": ts.re,
                "sd": ts.sd,
            })

        if intake.woofer_model:
            params["woofer_model"] = intake.woofer_model

        req_obj = DesignRequest(**params)
        return calculate_enclosure(req_obj)

    # ── AI Tavsiye (Hesap değil, yorum) ──────────────────────────

    def _ai_advice(self, packet: AcousticDesignPacket) -> str:
        """
        Akustik paket için insan diline yorum.
        Hesap YAPMAZ — sadece anlatır.
        AI adapter üzerinden çağrılır — SDK bilgisi yok.
        AI yoksa template tabanlı yorum döner.
        """
        # Template fallback — hizli ve guvenilir
        return self._template_advice(packet)


    @staticmethod
    def _template_advice(packet: AcousticDesignPacket) -> str:
        """AI olmadan üretilen standart saha tavsiyeleri."""
        lines = ["[Hesap Özeti]"]
        lines.append(
            f"Net hacim {packet.net_volume_l:.1f}L, "
            f"tuning {packet.tuning_hz:.0f}Hz."
        )
        if packet.port_velocity_ms and packet.port_velocity_ms > 20:
            lines.append(
                f"Port hizi yuksek ({packet.port_velocity_ms:.1f} m/s) — "
                "port agzina flare eklenebilir."
            )
        elif packet.port_velocity_ms:
            lines.append(
                f"Port hizi nominal ({packet.port_velocity_ms:.1f} m/s) — "
                "ek optimizasyon gerekmez."
            )
        if packet.peak_spl_db:
            lines.append(
                f"Teorik pik SPL tahmini {packet.peak_spl_db:.1f} dB. "
                "Gercek SPL montaj ve sinyal zincirine gore degisir."
            )
        return "\n".join(f"- {l}" if not l.startswith("[") else l for l in lines)

