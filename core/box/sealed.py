"""
core/box/sealed.py
DD1 Kapalı Kutu (Sealed Enclosure) Modülü

Kapalı kutu özellikleri:
  - Port YOK — hava sızıntısı olmayan tamamen kapalı yapı
  - Sıkı, kontrollü bas — düşük distorsiyon
  - Qtc (toplam Q) hedefi: 0.707 (Butterworth) optimal düzlük
  - Daha küçük hacimde çalışabilir (ported'a göre)

Formüller:
  - Vb = Vas × (Qts / Qtc)^(1/n)   [basitleştirilmiş: n=2]
  - Gerçek optimum: sealed alignment hesabı
  - fc (cut-off freq) = Fs × Qtc / Qts
"""
from __future__ import annotations
import logging
import math
from dataclasses import dataclass
from typing import Optional

from core.geometry import (
    CabinetGeometry, PanelDim, VolumeBreakdown,
    compute_inner_dims, compute_panels,
    check_volume_revalidation,
)

logger = logging.getLogger("dd1.box.sealed")

MM3_TO_L = 1e-6


# ── Giriş Verisi ─────────────────────────────────────────────────────────────

@dataclass
class SealedBoxInput:
    """
    Kullanıcı ve akustik motordan gelen kapalı kutu parametreleri.

    Temel:
      net_volume_l    → hedef net akustik hacim (litre)
      width_mm        → dış genişlik
      height_mm       → dış yükseklik
      depth_mm        → dış derinlik

    Malzeme:
      thickness_mm    → MDF kalınlığı (varsayılan 18mm)
      finger_joint    → parmak geçme (lazer kesim)
      kerf_mm         → lazer kerf telafisi
      tolerance_mm    → birleşim toleransı

    Sürücü:
      driver_hole_mm  → woofer delik çapı (ön panel baffle)
                        0 → delik çizilmez
      driver_xmax_mm  → lineer hareket (opsiyonel — ileride motor ısı hesabı)

    Akustik (opsiyonel — danışmanlık için):
      qts             → sürücü toplam Q
      vas_l           → eşdeğer hava hacmi (litre)
      fs_hz           → serbest rezonans frekansı
      target_qtc      → hedef Qtc (0.5~1.0, varsayılan 0.707)
    """
    # Boyutlar
    net_volume_l:   float
    width_mm:       float
    height_mm:      float
    depth_mm:       float

    # Malzeme
    thickness_mm:   float = 18.0
    finger_joint:   bool  = True
    kerf_mm:        float = 0.2
    tolerance_mm:   float = 0.1
    bracing_pct:    float = 0.02

    # Sürücü
    driver_hole_mm: float = 282.0
    driver_xmax_mm: float = 0.0

    # Akustik parametreler (opsiyonel)
    qts:            Optional[float] = None
    vas_l:          Optional[float] = None
    fs_hz:          Optional[float] = None
    target_qtc:     float = 0.707


# ── Akustik Tavsiye Motoru ────────────────────────────────────────────────────

@dataclass
class SealedAcousticReport:
    """
    Sealed alignment analizi raporu.
    Kullanıcıya danışmanlık bilgisi sunar — karar vermez.
    """
    qtc:             Optional[float]  # Gerçekleşen Qtc
    fc_hz:           Optional[float]  # -3dB kesim frekansı
    optimal_vol_l:   Optional[float]  # Qtc=0.707 için ideal hacim
    alignment:       str              # "tight" | "extended" | "overdamped"
    notes:           list[str]


def compute_sealed_acoustic(inp: SealedBoxInput) -> SealedAcousticReport:
    """
    Qts, Vas, Fs varsa sealed alignment hesapla.
    Yoksa boş rapor döner.
    """
    notes = []

    if not all([inp.qts, inp.vas_l, inp.fs_hz]):
        return SealedAcousticReport(
            qtc=None, fc_hz=None, optimal_vol_l=None,
            alignment="bilinmiyor",
            notes=["Qts/Vas/Fs girilmedi — akustik analiz atlandı."]
        )

    qts = inp.qts
    vas = inp.vas_l
    fs  = inp.fs_hz
    qtc_target = inp.target_qtc
    vb  = inp.net_volume_l

    # Qtc hesabı: Qtc = Qts × sqrt(1 + Vas/Vb)
    qtc = qts * math.sqrt(1 + vas / vb)
    qtc = round(qtc, 3)

    # fc = Fs × Qtc / Qts
    fc = fs * qtc / qts
    fc = round(fc, 1)

    # İdeal hacim (hedef Qtc için)
    # Vb_opt = Vas / ((Qtc_target/Qts)^2 - 1)
    try:
        vb_opt = vas / ((qtc_target / qts) ** 2 - 1)
        vb_opt = round(vb_opt, 2)
        if vb_opt <= 0:
            vb_opt = None
            notes.append("Bu sürücü için kapalı kutu önerilmiyor (Qts çok düşük).")
    except ZeroDivisionError:
        vb_opt = None

    # Alignment sınıfı
    if qtc < 0.6:
        alignment = "overdamped"
        notes.append(f"Qtc={qtc:.3f} — aşırı sönümlenmiş, bas yumuşak ve derin.")
    elif qtc <= 0.8:
        alignment = "optimal"
        notes.append(f"Qtc={qtc:.3f} — ideal bölge (0.6-0.8), düzgün frekans yanıtı.")
    elif qtc <= 1.0:
        alignment = "tight"
        notes.append(f"Qtc={qtc:.3f} — sıkı bas, biraz vurgulu, car audio için popüler.")
    else:
        alignment = "boomy"
        notes.append(f"Qtc={qtc:.3f} — fazla vurgulu, hacim çok küçük veya Qts yüksek.")

    if vb_opt:
        diff_pct = abs(vb - vb_opt) / vb_opt * 100
        if diff_pct > 20:
            notes.append(
                f"Önerilen hacim: {vb_opt:.1f}L "
                f"(mevcut {vb:.1f}L — %{diff_pct:.0f} sapma)."
            )

    return SealedAcousticReport(
        qtc=qtc, fc_hz=fc, optimal_vol_l=vb_opt,
        alignment=alignment, notes=notes
    )


# ── Ana Kabin Oluşturucu ──────────────────────────────────────────────────────

class SealedBox:
    """
    Kapalı kutu geometri ve akustik motoru.

    Kullanım:
        box = SealedBox()
        result = box.build(SealedBoxInput(...))
        cabinet  = result["cabinet"]   # CabinetGeometry
        acoustic = result["acoustic"]  # SealedAcousticReport
        panels   = result["panel_list"]  # kesim listesi
    """

    def build(self, inp: SealedBoxInput) -> dict:
        """
        SealedBoxInput → {cabinet, acoustic, panel_list, volume}

        Raises:
            ValueError: iç ölçüler negatif (çok küçük dış ölçü)
        """
        t   = inp.thickness_mm
        w, h, d = inp.width_mm, inp.height_mm, inp.depth_mm

        logger.info(
            "[SEALED] Build: W=%.0f H=%.0f D=%.0f t=%.0f net=%.2fL",
            w, h, d, t, inp.net_volume_l
        )

        # İç ölçü kontrolü
        iw, ih, id_ = compute_inner_dims(w, h, d, t)
        if any(x <= 0 for x in [iw, ih, id_]):
            raise ValueError(
                f"İç ölçüler negatif/sıfır: iç={iw:.1f}x{ih:.1f}x{id_:.1f}mm. "
                "Dış ölçüleri büyüt veya malzeme kalınlığını azalt."
            )
        if any(x < 50 for x in [iw, ih, id_]):
            logger.warning(
                "[SEALED] Çok küçük iç ölçü: %s — woofer sığmayabilir.",
                [round(x,1) for x in [iw, ih, id_]]
            )

        # Hacim breakdown (PORT YOK)
        gross_l  = w * h * d * MM3_TO_L
        inner_l  = iw * ih * id_ * MM3_TO_L
        brace_l  = inner_l * inp.bracing_pct

        if inp.driver_hole_mm > 0:
            r_mm = inp.driver_hole_mm / 2.0
            driver_displ_l = math.pi * r_mm**2 * 50.0 * MM3_TO_L
        else:
            driver_displ_l = 0.0

        net_l = inner_l - driver_displ_l - brace_l
        error_pct = abs(net_l - inp.net_volume_l) / max(inp.net_volume_l, 0.001) * 100

        vol = VolumeBreakdown(
            gross_l=round(gross_l, 4),
            inner_l=round(inner_l, 4),
            driver_displ_l=round(driver_displ_l, 4),
            port_displ_l=0.0,          # SEALED — port yok
            bracing_displ_l=round(brace_l, 4),
            net_acoustic_l=round(net_l, 4),
            target_net_l=round(inp.net_volume_l, 4),
            error_pct=round(error_pct, 2),
        )
        logger.info(
            "[SEALED] Hacim: inner=%.3fL driver=%.3fL bracing=%.3fL NET=%.3fL (hedef=%.3fL delta=%%%.2f)",
            inner_l, driver_displ_l, brace_l, net_l, inp.net_volume_l, error_pct
        )

        # Paneller (6 ana panel — port duvarı YOK)
        panels = compute_panels(w, h, d, t)

        # Finger joint
        fj_active, fj_width = self._finger_joint_config(panels, t, inp.finger_joint)

        # CabinetGeometry
        cabinet = CabinetGeometry(
            outer_w_mm=w, outer_h_mm=h, outer_d_mm=d,
            inner_w_mm=iw, inner_h_mm=ih, inner_d_mm=id_,
            thickness_mm=t,
            volume=vol,
            panels=panels,
            port=None,                 # SEALED — port yok
            finger_joint_active=fj_active,
            finger_width_mm=fj_width,
            kerf_mm=inp.kerf_mm,
            tolerance_mm=inp.tolerance_mm,
            driver_hole_mm=inp.driver_hole_mm,
        )

        # Akustik tavsiye raporu
        acoustic = compute_sealed_acoustic(inp)

        # Panel kesim listesi (kullanıcıya gösterilecek)
        panel_list = self._build_panel_list(panels, t)

        logger.info(
            "[SEALED] Tamamlandi: %d panel, fj=%s, driver=%.0fmm, Qtc=%s",
            len(panels), fj_active, inp.driver_hole_mm,
            acoustic.qtc if acoustic.qtc else "N/A"
        )

        return {
            "cabinet":    cabinet,
            "acoustic":   acoustic,
            "panel_list": panel_list,
            "volume":     vol,
            "cab_type":   "sealed",
        }

    @staticmethod
    def _finger_joint_config(
        panels: list[PanelDim], t: float, enabled: bool
    ) -> tuple[bool, float]:
        if not enabled:
            return False, 0.0
        min_edge = min(min(p.width_mm, p.height_mm) for p in panels)
        if min_edge < 3 * t:
            logger.warning("[SEALED] Finger joint auto-disable: min_kenar=%.1fmm < %.1fmm", min_edge, 3*t)
            return False, 0.0
        return True, t

    @staticmethod
    def _build_panel_list(panels: list[PanelDim], t: float) -> list[dict]:
        """Kesim listesi — CNC/lazer için."""
        return [
            {
                "ad":        p.name,
                "en_mm":     round(p.width_mm, 1),
                "boy_mm":    round(p.height_mm, 1),
                "kalinlik":  round(t, 1),
                "adet":      1,
                "rol":       p.role,
            }
            for p in panels
        ]


# ── CLI Test ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    sys.path.insert(0, "C:/Users/DDSOUND/Desktop/exemiz/dd1_platform")

    box = SealedBox()

    # Test: 30L kapalı kutu, 12" woofer
    inp = SealedBoxInput(
        net_volume_l=30.0,
        width_mm=420, height_mm=380, depth_mm=320,
        thickness_mm=18,
        driver_hole_mm=282,
        # Akustik params (opsiyonel)
        qts=0.38, vas_l=55.0, fs_hz=28.0, target_qtc=0.707
    )

    result = box.build(inp)

    print("\n=== KAPALI KUTU TEST ===")
    print(f"Kabin türü : {result['cab_type']}")
    v = result["volume"]
    print(f"Net hacim  : {v.net_acoustic_l:.2f}L  (hedef: {v.target_net_l:.2f}L, sapma: %{v.error_pct:.2f})")
    print(f"Port       : YOK (sealed)")

    a = result["acoustic"]
    print(f"\nAkustik Rapor:")
    print(f"  Qtc      : {a.qtc}")
    print(f"  fc (-3dB): {a.fc_hz} Hz")
    print(f"  Alignment: {a.alignment}")
    for note in a.notes:
        print(f"  NOT: {note}")

    print(f"\nPanel Listesi ({len(result['panel_list'])} adet):")
    for p in result["panel_list"]:
        print(f"  {p['ad']:12s}  {p['en_mm']:.0f}x{p['boy_mm']:.0f}mm")
