"""
core/box/bandpass_4th.py
DD1 4. Derece Bandpass Kabin Modülü (Single-Reflex Bandpass)

4th Order Bandpass özellikleri:
  - İç oda: KAPALI (sealed) — woofer bu odaya monteli
  - Dış oda: PORTLU (ported/bass reflex) — port buradan çıkar
  - Ses sadece port üzerinden yayılır (woofer görünmez)
  - Bant geçiren filtre etkisi: alt + üst kesim frekansı
  - Yüksek SPL, dar bant — SQL/SPL yarışmaları için ideal
  - Car audio'da en yaygın bandpass türü

Frekans yanıtı:
  - f_low  ≈ fc_sealed (iç oda rezonansı) — alt sınır
  - f_high ≈ fb_ported (dış oda tuning frekansı) — üst sınır
  - Bant: f_low ~ f_high arası geçirimli, dışarısı 24dB/oct roll-off

Hacim oranı:
  - V_sealed / V_ported ≈ 0.4 ~ 0.6 (tipik)
  - Düşük oran (0.4): dar bant, yüksek SPL
  - Yüksek oran (0.6): geniş bant, daha doğal

Yapı:
  - Bölme duvarı (divider) iki odayı ayırır
  - Woofer bölme duvarına monte edilir
  - Port dış odanın ön/arka panelinden çıkar
"""
from __future__ import annotations
import logging
import math
from dataclasses import dataclass
from typing import Optional

from core.geometry import (
    CabinetGeometry, PanelDim, PortGeometry, VolumeBreakdown,
    compute_inner_dims, compute_port_geometry,
    compute_port_wall_panel,
)

logger = logging.getLogger("dd1.box.bandpass4")

MM3_TO_L = 1e-6


# ── Giriş Verisi ─────────────────────────────────────────────────────────────

@dataclass
class Bandpass4thInput:
    """
    4. Derece Bandpass kabin parametreleri.

    Toplam dış ölçüler belirlenir, iç bölme oranla hesaplanır.

    volume_ratio: sealed_vol / total_inner_vol (varsayılan 0.45)
      - 0.35 → dar bant, çok yüksek SPL (SQL)
      - 0.45 → dengeli bandpass
      - 0.60 → geniş bant, daha doğal ses
    """
    # Dış ölçüler (toplam kabin)
    total_width_mm:  float
    total_height_mm: float
    total_depth_mm:  float

    # Hedef hacimler (ikisi de verilebilir ya da oran kullanılır)
    sealed_vol_l:    float = 0.0    # 0 → otomatik (ratio'dan)
    ported_vol_l:    float = 0.0    # 0 → otomatik

    # Hacim oranı (sealed / total)
    volume_ratio:    float = 0.45

    # Malzeme
    thickness_mm:    float = 18.0
    finger_joint:    bool  = True
    kerf_mm:         float = 0.2
    tolerance_mm:    float = 0.1
    bracing_pct:     float = 0.02

    # Sürücü (bölme duvarına monteli)
    driver_hole_mm:  float = 282.0

    # Port (dış oda)
    port_area_cm2:   float = 0.0    # 0 → otomatik
    port_length_cm:  float = 0.0    # 0 → otomatik
    port_type:       str   = "rectangular_slot"
    port_count:      int   = 1
    target_fb_hz:    float = 0.0    # Dış oda tuning (üst sınır frekansı)

    # Akustik (opsiyonel)
    qts:             Optional[float] = None
    vas_l:           Optional[float] = None
    fs_hz:           Optional[float] = None


# ── Akustik Rapor ─────────────────────────────────────────────────────────────

@dataclass
class Bandpass4thAcousticReport:
    """4th order bandpass alignment raporu."""
    f_low_hz:        Optional[float]  # Alt sınır ~ iç oda kesim frekansı
    f_high_hz:       float            # Üst sınır ~ tuning frekansı (fb)
    bandwidth_hz:    Optional[float]  # Bant genişliği
    volume_ratio:    float            # sealed / (sealed+ported)
    alignment:       str              # "sql" | "balanced" | "wide"
    notes:           list[str]


def _compute_fb(port_area_cm2: float, port_length_cm: float, vol_l: float) -> float:
    """Helmholtz rezonans frekansı (m → Hz)."""
    Av = port_area_cm2 * 1e-4
    Vb = vol_l * 1e-3
    Lv = port_length_cm * 1e-2
    if Lv <= 0 or Vb <= 0 or Av <= 0:
        return 0.0
    return round((343.0 / (2 * math.pi)) * math.sqrt(Av / (Vb * Lv)), 1)


def _auto_port(ported_vol_l: float, target_fb: float, fs_hz: Optional[float]) -> tuple[float, float]:
    """Otomatik port hesabı (ported.py ile aynı mantık)."""
    if target_fb <= 0:
        target_fb = (fs_hz * 1.2) if fs_hz else 50.0
    port_area = max(ported_vol_l * 1.2, 30.0)
    Av = port_area * 1e-4
    Vb = ported_vol_l * 1e-3
    Lv_m = (343.0**2 * Av) / (4 * math.pi**2 * target_fb**2 * Vb)
    port_length = max(round(Lv_m * 100, 1), 5.0)
    return round(port_area, 1), port_length


# ── Panel Hesaplama ───────────────────────────────────────────────────────────

def _compute_bandpass4_panels(
    w: float, h: float, d: float,
    t: float, divider_depth_mm: float,
) -> list[PanelDim]:
    """
    Bandpass 4th order panel listesi.

    Bölme (divider) derinliği: iç oda derinliğine eşit.
    Toplam derinlik = sealed_derinlik + divider_t + ported_derinlik

    Panel rolleri:
      main      → 6 dış panel
      divider   → bölme duvarı (woofer montaj yeri)
      port_wall → dış odanın port duvarı
    """
    panels = [
        PanelDim("ON_PANEL",    w,           h,           t, role="main"),
        PanelDim("ARKA_PANEL",  w,           h,           t, role="main"),
        PanelDim("UST_PANEL",   w,           d - 2*t,     t, role="main"),
        PanelDim("ALT_PANEL",   w,           d - 2*t,     t, role="main"),
        PanelDim("SAG_PANEL",   h - 2*t,     d - 2*t,     t, role="main"),
        PanelDim("SOL_PANEL",   h - 2*t,     d - 2*t,     t, role="main"),
        # Bölme duvarı: tam iç yükseklik × iç genişlik
        PanelDim("BOLME_DUVARI", w - 2*t,   h - 2*t,     t, role="divider"),
    ]
    return panels


# ── Ana Oluşturucu ────────────────────────────────────────────────────────────

class Bandpass4thBox:
    """
    4. Derece Bandpass kabin geometri motoru.

    Kullanım:
        box = Bandpass4thBox()
        result = box.build(Bandpass4thInput(...))
    """

    def build(self, inp: Bandpass4thInput) -> dict:
        t = inp.thickness_mm
        W, H, D = inp.total_width_mm, inp.total_height_mm, inp.total_depth_mm

        logger.info(
            "[BP4] Build: W=%.0f H=%.0f D=%.0f t=%.0f ratio=%.2f",
            W, H, D, t, inp.volume_ratio
        )

        # İç toplam hacim
        iW = W - 2*t
        iH = H - 2*t
        iD = D - 2*t
        total_inner_l = iW * iH * iD * MM3_TO_L

        # Oda hacimleri
        if inp.sealed_vol_l > 0 and inp.ported_vol_l > 0:
            sealed_l = inp.sealed_vol_l
            ported_l = inp.ported_vol_l
        else:
            sealed_l = total_inner_l * inp.volume_ratio
            ported_l = total_inner_l * (1.0 - inp.volume_ratio)

        # Bracing
        sealed_net = sealed_l * (1 - inp.bracing_pct)
        ported_net = ported_l * (1 - inp.bracing_pct)

        # Driver displacement — iç odadan çıkar
        if inp.driver_hole_mm > 0:
            r = inp.driver_hole_mm / 2.0
            drv_l = math.pi * r**2 * 50.0 * MM3_TO_L
            sealed_net -= drv_l
        else:
            drv_l = 0.0

        # Bölme duvarı derinliği (bölme toplam derinliği ayırır)
        # Oran: sealed derinliği / toplam iç derinlik
        divider_d = iD * inp.volume_ratio

        # Port (dış oda)
        if inp.port_area_cm2 <= 0 or inp.port_length_cm <= 0:
            pa, pl = _auto_port(ported_net, inp.target_fb_hz, inp.fs_hz)
        else:
            pa, pl = inp.port_area_cm2, inp.port_length_cm

        port = compute_port_geometry(
            port_area_cm2=pa,
            port_length_cm=pl,
            port_type=inp.port_type,
            port_count=inp.port_count,
            cabinet_inner_h_mm=iH,
            cabinet_inner_w_mm=iW,
        )

        fb = _compute_fb(port.area_cm2, port.length_mm / 10.0, ported_net)

        # Volume breakdown (total perspektifinden)
        gross_l = W * H * D * MM3_TO_L
        vol = VolumeBreakdown(
            gross_l=round(gross_l, 4),
            inner_l=round(total_inner_l, 4),
            driver_displ_l=round(drv_l, 4),
            port_displ_l=round(port.displacement_l, 4),
            bracing_displ_l=round(total_inner_l * inp.bracing_pct, 4),
            net_acoustic_l=round(sealed_net + ported_net, 4),
            target_net_l=round(sealed_net + ported_net, 4),
            error_pct=0.0,
        )

        # Paneller
        panels = _compute_bandpass4_panels(W, H, D, t, divider_d)
        port_wall = compute_port_wall_panel(port, t)
        port_wall = PanelDim("PORT_DUVARI", port.length_mm, port.height_mm, t, role="port_wall")
        panels.append(port_wall)

        # Finger joint
        fj_active, fj_width = self._finger_joint_config(panels, t, inp.finger_joint)

        cabinet = CabinetGeometry(
            outer_w_mm=W, outer_h_mm=H, outer_d_mm=D,
            inner_w_mm=iW, inner_h_mm=iH, inner_d_mm=iD,
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

        # Akustik rapor
        notes = []
        f_low = None
        if inp.fs_hz and inp.qts:
            f_low = round(inp.fs_hz * math.sqrt(1 + inp.vas_l / sealed_net) / inp.qts * inp.qts, 1) if inp.vas_l else None

        bw = round(fb - f_low, 1) if (fb and f_low) else None

        ratio = sealed_l / (sealed_l + ported_l)
        if ratio < 0.40:
            alignment = "sql"
            notes.append(f"Oran {ratio:.2f} — dar bant, çok yüksek SPL (SQL/SPL).")
        elif ratio <= 0.55:
            alignment = "balanced"
            notes.append(f"Oran {ratio:.2f} — dengeli bandpass, iyi punch.")
        else:
            alignment = "wide"
            notes.append(f"Oran {ratio:.2f} — geniş bant, daha doğal ses.")

        notes.append(f"İç oda (sealed): ~{sealed_net:.1f}L  |  Dış oda (ported): ~{ported_net:.1f}L")
        notes.append(f"Tuning (fb): {fb}Hz — bant üst sınırı.")
        notes.append("Woofer bölme duvarına monte edilir — ses sadece porttan çıkar.")

        acoustic = Bandpass4thAcousticReport(
            f_low_hz=f_low, f_high_hz=fb,
            bandwidth_hz=bw, volume_ratio=round(ratio, 3),
            alignment=alignment, notes=notes
        )

        panel_list = [
            {"ad": p.name, "en_mm": round(p.width_mm, 1),
             "boy_mm": round(p.height_mm, 1), "kalinlik": t, "adet": 1, "rol": p.role}
            for p in panels
        ]

        logger.info("[BP4] Tamamlandi: %d panel, fb=%.1fHz, ratio=%.2f", len(panels), fb, ratio)

        return {
            "cabinet":       cabinet,
            "acoustic":      acoustic,
            "panel_list":    panel_list,
            "volume":        vol,
            "cab_type":      "bandpass_4th",
            "sealed_vol_l":  round(sealed_net, 2),
            "ported_vol_l":  round(ported_net, 2),
        }

    @staticmethod
    def _finger_joint_config(panels, t, enabled):
        if not enabled:
            return False, 0.0
        min_edge = min(min(p.width_mm, p.height_mm) for p in panels if p.role in ("main", "divider"))
        return (True, t) if min_edge >= 3 * t else (False, 0.0)


# ── CLI Test ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    sys.path.insert(0, "C:/Users/DDSOUND/Desktop/exemiz/dd1_platform")

    box = Bandpass4thBox()
    inp = Bandpass4thInput(
        total_width_mm=600, total_height_mm=450, total_depth_mm=500,
        thickness_mm=18,
        volume_ratio=0.45,
        driver_hole_mm=310,
        target_fb_hz=50.0,
        qts=0.38, vas_l=55.0, fs_hz=28.0,
    )
    result = box.build(inp)

    print("\n=== 4TH ORDER BANDPASS TEST ===")
    print(f"Kabin turu   : {result['cab_type']}")
    print(f"IC oda        : {result['sealed_vol_l']:.1f}L (kapali)")
    print(f"Dis oda       : {result['ported_vol_l']:.1f}L (portlu)")
    a = result["acoustic"]
    print(f"Tuning (fb)  : {a.f_high_hz}Hz")
    print(f"Alt sinir    : {a.f_low_hz}Hz")
    print(f"Bant         : {a.bandwidth_hz}Hz")
    print(f"Alignment    : {a.alignment}")
    for n in a.notes:
        print(f"  NOT: {n}")
    print(f"Panel sayisi : {len(result['panel_list'])}")
    for p in result["panel_list"]:
        print(f"  {p['ad']:15s} {p['en_mm']:.0f}x{p['boy_mm']:.0f}mm  [{p['rol']}]")
