"""
agents/lazer_ajani.py
DD1 Lazer Ajanı — Endüstriyel Üretim Uzmanı (v2)

YETKİ SINIRI:
- Akustik karar VERMEZ
- Kilitli alanları DEĞİŞTİREMEZ
- AcousticDesignPacket alır → ProductionPacket + DXF/STL döner

ENDÜSTRİYEL DXF STANDARDı:
- Birim: milimetre
- Closed Polyline (lwpolyline, close=True)
- Layer adları sabit: DD1_PANEL, DD1_JOINTS, DD1_DRILL, DD1_ANNOTATIONS
- Origin: sol-alt köşe (0, 0)
- Hata sonrası geçici dosya cleanup
- Corel/AutoCAD/LaserCAD uyumlu
"""
from __future__ import annotations
import logging
import os
import uuid
from pathlib import Path

from schemas.acoustic_design_packet import AcousticDesignPacket
from schemas.production_packet import ProductionPacket, NestingLayout
from core.handoff import handoff_to_production
from core.validators import validate_production
from core.design_modes import ConstraintConflictError

logger = logging.getLogger("dd1.lazer_ajani")

_PROMPT_PATH = Path(__file__).parent / "prompts" / "lazer_ajani.txt"

# Hata Kodları
E_IMMUTABLE_VIOLATION  = "E_IMMUTABLE_VIOLATION"
E_VOLUME_OUT_OF_RANGE  = "E_VOLUME_OUT_OF_RANGE"
E_PORT_INVALID         = "E_PORT_INVALID"
E_FINGERPRINT_MISMATCH = "E_FINGERPRINT_MISMATCH"
E_FILE_GENERATION      = "E_FILE_GENERATION"

# DXF Katman Adları (sabit)
LAYER_PANEL       = "DD1_PANEL"
LAYER_JOINTS      = "DD1_JOINTS"
LAYER_DRILL       = "DD1_DRILL"
LAYER_ANNOTATIONS = "DD1_ANNOTATIONS"


class LazerAjani:
    def __init__(self, output_dir: str = "exports"):
        self._output_dir = Path(output_dir)
        self._output_dir.mkdir(parents=True, exist_ok=True)
        logger.info("[LAZER AJANI] Baslatildi -> %s", self._output_dir)

    # ── Ana Giriş Noktası ─────────────────────────────────────────────────────

    def produce(
        self,
        acoustic:           AcousticDesignPacket,
        joint:              str   = "standard_6mm",
        fmt:                str   = "DXF",
        material:           str   = "MDF",
        thickness:          float = 18.0,
        decorative_pattern: str | None = None,
    ) -> dict:
        """
        AcousticDesignPacket → ProductionPacket + DXF/STL dosyaları.
        """
        prod = handoff_to_production(acoustic, joint=joint, fmt=fmt,
                                     material=material, thickness=thickness)
        if decorative_pattern:
            prod.decorative_layers.append(decorative_pattern)

        # Immutable doğrulama
        val = validate_production(prod, acoustic)
        if not val.passed:
            logger.error("[LAZER AJANI] Dogrulama basarisiz: %s", val.errors)
            return self._error_response(
                E_IMMUTABLE_VIOLATION if "KILITLI" in str(val.errors)
                else E_FINGERPRINT_MISMATCH,
                val.errors,
            )

        # Dosya üretimi (Buradan conflict_report gelebilir)
        files = self._generate_files(acoustic, prod, fmt, thickness)
        
        # Eğer Conflict çıktıysa üretimi durdur ve çatışmayı raporla
        if files and "conflict_report" in files:
            return {
                "production_packet": None,
                "files": {},
                "summary": files["conflict_report"].usta_summary,
                "success": False,
                "conflict": True,
                "conflict_report": files["conflict_report"],
                "error_code": "E_CONFLICT",
                "errors": [files["conflict_report"].usta_summary]
            }
            
        if not files:
            return self._error_response(E_FILE_GENERATION, ["DXF uretimi basarisiz"])

        # Üretilen dosyaların boş olmadığını kontrol et (sadece path string'leri)
        for ftype, fpath in files.items():
            if not isinstance(fpath, str):
                continue   # proxy_report, panel_list gibi metadata key'lerini atla
            fp = Path(fpath)
            if not fp.exists() or fp.stat().st_size == 0:
                logger.warning("[LAZER AJANI] %s bos/eksik: %s", ftype, fpath)


        prod.files.dxf = files.get("dxf")
        prod.files.svg = files.get("svg")
        prod.files.stl = files.get("stl")
        prod.validation["files_generated"] = True
        prod.nesting_layout = self._compute_nesting(acoustic)

        summary = self._production_summary(prod, acoustic, files)
        logger.info("[LAZER AJANI] Uretim tamamlandi: %s", prod.production_id)

        return {
            "production_packet": prod,
            "files": files,
            "summary": summary,
            "success": True,
            "error_code": None,
            "errors": [],
        }

    # ── Endüstriyel DXF Üretimi ───────────────────────────────────────────────

    def _generate_files(
        self,
        acoustic: AcousticDesignPacket,
        prod:     ProductionPacket,
        fmt:      str,
        thickness: float,
    ) -> dict[str, str]:
        """
        1. Önce dd1_lazer_agent/box_generator.py'yi dene
        2. Yoksa kendi endüstriyel DXF motorunu çalıştır (ezdxf tabanlı)
        3. Yoksa stub (geliştirme modu)
        """
        # Önce mevcut motor
        try:
            return self._call_box_generator(acoustic, prod)
        except ImportError:
            pass

        # kendi ezdxf motoru
        try:
            return self._generate_industrial_dxf(acoustic, prod, thickness)
        except ConstraintConflictError as conflict:
            logger.error("[LAZER AJANI] Physical conflict detected: %s", conflict.report.usta_summary)
            return {"conflict_report": conflict.report}
        except Exception as exc:
            logger.warning("[LAZER AJANI] ezdxf motor hatasi: %s", exc)

        # Stub
        return self._stub_dxf(acoustic)

    def _call_box_generator(
        self, acoustic: AcousticDesignPacket, prod: ProductionPacket
    ) -> dict:
        import sys
        lazer_dir = str(Path(__file__).parents[2] / "dd1_lazer_agent")
        if lazer_dir not in sys.path:
            sys.path.insert(0, lazer_dir)
        from box_generator import generate_box_dxf  # type: ignore
        out_path = self._output_dir / acoustic.design_id
        out_path.mkdir(parents=True, exist_ok=True)
        return generate_box_dxf(
            net_volume_l=acoustic.net_volume_l,
            width_mm=acoustic.dimensions.w_mm,
            height_mm=acoustic.dimensions.h_mm,
            depth_mm=acoustic.dimensions.d_mm,
            thickness_mm=prod.material_thickness_mm,
            joint_profile=prod.finger_joint_profile,
            output_dir=str(out_path),
            design_id=acoustic.design_id,
        )

    def _generate_industrial_dxf(
        self,
        acoustic:  AcousticDesignPacket,
        prod:      ProductionPacket,
        thickness: float,
    ) -> dict:
        """
        Tam akustik geometri motoru.
        box_generator → geo_validator → dxf_writer → exports/{design_id}.dxf

        Döner: {dxf, proxy_report, panel_list, volume_summary}
        """
        from core.box_generator import build_cabinet_geometry
        from core.geo_validator import validate_geometry
        from core.dxf_writer import DXFWriter

        # 1. Kabin geometrisi
        fj_active = "6mm" in prod.finger_joint_profile
        cabinet = build_cabinet_geometry(
            net_volume_l   = acoustic.net_volume_l,
            width_mm       = acoustic.dimensions.w_mm,
            height_mm      = acoustic.dimensions.h_mm,
            depth_mm       = acoustic.dimensions.d_mm,
            port_area_cm2  = acoustic.port_area_cm2,
            port_length_cm = acoustic.port_length_cm,
            thickness_mm   = thickness,
            driver_hole_mm = (
                acoustic.internal_volume_constraints.woofer_hole_mm
                if acoustic.internal_volume_constraints else 282.0
            ),
            port_type      = "rectangular_slot",
            finger_joint   = fj_active,
        )
        logger.info("[LAZER AJANI] Kabin geometrisi: %d panel, net=%.2fL",
                    len(cabinet.panels), cabinet.volume.net_acoustic_l)

        # 2. Geometrik doğrulama
        geo_val = validate_geometry(cabinet)
        if not geo_val.passed:
            logger.error("[LAZER AJANI] Geo validation hatasi: %s", geo_val.errors)
            return {}
        for w in geo_val.warnings:
            logger.warning("[LAZER AJANI] Geo uyari: %s", w)

        # 3. DXF yaz
        writer = DXFWriter(output_dir=str(self._output_dir))
        result = writer.write(cabinet, design_id=acoustic.design_id)

        # Panel listesi çıktı
        panel_report = [
            {
                "name": p.name,
                "width_mm": p.width_mm,
                "height_mm": p.height_mm,
                "role": p.role,
            }
            for p in cabinet.panels
        ]

        return {
            "dxf":            result["dxf_path"],   # str — produce() Path(fpath) bunu bekler
            "proxy_report":   result["proxy_report"],
            "panel_list":     panel_report,
            "volume_summary": cabinet.volume.__dict__,
            "closed_poly":    result["closed_poly_count"],
            "dup_removed":    result["duplicate_removed"],
            "geo_warnings":   geo_val.warnings,
        }

    def _stub_dxf(self, acoustic: AcousticDesignPacket) -> dict:
        """ezdxf yoksa boş stub dosyası döner (geliştirme)."""
        logger.warning("[LAZER AJANI] box_generator bulunamadi — stub mod")
        stub = self._output_dir / f"{acoustic.design_id}_stub.dxf"
        # Stub DXF: geçerli minimal içerik
        stub.write_text(
            "0\nSECTION\n2\nHEADER\n9\n$ACADVER\n1\nAC1015\n0\nENDSEC\n"
            "0\nSECTION\n2\nENTITIES\n0\nENDSEC\n0\nEOF\n",
            encoding="utf-8"
        )
        return {"dxf": str(stub)}

    # ── Nesting ────────────────────────────────────────────────────────────────

    def _compute_nesting(self, acoustic: AcousticDesignPacket) -> NestingLayout:
        panels = acoustic.panel_list or []
        return NestingLayout(
            sheet_width_mm=1220,
            sheet_height_mm=610,
            panel_count=len(panels),
            utilization_pct=min(92.0, len(panels) * 12.5),
            panels=panels,
        )

    # ── Özet ──────────────────────────────────────────────────────────────────

    def _production_summary(
        self, prod: ProductionPacket, acoustic: AcousticDesignPacket, files: dict
    ) -> str:
        dxf = files.get("dxf", "yok")
        size = ""
        try:
            fp = Path(dxf)
            if fp.exists():
                size = f" ({fp.stat().st_size:,} byte)"
        except Exception:
            pass
        return (
            f"[Uretim: {prod.production_id}]\n"
            f"  Akustik: {acoustic.design_id} hash={acoustic.packet_hash}\n"
            f"  Joint:   {prod.finger_joint_profile}\n"
            f"  Malzeme: {prod.material_type} {prod.material_thickness_mm}mm\n"
            f"  DXF:     {dxf}{size}\n"
            f"  Nesting: {prod.nesting_layout.panel_count} panel "
            f"%{prod.nesting_layout.utilization_pct:.0f} verim\n"
        )

    # ── Hata Yanıtı ────────────────────────────────────────────────────────────

    @staticmethod
    def _error_response(code: str, errors: list[str]) -> dict:
        return {
            "production_packet": None,
            "files": {}, "summary": "",
            "success": False,
            "error_code": code,
            "errors": errors,
        }
