"""
PDF Kabin Tasarım Raporu Üretici
reportlab ile profesyonel teknik rapor.
"""
import os
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.colors import HexColor
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image,
    PageBreak, HRFlowable
)
from reportlab.lib.enums import TA_LEFT, TA_CENTER
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

from engine.ts_calculator import CabinetResult
from engine.panel_calculator import PanelList


# ─── Renkler ──────────────────────────────────────────────────────────────────
BG_DARK   = HexColor("#0f1923")
BLUE      = HexColor("#2563eb")
PURPLE    = HexColor("#7c3aed")
WHITE     = HexColor("#ffffff")
GRAY      = HexColor("#94a3b8")
CYAN_LT   = HexColor("#7dd3fc")


def generate_pdf(
    result: CabinetResult,
    panels: PanelList,
    vehicle: str,
    purpose: str,
    diameter_inch: int,
    rms_power: float,
    mat_thickness_mm: float,
    usta_tavsiyesi: str,
    svg_path: str | None = None,
    output_path: str | None = None,
) -> str:
    """Kapsamlı PDF teknik rapor üret."""

    if not output_path:
        from config import OUTPUT_DIR
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = str(OUTPUT_DIR / f"DD1_Box_Report_{ts}.pdf")

    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        leftMargin=20*mm,
        rightMargin=20*mm,
        topMargin=15*mm,
        bottomMargin=15*mm,
    )

    # ── Font Kaydı (Türkçe Karakter Desteği) ───────────────────────────────────
    try:
        win_fonts = os.path.join(os.environ.get('WINDIR', 'C:\\Windows'), 'Fonts')
        arial_ttf = os.path.join(win_fonts, 'arial.ttf')
        arial_bd_ttf = os.path.join(win_fonts, 'arialbd.ttf')
        
        if os.path.exists(arial_ttf):
            pdfmetrics.registerFont(TTFont('Arial', arial_ttf))
            pdfmetrics.registerFont(TTFont('Arial-Bold', arial_bd_ttf))
            FONT_NAME = "Arial"
            FONT_BOLD = "Arial-Bold"
        else:
            FONT_NAME = "Helvetica"
            FONT_BOLD = "Helvetica-Bold"
    except:
        FONT_NAME = "Helvetica"
        FONT_BOLD = "Helvetica-Bold"

    styles = getSampleStyleSheet()

    # Özel stiller
    styles.add(ParagraphStyle(
        "Title_DD1", parent=styles["Title"],
        fontSize=22, textColor=BLUE, spaceAfter=4*mm, fontName=FONT_BOLD,
    ))
    styles.add(ParagraphStyle(
        "H2_DD1", parent=styles["Heading2"],
        fontSize=14, textColor=BLUE, spaceAfter=3*mm, fontName=FONT_BOLD,
    ))
    styles.add(ParagraphStyle(
        "Body_DD1", parent=styles["Normal"],
        fontSize=10, leading=14, spaceAfter=2*mm, fontName=FONT_NAME,
    ))
    styles.add(ParagraphStyle(
        "Small_DD1", parent=styles["Normal"],
        fontSize=8, textColor=GRAY, spaceAfter=1*mm, fontName=FONT_NAME,
    ))

    elements = []

    # ── Başlık ────────────────────────────────────────────────────────────────
    elements.append(Paragraph("DD1 BOX ENGINEERING REPORT", styles["Title_DD1"]))
    elements.append(Paragraph(
        f"Tarih: {datetime.now().strftime('%d.%m.%Y %H:%M')}  |  "
        f"Hesaplama Modu: {result.mode}",
        styles["Small_DD1"]
    ))
    elements.append(HRFlowable(width="100%", thickness=1, color=BLUE))
    elements.append(Spacer(1, 6*mm))

    # ── Bölüm 1: Giriş Parametreleri ─────────────────────────────────────────
    elements.append(Paragraph("1. GİRİŞ PARAMETRELERİ", styles["H2_DD1"]))
    input_data = [
        ["Parametre", "Değer"],
        ["Subwoofer Çapı", f'{diameter_inch}"'],
        ["RMS Güç", f"{rms_power:.0f} W"],
        ["Araç Tipi", vehicle],
        ["Kullanım Amacı", purpose],
        ["Malzeme Kalınlığı", f"{mat_thickness_mm:.1f} mm"],
    ]
    t1 = Table(input_data, colWidths=[60*mm, 80*mm])
    t1.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), BLUE),
        ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
        ("FONTNAME", (0, 0), (-1, 0), FONT_BOLD),
        ("FONTNAME", (0, 1), (-1, -1), FONT_NAME),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("GRID", (0, 0), (-1, -1), 0.5, GRAY),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [HexColor("#f8fafc"), WHITE]),
        ("ALIGN", (0, 0), (-1, -1), "LEFT"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    elements.append(t1)
    elements.append(Spacer(1, 6*mm))

    # ── Bölüm 2: Kabin Hesap Sonuçları ───────────────────────────────────────
    elements.append(Paragraph("2. KABİN HESAP SONUÇLARI", styles["H2_DD1"]))
    calc_data = [
        ["Parametre", "Değer"],
        ["Net Kabin Hacmi", f"{result.vb_litre} L"],
        ["Tuning Frekansı", f"{result.fb_hz} Hz"],
        ["Port Alanı", f"{result.port_area_cm2} cm²"],
        ["Port Uzunluğu", f"{result.port_length_cm} cm"],
        ["Slot Port Genişliği", f"{result.slot_width_cm} cm"],
        ["Slot Port Yüksekliği", f"{result.slot_height_cm} cm"],
    ]
    t2 = Table(calc_data, colWidths=[60*mm, 80*mm])
    t2.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), BLUE),
        ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
        ("FONTNAME", (0, 0), (-1, 0), FONT_BOLD),
        ("FONTNAME", (0, 1), (-1, -1), FONT_NAME),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("GRID", (0, 0), (-1, -1), 0.5, GRAY),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [HexColor("#f8fafc"), WHITE]),
        ("ALIGN", (0, 0), (-1, -1), "LEFT"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    elements.append(t2)
    elements.append(Spacer(1, 6*mm))

    # ── Bölüm 3: Panel Ölçüleri ──────────────────────────────────────────────
    elements.append(Paragraph("3. PANEL ÖLÇÜ LİSTESİ", styles["H2_DD1"]))
    panel_header = ["Panel", "Adet", "Genişlik (mm)", "Yükseklik (mm)", "Not"]
    panel_rows = [panel_header]
    for p in panels.panels:
        panel_rows.append([
            p["name"], str(p["qty"]),
            str(p["w"]), str(p["h"]),
            p.get("note", ""),
        ])
    # Port bölme
    pb = panels.port_brace
    panel_rows.append([pb["name"], str(pb["qty"]),
                       str(pb["w"]), str(pb["h"]), pb.get("note", "")])

    t3 = Table(panel_rows, colWidths=[35*mm, 12*mm, 28*mm, 28*mm, 55*mm])
    t3.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), BLUE),
        ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
        ("FONTNAME", (0, 0), (-1, 0), FONT_BOLD),
        ("FONTNAME", (0, 1), (-1, -1), FONT_NAME),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("GRID", (0, 0), (-1, -1), 0.5, GRAY),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [HexColor("#f8fafc"), WHITE]),
        ("ALIGN", (1, 0), (3, -1), "CENTER"),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    elements.append(t3)
    elements.append(Spacer(1, 4*mm))

    elements.append(Paragraph(
        f"<b>Dış Boyutlar:</b> {panels.outer_w_mm:.0f} × "
        f"{panels.outer_h_mm:.0f} × {panels.outer_d_mm:.0f} mm  |  "
        f"<b>Sürücü Kesim:</b> Ø{panels.sub_cutout_mm:.0f} mm",
        styles["Body_DD1"]
    ))
    elements.append(Spacer(1, 6*mm))

    # ── Bölüm 4: Akustik Analiz ──────────────────────────────────────────────
    elements.append(Paragraph("4. AKUSTİK ANALİZ", styles["H2_DD1"]))
    analysis_data = [
        ["Analiz", "Değer", "Not"],
        ["Cone Excursion", f"{result.cone_excursion_mm} mm",
         "Xmax sınırı kontrolü"],
        ["Port Hava Hızı", f"{result.port_velocity_ms} m/s",
         "< 17 m/s güvenli" if result.port_velocity_ms < 17 else "⚠ Yüksek!"],
        ["Tahmini Tepe SPL", f"{result.peak_spl_db} dB",
         "Cabin gain dahil"],
        ["Cabin Gain", f"+{result.cabin_gain_db} dB",
         vehicle],
    ]
    t4 = Table(analysis_data, colWidths=[40*mm, 35*mm, 65*mm])
    t4.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), BLUE),
        ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
        ("FONTNAME", (0, 0), (-1, 0), FONT_BOLD),
        ("FONTNAME", (0, 1), (-1, -1), FONT_NAME),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("GRID", (0, 0), (-1, -1), 0.5, GRAY),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [HexColor("#f8fafc"), WHITE]),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    elements.append(t4)
    elements.append(Spacer(1, 4*mm))

    # Notlar
    if result.notes:
        for note in result.notes:
            elements.append(Paragraph(note, styles["Body_DD1"]))
    elements.append(Spacer(1, 6*mm))

    # ── Bölüm 5: SVG Çizim (varsa) ──────────────────────────────────────────
    if svg_path and os.path.exists(svg_path):
        elements.append(PageBreak())
        elements.append(Paragraph("5. TEKNİK ÇİZİM", styles["H2_DD1"]))
        elements.append(Paragraph(
            f"SVG çizim dosyası: {os.path.basename(svg_path)}",
            styles["Small_DD1"]
        ))

    # ── Bölüm 6: DD1 Akustik Tavsiyesi ──────────────────────────────────────
    elements.append(Spacer(1, 4*mm))
    elements.append(Paragraph("6. DD1 AKUSTİK TAVSİYESİ", styles["H2_DD1"]))
    if result.acoustic_advice:
        elements.append(Paragraph(result.acoustic_advice, styles["Body_DD1"]))
        elements.append(Spacer(1, 2*mm))
    
    if result.expert_comment:
        elements.append(Paragraph(f"<i>{result.expert_comment}</i>", styles["Body_DD1"]))
        elements.append(Spacer(1, 4*mm))

    # ── Bölüm 7: Usta Tavsiyesi ─────────────────────────────────────────────
    elements.append(Paragraph("7. USTA TAVSİYESİ (Kurulum İpuçları)", styles["H2_DD1"]))
    for paragraph in usta_tavsiyesi.split("\n\n"):
        clean = paragraph.strip().replace("─", "")
        if clean:
            elements.append(Paragraph(clean, styles["Body_DD1"]))
            elements.append(Spacer(1, 2*mm))

    # ── Footer ────────────────────────────────────────────────────────────────
    elements.append(Spacer(1, 10*mm))
    elements.append(HRFlowable(width="100%", thickness=0.5, color=GRAY))
    elements.append(Paragraph(
        "DD1 Box Engineering Agent — Bu rapor mühendislik hesaplarına dayalı olarak "
        "otomatik üretilmiştir. Nihai tasarım sorumluluğu kullanıcıya aittir.",
        styles["Small_DD1"]
    ))

    doc.build(elements)
    return output_path
