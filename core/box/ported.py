"""
core/box/ported.py
DD1 Portlu Kabin (Bass Reflex / Ported Enclosure) Modülü

Bass Reflex özellikleri:
  - Tuned port (rezonans tüneli) — Helmholtz rezonatörü prensibi
  - fb (tuning frequency): port uzunluğu ve alanıyla ayarlanır
  - Sealed'e göre daha derin bas, daha yüksek SPL
  - Port: dikdörtgen slot, yuvarlak boru veya L-port
  - Woofer cutoff altında hızlı roll-off (24dB/oct)

Formüller:
  - fb = (c / 2π) × sqrt(Av / (Vb × Lv))
    Av: port kesit alanı (cm²), Lv: efektif uzunluk (cm), Vb: net hacim (litre)
  - Optimal fb ≈ Fs × (Qts/0.4)^(1/n)
  - Port çapı minimum: prevent port chuffing (hava hızı < 17 m/s)
"""
from __future__ import annotations
import logging
import math
from dataclasses import dataclass
from typing import Optional

from core.geometry import (
    CabinetGeometry, PanelDim, PortGeometry, VolumeBreakdown,
    compute_inner_dims, compute_panels, compute_port_geometry,
    compute_port_wall_panel, check_volume_revalidation,
)

logger = logging.getLogger("dd1.box.ported")

MM3_TO_L = 1e-6
C_SOUND  = 34300.0   # Ses hızı mm/s (20°C)


# ── Giriş Verisi ─────────────────────────────────────────────────────────────

@dataclass
class PortedBoxInput:
    """
    Portlu kabin parametreleri.

    Port:
      port_area_cm2    → port ağzı kesit alanı (cm²)
      port_length_cm   → port tüp uzunluğu (cm)
      port_type        → "rectangular_slot" | "circular"
      port_count       → port adedi (1 veya 2)

    Akustik (opsiyonel):
      qts, vas_l, fs_hz → sürücü parametreleri
      target_fb_hz      → hedef tuning frekansı (Hz) — 0 ise otomatik
    """
    # Boyutlar
    net_volume_l:    float
    width_mm:        float
    height_mm:       float
    depth_mm:        float

    # Malzeme
    thickness_mm:    float = 18.0
    finger_joint:    bool  = True
    kerf_mm:         float = 0.2
    tolerance_mm:    float = 0.1
    bracing_pct:     float = 0.02

    # Sürücü
    driver_hole_mm:  float = 282.0

    # Port
    port_area_cm2:   float = 0.0    # 0 → otomatik (tuning'e göre)
    port_length_cm:  float = 0.0    # 0 → otomatik
    port_type:       str   = "rectangular_slot"
    port_count:      int   = 1

    # Akustik
    qts:             Optional[float] = None
    vas_l:           Optional[float] = None
    fs_hz:           Optional[float] = None
    target_fb_hz:    float = 0.0    # 0 → otomatik (Fs × 0.7 kestirimi)


# ── Akustik Tavsiye Motoru ────────────────────────────────────────────────────

@dataclass
class PortedAcousticReport:
    """Bass reflex alignment raporu."""
    fb_hz:           float             # Gerçekleşen tuning frekansı
    port_velocity_ms: Optional[float]  # Max hava hızı (chuffing kontrolü)
    chuffing_risk:   str               # "low" | "medium" | "high"
    optimal_fb_hz:   Optional[float]   # Sürücüye göre ideal fb
    alignment:       str               # "qtl" | "sb4" | "custom"
    notes:           list[str]


def compute_fb(port_area_cm2: float, port_length_cm: float, net_vol_l: float) -> float:
    """
    Helmholtz rezonans frekansı.
    fb = (c/2π) × sqrt(Av / (Vb × Lv))
    Tüm birimler SI (m³, m²) → Hz
    """
    Av = port_area_cm2 * 1e-4              # cm² → m²
    Vb = net_vol_l * 1e-3                  # L → m³
    Lv = port_length_cm * 1e-2            # cm → m
    if Lv <= 0 or Vb <= 0 or Av <= 0:
        return 0.0
    c  = 343.0                             # m/s
    fb = (c / (2 * math.pi)) * math.sqrt(Av / (Vb * Lv))
    return round(fb, 1)


def compute_ported_acoustic(inp: PortedBoxInput, port: PortGeometry) -> PortedAcousticReport:
    """Bass reflex alignment analizi."""
    notes = []

    fb = compute_fb(port.area_cm2, port.length_mm / 10.0, inp.net_volume_l)

    # Port hava hızı (chuffing kontrolü)
    # Max SPL @ Xmax → port velocity ≈ (Sd × Xmax × f) / Av
    port_vel = None
    chuffing = "bilinmiyor"
    if port.area_cm2 > 0:
        # Kestirme: 50W @ 8ohm → ~2.5m/s port hızı tipik
        # Gerçek hesap için Xmax ve Sd gerekir
        chuffing = "low"
        notes.append("Port hava hızı hesabı için Xmax ve Sd gerekli (opsiyonel).")

    # İdeal fb
    optimal_fb = None
    if inp.fs_hz and inp.qts:
        # QBP4 alignment: fb ≈ Fs × (Qts/0.4)^0.96
        optimal_fb = round(inp.fs_hz * (inp.qts / 0.4) ** 0.96, 1)
        notes.append(f"Sürücüye göre optimal fb: ~{optimal_fb}Hz")
        if fb > 0:
            diff = abs(fb - optimal_fb)
            if diff > 5:
                notes.append(
                    f"Tuning farkı: {diff:.1f}Hz — port uzunluğunu ayarla."
                )

    # Alignment türü
    if inp.target_fb_hz > 0:
        alignment = "custom"
    elif inp.qts and inp.qts <= 0.35:
        alignment = "sb4"
        notes.append("Düşük Qts → SB4 alignment önerilir.")
    else:
        alignment = "qtl"

    if fb > 0:
        if fb < 25:
            notes.append(f"fb={fb}Hz çok düşük — derin SQL bas ama evde zorlanıyor.")
        elif fb <= 40:
            notes.append(f"fb={fb}Hz — derin bas hedefli, iyi denge.")
        elif fb <= 60:
            notes.append(f"fb={fb}Hz — orta tuning, punch ve bas dengeli.")
        else:
            notes.append(f"fb={fb}Hz — yüksek tuning, fazla punch, derin bas az.")

    return PortedAcousticReport(
        fb_hz=fb, port_velocity_ms=port_vel,
        chuffing_risk=chuffing, optimal_fb_hz=optimal_fb,
        alignment=alignment, notes=notes
    )


# ── Otomatik Port Hesaplayıcı ─────────────────────────────────────────────────

def auto_port_params(
    net_vol_l: float,
    target_fb_hz: float,
    fs_hz: Optional[float],
    qts: Optional[float],
) -> tuple[float, float]:
    """
    Hedef fb'ye göre port alanı ve uzunluğunu hesapla.
    Kurallar:
      - Port alanı: net_vol_l × 12 cm² (kestirme)
      - Port uzunluğu: fb formülünden geri hesap
    """
    if target_fb_hz <= 0:
        # Otomatik: Fs × 0.7 veya 35Hz (varsayılan)
        if fs_hz:
            target_fb_hz = round(fs_hz * 0.7, 1)
        else:
            target_fb_hz = 35.0

    # Port alanı kestirimi: Vb(L) × 12 cm² (endüstri kural-of-thumb)
    port_area = round(net_vol_l * 1.2, 1)
    port_area = max(port_area, 30.0)  # minimum 30cm²

    # Port uzunluğu: Lv = c²×Av / (4π²×fb²×Vb)  (SI → cm'ye çevir)
    Av = port_area * 1e-4    # m²
    Vb = net_vol_l * 1e-3    # m³
    fb = target_fb_hz
    c  = 343.0
    Lv_m = (c**2 * Av) / (4 * math.pi**2 * fb**2 * Vb)
    port_length = round(Lv_m * 100, 1)  # m → cm
    port_length = max(port_length, 5.0)   # minimum 5cm

    return port_area, port_length


# ── Ana Kabin Oluşturucu ──────────────────────────────────────────────────────

class PortedBox:
    """
    Portlu kabin (bass reflex) geometri ve akustik motoru.

    Kullanım:
        box = PortedBox()
        result = box.build(PortedBoxInput(...))
    """

    VOLUME_REVALIDATION_TOL = 25.0

    def build(self, inp: PortedBoxInput) -> dict:
        """
        PortedBoxInput → {cabinet, acoustic, panel_list, volume}
        """
        t   = inp.thickness_mm
        w, h, d = inp.width_mm, inp.height_mm, inp.depth_mm

        logger.info(
            "[PORTED] Build: W=%.0f H=%.0f D=%.0f t=%.0f net=%.2fL port_area=%.1fcm2",
            w, h, d, t, inp.net_volume_l, inp.port_area_cm2
        )

        # İç ölçüler
        iw, ih, id_ = compute_inner_dims(w, h, d, t)
        if any(x <= 0 for x in [iw, ih, id_]):
            raise ValueError(
                f"İç ölçüler negatif: {iw:.1f}x{ih:.1f}x{id_:.1f}mm"
            )

        # Port parametreleri — oto veya kullanıcı girişi
        if inp.port_area_cm2 <= 0 or inp.port_length_cm <= 0:
            pa, pl = auto_port_params(
                inp.net_volume_l, inp.target_fb_hz, inp.fs_hz, inp.qts
            )
            logger.info("[PORTED] Oto port: alan=%.1fcm2 uzunluk=%.1fcm fb_hedef=%.1fHz",
                        pa, pl, inp.target_fb_hz or 35.0)
        else:
            pa, pl = inp.port_area_cm2, inp.port_length_cm

        # Port geometrisi
        port = compute_port_geometry(
            port_area_cm2=pa,
            port_length_cm=pl,
            port_type=inp.port_type,
            port_count=inp.port_count,
            cabinet_inner_h_mm=ih,
            cabinet_inner_w_mm=iw,
        )

        # Hacim breakdown
        gross_l = w * h * d * MM3_TO_L
        inner_l = iw * ih * id_ * MM3_TO_L
        brace_l = inner_l * inp.bracing_pct

        if inp.driver_hole_mm > 0:
            r_mm = inp.driver_hole_mm / 2.0
            drv_l = math.pi * r_mm**2 * 50.0 * MM3_TO_L
        else:
            drv_l = 0.0

        net_l = inner_l - drv_l - port.displacement_l - brace_l
        error_pct = abs(net_l - inp.net_volume_l) / max(inp.net_volume_l, 0.001) * 100

        vol = VolumeBreakdown(
            gross_l=round(gross_l, 4),
            inner_l=round(inner_l, 4),
            driver_displ_l=round(drv_l, 4),
            port_displ_l=round(port.displacement_l, 4),
            bracing_displ_l=round(brace_l, 4),
            net_acoustic_l=round(net_l, 4),
            target_net_l=round(inp.net_volume_l, 4),
            error_pct=round(error_pct, 2),
        )

        # Paneller + port duvar paneli
        panels = compute_panels(w, h, d, t)
        port_wall = compute_port_wall_panel(port, t)
        panels.append(port_wall)

        # Finger joint
        fj_active, fj_width = self._finger_joint_config(panels, t, inp.finger_joint)

        cabinet = CabinetGeometry(
            outer_w_mm=w, outer_h_mm=h, outer_d_mm=d,
            inner_w_mm=iw, inner_h_mm=ih, inner_d_mm=id_,
            thickness_mm=t,
            volume=vol,
            panels=panels,
            port=port,
            finger_joint_active=fj_active,
            finger_width_mm=fj_width,
            kerf_mm=inp.kerf_mm,
            tolerance_mm=inp.tolerance_mm,
            driver_hole_mm=inp.driver_hole_mm,
        )

        acoustic = compute_ported_acoustic(inp, port)
        panel_list = self._build_panel_list(panels, t)

        logger.info(
            "[PORTED] Tamamlandi: %d panel, fj=%s, fb=%.1fHz, port=%s",
            len(panels), fj_active, acoustic.fb_hz, inp.port_type
        )

        return {
            "cabinet":    cabinet,
            "acoustic":   acoustic,
            "panel_list": panel_list,
            "volume":     vol,
            "cab_type":   "ported",
        }

    @staticmethod
    def _finger_joint_config(panels, t, enabled):
        if not enabled:
            return False, 0.0
        min_edge = min(min(p.width_mm, p.height_mm) for p in panels if p.role == "main")
        if min_edge < 3 * t:
            return False, 0.0
        return True, t

    @staticmethod
    def _build_panel_list(panels, t):
        return [
            {
                "ad":       p.name,
                "en_mm":    round(p.width_mm, 1),
                "boy_mm":   round(p.height_mm, 1),
                "kalinlik": round(t, 1),
                "adet":     1,
                "rol":      p.role,
            }
            for p in panels
        ]


# ── CLI Test ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    sys.path.insert(0, "C:/Users/DDSOUND/Desktop/exemiz/dd1_platform")

    box = PortedBox()
    inp = PortedBoxInput(
        net_volume_l=50.0,
        width_mm=500, height_mm=420, depth_mm=380,
        thickness_mm=18,
        driver_hole_mm=310,
        port_area_cm2=0, port_length_cm=0,  # oto hesap
        target_fb_hz=35.0,
        qts=0.42, vas_l=80.0, fs_hz=26.0,
    )
    result = box.build(inp)

    print("\n=== PORTLU KABIN TEST ===")
    print(f"Kabin turu : {result['cab_type']}")
    v = result["volume"]
    print(f"Net hacim  : {v.net_acoustic_l:.2f}L (hedef: {v.target_net_l:.2f}L, sapma: %{v.error_pct:.2f})")
    a = result["acoustic"]
    print(f"fb (tuning): {a.fb_hz}Hz  Alignment: {a.alignment}")
    cab = result["cabinet"]
    print(f"Port       : {cab.port.width_mm:.0f}x{cab.port.height_mm:.0f}mm L={cab.port.length_mm:.0f}mm")
    for n in a.notes:
        print(f"  NOT: {n}")
    print(f"Panel sayisi: {len(result['panel_list'])}")
    for p in result["panel_list"]:
        print(f"  {p['ad']:12s} {p['en_mm']:.0f}x{p['boy_mm']:.0f}mm  [{p['rol']}]")
