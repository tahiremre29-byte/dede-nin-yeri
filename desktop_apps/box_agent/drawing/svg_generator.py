"""
SVG Teknik Çizim Üretici — Profesyonel Mühendislik Çizimi
Front view, Side view, Top view, Port Section view.
Ok uçlu ölçü çizgileri, malzeme hatching, port kanalı detayı.
"""
import math
import svgwrite
from engine.ts_calculator import CabinetResult
from engine.panel_calculator import PanelList


# ─── Çizim Sabitleri ──────────────────────────────────────────────────────────
MARGIN       = 50
VIEW_GAP     = 70
SCALE        = 0.55      # mm → px

# Renkler
BG           = "#0d1117"
PANEL_FILL   = "#161b22"
PANEL_STROKE = "#c9d1d9"
INNER_STROKE = "#30363d"
PORT_FILL    = "#1f3d73"
PORT_STROKE  = "#58a6ff"
SUB_STROKE   = "#a371f7"
SUB_FILL     = "#1c1430"
DIM_COLOR    = "#8b949e"
TITLE_CLR    = "#58a6ff"
ACCENT       = "#f0883e"
LABEL_CLR    = "#e6edf3"
HATCH_CLR    = "#21262d"
GREEN        = "#3fb950"
WARN_CLR     = "#d29922"
GRID_CLR     = "#161b22"

# Ölçü çizgisi sabitleri
DIM_OFFSET   = 25       # px — ölçü çizgisi uzaklığı
ARROW_SIZE   = 5        # ok ucu boyutu
DIM_FONT     = 10       # px


def generate_svg(result: CabinetResult, panels: PanelList, filepath: str) -> str:
    """Profesyonel 4 görünümlü SVG teknik çizim."""

    # Ölçekleme
    ow = panels.outer_w_mm * SCALE
    oh = panels.outer_h_mm * SCALE
    od = panels.outer_d_mm * SCALE
    t  = panels.thickness_mm * SCALE
    sub_r = panels.sub_cutout_mm * SCALE / 2
    sub_outer_r = panels.diameter_inch * 25.4 * SCALE / 2

    # Port boyutlarını PanelList'ten al (hesaplanmış ve kabine sığdırılmış)
    slot_h_px = panels.port_brace["height_check"] * SCALE
    slot_w_px = panels.port_brace["w"] * SCALE
    port_len_px = result.port_length_cm * 10 * SCALE

    # Canvas boyutları
    row1_h = max(oh, 200) + DIM_OFFSET * 3
    row2_h = max(od, 150) + DIM_OFFSET * 3
    col1_w = max(ow, 200) + DIM_OFFSET * 3
    col2_w = max(od, 200) + DIM_OFFSET * 3
    info_h = 200

    canvas_w = int(MARGIN * 2 + col1_w + VIEW_GAP + col2_w + 60)
    canvas_h = int(MARGIN * 2 + row1_h + VIEW_GAP + row2_h + info_h + 50)

    dwg = svgwrite.Drawing(filepath, size=(f"{canvas_w}px", f"{canvas_h}px"))

    # Marker definitions (ok uçları)
    _define_markers(dwg)

    # Arka plan
    dwg.add(dwg.rect((0, 0), (canvas_w, canvas_h), fill=BG))

    # Çerçeve
    _draw_border(dwg, canvas_w, canvas_h)

    # ─── Başlık Kutusu ────────────────────────────────────────────────────────
    _draw_title_block(dwg, canvas_w, canvas_h, result, panels)

    # ─── View koordinatları ───────────────────────────────────────────────────
    # Front: sol üst
    fx = MARGIN + DIM_OFFSET * 2
    fy = MARGIN + 50

    # Side: sağ üst
    sx = fx + ow + VIEW_GAP + DIM_OFFSET
    sy = fy

    # Top: sol alt
    tx = fx
    ty = fy + oh + VIEW_GAP + DIM_OFFSET

    # Section: sağ alt (port kesit detayı)
    secx = sx
    secy = ty

    # ─── Çizimler ─────────────────────────────────────────────────────────────
    _draw_front_view(dwg, fx, fy, ow, oh, t, sub_r, sub_outer_r, slot_w_px, slot_h_px, panels, result)
    _draw_side_view(dwg, sx, sy, od, oh, t, slot_w_px, slot_h_px, port_len_px, panels, result)
    _draw_top_view(dwg, tx, ty, ow, od, t, slot_w_px, slot_h_px, port_len_px, panels, result)
    _draw_port_section(dwg, secx, secy, od, slot_h_px, slot_w_px, port_len_px, t, panels, result)

    # ─── Bilgi Tablosu ────────────────────────────────────────────────────────
    info_y = ty + od + DIM_OFFSET * 3 + 20
    _draw_info_table(dwg, MARGIN, info_y, canvas_w - MARGIN * 2, result, panels)

    dwg.save()
    return filepath


# ═══════════════════════════════════════════════════════════════════════════════
# MARKER & BORDER
# ═══════════════════════════════════════════════════════════════════════════════

def _define_markers(dwg):
    """Ok ucu marker tanımla"""
    # Dolgu ok
    marker = dwg.marker(id="arrow", insert=(ARROW_SIZE, ARROW_SIZE/2),
                        size=(ARROW_SIZE*2, ARROW_SIZE),
                        orient="auto", markerUnits="userSpaceOnUse")
    marker.add(dwg.polygon(
        points=[(0, 0), (ARROW_SIZE*2, ARROW_SIZE/2), (0, ARROW_SIZE)],
        fill=DIM_COLOR
    ))
    dwg.defs.add(marker)

    # Ters ok (180° döndürülmüş polygon)
    marker2 = dwg.marker(id="arrow_rev", insert=(0, ARROW_SIZE/2),
                         size=(ARROW_SIZE*2, ARROW_SIZE),
                         orient="auto", markerUnits="userSpaceOnUse")
    marker2.add(dwg.polygon(
        points=[(ARROW_SIZE*2, 0), (0, ARROW_SIZE/2), (ARROW_SIZE*2, ARROW_SIZE)],
        fill=DIM_COLOR
    ))
    dwg.defs.add(marker2)


def _draw_border(dwg, w, h):
    """Çizim çerçevesi"""
    m = 8
    dwg.add(dwg.rect((m, m), (w - 2*m, h - 2*m),
                      fill="none", stroke=PANEL_STROKE, stroke_width=1.5))
    dwg.add(dwg.rect((m+2, m+2), (w - 2*m - 4, h - 2*m - 4),
                      fill="none", stroke=INNER_STROKE, stroke_width=0.5))


# ═══════════════════════════════════════════════════════════════════════════════
# FRONT VIEW
# ═══════════════════════════════════════════════════════════════════════════════

def _draw_front_view(dwg, x, y, w, h, t, sub_r, sub_outer_r, slot_w, slot_h, panels, result):
    # Başlık
    _view_title(dwg, x + w/2, y - 18, "ON GORUNUM (FRONT VIEW)")

    # Dış kutu — çift çizgi (malzeme)
    dwg.add(dwg.rect((x, y), (w, h), fill=PANEL_FILL, stroke=PANEL_STROKE, stroke_width=2))
    # İç kutu
    dwg.add(dwg.rect((x+t, y+t), (w-2*t, h-2*t),
                      fill="none", stroke=INNER_STROKE, stroke_width=1,
                      stroke_dasharray="6,3"))

    # Malzeme kalınlığı hatching (4 kenar)
    _hatch_rect(dwg, x, y, t, h, "vertical")           # sol kenar
    _hatch_rect(dwg, x+w-t, y, t, h, "vertical")       # sağ kenar
    _hatch_rect(dwg, x, y, w, t, "horizontal")          # üst kenar
    _hatch_rect(dwg, x, y+h-t, w, t, "horizontal")     # alt kenar

    # Subwoofer - Merkeze yakın ama port payı bırakılmış
    cx = x + t + (w - 2*t - slot_w) / 2
    cy = y + h / 2
    # Dış çap dairesi
    dwg.add(dwg.circle((cx, cy), sub_outer_r,
                        fill="none", stroke=SUB_STROKE, stroke_width=1,
                        stroke_dasharray="3,2"))
    # Kesim dairesi
    dwg.add(dwg.circle((cx, cy), sub_r,
                        fill=SUB_FILL, stroke=SUB_STROKE, stroke_width=2))
    # Label
    _label(dwg, cx, cy + sub_r + 14, f'{panels.diameter_inch}" DRIVER',
           SUB_STROKE, 9, anchor="middle")

    # Slot port (SAĞ YAN - DİKEY)
    port_x = x + w - t - slot_w
    port_y = y + t
    dwg.add(dwg.rect((port_x, port_y), (slot_w, h - 2*t),
                      fill=PORT_FILL, fill_opacity=0.3,
                      stroke=PORT_STROKE, stroke_width=1.5))
    
    # Mavi Port Şeridi (Hatching)
    _hatch_rect(dwg, port_x, port_y, slot_w, h - 2*t, "vertical", PORT_STROKE)
    
    # Mavi Hava Akışı (Dikey Oklar)
    arrow_center_x = port_x + slot_w / 2
    for ay in range(int(port_y + 20), int(port_y + h - 2*t - 20), 40):
        dwg.add(dwg.line((arrow_center_x, ay + 15), (arrow_center_x, ay),
                          stroke=PORT_STROKE, stroke_width=1.5,
                          marker_end="url(#arrow)"))

    # Port label
    _label(dwg, port_x + slot_w/2, port_y - 8, "SIDE PORT",
           PORT_STROKE, 8, anchor="middle")
    # Port iç ölçü (Genişlik)
    _dim_inside_w(dwg, port_x, port_x + slot_w, port_y + h - 2*t + 10,
                  f"W:{slot_w/SCALE:.0f}mm", 7)

    # ─── Boyut çizgileri ──────────────────────────────────────────────────────
    # Yükseklik (sol)
    _dim_vertical(dwg, x - DIM_OFFSET, y, y + h, f"{panels.outer_h_mm:.0f}")
    # Genişlik (alt)
    _dim_horizontal(dwg, x, x + w, y + h + DIM_OFFSET, f"{panels.outer_w_mm:.0f}")
    # Malzeme kalınlığı notu
    _label(dwg, x + t/2, y + h + 8, f"t={panels.thickness_mm:.0f}",
           ACCENT, 7, anchor="middle")


# ═══════════════════════════════════════════════════════════════════════════════
# SIDE VIEW
# ═══════════════════════════════════════════════════════════════════════════════

def _draw_side_view(dwg, x, y, d, h, t, slot_w, slot_h, port_len, panels, result):
    _view_title(dwg, x + d/2, y - 18, "YAN GORUNUM (SIDE VIEW)")

    # Dış kutu
    dwg.add(dwg.rect((x, y), (d, h), fill=PANEL_FILL, stroke=PANEL_STROKE, stroke_width=2))
    # İç kutu
    dwg.add(dwg.rect((x+t, y+t), (d-2*t, h-2*t),
                      fill="none", stroke=INNER_STROKE, stroke_width=1,
                      stroke_dasharray="6,3"))

    # Hatching
    _hatch_rect(dwg, x, y, t, h, "vertical")
    _hatch_rect(dwg, x+d-t, y, t, h, "vertical")
    _hatch_rect(dwg, x, y, d, t, "horizontal")
    _hatch_rect(dwg, x, y+h-t, d, t, "horizontal")

    # Port kanalı (Dikey yan port, D derinliği boyunca)
    actual_len = min(port_len, d - 2*t)
    port_w = slot_h # Yan görünümde yan portun genişliği dikey slot_height'tır? Hayır, 
                    # yan görünümde yan portun DERİNLİĞİ d'dir. Ama kanal iç duvarı t kadar içeridedir.
    
    # Port kanalı (üstten alta tam boy yan panel arkası)
    port_canal_x = x + d - t - slot_w
    dwg.add(dwg.rect((port_canal_x, y + t), (slot_w, h - 2*t),
                      fill=PORT_FILL, fill_opacity=0.4,
                      stroke=PORT_STROKE, stroke_width=1.5))
    _hatch_rect(dwg, port_canal_x, y + t, slot_w, h - 2*t, "vertical", PORT_STROKE)
    
    # Mavi Hava Akışı (Yan Görünümde Derinliğe Doğru)
    for ad in range(int(x + 20), int(x + d - 40), 50):
        dwg.add(dwg.line((ad, y + h/2), (ad + 20, y + h/2),
                          stroke=PORT_STROKE, stroke_width=1.5,
                          marker_end="url(#arrow)"))

    # Port uzunluk ölçüsü
    _dim_inside_w(dwg, x + d - t - actual_len, x + d - t, y + h - t - 20,
                  f"Lp={result.port_length_cm:.0f}cm", 8)

    # Sürücü (yan profil)
    driver_depth = 12 * SCALE
    cy = y + h / 2
    dwg.add(dwg.rect((x + t, cy - 50), (driver_depth, 100),
                      fill="none", stroke=SUB_STROKE, stroke_width=1.5,
                      stroke_dasharray="4,2"))

    # Boyutlar
    _dim_horizontal(dwg, x, x + d, y + h + DIM_OFFSET, f"{panels.outer_d_mm:.0f}")
    _dim_vertical(dwg, x + d + DIM_OFFSET, y, y + h, f"{panels.outer_h_mm:.0f}")


# ═══════════════════════════════════════════════════════════════════════════════
# TOP VIEW
# ═══════════════════════════════════════════════════════════════════════════════

def _draw_top_view(dwg, x, y, w, d, t, slot_w, slot_h, port_len_px, panels, result):
    _view_title(dwg, x + w/2, y - 18, "UST GORUNUM (TOP VIEW)")

    # Dış kutu
    dwg.add(dwg.rect((x, y), (w, d), fill=PANEL_FILL, stroke=PANEL_STROKE, stroke_width=2))
    # İç kutu
    dwg.add(dwg.rect((x+t, y+t), (w-2*t, d-2*t),
                      fill="none", stroke=INNER_STROKE, stroke_width=1,
                      stroke_dasharray="6,3"))

    # Hatching
    _hatch_rect(dwg, x, y, t, d, "vertical")
    _hatch_rect(dwg, x+w-t, y, t, d, "vertical")
    _hatch_rect(dwg, x, y, w, t, "horizontal")
    _hatch_rect(dwg, x, y+d-t, w, t, "horizontal")

    # Port çıkış (Sağ yan tarafta)
    port_x = x + w - t - slot_w
    dwg.add(dwg.rect((port_x, y + t), (slot_w, d - 2*t),
                      fill=PORT_FILL, fill_opacity=0.7,
                      stroke=PORT_STROKE, stroke_width=1.5))
    
    # Port çıkış ağzı (Sağ kenar)
    dwg.add(dwg.rect((x + w - t, y + t), (t, d - 2*t),
                      fill=PORT_FILL, fill_opacity=0.9,
                      stroke=PORT_STROKE, stroke_width=1))

    # Mavi Hava Akışı (Dönüş Okları)
    # 1. Kanaldan geliş
    dwg.add(dwg.line((port_x + slot_w/2, y + d - t - 20), (port_x + slot_w/2, y + d/2),
                      stroke=PORT_STROKE, stroke_width=1.5, marker_end="url(#arrow)"))
    # 2. Dışarı çıkış
    dwg.add(dwg.line((port_x + slot_w/2, y + d/2), (x + w - 5, y + d/2),
                      stroke=PORT_STROKE, stroke_width=1.5, marker_end="url(#arrow)"))

    _label(dwg, port_x - 5, y + d/2, "SIDE PORT EXIT",
           PORT_STROKE, 8, anchor="end")

    # Subwoofer (üstten)
    cx = x + t + (w - 2*t - slot_w) / 2
    cy = y + d / 2
    sub_r_top = panels.sub_cutout_mm * SCALE / 2
    dwg.add(dwg.circle((cx, cy), sub_r_top,
                        fill="none", stroke=SUB_STROKE, stroke_width=1.5,
                        stroke_dasharray="4,2"))

    # Boyutlar
    _dim_horizontal(dwg, x, x + w, y + d + DIM_OFFSET, f"{panels.outer_w_mm:.0f}")
    _dim_vertical(dwg, x - DIM_OFFSET, y, y + d, f"{panels.outer_d_mm:.0f}")


# ═══════════════════════════════════════════════════════════════════════════════
# PORT SECTION VIEW (Kesit)
# ═══════════════════════════════════════════════════════════════════════════════

def _draw_port_section(dwg, x, y, d, slot_h, slot_w, port_len, t, panels, result):
    """Port kesit detayı — kabin yandan kesilmiş port görünümü"""
    _view_title(dwg, x + d/2, y - 18, "PORT KESIT DETAYI")

    scale_d = min(d, 250)
    scale_h = min(slot_h * 4 + t * 4, 150)

    # Dış çerçeve
    dwg.add(dwg.rect((x, y), (scale_d, scale_h),
                      fill=PANEL_FILL, stroke=INNER_STROKE, stroke_width=1))

    # Port kesit gösterimi (büyütülmüş)
    px = x + 10
    py = y + scale_h * 0.3
    pw = scale_d - 20
    ph = min(slot_h * 2.5, scale_h * 0.4)

    # Alt panel
    dwg.add(dwg.rect((px, py + ph), (pw, t * 2),
                      fill=HATCH_CLR, stroke=PANEL_STROKE, stroke_width=1))
    _hatch_rect(dwg, px, py + ph, pw, t * 2, "horizontal")

    # Üst panel (port tavanı)
    dwg.add(dwg.rect((px, py - t * 2), (pw, t * 2),
                      fill=HATCH_CLR, stroke=PANEL_STROKE, stroke_width=1))
    _hatch_rect(dwg, px, py - t * 2, pw, t * 2, "horizontal")

    # Port boşluğu
    dwg.add(dwg.rect((px, py), (pw, ph),
                      fill=PORT_FILL, fill_opacity=0.3,
                      stroke=PORT_STROKE, stroke_width=1.5))
    _hatch_rect(dwg, px, py, pw, ph, "vertical", PORT_STROKE)

    # Hava akış okları
    arrow_y = py + ph / 2
    for ax in range(int(px + 20), int(px + pw - 20), 35):
        dwg.add(dwg.line((ax, arrow_y), (ax + 20, arrow_y),
                          stroke=PORT_STROKE, stroke_width=1,
                          marker_end="url(#arrow)"))

    # Etiketler
    _label(dwg, px + pw/2, py + ph/2 + 3, "HAVA AKISI", PORT_STROKE, 8, anchor="middle")
    
    # Detaylı Port Bilgileri (Kullanıcı Talebi)
    label_y = py + ph + t * 2 + 16
    _label(dwg, px, label_y, f"Port Area: {result.port_area_cm2:.1f} cm2", ACCENT, 8)
    _label(dwg, px, label_y + 12, f"Port Length: {result.port_length_cm:.1f} cm", ACCENT, 8)
    _label(dwg, px, label_y + 24, f"Port Velocity: {result.port_velocity_ms:.1f} m/s", ACCENT, 8)

    # Port yükseklik ölçüsü
    _dim_inside_h(dwg, px + pw + 8, py, py + ph,
                  f"{result.slot_height_cm*10:.0f} mm", 8)

    # Port uzunluk ölçüsü
    _dim_inside_w(dwg, px, px + pw, py - t * 2 - 10,
                  f"Lp={result.port_length_cm:.0f}cm", 8)


# ═══════════════════════════════════════════════════════════════════════════════
# TITLE BLOCK
# ═══════════════════════════════════════════════════════════════════════════════

def _draw_title_block(dwg, cw, ch, result, panels):
    """Sağ alt köşe başlık kutusu"""
    bw = 320
    bh = 70
    bx = cw - bw - 12
    by = ch - bh - 12

    dwg.add(dwg.rect((bx, by), (bw, bh),
                      fill=PANEL_FILL, stroke=PANEL_STROKE, stroke_width=1))
    # Başlık
    dwg.add(dwg.text("DD1 BOX ENGINEERING",
                      insert=(bx + bw/2, by + 18),
                      fill=TITLE_CLR, font_size="13px",
                      font_family="Consolas, monospace", font_weight="bold",
                      text_anchor="middle"))
    # Alt bilgi
    dwg.add(dwg.text(f"Hacim: {result.vb_litre}L | Tuning: {result.fb_hz}Hz | "
                     f"Port: {result.port_area_cm2}cm2",
                      insert=(bx + bw/2, by + 34),
                      fill=DIM_COLOR, font_size="9px",
                      font_family="Consolas", text_anchor="middle"))
    # Malzeme kalınlığı detayı (18x2=36)
    t_val = panels.thickness_mm
    dwg.add(dwg.text(f"Dış = İç + 2x{t_val:.0f}mm ({t_val*2:.0f}mm)",
                      insert=(bx + bw/2, by + 48),
                      fill=ACCENT, font_size="9px",
                      font_family="Consolas", text_anchor="middle"))
    
    dwg.add(dwg.text(f"Dis: {panels.outer_w_mm:.0f}x{panels.outer_h_mm:.0f}x"
                     f"{panels.outer_d_mm:.0f}mm",
                      insert=(bx + bw/2, by + 60),
                      fill=DIM_COLOR, font_size="9px",
                      font_family="Consolas", text_anchor="middle"))
    dwg.add(dwg.text(f"{result.mode}",
                      insert=(bx + bw/2, by + 72),
                      fill=GREEN, font_size="8px",
                      font_family="Consolas", text_anchor="middle"))


def _draw_info_table(dwg, x, y, w, result, panels):
    """Alt bilgi tablosu"""
    cols = [
        ("KABiN", [
            f"Net Hacim: {result.vb_litre} L",
            f"Dis: {panels.outer_w_mm:.0f}x{panels.outer_h_mm:.0f}x{panels.outer_d_mm:.0f} mm",
            f"Malzeme: {panels.thickness_mm:.0f} mm",
        ]),
        ("PORT", [
            f"Alan: {result.port_area_cm2} cm2",
            f"Uzunluk: {result.port_length_cm} cm",
            f"Slot: {result.slot_width_cm} x {result.slot_height_cm} cm",
        ]),
        ("AKUSTIK", [
            f"Tuning: {result.fb_hz} Hz",
            f"SPL: {result.peak_spl_db} dB",
            f"Hava Hizi: {result.port_velocity_ms} m/s",
        ]),
        ("DRIVER", [
            f'Cap: {panels.diameter_inch}"',
            f"Kesim: {panels.sub_cutout_mm:.0f} mm",
            f"Xpeak: {result.cone_excursion_mm} mm",
        ]),
    ]

    col_w = (w - 20) / len(cols)
    for i, (title, lines) in enumerate(cols):
        cx = x + 10 + i * col_w
        dwg.add(dwg.text(title, insert=(cx, y + 12),
                          fill=ACCENT, font_size="10px",
                          font_family="Consolas", font_weight="bold"))
        for j, line in enumerate(lines):
            dwg.add(dwg.text(line, insert=(cx, y + 26 + j * 14),
                              fill=DIM_COLOR, font_size="9px",
                              font_family="Consolas"))


# ═══════════════════════════════════════════════════════════════════════════════
# YARDIMCI FONKSİYONLAR
# ═══════════════════════════════════════════════════════════════════════════════

def _view_title(dwg, x, y, text):
    """Görünüm başlığı"""
    dwg.add(dwg.text(text, insert=(x, y),
                      fill=TITLE_CLR, font_size="11px",
                      font_family="Consolas, monospace", font_weight="bold",
                      text_anchor="middle"))


def _label(dwg, x, y, text, color, size=9, anchor="start"):
    """Etiket metni"""
    dwg.add(dwg.text(text, insert=(x, y),
                      fill=color, font_size=f"{size}px",
                      font_family="Consolas, monospace", text_anchor=anchor))


def _hatch_rect(dwg, x, y, w, h, direction="horizontal", color=HATCH_CLR):
    """Malzeme kesit hatching (45° çizgiler)"""
    g = dwg.g()
    step = 5
    if direction == "horizontal":
        for i in range(-int(h), int(w + h), step):
            lx1 = x + max(0, i)
            ly1 = y + max(0, -i)
            lx2 = x + min(w, i + h)
            ly2 = y + min(h, h - i)
            if lx1 < x + w and ly1 < y + h:
                g.add(dwg.line((lx1, ly1), (lx2, ly2),
                                stroke=color, stroke_width=0.5, stroke_opacity=0.5))
    else:  # vertical
        for i in range(-int(w), int(w + h), step):
            lx1 = x + max(0, i)
            ly1 = y + max(0, -i)
            lx2 = x + min(w, i + h)
            ly2 = y + min(h, h - i)
            if lx1 < x + w and ly1 < y + h:
                g.add(dwg.line((lx1, ly1), (lx2, ly2),
                                stroke=color, stroke_width=0.5, stroke_opacity=0.5))
    dwg.add(g)


def _dim_horizontal(dwg, x1, x2, y, text):
    """Yatay ölçü çizgisi (ok uçlu, extension lines)"""
    # Extension lines
    dwg.add(dwg.line((x1, y - DIM_OFFSET + 5), (x1, y + 5),
                      stroke=DIM_COLOR, stroke_width=0.4))
    dwg.add(dwg.line((x2, y - DIM_OFFSET + 5), (x2, y + 5),
                      stroke=DIM_COLOR, stroke_width=0.4))
    # Dimension line (ok uçlu)
    line = dwg.line((x1 + 1, y), (x2 - 1, y),
                     stroke=DIM_COLOR, stroke_width=0.6)
    line["marker-start"] = "url(#arrow_rev)"
    line["marker-end"] = "url(#arrow)"
    dwg.add(line)
    # Ölçü metni
    mid_x = (x1 + x2) / 2
    dwg.add(dwg.text(text, insert=(mid_x, y - 3),
                      fill=LABEL_CLR, font_size=f"{DIM_FONT}px",
                      font_family="Consolas", text_anchor="middle",
                      font_weight="bold"))


def _dim_vertical(dwg, x, y1, y2, text, small=False):
    """Dikey ölçü çizgisi (ok uçlu)"""
    fs = DIM_FONT - 2 if small else DIM_FONT
    clr = DIM_COLOR if small else LABEL_CLR
    sw = 0.4 if small else 0.6

    # Extension lines
    dwg.add(dwg.line((x - 5, y1), (x + DIM_OFFSET - 5, y1),
                      stroke=DIM_COLOR, stroke_width=0.4))
    dwg.add(dwg.line((x - 5, y2), (x + DIM_OFFSET - 5, y2),
                      stroke=DIM_COLOR, stroke_width=0.4))
    # Dimension line
    line = dwg.line((x, y1 + 1), (x, y2 - 1),
                     stroke=DIM_COLOR, stroke_width=sw)
    line["marker-start"] = "url(#arrow_rev)"
    line["marker-end"] = "url(#arrow)"
    dwg.add(line)
    # Ölçü metni
    mid_y = (y1 + y2) / 2
    dwg.add(dwg.text(text, insert=(x - 3, mid_y),
                      fill=clr, font_size=f"{fs}px",
                      font_family="Consolas", text_anchor="end",
                      transform=f"rotate(-90,{x - 3},{mid_y})"))


def _dim_inside_h(dwg, x, y1, y2, text, size=8):
    """İç ölçü — dikey (ok uçsuz, küçük)"""
    dwg.add(dwg.line((x, y1), (x, y2), stroke=DIM_COLOR, stroke_width=0.4))
    dwg.add(dwg.line((x-2, y1), (x+2, y1), stroke=DIM_COLOR, stroke_width=0.4))
    dwg.add(dwg.line((x-2, y2), (x+2, y2), stroke=DIM_COLOR, stroke_width=0.4))
    mid = (y1 + y2) / 2
    dwg.add(dwg.text(text, insert=(x + 4, mid + 3),
                      fill=DIM_COLOR, font_size=f"{size}px", font_family="Consolas"))


def _dim_inside_w(dwg, x1, x2, y, text, size=8, arrows=True):
    """İç ölçü — yatay (ok uçlu seçenekli)"""
    line = dwg.line((x1, y), (x2, y), stroke=DIM_COLOR, stroke_width=0.4)
    if arrows:
        line["marker-start"] = "url(#arrow_rev)"
        line["marker-end"] = "url(#arrow)"
    dwg.add(line)
    dwg.add(dwg.line((x1, y-2), (x1, y+2), stroke=DIM_COLOR, stroke_width=0.4))
    dwg.add(dwg.line((x2, y-2), (x2, y+2), stroke=DIM_COLOR, stroke_width=0.4))
    mid = (x1 + x2) / 2
    dwg.add(dwg.text(text, insert=(mid, y - 4),
                      fill=DIM_COLOR, font_size=f"{size}px",
                      font_family="Consolas", text_anchor="middle"))
