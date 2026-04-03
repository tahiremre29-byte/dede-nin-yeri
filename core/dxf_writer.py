"""
core/dxf_writer.py
DD1 Endüstriyel DXF Yazıcısı

Girdi:  CabinetGeometry (box_generator çıktısı)
Çıktı:  .dxf dosyası + CorelCAD proxy raporu

Standartlar:
  - Unit: mm ($INSUNITS=4)
  - Version: R2010 (AC1024) — CorelDraw + AutoCAD uyumlu
  - Origin: (0,0) — sol-alt referans
  - Katmanlar:
      CUT_RED       → dış kenar kesim hatları (renk=1:kırmızı)
      ENGRAVE_BLUE  → yazı, montaj işaretleri (renk=5:mavi)
      PORT_GREEN    → port detayları (renk=3:yeşil)
  - Her panel: tek parça kapalı LWPolyline
  - Finger joint: kapalı polyline notch'ları CUT_RED üzerinde
  - Nesting: paneller grid halinde yan yana
  - Duplicate cleanup: çakışan segmentleri sil, sayısını raporla
"""
from __future__ import annotations
import logging
import math
import os
import uuid
from pathlib import Path
from typing import Optional

import ezdxf
from ezdxf import units

from core.geometry import CabinetGeometry, PanelDim, PortGeometry

logger = logging.getLogger("dd1.dxf_writer")

# DXF versiyon haritasi (ezdxf icin)
_DXF_VERSION_MAP = {
    "R2010": "R2010",   # AC1024 — modern, tam kompatibel
    "R12":   "R12",     # AC1009 — legacy, CorelDraw eski surum uyumu
    "R2000": "R2000",   # AC1015
}

# ── Katman Sabitleri ──────────────────────────────────────────────────────────
LAYER_CUT     = "CUT_RED"        # color=1 (kırmızı) — lazer kesim
LAYER_ENGRAVE = "ENGRAVE_BLUE"   # color=5 (mavi)    — gravür / yazı
LAYER_PORT    = "PORT_GREEN"     # color=3 (yeşil)   — port detayı
LAYER_DIVIDER = "DIVIDER_YELLOW" # color=2 (sarı)    — bandpass bölme duvarı

# Grid layout parametresi
NESTING_GAP_MM = 10.0   # paneller arası boşluk


# ── Çift Çizgi Dedektörü ──────────────────────────────────────────────────────

class DuplicateCleaner:
    """
    Segment tespiti: aynı başlangıç-bitiş çiftine sahip segmentleri sil.
    Toplam temizlenen segment sayısını raporla.
    """

    def __init__(self):
        self._seen: set[frozenset] = set()
        self.removed = 0

    def is_duplicate(self, p1: tuple, p2: tuple) -> bool:
        key = frozenset({
            (round(p1[0], 3), round(p1[1], 3)),
            (round(p2[0], 3), round(p2[1], 3)),
        })
        if key in self._seen:
            self.removed += 1
            return True
        self._seen.add(key)
        return False


# ── Finger Joint Geometrisi ───────────────────────────────────────────────────

def _finger_joint_points(
    x0: float, y0: float,
    length: float,
    direction: str,     # "H" (yatay) | "V" (dikey)
    tooth_w: float,
    tooth_d: float,     # derinlik = malzeme kalınlığı
    kerf: float,
    tolerance: float,
    outward: bool = True,   # dış mı içe mi
) -> list[tuple[float, float]]:
    """
    Tek kenar için finger joint poly noktaları üretir.
    Sonuç: kenarın kendisi + diş konturları (closed polyline için).
    """
    tooth_w  = tooth_w  + tolerance
    tooth_d  = tooth_d  + kerf / 2
    # Deterministik: math.floor (int() float precision farklilik yaratabilir)
    n_teeth  = max(1, math.floor(length / (tooth_w * 2)))
    spacing  = length / n_teeth
    half_t   = spacing * 0.5

    pts: list[tuple[float, float]] = []

    sign = 1.0 if outward else -1.0

    for i in range(n_teeth):
        if direction == "H":
            tx = x0 + i * spacing
            pts += [
                (tx,          y0),
                (tx,          y0 + sign * tooth_d),
                (tx + half_t, y0 + sign * tooth_d),
                (tx + half_t, y0),
            ]
        else:
            ty = y0 + i * spacing
            pts += [
                (x0,                ty),
                (x0 + sign*tooth_d, ty),
                (x0 + sign*tooth_d, ty + half_t),
                (x0,                ty + half_t),
            ]
    return pts


# ── Panel Çizici ──────────────────────────────────────────────────────────────

class PanelDrawer:
    """Tek paneli msp'ye çizer. Finger joint opsiyonel."""

    def __init__(
        self,
        msp,
        cleaner: DuplicateCleaner,
        finger_joint: bool,
        tooth_w: float,
        kerf: float,
        tolerance: float,
        t_mm: float,
        is_r12: bool = False,
    ):
        self.msp       = msp
        self.cleaner   = cleaner
        self.fj        = finger_joint
        self.tooth_w   = tooth_w
        self.kerf      = kerf
        self.tolerance = tolerance
        self.t         = t_mm
        self.is_r12    = is_r12
        self.closed_count = 0

    def draw_panel(
        self, panel: PanelDim, ox: float, oy: float,
        with_finger_joints: bool = True,
    ) -> None:
        """
        (ox, oy): sol-alt köşe origin.
        Dış kontur → CUT_RED, closed LWPolyline.
        Joints → CUT_RED ayrı closed polyline'lar.
        Etiket → ENGRAVE_BLUE Text.
        """
        w, h = panel.width_mm, panel.height_mm
        if panel.role == "port_wall":
            layer = LAYER_PORT
        elif panel.role == "divider":
            layer = LAYER_DIVIDER
        else:
            layer = LAYER_CUT

        # Dış kontur
        outer = [
            (ox,   oy),
            (ox+w, oy),
            (ox+w, oy+h),
            (ox,   oy+h),
        ]
        self._add_closed_poly(outer, layer)

        # Finger joint notch'lar
        if self.fj and with_finger_joints and self.tooth_w > 0:
            self._draw_joints(ox, oy, w, h, layer)

        # Etiket
        label = f"{panel.name}\n{w:.0f}x{h:.0f}mm"
        self.msp.add_text(
            label,
            dxfattribs={"layer": LAYER_ENGRAVE, "height": min(6.0, h * 0.04)}
        ).set_placement((ox + 4, oy + h / 2))

    def _add_closed_poly(
        self, pts: list[tuple], layer: str
    ) -> None:
        if self.is_r12:
            # R12: LWPOLYLINE desteklenmez, LINE entity dizisi kullan
            for i in range(len(pts)):
                p1, p2 = pts[i], pts[(i + 1) % len(pts)]
                if not self.cleaner.is_duplicate(p1, p2):
                    self.msp.add_line(
                        start=(p1[0], p1[1], 0),
                        end=(p2[0], p2[1], 0),
                        dxfattribs={"layer": layer},
                    )
            self.closed_count += 1
        else:
            # R2000+: LWPOLYLINE tercih edilir (toplu)
            clean_pts = []
            for i in range(len(pts)):
                p1, p2 = pts[i], pts[(i+1) % len(pts)]
                if not self.cleaner.is_duplicate(p1, p2):
                    if not clean_pts:
                        clean_pts.append(p1)
                    clean_pts.append(p2)

            if len(clean_pts) >= 3:
                lw = self.msp.add_lwpolyline(
                    clean_pts[:len(pts)],
                    dxfattribs={"layer": layer}
                )
                lw.close(True)
                self.closed_count += 1

    def _draw_joints(
        self, ox: float, oy: float, w: float, h: float, layer: str
    ) -> None:
        """4 kenara finger joints."""
        t = self.t
        # Alt kenar (yatay)
        if w >= 3 * self.tooth_w:
            pts = _finger_joint_points(
                ox, oy, w, "H", self.tooth_w, t, self.kerf, self.tolerance,
                outward=False
            )
            if pts:
                self._add_closed_poly(pts, layer)

        # Üst kenar
        if w >= 3 * self.tooth_w:
            pts = _finger_joint_points(
                ox, oy+h, w, "H", self.tooth_w, t, self.kerf, self.tolerance,
                outward=True
            )
            if pts:
                self._add_closed_poly(pts, layer)


# ── Ana DXF Yazıcı ────────────────────────────────────────────────────────────

class DXFWriter:
    """
    CabinetGeometry → DXF dosyası

    Kullanım:
        writer = DXFWriter(output_dir="exports")
        report = writer.write(cabinet, design_id="dd1_abc123")
        # report["dxf_path"], report["closed_poly_count"], ...
    """

    def __init__(self, output_dir: str = "exports", dxf_version: Optional[str] = None):
        self._outdir = Path(output_dir)
        self._outdir.mkdir(parents=True, exist_ok=True)
        # Versiyon: parametre > config > varsayilan R2010
        if dxf_version:
            self._dxf_ver = _DXF_VERSION_MAP.get(dxf_version.upper(), "R2010")
        else:
            try:
                from core.config import cfg
                self._dxf_ver = _DXF_VERSION_MAP.get(cfg.dxf_version.upper(), "R2010")
            except Exception:
                self._dxf_ver = "R2010"
        logger.info("[DXF_WRITER] DXF version: %s", self._dxf_ver)

    def write(
        self,
        cabinet:   CabinetGeometry,
        design_id: str,
    ) -> dict:
        """
        Returns:
          dxf_path, file_size_bytes, closed_poly_count, duplicate_removed,
          layer_map, bounding_box, proxy_report (CorelCAD uyum raporu)
        """
        dxf_path = self._outdir / f"{design_id}.dxf"
        tmp_path = self._outdir / f"{design_id}_{uuid.uuid4().hex[:6]}.tmp.dxf"

        try:
            doc = ezdxf.new(dxfversion=self._dxf_ver)
            doc.header["$INSUNITS"] = 4   # mm

            # Katmanları tanımla
            doc.layers.add(LAYER_CUT,     color=1)   # kırmızı
            doc.layers.add(LAYER_ENGRAVE, color=5)   # mavi
            doc.layers.add(LAYER_PORT,    color=3)   # yeşil
            doc.layers.add(LAYER_DIVIDER, color=2)   # sarı — bandpass bölme duvarı

            msp = doc.modelspace()
            cleaner = DuplicateCleaner()

            drawer = PanelDrawer(
                msp=msp,
                cleaner=cleaner,
                finger_joint=cabinet.finger_joint_active,
                tooth_w=cabinet.finger_width_mm,
                kerf=cabinet.kerf_mm,
                tolerance=cabinet.tolerance_mm,
                t_mm=cabinet.thickness_mm,
                is_r12=(self._dxf_ver == "R12"),
            )

            # Nesting: grid layout
            bounding_box = self._nest_and_draw(
                drawer, cabinet, msp, cleaner
            )

            # Driver deliği (ön panel + arka panel)
            if cabinet.driver_hole_mm > 0:
                self._draw_driver_holes(
                    msp, cabinet, cleaner
                )

            # Port deliği (arka panel konumunda)
            if cabinet.port:
                self._draw_port_on_back(msp, cabinet, cleaner)

            # Atomik yazma: .tmp → .dxf
            doc.saveas(str(tmp_path))
            os.replace(str(tmp_path), str(dxf_path))

            size = dxf_path.stat().st_size
            logger.info(
                "[DXF_WRITER] %s: %d byte, closed_poly=%d, dup_removed=%d",
                dxf_path.name, size,
                drawer.closed_count, cleaner.removed,
            )

            # Delta kontrolu: volume sapma > %2 ise uretimi engelle
            vol = cabinet.volume
            if vol:
                delta = vol.delta_pct if vol.delta_pct else vol.error_pct
                if delta > 2.0:
                    # Dosyayi temizle
                    dxf_path.unlink(missing_ok=True)
                    raise ValueError(
                        f"[DXF_WRITER] Delta limit asildi: %{delta:.2f} > %2.0. "
                        f"Hesaplanan={vol.net_acoustic_l:.2f}L Hedef={vol.target_net_l:.2f}L. "
                        "Auto-resize uygulandi mi kontrol edin."
                    )

            # CorelCAD proxy raporu
            proxy = self._proxy_report(
                dxf_path=str(dxf_path),
                cabinet=cabinet,
                closed_count=drawer.closed_count,
                dup_removed=cleaner.removed,
                bbox=bounding_box,
                file_size=size,
            )

            return {
                "dxf_path":          str(dxf_path),
                "file_size_bytes":   size,
                "closed_poly_count": drawer.closed_count,
                "duplicate_removed": cleaner.removed,
                "layer_map": {
                    LAYER_CUT:     "Lazer kesim hatlari (kirimizi)",
                    LAYER_ENGRAVE: "Gravur / montaj isaretleri (mavi)",
                    LAYER_PORT:    "Port geometrisi (yesil)",
                    LAYER_DIVIDER: "Bandpass bolme duvari (sari)",
                },
                "bounding_box":   bounding_box,
                "proxy_report":   proxy,
            }

        except Exception as exc:
            if tmp_path.exists():
                tmp_path.unlink(missing_ok=True)
            logger.error("[DXF_WRITER] Hata: %s", exc)
            raise

    # ── Grid Nesting ──────────────────────────────────────────────────────────

    def _nest_and_draw(
        self, drawer: PanelDrawer,
        cabinet: CabinetGeometry,
        msp, cleaner: DuplicateCleaner,
    ) -> dict:
        """
        Panelleri grid formatında yan yana diz.
        Maksimum genişlik 1220mm (standart MDF levha).
        Döner: bounding_box dict.
        """
        gap = NESTING_GAP_MM
        x, y = 0.0, 0.0
        max_h_in_row = 0.0
        SHEET_W = 1220.0

        x_max, y_max = 0.0, 0.0

        for panel in cabinet.panels:
            # Yeni satıra geç?
            if x + panel.width_mm + gap > SHEET_W and x > 0:
                x = 0.0
                y += max_h_in_row + gap
                max_h_in_row = 0.0

            # Port duvarı ve bölme duvarı için joint yok
            fj = panel.role not in ("port_wall", "divider")
            drawer.draw_panel(panel, x, y, with_finger_joints=fj)

            x_max = max(x_max, x + panel.width_mm)
            y_max = max(y_max, y + panel.height_mm)
            max_h_in_row = max(max_h_in_row, panel.height_mm)
            x += panel.width_mm + gap

        return {
            "min_x": 0, "min_y": 0,
            "max_x": round(x_max, 2),
            "max_y": round(y_max, 2),
            "total_area_mm2": round(x_max * y_max, 2),
        }

    # ── Driver Deliği ─────────────────────────────────────────────────────────

    def _draw_driver_holes(
        self, msp, cabinet: CabinetGeometry, cleaner: DuplicateCleaner
    ) -> None:
        """
        Ön panel üzerinde woofer deliği.
        Merkez: ön panelin ortası.
        """
        # Ön panel ilk panel (grid'de ox=0, oy=0)
        cx = cabinet.outer_w_mm / 2
        cy = cabinet.outer_h_mm / 2
        r  = cabinet.driver_hole_mm / 2

        msp.add_circle(
            center=(cx, cy),
            radius=r,
            dxfattribs={"layer": LAYER_CUT},
        )
        msp.add_text(
            f"WOOFER d={cabinet.driver_hole_mm:.0f}mm",
            dxfattribs={"layer": LAYER_ENGRAVE, "height": 6}
        ).set_placement((cx + r + 5, cy))

    # ── Port Deliği (Arka Panel) ──────────────────────────────────────────────

    def _draw_port_on_back(
        self, msp, cabinet: CabinetGeometry, cleaner: DuplicateCleaner
    ) -> None:
        """
        Arka panelde slot port deliği.
        Arka panel: grid'de 2. konum (x = ON_PANEL.width + gap).
        """
        port = cabinet.port
        gap  = NESTING_GAP_MM
        bx = cabinet.outer_w_mm + gap
        by = 0.0
        cx = bx + cabinet.outer_w_mm / 2
        cy = by + cabinet.outer_h_mm / 2
        px = cx - port.width_mm / 2
        py = cy - port.height_mm / 2

        pts = [
            (px,              py),
            (px + port.width_mm, py),
            (px + port.width_mm, py + port.height_mm),
            (px,              py + port.height_mm),
        ]

        is_r12 = self._dxf_ver == "R12"
        if is_r12:
            for i in range(len(pts)):
                p1, p2 = pts[i], pts[(i+1) % len(pts)]
                msp.add_line(
                    start=(p1[0], p1[1], 0),
                    end=(p2[0], p2[1], 0),
                    dxfattribs={"layer": LAYER_PORT},
                )
        else:
            lw = msp.add_lwpolyline(pts, dxfattribs={"layer": LAYER_PORT})
            lw.close(True)

        msp.add_text(
            f"PORT {port.width_mm:.0f}x{port.height_mm:.0f}mm L={port.length_mm:.0f}mm",
            dxfattribs={"layer": LAYER_ENGRAVE, "height": 5}
        ).set_placement((px, py - 8))

    # ── CorelCAD Proxy Raporu ─────────────────────────────────────────────────

    def _proxy_report(
        self,
        dxf_path: str, cabinet: CabinetGeometry,
        closed_count: int, dup_removed: int,
        bbox: dict, file_size: int,
    ) -> dict:
        vol = cabinet.volume
        delta = vol.delta_pct if vol.delta_pct else vol.error_pct
        delta_status = "OK" if delta <= 2.0 else "WARN"
        # DXF versiyon gosterimi
        ver_display = {
            "R12":   "DXF R12 (AC1009) — Legacy/CorelDraw",
            "R2000": "DXF R2000 (AC1015)",
            "R2010": "DXF R2010 (AC1024) — Modern",
        }.get(self._dxf_ver, f"DXF {self._dxf_ver}")

        return {
            "origin_reference":  "Sol-alt kose (0,0) — CorelDraw/AutoCAD standart",
            "unit":              "mm ($INSUNITS=4)",
            "export_version":    ver_display,
            "closed_polyline_count": closed_count,
            "duplicate_line_count":  dup_removed,
            "layer_map": {
                "CUT_RED":      "Lazer kesim — renk 1 (kirimizi)",
                "ENGRAVE_BLUE": "Gravur/etiket — renk 5 (mavi)",
                "PORT_GREEN":   "Port geometrisi — renk 3 (yesil)",
            },
            "bounding_box_mm":   bbox,
            "file_path":         dxf_path,
            "file_size_bytes":   file_size,
            "finger_joint":      cabinet.finger_joint_active,
            "finger_tooth_w_mm": cabinet.finger_width_mm,
            "kerf_mm":           cabinet.kerf_mm,
            "tolerance_mm":      cabinet.tolerance_mm,
            "volume_summary": {
                "gross_l":           vol.gross_l,
                "inner_l":           vol.inner_l,
                "driver_displ_l":    vol.driver_displ_l,
                "port_displ_l":      vol.port_displ_l,
                "bracing_displ_l":   vol.bracing_displ_l,
                "net_target_l":      vol.target_net_l,
                "final_calc_net_l":  vol.net_acoustic_l,
                "delta_pct":         round(delta, 3),
                "delta_status":      delta_status,
                "auto_resized":      vol.resized,
            },
            "port": {
                "type":       cabinet.port.port_type if cabinet.port else None,
                "width_mm":   cabinet.port.width_mm if cabinet.port else None,
                "height_mm":  cabinet.port.height_mm if cabinet.port else None,
                "length_mm":  cabinet.port.length_mm if cabinet.port else None,
                "area_cm2":   cabinet.port.area_cm2 if cabinet.port else None,
                "displ_l":    cabinet.port.displacement_l if cabinet.port else None,
            },
        }
