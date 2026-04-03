"""
core/box/bandpass_6th.py
DD1 6. Derece Bandpass Kabin Modülü (Dual-Reflex Bandpass)

6th Order Bandpass özellikleri:
  - İç oda: PORTLU (bass reflex) — düşük fb, alt sınır
  - Dış oda: PORTLU (bass reflex) — yüksek fb, üst sınır
  - Woofer iki oda arasındaki bölme duvarına monte edilir
  - Her iki odanın portları farklı frekansa tuned edilir
  - İki ayrı bant geçiren filtre → 6. derece roll-off (36dB/oct)
  - 4th order'dan daha geniş bant, daha kontrollü
  - Karmaşık tasarım — iki port, iki tuning frekansı

Frekans yanıtı:
  - f_low  = iç odanın fb'si     → alt kesim (24dB/oct)
  - f_high = dış odanın fb'si    → üst kesim (24dB/oct)
  - Toplam: 36dB/oct roll-off her iki yönde

Tipik uygulama:
  - Hi-fi subwoofer, geniş bant bass
  - Car audio'da nadir — 4th order daha yaygın
  - Kabin daha büyük gerektiriyor
"""
from __future__ import annotations
import logging
import math
from dataclasses import dataclass
from typing import Optional

from core.geometry import (
    CabinetGeometry, PanelDim, PortGeometry, VolumeBreakdown,
    compute_inner_dims, compute_port_geometry,
)

logger = logging.getLogger("dd1.box.bandpass6")

MM3_TO_L = 1e-6


@dataclass
class Bandpass6thInput:
    """
    6. Derece Bandpass kabin parametreleri.

    İki ayrı oda, iki ayrı port:
      - inner_fb_hz: iç odanın tuning frekansı (alt sınır)
      - outer_fb_hz: dış odanın tuning frekansı (üst sınır)

    volume_ratio: inner_vol / total_inner_vol (varsayılan 0.45)
    """
    total_width_mm:  float
    total_height_mm: float
    total_depth_mm:  float

    # Hacim oranı: iç / toplam
    volume_ratio:    float = 0.45

    # Malzeme
    thickness_mm:    float = 18.0
    finger_joint:    bool  = True
    kerf_mm:         float = 0.2
    tolerance_mm:    float = 0.1
    bracing_pct:     float = 0.02

    # Sürücü
    driver_hole_mm:  float = 282.0

    # Port tuning
    inner_fb_hz:     float = 0.0    # 0 → otomatik (fs × 0.7)
    outer_fb_hz:     float = 0.0    # 0 → otomatik (fs × 1.4)
    port_type:       str   = "rectangular_slot"

    # Akustik
    qts:             Optional[float] = None
    vas_l:           Optional[float] = None
    fs_hz:           Optional[float] = None


@dataclass
class Bandpass6thAcousticReport:
    inner_fb_hz:   float   # İç oda tuning (alt sınır)
    outer_fb_hz:   float   # Dış oda tuning (üst sınır)
    bandwidth_hz:  float   # Bant genişliği
    volume_ratio:  float
    alignment:     str
    notes:         list[str]


def _fb(area_cm2: float, length_cm: float, vol_l: float) -> float:
    Av = area_cm2 * 1e-4
    Vb = vol_l * 1e-3
    Lv = length_cm * 1e-2
    if any(x <= 0 for x in [Av, Vb, Lv]):
        return 0.0
    return round((343.0 / (2 * math.pi)) * math.sqrt(Av / (Vb * Lv)), 1)


def _auto_port(vol_l: float, target_fb: float) -> tuple[float, float]:
    port_area = max(vol_l * 1.2, 30.0)
    Av = port_area * 1e-4
    Vb = vol_l * 1e-3
    fb = max(target_fb, 10.0)
    Lv = (343.0**2 * Av) / (4 * math.pi**2 * fb**2 * Vb)
    port_length = max(round(Lv * 100, 1), 5.0)
    return round(port_area, 1), port_length


class Bandpass6thBox:
    """
    6. Derece (Dual-Reflex) Bandpass kabin geometri motoru.
    """

    def build(self, inp: Bandpass6thInput) -> dict:
        t   = inp.thickness_mm
        W, H, D = inp.total_width_mm, inp.total_height_mm, inp.total_depth_mm

        logger.info("[BP6] Build: W=%.0f H=%.0f D=%.0f ratio=%.2f", W, H, D, inp.volume_ratio)

        iW, iH, iD = W - 2*t, H - 2*t, D - 2*t
        total_inner_l = iW * iH * iD * MM3_TO_L

        inner_l = total_inner_l * inp.volume_ratio
        outer_l = total_inner_l * (1 - inp.volume_ratio)

        bracing = inp.bracing_pct
        inner_net = inner_l * (1 - bracing)
        outer_net = outer_l * (1 - bracing)

        # Driver displacement — bölme duvarında, iç odadan çıkar
        if inp.driver_hole_mm > 0:
            r = inp.driver_hole_mm / 2.0
            drv_l = math.pi * r**2 * 50.0 * MM3_TO_L
            inner_net -= drv_l
        else:
            drv_l = 0.0

        # Oto tuning frekansları
        fs = inp.fs_hz
        inner_fb_target = inp.inner_fb_hz or ((fs * 0.7) if fs else 30.0)
        outer_fb_target = inp.outer_fb_hz or ((fs * 1.4) if fs else 55.0)

        # İç oda port
        inner_pa, inner_pl = _auto_port(inner_net, inner_fb_target)
        inner_port = compute_port_geometry(
            port_area_cm2=inner_pa, port_length_cm=inner_pl,
            port_type=inp.port_type, port_count=1,
            cabinet_inner_h_mm=iH, cabinet_inner_w_mm=iW,
        )
        inner_net -= inner_port.displacement_l

        # Dış oda port
        outer_pa, outer_pl = _auto_port(outer_net, outer_fb_target)
        outer_port = compute_port_geometry(
            port_area_cm2=outer_pa, port_length_cm=outer_pl,
            port_type=inp.port_type, port_count=1,
            cabinet_inner_h_mm=iH, cabinet_inner_w_mm=iW,
        )
        outer_net -= outer_port.displacement_l

        # Tuning frekansları
        inner_fb = _fb(inner_port.area_cm2, inner_port.length_mm / 10.0, max(inner_net, 0.1))
        outer_fb = _fb(outer_port.area_cm2, outer_port.length_mm / 10.0, max(outer_net, 0.1))

        # Hacim breakdown
        gross_l = W * H * D * MM3_TO_L
        vol = VolumeBreakdown(
            gross_l=round(gross_l, 4),
            inner_l=round(total_inner_l, 4),
            driver_displ_l=round(drv_l, 4),
            port_displ_l=round(inner_port.displacement_l + outer_port.displacement_l, 4),
            bracing_displ_l=round(total_inner_l * bracing, 4),
            net_acoustic_l=round(inner_net + outer_net, 4),
            target_net_l=round(inner_net + outer_net, 4),
            error_pct=0.0,
        )

        # Paneller
        panels = [
            PanelDim("ON_PANEL",     W,       H,       t, role="main"),
            PanelDim("ARKA_PANEL",   W,       H,       t, role="main"),
            PanelDim("UST_PANEL",    W,       iD,      t, role="main"),
            PanelDim("ALT_PANEL",    W,       iD,      t, role="main"),
            PanelDim("SAG_PANEL",    iH,      iD,      t, role="main"),
            PanelDim("SOL_PANEL",    iH,      iD,      t, role="main"),
            # Bölme duvarı (woofer montaj)
            PanelDim("BOLME_DUVARI", iW,      iH,      t, role="divider"),
            # İç oda port duvarı
            PanelDim("IC_PORT_DUVARI",  inner_port.length_mm, inner_port.height_mm, t, role="port_wall"),
            # Dış oda port duvarı
            PanelDim("DIS_PORT_DUVARI", outer_port.length_mm, outer_port.height_mm, t, role="port_wall"),
        ]

        fj_main = [p for p in panels if p.role in ("main", "divider")]
        fj_active = False
        fj_width = 0.0
        if inp.finger_joint and fj_main:
            min_edge = min(min(p.width_mm, p.height_mm) for p in fj_main)
            if min_edge >= 3 * t:
                fj_active, fj_width = True, t

        cabinet = CabinetGeometry(
            outer_w_mm=W, outer_h_mm=H, outer_d_mm=D,
            inner_w_mm=iW, inner_h_mm=iH, inner_d_mm=iD,
            thickness_mm=t, volume=vol, panels=panels,
            port=outer_port,    # DXF için dış oda port (ön panel)
            finger_joint_active=fj_active, finger_width_mm=fj_width,
            kerf_mm=inp.kerf_mm, tolerance_mm=inp.tolerance_mm,
            driver_hole_mm=inp.driver_hole_mm,
        )

        bw = round(outer_fb - inner_fb, 1)
        ratio = inner_l / (inner_l + outer_l)

        notes = [
            f"İç oda (portlu): ~{inner_net:.1f}L  fb={inner_fb}Hz — alt sınır",
            f"Dış oda (portlu): ~{outer_net:.1f}L  fb={outer_fb}Hz — üst sınır",
            f"Bant genişliği: {bw}Hz  |  Oran: {ratio:.2f}",
            "Woofer bölme duvarına monte edilir.",
            "İki ayrı port: iç odadan alt, dış odadan üst frekanslara tuned.",
        ]

        alignment = "balanced" if 0.40 <= ratio <= 0.55 else ("narrow" if ratio < 0.40 else "wide")

        acoustic = Bandpass6thAcousticReport(
            inner_fb_hz=inner_fb, outer_fb_hz=outer_fb,
            bandwidth_hz=bw, volume_ratio=round(ratio, 3),
            alignment=alignment, notes=notes,
        )

        panel_list = [
            {"ad": p.name, "en_mm": round(p.width_mm, 1),
             "boy_mm": round(p.height_mm, 1), "kalinlik": t, "adet": 1, "rol": p.role}
            for p in panels
        ]

        return {
            "cabinet":      cabinet,
            "acoustic":     acoustic,
            "panel_list":   panel_list,
            "volume":       vol,
            "cab_type":     "bandpass_6th",
            "inner_vol_l":  round(inner_net, 2),
            "outer_vol_l":  round(outer_net, 2),
            "inner_fb_hz":  inner_fb,
            "outer_fb_hz":  outer_fb,
        }
