"""
core/design_modes.py
DD1 Çok Modlu Tasarım Motoru — Kısıt Tanımları ve Hata Sınıfları

Üç tasarım modu:
  FIXED_EXTERNAL  — Dış ölçüler kutsaldır (bagaj odaklı)
  FIXED_ACOUSTIC  — Net litre + tuning kutsaldır (akustik odaklı)
  COMPROMISE      — Sistem en az sapmayla 3 seçenek üretir

Kural: Sessiz resize YASAK.
  - FIXED_EXTERNAL modunda dış ölçüler 0.1mm dahilinde bile değişemez.
  - Çakışma olursa ConstraintConflictError fırlatılır + alternatifler sunulur.
"""
from __future__ import annotations
import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


# ── Mod Enum ─────────────────────────────────────────────────────────────────

class DesignMode(str, Enum):
    FIXED_EXTERNAL = "fixed_external"   # Bagaj odaklı: dış ölçüler kilitli
    FIXED_ACOUSTIC = "fixed_acoustic"   # Akustik odaklı: litre+tuning kilitli
    COMPROMISE     = "compromise"        # Uzlaşma: 3 senaryo üret


# ── Çatışma Tipleri ───────────────────────────────────────────────────────────

class ConflictType(str, Enum):
    PORT_FIT_FAILURE          = "port_fit_failure"
    VOLUME_INSUFFICIENT       = "volume_insufficient"
    SPACE_TOO_NARROW          = "space_too_narrow"
    MATERIAL_THICKNESS_IMPACT = "material_thickness_impact"
    ACOUSTIC_TARGET_UNREACHABLE = "acoustic_target_unreachable"
    OUTER_DIM_CHANGED         = "outer_dim_changed"   # Sessiz resize tespit edildi
    DELTA_LIMIT_EXCEEDED      = "delta_limit_exceeded"


class ConflictSeverity(str, Enum):
    WARNING  = "warning"   # Devam edilebilir, uyarı ile
    ERROR    = "error"     # Üretim durdu, alternatif gerekli
    CRITICAL = "critical"  # Fiziksel imkansız


# ── Kısıt Tanımı ─────────────────────────────────────────────────────────────

@dataclass
class DesignConstraints:
    """Aktif tasarım modunun kısıt seti."""
    mode:                    DesignMode = DesignMode.FIXED_ACOUSTIC

    # FIXED_EXTERNAL kısıtları
    outer_w_mm:              Optional[float] = None   # Kilitli dış genişlik
    outer_h_mm:              Optional[float] = None   # Kilitli dış yükseklik
    outer_d_mm:              Optional[float] = None   # Kilitli dış derinlik
    outer_dims_locked:       bool = False
    bagaj_max_w_mm:          Optional[float] = None   # Bagaj maks genişlik
    bagaj_max_h_mm:          Optional[float] = None   # Bagaj maks yükseklik
    bagaj_max_d_mm:          Optional[float] = None   # Bagaj maks derinlik

    # FIXED_ACOUSTIC kısıtları
    net_volume_locked:       bool = False
    tuning_hz_locked:        bool = False
    port_area_locked:        bool = False

    # Kullanıcı onayı
    explicit_user_approval:  bool = False   # True ise auto-resize serbest

    # Tolerans (0.1 mm — değiştirilemez sınır)
    dim_tolerance_mm:        float = 0.1

    @classmethod
    def fixed_external(
        cls, outer_w: float, outer_h: float, outer_d: float,
        bagaj_w: Optional[float] = None,
        bagaj_h: Optional[float] = None,
        bagaj_d: Optional[float] = None,
    ) -> "DesignConstraints":
        """Bagaj odaklı mod — dış ölçüler kilitli."""
        return cls(
            mode=DesignMode.FIXED_EXTERNAL,
            outer_w_mm=outer_w, outer_h_mm=outer_h, outer_d_mm=outer_d,
            outer_dims_locked=True,
            bagaj_max_w_mm=bagaj_w, bagaj_max_h_mm=bagaj_h, bagaj_max_d_mm=bagaj_d,
            net_volume_locked=False,
        )

    @classmethod
    def fixed_acoustic(
        cls, explicit_approval: bool = False
    ) -> "DesignConstraints":
        """Akustik odaklı mod — litre + tuning kilitli, ölçüler değişebilir."""
        return cls(
            mode=DesignMode.FIXED_ACOUSTIC,
            outer_dims_locked=False,
            net_volume_locked=True, tuning_hz_locked=True, port_area_locked=True,
            explicit_user_approval=explicit_approval,
        )

    @classmethod
    def compromise(cls) -> "DesignConstraints":
        """Uzlaşma modu — 3 seçenek üretilir."""
        return cls(mode=DesignMode.COMPROMISE)

    @property
    def resize_allowed(self) -> bool:
        """Auto-resize sadece fixed_acoustic modunda veya açık onay varsa serbest."""
        if self.mode == DesignMode.FIXED_EXTERNAL:
            return False            # HİÇBİR ZAMAN
        if self.mode == DesignMode.COMPROMISE:
            return False            # Compromise kendi seçeneklerini üretir
        # FIXED_ACOUSTIC: her zaman serbest
        return True


# ── Malzeme Değişimi Yeniden Hesaplama Kaydı ─────────────────────────────────

@dataclass
class MaterialRecalculation:
    """
    Malzeme değişimi seçildiyse tüm bağımlı geometri yeniden hesaplanmalıdır.
    recalculation_applied=False → seçenek sadece "öneri", production-ready değil.
    """
    original_material_thickness_mm:  float
    proposed_material_thickness_mm:  float

    # Hacim delta
    volume_gain_l:                   float = 0.0

    # Finger joint (yeni malzemeye göre)
    finger_joint_recalculated:       bool  = False
    joint_depth_mm:                  float = 0.0   # = proposed thickness
    joint_count:                     int   = 0     # en küçük kenar için
    joint_spacing_mm:                float = 0.0

    # Kerf / tolerans (yeni malzemeye göre)
    kerf_tolerance_mm:               float = 0.0

    # Panel boyutları değişti mi?
    panel_dims_recalculated:         bool  = False

    # Port geometrisi değişti mi?
    port_geometry_recalculated:      bool  = False

    # Genel bayrak
    recalculation_applied:           bool  = False

    def to_dict(self) -> dict:
        return {
            "original_material_thickness_mm":  self.original_material_thickness_mm,
            "proposed_material_thickness_mm":  self.proposed_material_thickness_mm,
            "volume_gain_l":                   round(self.volume_gain_l, 3),
            "finger_joint_recalculated":       self.finger_joint_recalculated,
            "joint_depth_mm":                  round(self.joint_depth_mm, 1),
            "joint_count":                     self.joint_count,
            "joint_spacing_mm":                round(self.joint_spacing_mm, 1),
            "kerf_tolerance_mm":               round(self.kerf_tolerance_mm, 2),
            "panel_dims_recalculated":         self.panel_dims_recalculated,
            "port_geometry_recalculated":      self.port_geometry_recalculated,
            "recalculation_applied":           self.recalculation_applied,
        }


# ── Çatışma Seçeneği ─────────────────────────────────────────────────────────

@dataclass
class ConflictOption:
    """Tek çözüm alternatifi — makine okunur + insan okunur."""
    option_id:                 str     # "A", "B", "C"
    strategy:                  str     # "shorten_port", "invert_driver", ...

    # Hacim hedefleri
    net_target_l:              float
    estimated_final_net_l:     float

    # Tuning
    tuning_target_hz:          float
    estimated_final_tuning_hz: float

    # Boyut
    outer_dimensions_mm:       list    # [w, h, d]

    # Malzeme (zorunlu alanlar — her seçenekte belirtilmeli)
    material_thickness_mm:     float = 18.0   # Mevcut/önerilen malzeme kalınlığı
    panel_join_strategy:       str   = "finger_joint"  # "finger_joint" | "dado" | "pocket_screw" | "dowel"

    # Durum
    fit_status:                str = "fits"        # "fits" | "exceeds_bagaj" | "marginal"
    manufacturability_status:  str = "ok"          # "ok" | "requires_tooling" | "not_feasible"

    # Deltalar
    acoustic_delta_pct:        float = 0.0
    space_delta_mm:            float = 0.0

    # Öneri & özet
    recommended:               bool  = False
    usta_summary:              str   = ""

    # Malzeme değişimi yeniden hesaplama (opsiyonel — sadece malzeme değişim senaryolarında)
    material_recalculation:    Optional["MaterialRecalculation"] = None

    # Üretim hazırlığı:
    # False → seçenek yalnızca "öneri", üretime gönderilemez
    production_ready:          bool  = True

    def __post_init__(self):
        """recalculation_applied=False olan malzeme değişimi → production_ready=False."""
        if self.material_recalculation is not None:
            if not self.material_recalculation.recalculation_applied:
                self.production_ready = False

    def to_dict(self) -> dict:
        d = {
            "option_id":                 self.option_id,
            "strategy":                  self.strategy,
            "net_target_l":              round(self.net_target_l, 3),
            "estimated_final_net_l":     round(self.estimated_final_net_l, 3),
            "tuning_target_hz":          round(self.tuning_target_hz, 1),
            "estimated_final_tuning_hz": round(self.estimated_final_tuning_hz, 1),
            "outer_dimensions_mm":       self.outer_dimensions_mm,
            "material_thickness_mm":     self.material_thickness_mm,
            "panel_join_strategy":       self.panel_join_strategy,
            "fit_status":                self.fit_status,
            "manufacturability_status":  self.manufacturability_status,
            "acoustic_delta_pct":        round(self.acoustic_delta_pct, 2),
            "space_delta_mm":            round(self.space_delta_mm, 1),
            "recommended":               self.recommended,
            "production_ready":          self.production_ready,
            "usta_summary":              self.usta_summary,
        }
        if self.material_recalculation is not None:
            d["material_recalculation"] = self.material_recalculation.to_dict()
        return d


# ── Çatışma Raporu ────────────────────────────────────────────────────────────

@dataclass
class ConflictReport:
    """Çakışma tespitinde üretilen tam rapor."""
    mode:                   str
    conflict_detected:      bool
    conflict_type:          str
    conflict_severity:      str
    outer_dimensions_locked: bool
    acoustic_targets_locked: bool
    options:                list   # list[ConflictOption]

    # Teknik detay
    net_target_l:           float = 0.0
    final_calculated_net_l: float = 0.0
    delta_pct:              float = 0.0
    tuning_target_hz:       float = 0.0
    outer_original_mm:      list  = field(default_factory=list)
    outer_final_mm:         list  = field(default_factory=list)
    volume_lock_status:     str   = "unlocked"
    space_fit_status:       str   = "unknown"
    manufacturability_status: str = "unknown"
    resize_applied:         bool  = False
    resize_allowed:         bool  = False

    # Usta özeti (insan okunur)
    usta_summary:           str   = ""

    def to_dict(self) -> dict:
        return {
            "mode":                    self.mode,
            "conflict_detected":       self.conflict_detected,
            "conflict_type":           self.conflict_type,
            "conflict_severity":       self.conflict_severity,
            "outer_dimensions_locked": self.outer_dimensions_locked,
            "acoustic_targets_locked": self.acoustic_targets_locked,
            "net_target_l":            round(self.net_target_l, 3),
            "final_calculated_net_l":  round(self.final_calculated_net_l, 3),
            "delta_pct":               round(self.delta_pct, 2),
            "tuning_target_hz":        round(self.tuning_target_hz, 1),
            "outer_original_mm":       self.outer_original_mm,
            "outer_final_mm":          self.outer_final_mm,
            "volume_lock_status":      self.volume_lock_status,
            "space_fit_status":        self.space_fit_status,
            "manufacturability_status":self.manufacturability_status,
            "resize_applied":          self.resize_applied,
            "resize_allowed":          self.resize_allowed,
            "usta_summary":            self.usta_summary,
            "options":                 [o.to_dict() for o in self.options],
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent)

    @property
    def has_options(self) -> bool:
        return len(self.options) > 0

    @property
    def recommended_option(self) -> Optional[ConflictOption]:
        for o in self.options:
            if o.recommended:
                return o
        return self.options[0] if self.options else None


# ── Hata Sınıfı ──────────────────────────────────────────────────────────────

class ConstraintConflictError(Exception):
    """
    Kısıt çakışması tespit edildi.

    Bu bir "dur ve bak" sinyali — ham hata değil.
    Caller .conflict_report üzerinden alternatiflere ulaşabilir.
    """

    def __init__(
        self,
        conflict_type: ConflictType,
        severity: ConflictSeverity,
        report: ConflictReport,
        message: str = "",
    ):
        self.conflict_type = conflict_type
        self.severity      = severity
        self.conflict_report = report
        msg = message or (
            f"[CONSTRAINT] {conflict_type.value} / {severity.value}: "
            f"{report.usta_summary}"
        )
        super().__init__(msg)

    def to_dict(self) -> dict:
        return self.conflict_report.to_dict()

    def to_json(self) -> str:
        return self.conflict_report.to_json()
