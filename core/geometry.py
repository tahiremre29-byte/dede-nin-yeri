"""
core/geometry.py
DD1 Akustik Geometri Motoru

Net/gross hacim hesaplama, displacement breakdown, panel ölçüleri.
Tüm hesaplar milimetrik veriden litre'ye çevrilir.

Kural: Bu modül saf matematik — I/O yok, ezdxf yok, ajan yok.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional
import math


MM3_TO_L = 1e-6   # mm³ → litre


# ── Veri Yapıları ──────────────────────────────────────────────────────────────

@dataclass
class PanelDim:
    """Tek panel milimetrik ölçüsü."""
    name:       str
    width_mm:   float
    height_mm:  float
    thickness_mm: float
    role:       str = "main"   # main | port_wall | brace

    @property
    def area_mm2(self) -> float:
        return self.width_mm * self.height_mm

    def __repr__(self) -> str:
        return (f"Panel({self.name} "
                f"{self.width_mm:.1f}x{self.height_mm:.1f}x{self.thickness_mm:.1f}mm)")


@dataclass
class VolumeBreakdown:
    """Hacim analizi — tüm değerler litre cinsinden."""
    gross_l:            float   # Dış ölçülerin body hacmi
    inner_l:            float   # İç boşluk (malzeme kalınlığı çıkarılmış)
    driver_displ_l:     float   # Sürücü displacement
    port_displ_l:       float   # Port displacement
    bracing_displ_l:    float   # Takoz/bracing displacement
    net_acoustic_l:     float   # Gerçek akustik net hacim
    target_net_l:       float   # Kabin Ustası hedef net hacmi
    error_pct:          float   # Sapma %
    delta_pct:          float = 0.0   # Final delta (auto-resize sonrası)
    resized:            bool  = False  # Auto-resize uygulandı mı


@dataclass
class PortGeometry:
    """Slot port geometrisi."""
    port_type:      str       # "rectangular_slot" | "circular" | "l_port"
    width_mm:       float
    height_mm:      float
    length_mm:      float
    count:          int = 1
    area_cm2:       float = 0.0
    displacement_l: float = 0.0

    def __post_init__(self):
        if not self.area_cm2:
            self.area_cm2 = (self.width_mm * self.height_mm) / 100.0
        if not self.displacement_l:
            self.displacement_l = (
                self.width_mm * self.height_mm * self.length_mm
                * self.count * MM3_TO_L
            )


@dataclass
class CabinetGeometry:
    """Tam kabin geometrisi — box_generator'ın ana çıktısı."""
    # Ölçüler
    outer_w_mm:   float
    outer_h_mm:   float
    outer_d_mm:   float
    inner_w_mm:   float
    inner_h_mm:   float
    inner_d_mm:   float
    thickness_mm: float

    # Hacim
    volume:       VolumeBreakdown = field(default=None)

    # Paneller
    panels:       list[PanelDim] = field(default_factory=list)

    # Port
    port:         Optional[PortGeometry] = None

    # Finger joint
    finger_joint_active: bool = True
    finger_width_mm:     float = 0.0   # malzeme kalınlığı = diş genişliği
    kerf_mm:             float = 0.2   # lazer kerf telafisi
    tolerance_mm:        float = 0.1

    # Driver
    driver_hole_mm:      float = 0.0   # baffle woofer hole çapı


# ── Ana Hesaplama Fonksiyonları ────────────────────────────────────────────────

def compute_inner_dims(
    w_mm: float, h_mm: float, d_mm: float, t_mm: float
) -> tuple[float, float, float]:
    """
    Dış ölçü + malzeme kalınlığı → iç ölçü.
    Standart: Üst/Alt panel tam genişlik, Sağ/Sol kısa (araya sığar).
    Ön/Arka tam genişlik.
    """
    inner_w = w_mm - 2 * t_mm
    inner_h = h_mm - 2 * t_mm
    inner_d = d_mm - 2 * t_mm
    return inner_w, inner_h, inner_d


def volume_breakdown(
    w_mm: float, h_mm: float, d_mm: float, t_mm: float,
    target_net_l: float,
    driver_hole_mm: float = 282.0,  # woofer delik çapı mm
    port: Optional[PortGeometry] = None,
    bracing_pct: float = 0.02,      # % bracing hacim payı
) -> VolumeBreakdown:
    """
    Tam hacim analizi.

    gross_l       → dış bounding box hacmi
    inner_l       → iç boşluk (malzeme çıkarıldı)
    driver_displ  → woofer motor + basket (delik hacmi × panel derinliği %20 kestirimi)
    port_displ    → port objesi
    bracing_displ → iç ağaç takozlar (inner_l × bracing_pct)
    net_acoustic  → kullanılabilir akustik hacim
    """
    gross_l  = w_mm * h_mm * d_mm * MM3_TO_L

    iw, ih, id_ = compute_inner_dims(w_mm, h_mm, d_mm, t_mm)
    inner_l  = iw * ih * id_ * MM3_TO_L

    # Driver displacement: woofer delik hacmi × yaklaşık 50mm motor derinliği
    if driver_hole_mm > 0:
        r_mm = driver_hole_mm / 2.0
        driver_displ_l = math.pi * r_mm**2 * 50.0 * MM3_TO_L
    else:
        driver_displ_l = 0.0

    port_displ_l = port.displacement_l if port else 0.0
    bracing_displ_l = inner_l * bracing_pct

    net_acoustic_l = inner_l - driver_displ_l - port_displ_l - bracing_displ_l
    error_pct = abs(net_acoustic_l - target_net_l) / max(target_net_l, 0.001) * 100

    return VolumeBreakdown(
        gross_l=round(gross_l, 4),
        inner_l=round(inner_l, 4),
        driver_displ_l=round(driver_displ_l, 4),
        port_displ_l=round(port_displ_l, 4),
        bracing_displ_l=round(bracing_displ_l, 4),
        net_acoustic_l=round(net_acoustic_l, 4),
        target_net_l=round(target_net_l, 4),
        error_pct=round(error_pct, 2),
    )


def compute_panels(
    w_mm: float, h_mm: float, d_mm: float, t_mm: float
) -> list[PanelDim]:
    """
    6 ana panel (klasik ön kabuk yapısı).

    Birleşim kuralı:
      Ön / Arka → tam W × H (dışarıdan)
      Üst / Alt → tam W × (D - 2t) (genişlik tam, derinlikten 2t çıkılır)
      Sağ / Sol → (H - 2t) × (D - 2t) (her iki eksende kısalır)
    """
    iw = w_mm - 2 * t_mm
    ih = h_mm - 2 * t_mm
    id_ = d_mm - 2 * t_mm

    return [
        PanelDim("ON_PANEL",   w_mm, h_mm,  t_mm, role="main"),  # Ön (baffle)
        PanelDim("ARKA_PANEL", w_mm, h_mm,  t_mm, role="main"),  # Arka
        PanelDim("UST_PANEL",  w_mm, id_,   t_mm, role="main"),  # Üst
        PanelDim("ALT_PANEL",  w_mm, id_,   t_mm, role="main"),  # Alt
        PanelDim("SAG_PANEL",  ih,   id_,   t_mm, role="main"),  # Sağ yan
        PanelDim("SOL_PANEL",  ih,   id_,   t_mm, role="main"),  # Sol yan
    ]


def compute_port_geometry(
    port_area_cm2: float,
    port_length_cm: float,
    port_type: str = "rectangular_slot",
    port_count: int = 1,
    cabinet_inner_h_mm: float = 0.0,
    cabinet_inner_w_mm: float = 0.0,
) -> PortGeometry:
    """
    Port geometrisi hesapla.

    rectangular_slot: kare kesit (Alan = yan × yan)
    Desteklenmeyen tip → ValueError
    """
    SUPPORTED = ("rectangular_slot",)
    if port_type not in SUPPORTED:
        raise ValueError(
            f"Desteklenmeyen port tipi: '{port_type}'. "
            f"Desteklenenler: {SUPPORTED}. "
            "L-Port opsiyonel mod — port_type='rectangular_slot' kullanın."
        )

    area_mm2 = port_area_cm2 * 100.0   # cm² → mm²
    length_mm = port_length_cm * 10.0  # cm → mm

    # Kare kesit (eşit kenar)
    side_mm = math.sqrt(area_mm2)
    pw = side_mm
    ph = side_mm

    # Port panele sığıyor mu?
    if cabinet_inner_h_mm > 0 and ph > cabinet_inner_h_mm:
        raise ValueError(
            f"Port yuksekligi ({ph:.1f}mm) ic kabin yuksekligini "
            f"({cabinet_inner_h_mm:.1f}mm) asiyor! Port geometry siwmiyor."
        )
    if cabinet_inner_w_mm > 0 and pw > cabinet_inner_w_mm:
        raise ValueError(
            f"Port genisligi ({pw:.1f}mm) ic kabin genisligini "
            f"({cabinet_inner_w_mm:.1f}mm) asiyor!"
        )

    return PortGeometry(
        port_type=port_type,
        width_mm=round(pw, 2),
        height_mm=round(ph, 2),
        length_mm=round(length_mm, 2),
        count=port_count,
        area_cm2=round(port_area_cm2, 4),
    )


def compute_port_wall_panel(port: PortGeometry, t_mm: float) -> PanelDim:
    """Port iç duvar paneli (slot port için)."""
    return PanelDim(
        name="PORT_DUVAR",
        width_mm=port.length_mm,
        height_mm=port.height_mm,
        thickness_mm=t_mm,
        role="port_wall",
    )


def check_volume_revalidation(
    vol: VolumeBreakdown,
    tolerance_pct: float = 5.0,
) -> tuple[bool, str]:
    """
    Çizilen geometrinin net hacminin KabinUstası hedefiyle eşleşip eşleşmediğini kontrol et.
    tolerance_pct: izin verilen max sapma %
    Döner: (passed, mesaj)
    """
    delta = vol.delta_pct if vol.delta_pct else vol.error_pct
    if delta <= tolerance_pct:
        return True, f"Hacim dogrulama OK: {vol.net_acoustic_l:.2f}L (hedef {vol.target_net_l:.2f}L, delta %{delta:.2f})"
    else:
        return False, (
            f"Hacim sapma LIMITI ASILDI: hesaplanan={vol.net_acoustic_l:.2f}L "
            f"hedef={vol.target_net_l:.2f}L delta=%{delta:.2f} "
            f"(max={tolerance_pct}%)"
        )


# ── Auto-Resize ───────────────────────────────────────────────────────────────

def auto_resize_dims(
    target_net_l:  float,
    w_mm: float, h_mm: float, d_mm: float, t_mm: float,
    driver_hole_mm: float = 282.0,
    port: Optional[PortGeometry] = None,
    bracing_pct: float = 0.02,
    tolerance_pct: float = 1.0,
    max_iter: int = 64,
) -> tuple[float, float, float, VolumeBreakdown]:
    """
    İç net hacmi hedeflemek için dış ölçüleri otomatik büyüt.

    Algoritma: Binary search — ölçek katsayısı ile tüm boyutları orantılı ölçekle.
    Döner: (new_w, new_h, new_d, updated_VolumeBreakdown)
    Sapma hedefi: < tolerance_pct (varsayılan %1)

    Neden binary search:
      net_acoustic_l(scale) = f(scale) monoton artan → binary search garantili.
    """
    def _calc_net(scale: float) -> float:
        ws, hs, ds = w_mm * scale, h_mm * scale, d_mm * scale
        iw = ws - 2 * t_mm
        ih = hs - 2 * t_mm
        id_ = ds - 2 * t_mm
        if iw <= 0 or ih <= 0 or id_ <= 0:
            return 0.0
        inner_l = iw * ih * id_ * MM3_TO_L
        r_mm = driver_hole_mm / 2.0 if driver_hole_mm > 0 else 0.0
        drv = math.pi * r_mm**2 * 50.0 * MM3_TO_L if r_mm > 0 else 0.0
        prt = port.displacement_l if port else 0.0
        brc = inner_l * bracing_pct
        return inner_l - drv - prt - brc

    # Hızlı kestirme başlangıç ölçeği
    current_net = _calc_net(1.0)
    if current_net <= 0:
        raise ValueError("Başlangıç iç hacim sıfır veya negatif — ölçüler çok küçük.")

    # Büyütme mi küçültme mi?
    lo, hi = 0.5, 5.0
    for _ in range(max_iter):
        mid = (lo + hi) / 2.0
        net = _calc_net(mid)
        err = (net - target_net_l) / target_net_l * 100
        if abs(err) <= tolerance_pct:
            break
        if net < target_net_l:
            lo = mid
        else:
            hi = mid

    scale = (lo + hi) / 2.0
    new_w = round(w_mm * scale, 1)
    new_h = round(h_mm * scale, 1)
    new_d = round(d_mm * scale, 1)

    # Güncel volume breakdown
    vol = volume_breakdown(
        w_mm=new_w, h_mm=new_h, d_mm=new_d,
        t_mm=t_mm,
        target_net_l=target_net_l,
        driver_hole_mm=driver_hole_mm,
        port=port,
        bracing_pct=bracing_pct,
    )
    # delta_pct güncellemesi — dataclass frozen değil, field atama
    final_delta = abs(vol.net_acoustic_l - target_net_l) / max(target_net_l, 0.001) * 100
    # Yeni VolumeBreakdown delta_pct ile
    vol = VolumeBreakdown(
        gross_l=vol.gross_l,
        inner_l=vol.inner_l,
        driver_displ_l=vol.driver_displ_l,
        port_displ_l=vol.port_displ_l,
        bracing_displ_l=vol.bracing_displ_l,
        net_acoustic_l=vol.net_acoustic_l,
        target_net_l=vol.target_net_l,
        error_pct=vol.error_pct,
        delta_pct=round(final_delta, 3),
        resized=True,
    )
    return new_w, new_h, new_d, vol
