# vector_module.py — DD1 Lazer Agent  (v2 — temiz pipeline)
# Pipeline: Görsel → Grayscale → Kontrast → AdaptiveThreshold → BinaryMask
#           → Morphological Cleanup → Potrace/Contour → SVG → DXF
#
# Bağımlılıklar: opencv-python-headless, Pillow, ezdxf, numpy
# İsteğe bağlı: vtracer (pip install vtracer)

import os
import re
import math
import shutil
import subprocess
import tempfile
import traceback
import xml.etree.ElementTree as ET

import cv2
import numpy as np
from PIL import Image

try:
    import vtracer
    VTRACER_OK = True
except ImportError:
    VTRACER_OK = False

try:
    import ezdxf
    EZDXF_OK = True
except ImportError:
    EZDXF_OK = False

try:
    from svgpathtools import svg2paths
    from shapely.geometry import Polygon, MultiPolygon, LineString, MultiLineString
    from shapely.ops import unary_union, linemerge
    VECTOR_LIBS_OK = True
except ImportError:
    VECTOR_LIBS_OK = False

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QSlider, QCheckBox, QFileDialog, QGraphicsView,
    QGraphicsScene, QProgressBar, QSizePolicy,
    QMessageBox, QSplitter, QGroupBox
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QObject
from PyQt6.QtGui import QDragEnterEvent, QDropEvent, QPixmap
from PyQt6.QtSvg import QSvgRenderer
from PyQt6.QtSvgWidgets import QGraphicsSvgItem
from PyQt6.QtCore import QByteArray

MAX_DIM = 4096


# ══════════════════════════════════════════════════════════════════
#  POTRACE KEŞFİ  (binary + system PATH)
# ══════════════════════════════════════════════════════════════════
def _find_potrace() -> str | None:
    """potrace.exe ya da potrace binary'sini bulur. Bulamazsa None döner."""
    # 1. Aynı klasörde mevcut mu?
    here = os.path.dirname(os.path.abspath(__file__))
    for name in ("potrace.exe", "potrace"):
        candidate = os.path.join(here, name)
        if os.path.isfile(candidate):
            return candidate
    # 2. System PATH'te mi?
    for name in ("potrace", "potrace.exe"):
        try:
            result = subprocess.run(
                [name, "--version"], capture_output=True, timeout=5
            )
            if result.returncode == 0:
                return name
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass
    return None

POTRACE_BIN = _find_potrace()


# ══════════════════════════════════════════════════════════════════
#  GÖRÜNTÜ İŞLEME — TEMEL FONKSİYONLAR
# ══════════════════════════════════════════════════════════════════
def load_image_gray(path: str) -> tuple[np.ndarray, np.ndarray]:
    """
    Görseli yükler, beyaz arka plana birleştirir ve gri tona çevirir.
    Returns: (gray, orig_rgb) — her ikisi de uint8
    """
    img_pil = Image.open(path).convert("RGBA")
    w, h = img_pil.size
    if w > MAX_DIM or h > MAX_DIM:
        ratio = min(MAX_DIM / w, MAX_DIM / h)
        img_pil = img_pil.resize(
            (int(w * ratio), int(h * ratio)), Image.LANCZOS
        )
    # Alfa kanalını beyaz zemine baskı
    bg = Image.new("RGBA", img_pil.size, (255, 255, 255, 255))
    bg.paste(img_pil, mask=img_pil.split()[3])
    rgb = np.array(bg.convert("RGB"))
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    return gray, rgb


def enhance_gray(gray: np.ndarray) -> np.ndarray:
    """CLAHE ile kontrast / detay artırımı."""
    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
    return clahe.apply(gray)


def make_binary_mask(
    gray: np.ndarray,
    threshold: int,
    laser_mode: bool,
    detail: int,          # 1–10  (speckle filtresi; küçük: daha çok detay)
    smoothing: int,       # 1–10  (morfoloji boyutu; büyük: daha yumuşak)
) -> np.ndarray:
    """
    Doğru binary maske üretimi.
    Arka plan → SİYAH (0), parça → BEYAZ (255)
    Potrace beyaz alanı izler.
    """
    block = max(11, int(gray.shape[1] / 40) | 1)   # tek sayı olmalı
    C_val = max(2, 12 - threshold // 20)           # threshold'a göre C ayarı

    if laser_mode:
        # Güçlü adaptif — ince lokalde karar verir
        binary = cv2.adaptiveThreshold(
            gray, 255,
            cv2.ADAPTIVE_THRESH_MEAN_C,
            cv2.THRESH_BINARY_INV,
            blockSize=block, C=C_val
        )
    else:
        # Standart global + adaptif birleşimi
        _, global_b = cv2.threshold(
            gray, threshold, 255, cv2.THRESH_BINARY_INV
        )
        adaptive_b = cv2.adaptiveThreshold(
            gray, 255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY_INV,
            blockSize=block, C=C_val
        )
        # AND: ikisi de koyu diyen pikseller → daha az gürültü
        binary = cv2.bitwise_and(global_b, adaptive_b)

    # ── Morphological cleanup ─────────────────────────────────
    # smoothing (1–10) → kernel boyutu 3..11
    k_size = max(3, 2 * smoothing // 2 + 1)    # tek sayı 3,5,7,9,11
    kernel  = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k_size, k_size))

    # Kapatma: iç delikleri kapat, kapalı konturu güçlendir
    binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel, iterations=2)
    # Açma: küçük gürültü parçalarını temizle
    binary = cv2.morphologyEx(binary, cv2.MORPH_OPEN,  kernel, iterations=1)

    # ── Speckle temizleme (detail slider) ────────────────────
    # detail düşük → büyük min alan → sadece ana şekil
    # detail yüksek → küçük min alan → ince detaylar da korunur
    min_area = max(10, int(2500 / detail))
    contours, _ = cv2.findContours(
        binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
    )
    clean = np.zeros_like(binary)
    for cnt in contours:
        if cv2.contourArea(cnt) >= min_area:
            cv2.drawContours(clean, [cnt], -1, 255, -1)   # iç dolu
    # İç delikleri de koru (RETR_CCOMP ile)
    contours2, hierarchy = cv2.findContours(
        binary, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE
    )
    if hierarchy is not None:
        for i, cnt in enumerate(contours2):
            if hierarchy[0][i][3] != -1:          # iç kontur (delik)
                if cv2.contourArea(cnt) >= min_area // 4:
                    cv2.drawContours(clean, [cnt], -1, 0, -1)  # deliği sil

    return clean


# ══════════════════════════════════════════════════════════════════
#  SVG ÜRETİMİ
# ══════════════════════════════════════════════════════════════════
def binary_to_svg(binary: np.ndarray, smoothing: int) -> str:
    """
    Binary maskeden SVG üretir.
    Öncelik sırası: Potrace binary → vtracer → saf kontür-SVG
    """
    tmp = tempfile.gettempdir()
    png_path = os.path.join(tmp, "dd1_bin.png")
    svg_path = os.path.join(tmp, "dd1_out.svg")
    bmp_path = os.path.join(tmp, "dd1_bin.bmp")

    cv2.imwrite(png_path, binary)

    # ── 1. Potrace binary ─────────────────────────────────────
    if POTRACE_BIN:
        # Potrace PBM / BMP giriş bekler; BMP kullanıyoruz
        cv2.imwrite(bmp_path, binary)
        alphamax  = min(1.33, 0.5 + smoothing * 0.083)   # 0.58..1.33
        opttol    = 0.2
        turdsize  = max(1, 12 - smoothing)

        cmd = [
            POTRACE_BIN,
            "-s",                          # SVG çıktı
            "--turnpolicy", "black",
            "--alphamax",   str(alphamax),
            "--opttolerance", str(opttol),
            "--turdsize",   str(turdsize),
            "-o", svg_path,
            bmp_path,
        ]
        try:
            result = subprocess.run(
                cmd, capture_output=True, timeout=120
            )
            if result.returncode == 0 and os.path.isfile(svg_path):
                return svg_path
        except Exception:
            pass  # → vtracer fallback

    # ── 2. vtracer ────────────────────────────────────────────
    if VTRACER_OK:
        # smoothing (1-10) → corner_threshold (80..20)
        corner = max(20, 80 - smoothing * 6)
        # smoothing → splice_threshold (60..20)
        splice = max(20, 60 - smoothing * 4)

        vtracer.convert_image_to_svg_py(
            png_path,
            svg_path,
            colormode        = "binary",
            hierarchical     = "stacked",
            mode             = "spline",
            filter_speckle   = max(2, 14 - smoothing),
            color_precision  = 6,
            layer_difference = 16,
            corner_threshold = corner,
            length_threshold = 4.0,
            max_iterations   = 10,
            splice_threshold = splice,
            path_precision   = 4,
        )
        if os.path.isfile(svg_path):
            return svg_path

    # ── 3. Saf kontür → SVG (kesin fallback) ─────────────────
    h, w = binary.shape
    epsilon_factor = max(0.001, 0.005 - smoothing * 0.0004)

    contours, hierarchy = cv2.findContours(
        binary, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_TC89_KCOS
    )

    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'width="{w}" height="{h}" viewBox="0 0 {w} {h}">',
        '<rect width="100%" height="100%" fill="white"/>',
    ]

    if hierarchy is not None:
        for i, cnt in enumerate(contours):
            if len(cnt) < 3:
                continue
            eps = epsilon_factor * cv2.arcLength(cnt, True)
            approx = cv2.approxPolyDP(cnt, eps, True)
            pts = " ".join(
                f"{p[0][0]},{p[0][1]}" for p in approx
            )
            fill = "black" if hierarchy[0][i][3] == -1 else "white"
            lines.append(
                f'<polygon points="{pts}" fill="{fill}" stroke="none"/>'
            )
    lines.append("</svg>")

    with open(svg_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    return svg_path


# ══════════════════════════════════════════════════════════════════
#  SVG → DXF ENGINE (CorelDRAW Optimized)
# ══════════════════════════════════════════════════════════════════


def robust_svg_to_dxf(svg_path: str, dxf_path: str, simplification: int = 4, kerf_width: float = 0.0) -> None:
    """
    SVG → DXF R2000/R14 (CorelDRAW Uyumluluk Odaklı).
    
    Pipeline:
    1. svgpathtools ile eğrileri ayrıştır.
    2. Eğrileri LWPOLYLINE olarak örnekle.
    3. Kerf telafisi uygula (Eğer kerf_width > 0).
    4. Gereksiz düğümleri temizle ve sadeleştir.
    5. Unit ve Origin normalize edilmiş DXF olarak kaydet.
    """
    if not (EZDXF_OK and VECTOR_LIBS_OK):
        raise ImportError("Gerekli kütüphaneler (ezdxf, svgpathtools, shapely) eksik.")

    # 1. SVG'yi Oku
    paths, attributes = svg2paths(svg_path)
    
    # 2. DXF Dokümanı Oluştur (R2000 - Corel Uyumluluğu ve Birim Desteği)
    doc = ezdxf.new("R2000")
    doc.units = ezdxf.units.MM
    doc.header['$INSUNITS'] = 4 # Millimeters
    
    msp = doc.modelspace()
    
    # Lazer katmanları
    doc.layers.new("CUT", dxfattribs={"color": 7})   # Siyah
    doc.layers.new("ENGRAVE", dxfattribs={"color": 1}) # Kırmızı
    
    # Toleranslar
    SIMPLIFY_TOLERANCE = 0.01
    SNAP_TOLERANCE = 0.5
    PX_TO_MM = 0.264583
    
    open_paths_count = 0
    closed_paths_count = 0

    # Segmentleri topla
    kesim_lines = []
    kazima_lines = []

    for i, path in enumerate(paths):
        if len(path) == 0: continue
        attr = attributes[i] if i < len(attributes) else {}
        stroke = attr.get("stroke", "black").lower()
        fill = attr.get("fill", "black").lower()
        is_kazima = "red" in stroke or "#ff0000" in stroke or "red" in fill or "#ff0000" in fill
        
        for segment in path:
            num_samples = max(2, int(segment.length() / 1))
            pts = []
            for t in np.linspace(0, 1, num_samples):
                p = segment.point(t)
                pts.append((p.real * PX_TO_MM, -p.imag * PX_TO_MM))
            
            if len(pts) >= 2:
                ls = LineString(pts)
                if is_kazima: kazima_lines.append(ls)
                else: kesim_lines.append(ls)

    # 3. Line Merge
    merged_kesim = linemerge(kesim_lines)
    merged_kazima = linemerge(kazima_lines)

    # 4. Kerf Compensation (Sadece KESIM için)
    if kerf_width > 0 and not merged_kesim.is_empty:
        offset = kerf_width / 2.0
        from shapely.ops import polygonize
        
        # Polygonize bütün kapalı döngüleri bulur
        polygons = list(polygonize(merged_kesim))
        if polygons:
            # Alan büyüklüğüne göre sırala (en dıştaki en büyük)
            polygons.sort(key=lambda p: p.area, reverse=True)
            
            final_polys = []
            used_indices = set()
            for i, p in enumerate(polygons):
                if i in used_indices: continue
                shell = p.exterior
                holes = []
                for j in range(i + 1, len(polygons)):
                    if j in used_indices: continue
                    if p.contains(polygons[j]):
                        holes.append(polygons[j].exterior)
                        used_indices.add(j)
                final_polys.append(Polygon(shell, holes))
            
            # Compensation (Miter join = 2, keskin köşeler için)
            compensated_parts = []
            for p in final_polys:
                compensated_parts.append(p.buffer(offset, join_style=2))
            
            # Geriye MultiLineString çevir (DXF için)
            new_lines = []
            for cp in compensated_parts:
                if cp.is_empty: continue
                if isinstance(cp, Polygon):
                    new_lines.append(LineString(cp.exterior.coords))
                    for hole in cp.interiors:
                        new_lines.append(LineString(hole.coords))
                elif isinstance(cp, MultiPolygon):
                    for subp in cp.geoms:
                        new_lines.append(LineString(subp.exterior.coords))
                        for hole in subp.interiors:
                            new_lines.append(LineString(hole.coords))
            
            merged_kesim = MultiLineString(new_lines)

    # 5. Koordinat Normalizasyonu (Origin Fix: 0,0)
    all_merged_geoms = []
    if not merged_kesim.is_empty: all_merged_geoms.append(merged_kesim)
    if not merged_kazima.is_empty: all_merged_geoms.append(merged_kazima)

    min_x, min_y = 0, 0
    if all_merged_geoms:
        from shapely.geometry import GeometryCollection
        bounds = GeometryCollection(all_merged_geoms).bounds
        min_x, min_y = bounds[0], bounds[1]

    def process_merged_geometry(geometry, layer, color):
        nonlocal open_paths_count, closed_paths_count
        items = []
        if isinstance(geometry, LineString): items = [geometry]
        elif isinstance(geometry, MultiLineString): items = list(geometry.geoms)
        elif isinstance(geometry, (list, tuple)): items = geometry
        else: return

        for line in items:
            if not isinstance(line, LineString) or len(line.coords) < 2: continue
            
            # Origin Shift
            pts = [(c[0] - min_x, c[1] - min_y) for c in line.coords]
            
            # Sadeleştirme
            ls = LineString(pts).simplify(SIMPLIFY_TOLERANCE, preserve_topology=True)
            pts = list(ls.coords)
            
            # Kapanma
            is_closed = False
            if len(pts) > 2:
                d = np.linalg.norm(np.array(pts[0]) - np.array(pts[-1]))
                if d < SNAP_TOLERANCE:
                    is_closed = True
                    closed_paths_count += 1
                else:
                    open_paths_count += 1
            else:
                open_paths_count += 1
                
            msp.add_lwpolyline(pts, dxfattribs={"layer": layer, "color": color, "const_width": 0, "closed": is_closed})

    process_merged_geometry(merged_kesim, "CUT", 7)
    process_merged_geometry(merged_kazima, "ENGRAVE", 1)
    
    print(f"DXF Export: {closed_paths_count} yol kapatıldı, {open_paths_count} yol açık kaldı (Kerf: {kerf_width}mm).")
    doc.saveas(dxf_path)


# SVG path ayrıştırıcıları kaldırıldı — artık binary_to_dxf kullanılıyor


# ══════════════════════════════════════════════════════════════════
#  WORKER THREAD
# ══════════════════════════════════════════════════════════════════
class VectorWorker(QObject):
    progress = pyqtSignal(int, str)
    finished = pyqtSignal(str, object, object)  # (svg_path, orig_rgb ndarray, binary ndarray)
    error    = pyqtSignal(str)

    def __init__(
        self,
        img_path: str,
        threshold: int,
        laser_mode: bool,
        detail: int,
        smoothing: int,
    ):
        super().__init__()
        self.img_path   = img_path
        self.threshold  = threshold
        self.laser_mode = laser_mode
        self.detail     = detail
        self.smoothing  = smoothing

    def run(self) -> None:
        try:
            self.progress.emit(5,  "Görsel yükleniyor...")
            gray, orig_rgb = load_image_gray(self.img_path)

            self.progress.emit(20, "Kontrast artırılıyor...")
            gray = enhance_gray(gray)

            self.progress.emit(40, "Binary maske oluşturuluyor...")
            binary = make_binary_mask(
                gray,
                self.threshold,
                self.laser_mode,
                self.detail,
                self.smoothing,
            )

            self.progress.emit(65, "Vektör SVG üretiliyor...")
            svg_path = binary_to_svg(binary, self.smoothing)

            self.progress.emit(90, "Temizleme tamamlanıyor...")
            self.progress.emit(100, "✅ Tamamlandı!")
            self.finished.emit(svg_path, orig_rgb, binary)

        except Exception:
            self.error.emit(traceback.format_exc())


# ══════════════════════════════════════════════════════════════════
#  DRAG & DROP YÜKLEME ALANI
# ══════════════════════════════════════════════════════════════════
class DropZone(QLabel):
    file_dropped = pyqtSignal(str)
    SUPPORTED = (".png", ".jpg", ".jpeg", ".bmp", ".webp")

    _STYLE_BASE = """
        QLabel {
            border: 2px dashed %BORDER%;
            border-radius: 10px;
            background: #0f1a2e;
            color: #a0a0b0;
            font-size: 13px;
            font-weight: 500;
        }
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setText("📂  Görsel Yükle\n\nPNG · JPG · BMP · WEBP\n(sürükle-bırak veya tıkla)")
        self.setMinimumHeight(100)
        self._set_border("#2a2a4a")

    def _set_border(self, color: str) -> None:
        self.setStyleSheet(self._STYLE_BASE.replace("%BORDER%", color))

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                if url.toLocalFile().lower().endswith(self.SUPPORTED):
                    event.acceptProposedAction()
                    self._set_border("#e94560")
                    return
        event.ignore()

    def dragLeaveEvent(self, event) -> None:
        self._set_border("#2a2a4a")

    def dropEvent(self, event: QDropEvent) -> None:
        self._set_border("#2a2a4a")
        for url in event.mimeData().urls():
            path = url.toLocalFile()
            if path.lower().endswith(self.SUPPORTED):
                self.file_dropped.emit(path)
                return

    def mousePressEvent(self, event) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Görsel Seç", "",
            "Görseller (*.png *.jpg *.jpeg *.bmp *.webp)"
        )
        if path:
            self.file_dropped.emit(path)


# ══════════════════════════════════════════════════════════════════
#  ANA SEKME WIDGET
# ══════════════════════════════════════════════════════════════════
def _make_slider_row(label: str, lo: int, hi: int, default: int, val_width: int = 30):
    """(QHBoxLayout, QSlider, QLabel) üçlüsü üretir."""
    row = QHBoxLayout()
    lbl = QLabel(label)
    lbl.setStyleSheet("font-weight:600; font-size:12px;")
    lbl.setFixedWidth(105)
    slider = QSlider(Qt.Orientation.Horizontal)
    slider.setRange(lo, hi)
    slider.setValue(default)
    val_lbl = QLabel(str(default))
    val_lbl.setFixedWidth(val_width)
    val_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
    slider.valueChanged.connect(lambda v: val_lbl.setText(str(v)))
    row.addWidget(lbl)
    row.addWidget(slider)
    row.addWidget(val_lbl)
    return row, slider, val_lbl


class DXFSVGTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._svg_path    = None
        self._img_path    = None
        self._orig_rgb    = None
        self._binary_mask = None   # DXF export için saklanır
        self._thread    = None
        self._worker    = None
        self._setup_ui()

    # ── UI inşası ─────────────────────────────────────────────
    def _setup_ui(self) -> None:
        from ui_interface import make_separator

        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setStyleSheet(
            "QSplitter::handle { background: #2a2a4a; width: 2px; }"
        )

        # ═══ SOL PANEL: kontroller ═══════════════════════════
        left = QWidget()
        left.setFixedWidth(310)
        left.setStyleSheet("background: #1a1a2e;")
        lv = QVBoxLayout(left)
        lv.setContentsMargins(14, 14, 14, 14)
        lv.setSpacing(10)

        title = QLabel("✂  DD1 Lazer Agent")
        title.setObjectName("title")
        lv.addWidget(title)
        lv.addWidget(make_separator())

        # Drag-drop
        self._drop_zone = DropZone()
        self._drop_zone.file_dropped.connect(self._on_image_loaded)
        lv.addWidget(self._drop_zone)

        self._file_lbl = QLabel("")
        self._file_lbl.setObjectName("dim")
        self._file_lbl.setWordWrap(True)
        lv.addWidget(self._file_lbl)
        lv.addWidget(make_separator())

        # ── Ayar grubu ─────────────────────────────────────
        grp = QGroupBox("Parametreler")
        grp.setStyleSheet("""
            QGroupBox {
                color: #a0a0b0;
                border: 1px solid #2a2a4a;
                border-radius: 6px;
                margin-top: 8px;
                padding-top: 8px;
                font-size: 11px;
                font-weight: 600;
            }
            QGroupBox::title { subcontrol-position: top left; left: 10px; }
        """)
        gv = QVBoxLayout(grp)
        gv.setSpacing(8)

        # Threshold
        r1, self._thr_slider, _ = _make_slider_row("Threshold", 0, 255, 128)
        gv.addLayout(r1)

        # Detail
        r2, self._detail_slider, _ = _make_slider_row("Detail", 1, 10, 5)
        detail_hint = QLabel("↑ yüksek = daha fazla ince detay")
        detail_hint.setObjectName("dim")
        detail_hint.setStyleSheet("font-size:10px; color:#606080; margin-left:106px;")
        gv.addLayout(r2)
        gv.addWidget(detail_hint)

        # Smoothing
        r3, self._smooth_slider, _ = _make_slider_row("Smoothing", 1, 10, 4)
        smooth_hint = QLabel("↑ yüksek = daha pürüzsüz kontur")
        smooth_hint.setObjectName("dim")
        smooth_hint.setStyleSheet("font-size:10px; color:#606080; margin-left:106px;")
        gv.addLayout(r3)
        gv.addWidget(smooth_hint)

        lv.addWidget(grp)

        # Lazer Modu
        self._laser_chk = QCheckBox("⚡  Lazer Modu")
        self._laser_chk.setStyleSheet("font-weight:700; font-size:13px;")
        laser_hint = QLabel(
            "Adaptif eşikleme + güçlü morfoloji\n"
            "Düşük kontrastlı görseller için ideal"
        )
        laser_hint.setObjectName("dim")
        laser_hint.setWordWrap(True)
        laser_hint.setStyleSheet("font-size:11px; color:#606080;")
        lv.addWidget(self._laser_chk)
        lv.addWidget(laser_hint)
        lv.addWidget(make_separator())

        # Potrace durum rozeti
        potrace_status = "✅ Potrace aktif" if POTRACE_BIN else (
            "✅ vtracer aktif" if VTRACER_OK else "⚠ Kontür modu"
        )
        p_lbl = QLabel(potrace_status)
        p_lbl.setStyleSheet(
            "font-size:11px; color:#4ecdc4;" if POTRACE_BIN
            else ("font-size:11px; color:#a0c060;" if VTRACER_OK
                  else "font-size:11px; color:#f5a623;")
        )
        lv.addWidget(p_lbl)

        # Dönüştür butonu
        self._convert_btn = QPushButton("▶  Dönüştür")
        self._convert_btn.setMinimumHeight(42)
        self._convert_btn.setEnabled(False)
        self._convert_btn.clicked.connect(self._start_conversion)
        lv.addWidget(self._convert_btn)

        # İlerleme çubuğu
        self._progress = QProgressBar()
        self._progress.setValue(0)
        self._progress.setFormat("%p%")
        lv.addWidget(self._progress)

        self._status_lbl = QLabel("Görsel yükleyin.")
        self._status_lbl.setObjectName("dim")
        self._status_lbl.setWordWrap(True)
        lv.addWidget(self._status_lbl)
        lv.addStretch()

        # Export butonları
        lv.addWidget(make_separator())
        self._svg_btn = QPushButton("💾  SVG Olarak Kaydet")
        self._svg_btn.setMinimumHeight(38)
        self._svg_btn.setEnabled(False)
        self._svg_btn.clicked.connect(self._save_svg)

        self._dxf_btn = QPushButton("💾  DXF Olarak Kaydet")
        self._dxf_btn.setObjectName("secondary")
        self._dxf_btn.setMinimumHeight(38)
        self._dxf_btn.setEnabled(False)
        self._dxf_btn.clicked.connect(self._save_dxf)

        lv.addWidget(self._svg_btn)
        lv.addWidget(self._dxf_btn)

        # ═══ SAĞ PANEL: yan yana önizleme ════════════════════
        right = QWidget()
        rv = QVBoxLayout(right)
        rv.setContentsMargins(10, 14, 14, 14)
        rv.setSpacing(6)

        preview_header = QHBoxLayout()
        prv_lbl = QLabel("Ön İzleme")
        prv_lbl.setObjectName("title")
        hint_lbl = QLabel("Ctrl+Scroll ile zoom · Sol tık ile kaydır")
        hint_lbl.setObjectName("dim")
        hint_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        preview_header.addWidget(prv_lbl)
        preview_header.addWidget(hint_lbl)
        rv.addLayout(preview_header)

        # Yan yana splitter: orijinal | vektör
        preview_split = QSplitter(Qt.Orientation.Horizontal)
        preview_split.setStyleSheet(
            "QSplitter::handle { background: #e94560; width: 2px; }"
        )

        # Orijinal görsel paneli
        orig_w = QWidget()
        orig_w.setStyleSheet("background:#0a0a18;")
        orig_v = QVBoxLayout(orig_w)
        orig_v.setContentsMargins(4, 4, 4, 4)
        orig_title = QLabel("Orijinal Görsel")
        orig_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        orig_title.setStyleSheet("font-size:11px; color:#e94560; font-weight:600;")
        orig_v.addWidget(orig_title)
        self._orig_scene = QGraphicsScene()
        self._orig_view  = QGraphicsView(self._orig_scene)
        self._orig_view.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self._orig_view.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        orig_v.addWidget(self._orig_view)

        # Vektör önizleme paneli
        vec_w = QWidget()
        vec_w.setStyleSheet("background:#0a0a18;")
        vec_v = QVBoxLayout(vec_w)
        vec_v.setContentsMargins(4, 4, 4, 4)
        vec_title = QLabel("Vektör Çıktısı (SVG)")
        vec_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        vec_title.setStyleSheet("font-size:11px; color:#4ecdc4; font-weight:600;")
        vec_v.addWidget(vec_title)
        self._vec_scene = QGraphicsScene()
        self._vec_view  = QGraphicsView(self._vec_scene)
        self._vec_view.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self._vec_view.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        vec_v.addWidget(self._vec_view)

        preview_split.addWidget(orig_w)
        preview_split.addWidget(vec_w)
        rv.addWidget(preview_split)

        # Ana splitter birleştir
        splitter.addWidget(left)
        splitter.addWidget(right)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)

        root.addWidget(splitter)

    # ── Zoom ──────────────────────────────────────────────────
    def wheelEvent(self, event) -> None:
        if event.modifiers() == Qt.KeyboardModifier.ControlModifier:
            f = 1.15 if event.angleDelta().y() > 0 else 1 / 1.15
            self._orig_view.scale(f, f)
            self._vec_view.scale(f, f)
        else:
            super().wheelEvent(event)

    # ── Slotlar ───────────────────────────────────────────────
    def _on_image_loaded(self, path: str) -> None:
        self._img_path = path
        self._file_lbl.setText(f"📄 {os.path.basename(path)}")
        self._convert_btn.setEnabled(True)
        self._status_lbl.setText("Görsel yüklendi. Dönüştür'e basın.")
        self._svg_path = None
        self._svg_btn.setEnabled(False)
        self._dxf_btn.setEnabled(False)
        # Orijinal görseli sol panelde göster
        self._show_original(path)

    def _show_original(self, path: str) -> None:
        self._orig_scene.clear()
        try:
            pix = QPixmap(path)
            if not pix.isNull():
                self._orig_scene.addPixmap(pix)
                self._orig_view.fitInView(
                    self._orig_scene.itemsBoundingRect(),
                    Qt.AspectRatioMode.KeepAspectRatio
                )
        except Exception as e:
            self._orig_scene.addText(f"Önizleme hatası: {e}")

    def _start_conversion(self) -> None:
        if not self._img_path:
            return
        self._convert_btn.setEnabled(False)
        self._svg_btn.setEnabled(False)
        self._dxf_btn.setEnabled(False)
        self._progress.setValue(0)
        self._vec_scene.clear()

        self._thread = QThread()
        self._worker = VectorWorker(
            self._img_path,
            self._thr_slider.value(),
            self._laser_chk.isChecked(),
            self._detail_slider.value(),
            self._smooth_slider.value(),
        )
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._on_finished)
        self._worker.error.connect(self._on_error)
        self._worker.finished.connect(self._thread.quit)
        self._worker.error.connect(self._thread.quit)
        self._thread.finished.connect(
            lambda: self._convert_btn.setEnabled(True)
        )
        self._thread.start()

    def _on_progress(self, value: int, desc: str) -> None:
        self._progress.setValue(value)
        self._status_lbl.setText(desc)

    def _on_finished(self, svg_path: str, orig_rgb, binary) -> None:
        self._svg_path    = svg_path
        self._binary_mask = binary          # DXF için sakla
        self._svg_btn.setEnabled(True)
        self._dxf_btn.setEnabled(True)
        self._status_lbl.setText("✅ Dönüştürme tamamlandı!")
        self._show_svg_preview(svg_path)

    def _on_error(self, msg: str) -> None:
        self._status_lbl.setText("❌ Hata oluştu.")
        QMessageBox.critical(self, "İşlem Hatası", msg)
        self._convert_btn.setEnabled(True)

    def _show_svg_preview(self, svg_path: str) -> None:
        self._vec_scene.clear()
        try:
            with open(svg_path, "rb") as f:
                data = QByteArray(f.read())
            renderer = QSvgRenderer(data)
            svg_item = QGraphicsSvgItem()
            svg_item.setSharedRenderer(renderer)
            self._vec_scene.addItem(svg_item)
            self._vec_view.fitInView(
                self._vec_scene.itemsBoundingRect(),
                Qt.AspectRatioMode.KeepAspectRatio
            )
        except Exception as e:
            self._vec_scene.addText(f"SVG önizleme hatası: {e}")

    def _save_svg(self) -> None:
        if not self._svg_path:
            return
        dest, _ = QFileDialog.getSaveFileName(
            self, "SVG Olarak Kaydet", "cizim.svg", "SVG Dosyası (*.svg)"
        )
        if dest:
            shutil.copy2(self._svg_path, dest)
            self._status_lbl.setText(f"SVG kaydedildi: {os.path.basename(dest)}")

    def _save_dxf(self) -> None:
        if self._binary_mask is None:
            QMessageBox.warning(self, "DXF", "Önce dönüştürme yapın.")
            return
        dest, _ = QFileDialog.getSaveFileName(
            self, "DXF Olarak Kaydet", "cizim.dxf", "DXF Dosyası (*.dxf)"
        )
        if dest:
            try:
                # Yeni Nesil Robust SVG -> DXF Motoru
                robust_svg_to_dxf(
                    self._svg_path,
                    dest,
                    simplification=self._smooth_slider.value(),
                )
                self._status_lbl.setText(f"DXF kaydedildi (R14): {os.path.basename(dest)}")
            except Exception as e:
                QMessageBox.critical(self, "DXF Hatası", str(e))
