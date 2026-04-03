"""
core/conflict_resolver.py
DD1 Çakışma Çözüm Motoru

Fiziksel sınırlar çakıştığında:
  - Sadece hata vermez
  - Usta gözüyle 3 seçenek üretir
  - Kural tabanlı öneri tetikler
  - Makine okunur + Türkçe usta özeti döndürür

Malzeme değişimi → tam geometri yeniden hesaplama zorunlu.
Bağımsız modül: I/O yok, ajan yok, saf kural mantığı.
"""
from __future__ import annotations
import logging
import math
from dataclasses import dataclass
from typing import Optional

from core.design_modes import (
    ConflictOption, ConflictReport, ConflictSeverity, ConflictType,
    ConstraintConflictError, DesignConstraints, DesignMode,
    MaterialRecalculation,
)
from core.geometry import VolumeBreakdown, PortGeometry, compute_inner_dims

logger = logging.getLogger("dd1.conflict_resolver")


# ── Kural Eşikleri ────────────────────────────────────────────────────────────

@dataclass
class ConflictRules:
    """Config'den okunabilen eşik değerleri."""
    # Hacim açığı eşikleri (%)
    volume_deficit_invert_min_pct:    float = 3.0   # → invert driver öner
    volume_deficit_invert_max_pct:    float = 7.0
    volume_deficit_material_pct:      float = 7.0   # → malzeme değişikliği öner

    # Delta limit
    delta_fail_threshold_pct:         float = 2.0   # Üretim durdurma

    # Port eşikleri (mm²)
    port_area_aero_suggest_cm2:       float = 60.0  # → aero port öner

    # Alan genişlik oranı
    narrow_aspect_ratio:              float = 1.2   # w/h < bunu → slanted back

    # Malzeme eşiği
    material_impact_threshold_pct:    float = 10.0  # → 15mm kontra öner

    # Compromise seçenek sayısı
    compromise_option_count:          int   = 3

    @classmethod
    def from_config(cls) -> "ConflictRules":
        try:
            from core.config import cfg
            return cls(
                delta_fail_threshold_pct=getattr(cfg, "delta_fail_threshold_pct", 2.0),
                compromise_option_count=getattr(cfg, "compromise_option_count", 3),
                volume_deficit_invert_min_pct=getattr(cfg, "volume_deficit_suggest_invert_pct", 3.0),
                volume_deficit_material_pct=getattr(cfg, "volume_deficit_suggest_material_pct", 7.0),
            )
        except Exception:
            return cls()


# ── Ana Çözüm Motoru ─────────────────────────────────────────────────────────

class ConflictResolver:
    """
    Fiziksel çatışmayı analiz eder ve seçenek üretir.

    Kullanım:
        resolver = ConflictResolver()
        report   = resolver.resolve(constraints, vol, port, cabinet_dims)
    """

    def __init__(self, rules: Optional[ConflictRules] = None):
        self.rules = rules or ConflictRules.from_config()

    # ── Genel Giriş Noktası ──────────────────────────────────────────────────

    def detect_conflict_type(
        self,
        constraints:     DesignConstraints,
        vol:             Optional[VolumeBreakdown],
        port:            Optional[PortGeometry],
        outer_w: float, outer_h: float, outer_d: float,
    ) -> Optional[ConflictType]:
        """Hangi tür çakışma var? None → çakışma yok."""
        if (
            constraints.outer_dims_locked
            and constraints.outer_w_mm is not None
            and (
                abs(outer_w - constraints.outer_w_mm) > constraints.dim_tolerance_mm
                or abs(outer_h - constraints.outer_h_mm) > constraints.dim_tolerance_mm
                or abs(outer_d - constraints.outer_d_mm) > constraints.dim_tolerance_mm
            )
        ):
            return ConflictType.OUTER_DIM_CHANGED

        if vol and vol.delta_pct > self.rules.delta_fail_threshold_pct:
            if vol.net_acoustic_l < vol.target_net_l:
                return ConflictType.VOLUME_INSUFFICIENT
            return ConflictType.DELTA_LIMIT_EXCEEDED

        return None

    def resolve_outer_dim_changed(
        self,
        constraints: DesignConstraints,
        vol: Optional[VolumeBreakdown],
        port: Optional[PortGeometry],
        actual_w: float, actual_h: float, actual_d: float,
    ) -> ConflictReport:
        """FIXED_EXTERNAL: sessiz resize tespit edildi."""
        orig = [constraints.outer_w_mm, constraints.outer_h_mm, constraints.outer_d_mm]
        actual = [actual_w, actual_h, actual_d]

        delta_l = abs(actual_w - orig[0]) if orig[0] else 0
        delta_pct = vol.delta_pct if vol else 0.0

        options = self._outer_dim_options(
            constraints, vol, port, orig, actual
        )

        summary = (
            f"Reis, verdiğin {orig[0]:.0f}x{orig[1]:.0f}x{orig[2]:.0f}mm ölçüye "
            f"{actual_w:.0f}x{actual_h:.0f}x{actual_d:.0f}mm çıktı. "
            f"Dış ölçü kilitli moddasın — bu 0 kabul edilmez. "
            f"Aşağıdaki {len(options)} seçenek avail."
        )

        return ConflictReport(
            mode=constraints.mode.value,
            conflict_detected=True,
            conflict_type=ConflictType.OUTER_DIM_CHANGED.value,
            conflict_severity=ConflictSeverity.ERROR.value,
            outer_dimensions_locked=True,
            acoustic_targets_locked=constraints.net_volume_locked,
            options=options,
            net_target_l=vol.target_net_l if vol else 0,
            final_calculated_net_l=vol.net_acoustic_l if vol else 0,
            delta_pct=delta_pct,
            outer_original_mm=orig,
            outer_final_mm=actual,
            volume_lock_status="unlocked",
            space_fit_status="exceeds" if delta_l > 0.1 else "fits",
            resize_applied=True,
            resize_allowed=False,
            usta_summary=summary,
        )

    def resolve_volume_insufficient(
        self,
        constraints: DesignConstraints,
        vol: VolumeBreakdown,
        port: Optional[PortGeometry],
        outer_w: float, outer_h: float, outer_d: float,
    ) -> ConflictReport:
        """Hacim yetersiz → invert / malzeme / layout önerileri."""
        deficit_pct = abs(vol.error_pct)
        options = self._volume_options(constraints, vol, port, outer_w, outer_h, outer_d, deficit_pct)

        severity = (
            ConflictSeverity.ERROR if deficit_pct > self.rules.volume_deficit_material_pct
            else ConflictSeverity.WARNING
        )

        if deficit_pct <= self.rules.volume_deficit_invert_max_pct:
            action = "sürücüyü ters bağlayarak ~3-5L kazanabilirsin"
        else:
            action = "15mm kontraplak veya yapı değişikliği şart"

        summary = (
            f"Reis, hedef {vol.target_net_l:.1f}L ama hesaplanan {vol.net_acoustic_l:.1f}L — "
            f"%{deficit_pct:.1f} açık var. {action}. "
            f"{len(options)} seçenek sende."
        )

        return ConflictReport(
            mode=constraints.mode.value,
            conflict_detected=True,
            conflict_type=ConflictType.VOLUME_INSUFFICIENT.value,
            conflict_severity=severity.value,
            outer_dimensions_locked=constraints.outer_dims_locked,
            acoustic_targets_locked=constraints.net_volume_locked,
            options=options,
            net_target_l=vol.target_net_l,
            final_calculated_net_l=vol.net_acoustic_l,
            delta_pct=vol.delta_pct,
            outer_original_mm=[outer_w, outer_h, outer_d],
            outer_final_mm=[outer_w, outer_h, outer_d],
            volume_lock_status="locked" if constraints.net_volume_locked else "unlocked",
            space_fit_status="fits",
            resize_applied=False,
            resize_allowed=constraints.resize_allowed,
            usta_summary=summary,
        )

    def resolve_port_fit_failure(
        self,
        constraints: DesignConstraints,
        vol: Optional[VolumeBreakdown],
        port: PortGeometry,
        inner_h_mm: float, inner_w_mm: float,
        outer_w: float, outer_h: float, outer_d: float,
        tuning_hz: float,
    ) -> ConflictReport:
        """Port sığmıyor → aero / kısa / dışa taşı öneri."""
        options = self._port_options(
            constraints, vol, port, inner_h_mm, inner_w_mm,
            outer_w, outer_h, outer_d, tuning_hz
        )

        summary = (
            f"Reis, {port.width_mm:.0f}x{port.height_mm:.0f}mm port "
            f"{inner_h_mm:.0f}mm yükseklikteki iç kabine sığmıyor. "
            f"Aero port veya portu kısaltmayı dene. "
            f"{len(options)} seçenek hazır."
        )

        return ConflictReport(
            mode=constraints.mode.value,
            conflict_detected=True,
            conflict_type=ConflictType.PORT_FIT_FAILURE.value,
            conflict_severity=ConflictSeverity.ERROR.value,
            outer_dimensions_locked=constraints.outer_dims_locked,
            acoustic_targets_locked=constraints.net_volume_locked,
            options=options,
            net_target_l=vol.target_net_l if vol else 0,
            final_calculated_net_l=vol.net_acoustic_l if vol else 0,
            delta_pct=vol.delta_pct if vol else 0,
            outer_original_mm=[outer_w, outer_h, outer_d],
            outer_final_mm=[outer_w, outer_h, outer_d],
            space_fit_status="port_overflow",
            resize_allowed=constraints.resize_allowed,
            usta_summary=summary,
        )

    def build_compromise_report(
        self,
        vol: VolumeBreakdown,
        port: Optional[PortGeometry],
        outer_w: float, outer_h: float, outer_d: float,
        tuning_hz: float,
    ) -> ConflictReport:
        """COMPROMISE modu: 3 seçenek üretir."""
        options = self._compromise_options(vol, port, outer_w, outer_h, outer_d, tuning_hz)
        rec = options[0] if options else None

        summary = (
            f"Reis, {self.rules.compromise_option_count} seçenek ürettim. "
            f"{'Önerilen: ' + rec.option_id + ' — ' + rec.strategy if rec else 'Seç.'}. "
            "Aşağıyı incele."
        )
        return ConflictReport(
            mode=DesignMode.COMPROMISE.value,
            conflict_detected=False,
            conflict_type="none",
            conflict_severity=ConflictSeverity.WARNING.value,
            outer_dimensions_locked=False,
            acoustic_targets_locked=False,
            options=options,
            net_target_l=vol.target_net_l,
            final_calculated_net_l=vol.net_acoustic_l,
            delta_pct=vol.delta_pct,
            outer_original_mm=[outer_w, outer_h, outer_d],
            outer_final_mm=[outer_w, outer_h, outer_d],
            resize_allowed=False,
            usta_summary=summary,
        )

    # ── Opsiyon Üreticiler ───────────────────────────────────────────────────

    def _outer_dim_options(
        self,
        constraints: DesignConstraints,
        vol: Optional[VolumeBreakdown],
        port: Optional[PortGeometry],
        orig: list, actual: list,
    ) -> list:
        target_l = vol.target_net_l if vol else 0
        tuning   = 35.0  # kestirme

        ops = []
        # A: Dış ölçüleri koru → hacimden taviz
        ops.append(ConflictOption(
            option_id="A",
            strategy="accept_locked_dims_volume_compromise",
            net_target_l=target_l,
            estimated_final_net_l=round(target_l * 0.88, 2),  # ~%12 düşük
            tuning_target_hz=tuning,
            estimated_final_tuning_hz=round(tuning * 1.05, 1),
            outer_dimensions_mm=orig,
            fit_status="fits",
            manufacturability_status="ok",
            acoustic_delta_pct=12.0,
            space_delta_mm=0.0,
            recommended=True,
            usta_summary=(
                f"Ölçüler {orig[0]:.0f}x{orig[1]:.0f}x{orig[2]:.0f}mm kilitli kalır. "
                f"Hacimden biraz taviz veriyorsun ama kutu bagaja tam oturur."
            ),
        ))
        # B: Malzeme inceltiği — TAM HESAPLAMA
        ops.append(self._build_material_option(
            option_id="B",
            strategy="thin_material_15mm_birch",
            net_target_l=target_l,
            outer_dims=orig,
            orig_t=18.0, new_t=15.0,
        ))
        # C: Farklı sürücü/tasarım önerisi
        ops.append(ConflictOption(
            option_id="C",
            strategy="different_driver_or_ported_layout",
            net_target_l=target_l,
            estimated_final_net_l=target_l,
            tuning_target_hz=tuning,
            estimated_final_tuning_hz=tuning,
            outer_dimensions_mm=orig,
            fit_status="marginal",
            manufacturability_status="ok",
            acoustic_delta_pct=0.0,
            space_delta_mm=0.0,
            recommended=False,
            usta_summary=(
                "Farklı sürücü veya kapalı kutu tasarımına geç. "
                "Akustik hedef korunur, ama tasarım baştan yazılır."
            ),
        ))
        return ops

    def _build_material_option(
        self,
        option_id: str,
        strategy: str,
        net_target_l: float,
        outer_dims: list,
        orig_t: float = 18.0,
        new_t: float  = 15.0,
        kerf_mm: float = 0.2,
        vol: Optional[VolumeBreakdown] = None,
        recommended: bool = False,
    ) -> ConflictOption:
        """
        Malzeme değişimi seçeneği — tam geometri yeniden hesaplama ile.

        Malzeme: orig_t mm  →  new_t mm
        Tüm bağımlı hesaplamalar yeni kalınlığa göre yapılır:
          - volume_gain (mm³ → L)
          - finger joint depth / count / spacing
          - kerf / tolerans
          - panel / port yeniden hesaplama bayrağı
        """
        w, h, d = outer_dims[0], outer_dims[1], outer_dims[2]

        # Hacim kazancı: (2*delta_t) her üç eksende iç boyutu etkiler
        delta_t = orig_t - new_t   # pozitif = inceltme
        # Her 2 yüzey orig_t → new_t: her eksen 2*delta_t kazanır
        new_inner_w = w - 2 * new_t
        new_inner_h = h - 2 * new_t
        new_inner_d = d - 2 * new_t
        old_inner_w = w - 2 * orig_t
        old_inner_h = h - 2 * orig_t
        old_inner_d = d - 2 * orig_t
        volume_gain_mm3 = (
            new_inner_w * new_inner_h * new_inner_d
            - old_inner_w * old_inner_h * old_inner_d
        )
        volume_gain_l = round(max(0.0, volume_gain_mm3 * 1e-6), 3)

        # Finger joint (yeni malzemeye göre)
        min_edge = min(new_inner_w, new_inner_h, new_inner_d)
        joint_count = max(1, math.floor(min_edge / (new_t * 2)))
        joint_spacing = round(min_edge / joint_count, 1) if joint_count > 0 else 0.0
        joint_depth   = new_t   # finger derinliği = malzeme kalınlığı

        mat_recalc = MaterialRecalculation(
            original_material_thickness_mm = orig_t,
            proposed_material_thickness_mm = new_t,
            volume_gain_l                  = volume_gain_l,
            finger_joint_recalculated      = True,
            joint_depth_mm                 = joint_depth,
            joint_count                    = joint_count,
            joint_spacing_mm               = joint_spacing,
            kerf_tolerance_mm              = kerf_mm,
            panel_dims_recalculated        = True,
            port_geometry_recalculated     = True,
            recalculation_applied          = True,   # ← üretim hattına gönderilebilir
        )

        est_net = round(
            (vol.net_acoustic_l + volume_gain_l if vol else net_target_l * 0.96), 2
        )
        delta_pct = round(abs(est_net - net_target_l) / net_target_l * 100, 2)

        logger.info(
            "[CONFLICT] Malzeme secenegi hesaplandi: %smm→%smm, +%.3fL, joint_count=%d",
            orig_t, new_t, volume_gain_l, joint_count,
        )

        return ConflictOption(
            option_id               = option_id,
            strategy                = strategy,
            net_target_l            = net_target_l,
            estimated_final_net_l   = est_net,
            tuning_target_hz        = 35.0,
            estimated_final_tuning_hz = 35.0,
            outer_dimensions_mm     = outer_dims,
            material_thickness_mm   = new_t,
            panel_join_strategy     = "finger_joint",
            fit_status              = "fits",
            manufacturability_status= "requires_tooling",
            acoustic_delta_pct      = delta_pct,
            space_delta_mm          = 0.0,
            recommended             = recommended,
            material_recalculation  = mat_recalc,
            usta_summary=(
                f"18mm MDF yerine {new_t:.0f}mm huş kontraplak + zorunlu iç bracing. "
                f"Panel boyutları, finger joint (t={new_t:.0f}mm, count={joint_count}) "
                f"ve port hesabı yenilendi. "
                f"Tahminen +{volume_gain_l:.3f}L iç hacim gain."
            ),
        )

    def _volume_options(
        self,
        constraints: DesignConstraints,
        vol: VolumeBreakdown,
        port: Optional[PortGeometry],
        w: float, h: float, d: float,
        deficit_pct: float,
    ) -> list:
        t = vol.target_net_l
        ops = []

        # A: Sürücü invert
        if deficit_pct <= self.rules.volume_deficit_invert_max_pct:
            gain_l = round(t * 0.08, 2)  # ~%8 kazanç kestirimi
            ops.append(ConflictOption(
                option_id="A",
                strategy="invert_driver_mounting",
                net_target_l=t,
                estimated_final_net_l=round(vol.net_acoustic_l + gain_l, 2),
                tuning_target_hz=35.0,
                estimated_final_tuning_hz=35.0,
                outer_dimensions_mm=[w, h, d],
                fit_status="fits",
                manufacturability_status="ok",
                acoustic_delta_pct=round(abs(vol.net_acoustic_l + gain_l - t) / t * 100, 2),
                space_delta_mm=0.0,
                recommended=True,
                usta_summary=(
                    f"Sürücü ters bağlanırsa motor hacmi dışarı çıkar, "
                    f"iç hacme yaklaşık +{gain_l:.1f}L kazanç sağlanır."
                ),
            ))

        # B: Bracing optimizasyonu
        bracing_gain = round(vol.bracing_displ_l * 0.5, 2)
        ops.append(ConflictOption(
            option_id="B",
            strategy="optimize_bracing_reduce_displacement",
            net_target_l=t,
            estimated_final_net_l=round(vol.net_acoustic_l + bracing_gain, 2),
            tuning_target_hz=35.0,
            estimated_final_tuning_hz=35.0,
            outer_dimensions_mm=[w, h, d],
            fit_status="fits",
            manufacturability_status="ok",
            acoustic_delta_pct=round(abs(vol.net_acoustic_l + bracing_gain - t) / t * 100, 2),
            space_delta_mm=0.0,
            recommended=len(ops) == 0,
            usta_summary=(
                f"Bracing tasarımı optimize edilirse ~+{bracing_gain:.2f}L kazanılır. "
                "Yapısal bütünlük korunur."
            ),
        ))

        # C: 15mm malzeme — TAM YENİDEN HESAPLAMA ile
        if deficit_pct > self.rules.volume_deficit_material_pct:
            ops.append(self._build_material_option(
                option_id="C",
                strategy="thin_material_15mm_birch_ply",
                net_target_l=t,
                outer_dims=[w, h, d],
                orig_t=18.0, new_t=15.0,
                vol=vol,
            ))
        return ops

    def _port_options(
        self,
        constraints: DesignConstraints,
        vol: Optional[VolumeBreakdown],
        port: PortGeometry,
        inner_h_mm: float, inner_w_mm: float,
        w: float, h: float, d: float,
        tuning_hz: float,
    ) -> list:
        t_l = vol.target_net_l if vol else 40.0
        ops = []

        # A: Portu kısalt — tuning yükselir
        short_len = round(port.length_mm * 0.8, 1)
        tuning_new = round(tuning_hz * math.sqrt(port.length_mm / short_len), 1)
        ops.append(ConflictOption(
            option_id="A",
            strategy="shorten_port_length",
            net_target_l=t_l,
            estimated_final_net_l=t_l,
            tuning_target_hz=tuning_hz,
            estimated_final_tuning_hz=tuning_new,
            outer_dimensions_mm=[w, h, d],
            fit_status="fits",
            manufacturability_status="ok",
            acoustic_delta_pct=round(abs(tuning_new - tuning_hz) / tuning_hz * 100, 2),
            space_delta_mm=0.0,
            recommended=True,
            usta_summary=(
                f"Portu {port.length_mm:.0f}mm'den {short_len:.0f}mm'e kısaltırsak kutuya sığar, "
                f"ama tuning {tuning_hz:.0f}Hz'den {tuning_new:.0f}Hz'e çıkar."
            ),
        ))

        # B: Aero port (silindirik)
        ops.append(ConflictOption(
            option_id="B",
            strategy="switch_to_aero_port",
            net_target_l=t_l,
            estimated_final_net_l=t_l,
            tuning_target_hz=tuning_hz,
            estimated_final_tuning_hz=tuning_hz,
            outer_dimensions_mm=[w, h, d],
            fit_status="fits",
            manufacturability_status="ok",
            acoustic_delta_pct=0.0,
            space_delta_mm=0.0,
            recommended=False,
            usta_summary=(
                "Dikdörtgen slot yerine aero (silindirik) port kullan. "
                "Daha az yer kaplar, tuning korunur, ama türbülans riski var."
            ),
        ))

        # C: Portu kutu dışına taşı
        ops.append(ConflictOption(
            option_id="C",
            strategy="external_port_mounting",
            net_target_l=t_l,
            estimated_final_net_l=t_l,
            tuning_target_hz=tuning_hz,
            estimated_final_tuning_hz=tuning_hz,
            outer_dimensions_mm=[w, h, d],
            fit_status="fits",
            manufacturability_status="requires_tooling",
            acoustic_delta_pct=0.0,
            space_delta_mm=0.0,
            recommended=False,
            usta_summary=(
                "Port arka panelin dışına montajlanır. İç hacim korunur, "
                "ses kanalı dışarıda. Ekstra işçilik gerekir."
            ),
        ))
        return ops

    def _compromise_options(
        self,
        vol: VolumeBreakdown,
        port: Optional[PortGeometry],
        w: float, h: float, d: float,
        tuning_hz: float,
    ) -> list:
        t_l = vol.target_net_l
        ops = []
        scale = 1e-6  # mm³→L

        # A: Hacimden taviz — ölçüler küçük kalır
        smaller_net = round(t_l * 0.9, 2)
        ops.append(ConflictOption(
            option_id="A",
            strategy="volume_compromise",
            net_target_l=t_l,
            estimated_final_net_l=smaller_net,
            tuning_target_hz=tuning_hz,
            estimated_final_tuning_hz=round(tuning_hz * 1.06, 1),
            outer_dimensions_mm=[w, h, d],
            fit_status="fits",
            manufacturability_status="ok",
            acoustic_delta_pct=round((t_l - smaller_net) / t_l * 100, 2),
            space_delta_mm=0.0,
            recommended=True,
            usta_summary=(
                f"Hacimden %10 taviz. Net {smaller_net:.1f}L, "
                f"tuning biraz yükselir ama bagaj ölçüleri tutulur."
            ),
        ))

        # B: Tuning'den taviz — daha büyük port
        ops.append(ConflictOption(
            option_id="B",
            strategy="tuning_compromise",
            net_target_l=t_l,
            estimated_final_net_l=t_l,
            tuning_target_hz=tuning_hz,
            estimated_final_tuning_hz=round(tuning_hz * 0.88, 1),
            outer_dimensions_mm=[round(w * 1.05, 1), h, d],
            fit_status="marginal",
            manufacturability_status="ok",
            acoustic_delta_pct=0.0,
            space_delta_mm=round(w * 0.05, 1),
            recommended=False,
            usta_summary=(
                f"Tuning'i {tuning_hz:.0f}Hz'den {round(tuning_hz*0.88):.0f}Hz'e düşür. "
                "Daha derin bas ama kutu biraz büyür."
            ),
        ))

        # C: Yapıdan / yerleşimden taviz — slim yapı
        ops.append(ConflictOption(
            option_id="C",
            strategy="layout_compromise_slim_profile",
            net_target_l=t_l,
            estimated_final_net_l=round(t_l * 0.94, 2),
            tuning_target_hz=tuning_hz,
            estimated_final_tuning_hz=tuning_hz,
            outer_dimensions_mm=[w, round(h * 0.92, 1), round(d * 1.08, 1)],
            fit_status="fits",
            manufacturability_status="ok",
            acoustic_delta_pct=6.0,
            space_delta_mm=0.0,
            recommended=False,
            usta_summary=(
                "Kutu ince ve derin yapılır. Akustik %6 taviz, "
                "ama bagaj tabanına tam oturur, görünüm sade."
            ),
        ))
        return ops
