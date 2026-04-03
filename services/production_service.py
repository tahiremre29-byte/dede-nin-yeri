"""
services/production_service.py
DD1 Üretim Servisi

AcousticDesignPacket → LazerAjani → ProductionPacket + dosyalar
FastAPI /export endpoint'i bu servisi çağırır.
"""
from __future__ import annotations
import logging
from typing import Optional

from schemas.acoustic_design_packet import AcousticDesignPacket
from schemas.production_packet import ProductionPacket
from agents.lazer_ajani import LazerAjani

logger = logging.getLogger("dd1.production_service")

_lazer_ajani: Optional[LazerAjani] = None


def get_lazer_ajani(output_dir: str = "output") -> LazerAjani:
    global _lazer_ajani
    if _lazer_ajani is None:
        _lazer_ajani = LazerAjani(output_dir=output_dir)
    return _lazer_ajani


def run_production(
    acoustic: AcousticDesignPacket,
    joint:    str   = "standard_6mm",
    fmt:      str   = "DXF",
    material: str   = "MDF",
    thickness: float = 18.0,
    decorative_pattern: str | None = None,
) -> dict:
    """
    Tam üretim akışı:
    AcousticDesignPacket → LazerAjani.produce() → sonuç dict

    Döner:
      {
        "production_packet": ProductionPacket | None,
        "files": dict,
        "summary": str,
        "success": bool,
        "error_code": str | None,
        "errors": list[str],
      }
    """
    try:
        agent = get_lazer_ajani()
        result = agent.produce(
            acoustic=acoustic,
            joint=joint,
            fmt=fmt,
            material=material,
            thickness=thickness,
            decorative_pattern=decorative_pattern,
        )
        logger.info(
            "[PRODUCTION_SERVICE] %s → success=%s",
            acoustic.design_id, result.get("success", False)
        )
        return result
    except Exception as exc:
        logger.error("[PRODUCTION_SERVICE] Hata: %s", exc)
        return {
            "production_packet": None,
            "files": {},
            "summary": "",
            "success": False,
            "error_code": "E_SERVICE_ERROR",
            "errors": [str(exc)],
        }
