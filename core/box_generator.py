"""
core/box_generator.py
DD1 Kabin Geometri Kutusu — Tam Panel + Port + Finger Joint Motoru

Girdi:  AcousticDesignPacket (net_volume_l, dimensions, port, material_thickness)
Çıktı:  CabinetGeometry (panel listesi, volume breakdown, port geom, joint config)

Bu modül saf geometri — DXF yazımı dxf_writer.py'de.
"""
from __future__ import annotations
import logging
import math
from pathlib import Path
from typing import Optional

from core.geometry import (
    CabinetGeometry, PanelDim, PortGeometry, VolumeBreakdown,
    compute_inner_dims, volume_breakdown, compute_panels,
    compute_port_geometry, compute_port_wall_panel,
    check_volume_revalidation,
)
from core.design_modes import (
    DesignConstraints, DesignMode, ConstraintConflictError,
    ConflictType, ConflictSeverity, ConflictReport,
)

logger = logging.getLogger("dd1.box_generator")

# Hacim toleransi — driver + port + bracing displacement gercekci olarak ~15-20% yiyor
# 25% esigi asarsa AcousticIntegrityError firlatilir
VOLUME_REVALIDATION_TOLERANCE_PCT = 25.0


class BoxGenerator:
    """
    AcousticDesignPacket → CabinetGeometry
    """

    def __init__(
        self,
        material_thickness_mm: float = 18.0,
        finger_joint_active:   bool  = True,
        kerf_mm:               float = 0.2,
        tolerance_mm:          float = 0.1,
        bracing_pct:           float = 0.02,   # 2% bracing
    ):
        self.t                 = material_thickness_mm
        self.finger_joint      = finger_joint_active
        self.kerf              = kerf_mm
        self.tolerance         = tolerance_mm
        self.bracing_pct       = bracing_pct

    def build(
        self,
        net_volume_l:      float,
        width_mm:          float,
        height_mm:         float,
        depth_mm:          float,
        port_area_cm2:     float,
        port_length_cm:    float,
        driver_hole_mm:    float = 282.0,
        port_type:         str   = "rectangular_slot",
        port_count:        int   = 1,
        woofer_xmax_mm:    float = 0.0,
        constraints: Optional[DesignConstraints] = None,
    ) -> CabinetGeometry:
        """
        Ana build metodu — mode-aware.

        Mod davranışı:
          FIXED_EXTERNAL: dış ölçüler kilitli, auto-resize yasak.
                          Post-build dim check → ConstraintConflictError.
          FIXED_ACOUSTIC:  auto-resize serbest (mevcut davranış).
          COMPROMISE:      3 seçenek üretilir, conflict_report eklenir.
          None:            geriye dönük uyumluluk — FIXED_ACOUSTIC gibi davranır.

        Raises ConstraintConflictError: FIXED_EXTERNAL'da ölçü kayması.
        Raises ValueError: port type desteklenmiyor veya port sığmıyor.
        Raises AcousticIntegrityError: hacim yeniden doğrulama başarısız.
        """
        if constraints is None:
            constraints = DesignConstraints.fixed_acoustic()
        mode = constraints.mode

        # Orijinal dış ölçüleri kaydet (post-build dim check için)
        orig_w, orig_h, orig_d = width_mm, height_mm, depth_mm

        t = self.t
        logger.info(
            "[BOX_GEN] Build baslatildi [mode=%s]: net=%.2fL W=%.0f H=%.0f D=%.0f t=%.0fmm",
            mode.value, net_volume_l, width_mm, height_mm, depth_mm, t,
        )

        # 1. İç ölçüler
        iw, ih, id_ = compute_inner_dims(width_mm, height_mm, depth_mm, t)

        # 2. Port geometrisi
        port = compute_port_geometry(
            port_area_cm2=port_area_cm2,
            port_length_cm=port_length_cm,
            port_type=port_type,
            port_count=port_count,
            cabinet_inner_h_mm=ih,
            cabinet_inner_w_mm=iw,
        )
        logger.info(
            "[BOX_GEN] Port: %s %.1fx%.1fmm L=%.1fmm displ=%.3fL",
            port.port_type, port.width_mm, port.height_mm,
            port.length_mm, port.displacement_l,
        )

        # 3. Hacim breakdown
        vol = volume_breakdown(
            w_mm=width_mm, h_mm=height_mm, d_mm=depth_mm,
            t_mm=t,
            target_net_l=net_volume_l,
            driver_hole_mm=driver_hole_mm,
            port=port,
            bracing_pct=self.bracing_pct,
        )
        self._log_volume(vol)

        # 4. Auto-Resize: sadece FIXED_ACOUSTIC veya explicit_user_approval=True'da çalışır
        AUTO_RESIZE_THRESHOLD_PCT = 1.0
        if not constraints.resize_allowed:
            # FIXED_EXTERNAL veya COMPROMISE → auto-resize yasak
            if vol.error_pct > AUTO_RESIZE_THRESHOLD_PCT:
                logger.info(
                    "[BOX_GEN] Auto-resize BLOKE! Mode=%s sapma=%%%.1f (resize_allowed=False)",
                    mode.value, vol.error_pct,
                )
                # Sessiz geçme — ConflictResolver ilerleyen adımda çalışacak
        else:
            # FIXED_ACOUSTIC — auto-resize serbest
            if vol.error_pct > AUTO_RESIZE_THRESHOLD_PCT:
                from core.geometry import auto_resize_dims
                logger.info(
                    "[BOX_GEN] Auto-resize baslatildi: mevcut_sapma=%%%.1f hedef=%%%.1f",
                    vol.error_pct, AUTO_RESIZE_THRESHOLD_PCT
                )
                try:
                    new_w, new_h, new_d, vol = auto_resize_dims(
                        target_net_l=net_volume_l,
                        w_mm=width_mm, h_mm=height_mm, d_mm=depth_mm,
                        t_mm=t,
                        driver_hole_mm=driver_hole_mm,
                        port=port,
                        bracing_pct=self.bracing_pct,
                        tolerance_pct=AUTO_RESIZE_THRESHOLD_PCT,
                    )
                    width_mm, height_mm, depth_mm = new_w, new_h, new_d
                    iw, ih, id_ = compute_inner_dims(width_mm, height_mm, depth_mm, t)
                    logger.info(
                        "[BOX_GEN] Auto-resize tamamlandi: %.1fx%.1fx%.1fmm net=%.3fL delta=%%%.3f",
                        width_mm, height_mm, depth_mm,
                        vol.net_acoustic_l, vol.delta_pct,
                    )
                except ValueError as resize_err:
                    logger.warning("[BOX_GEN] Auto-resize basarisiz: %s", resize_err)

        # 4a. FIXED_EXTERNAL: post-build dim check — 0.1mm tolerans
        if mode == DesignMode.FIXED_EXTERNAL and constraints.outer_dims_locked:
            tol = constraints.dim_tolerance_mm
            dim_drift = (
                abs(width_mm  - orig_w) > tol
                or abs(height_mm - orig_h) > tol
                or abs(depth_mm  - orig_d) > tol
            )
            if dim_drift:
                # Sessiz resize yasaklı — ConstraintConflictError fırlat
                from core.conflict_resolver import ConflictResolver
                resolver = ConflictResolver()
                report   = resolver.resolve_outer_dim_changed(
                    constraints=constraints,
                    vol=vol,
                    port=port,
                    actual_w=width_mm, actual_h=height_mm, actual_d=depth_mm,
                )
                logger.error(
                    "[BOX_GEN] FIXED_EXTERNAL dim_drift tespit edildi! "
                    "orig=%s actual=%s — ConstraintConflictError firlatiliyor",
                    [orig_w, orig_h, orig_d], [width_mm, height_mm, depth_mm],
                )
                raise ConstraintConflictError(
                    conflict_type=ConflictType.OUTER_DIM_CHANGED,
                    severity=ConflictSeverity.ERROR,
                    report=report,
                )


        # 4b. Hacim yeniden doğrulama — TOLERANCE %25 (güvenlik sınırı)
        passed, msg = check_volume_revalidation(vol, VOLUME_REVALIDATION_TOLERANCE_PCT)
        if not passed:
            from core.validators import AcousticIntegrityError
            raise AcousticIntegrityError(
                design_id="geom_check",
                field="net_volume_l",
                original=net_volume_l,
                modified=vol.net_acoustic_l,
            )
        logger.info("[BOX_GEN] %s", msg)

        # 5. Paneller
        panels = compute_panels(width_mm, height_mm, depth_mm, t)

        # Port iç duvar paneli
        port_wall = compute_port_wall_panel(port, t)
        panels.append(port_wall)

        # 6. Finger joint konfigürasyonu
        fj_active, fj_width = self._finger_joint_config(panels)

        # 7. Driver delik çapı hesabı (ön panel için)
        # woofer_xmax → motor derinliğini hesaba katar (şimdilik sabit kestirimliyiz)

        cab = CabinetGeometry(
            outer_w_mm=width_mm,
            outer_h_mm=height_mm,
            outer_d_mm=depth_mm,
            inner_w_mm=iw,
            inner_h_mm=ih,
            inner_d_mm=id_,
            thickness_mm=t,
            volume=vol,
            panels=panels,
            port=port,
            finger_joint_active=fj_active,
            finger_width_mm=fj_width,
            kerf_mm=self.kerf,
            tolerance_mm=self.tolerance,
            driver_hole_mm=driver_hole_mm,
        )
        logger.info(
            "[BOX_GEN] Tamamlandi: %d panel, fj=%s, driver_hole=%.0fmm",
            len(panels), fj_active, driver_hole_mm,
        )
        return cab

    def _finger_joint_config(
        self, panels: list[PanelDim]
    ) -> tuple[bool, float]:
        """
        Finger joint kalıbı:
        - Opsiyonel (self.finger_joint)
        - Küçük kenar (< 3×t) varsa auto-disable
        """
        if not self.finger_joint:
            logger.info("[BOX_GEN] Finger joint: PASIF (kullanici secimi)")
            return False, 0.0

        # En küçük kenar kontrolü
        min_edge = min(
            min(p.width_mm, p.height_mm)
            for p in panels if p.role == "main"
        )
        min_viable = 3 * self.t
        if min_edge < min_viable:
            logger.warning(
                "[BOX_GEN] Finger joint auto-disable: min_kenar=%.1fmm < %.1fmm",
                min_edge, min_viable,
            )
            return False, 0.0

        finger_w = self.t  # diş genişliği = malzeme kalınlığı (standart)
        logger.info("[BOX_GEN] Finger joint: AKTIF, dis_w=%.1fmm kerf=%.2fmm tol=%.2fmm",
                    finger_w, self.kerf, self.tolerance)
        return True, finger_w

    @staticmethod
    def _log_volume(vol: VolumeBreakdown) -> None:
        logger.info(
            "[BOX_GEN] Hacim → gross=%.3fL inner=%.3fL "
            "driver=%.3fL port=%.3fL bracing=%.3fL net=%.3fL (hedef=%.3fL sapma=%%%.1f)",
            vol.gross_l, vol.inner_l,
            vol.driver_displ_l, vol.port_displ_l, vol.bracing_displ_l,
            vol.net_acoustic_l, vol.target_net_l, vol.error_pct,
        )


# ── Hızlı Erişim Fonksiyonu ───────────────────────────────────────────────────

def build_cabinet_geometry(
    net_volume_l:      float,
    width_mm:          float,
    height_mm:         float,
    depth_mm:          float,
    port_area_cm2:     float,
    port_length_cm:    float,
    thickness_mm:      float  = 18.0,
    driver_hole_mm:    float  = 282.0,
    port_type:         str    = "rectangular_slot",
    finger_joint:      bool   = True,
    kerf_mm:           float  = 0.2,
    tolerance_mm:      float  = 0.1,
) -> CabinetGeometry:
    """Wrapper — LazerAjanı'nın çağırdığı ana fonksiyon."""
    gen = BoxGenerator(
        material_thickness_mm=thickness_mm,
        finger_joint_active=finger_joint,
        kerf_mm=kerf_mm,
        tolerance_mm=tolerance_mm,
    )
    return gen.build(
        net_volume_l=net_volume_l,
        width_mm=width_mm,
        height_mm=height_mm,
        depth_mm=depth_mm,
        port_area_cm2=port_area_cm2,
        port_length_cm=port_length_cm,
        driver_hole_mm=driver_hole_mm,
        port_type=port_type,
    )
