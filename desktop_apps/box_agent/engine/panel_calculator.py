"""
Panel Ölçü Hesaplayıcı
Kabin iç hacminden, panel boyutlarını ve malzeme listesini üretir.
"""
import math
from dataclasses import dataclass
from engine.ts_calculator import CabinetResult


@dataclass
class PanelList:
    inner_w_mm: float   # İç genişlik
    inner_h_mm: float   # İç yükseklik
    inner_d_mm: float   # İç derinlik
    outer_w_mm: float
    outer_h_mm: float
    outer_d_mm: float
    thickness_mm: float
    panels: list[dict]  # her panel: {name, qty, w, h, note}
    port_brace: dict    # port bölme paneli
    total_area_cm2: float
    sub_cutout_mm: float  # sürücü kesim çapı
    diameter_inch: int


def calculate_panels(result: CabinetResult, diameter_inch: int,
                     mat_thickness_mm: float) -> PanelList:
    """
    Net kabin hacminden geriye dönük panel ölçülerini hesapla.
    Kabin oranı: en/boy/derinlik ≈ altın oran tabanlı (0.618, 1.0, 1.618)
    """
    t = mat_thickness_mm
    vb_cm3 = result.vb_litre * 1000
    # V_port Displacement = Sp * Lp
    v_port_cm3 = result.port_area_cm2 * result.port_length_cm
    # V_sub Displacement (estimations based on diameter)
    sub_disp_map = {8: 1500, 10: 2500, 12: 4000, 15: 7000, 18: 12000}
    v_sub_cm3 = sub_disp_map.get(diameter_inch, 4000)

    vb_gross_cm3 = vb_cm3 + v_port_cm3 + v_sub_cm3

    # İç boyutları Brüt hacme göre hesapla
    # V_gross = W × H × D   → oranlar: H=0.8, W=1.9, D=1.1 (geniş ve basık)
    ratio_w = 1.9
    ratio_h = 0.8
    ratio_d = 1.1

    # H³ × ratio_volume = vg_cm3
    h = (vb_gross_cm3 / (ratio_w * ratio_h * ratio_d)) ** (1/3)
    inner_w = h * ratio_w
    inner_h = h * ratio_h
    inner_d = h * ratio_d

    # mm'ye çevir
    inner_w_mm = inner_w * 10
    inner_h_mm = inner_h * 10
    inner_d_mm = inner_d * 10

    # Minimum yükseklik kontrolü (subwoofer sığmalı)
    sub_mm = diameter_inch * 25.4
    min_h_mm = sub_mm + 40  # sürücü çapı + 4cm pay
    if inner_h_mm < min_h_mm:
        old_h = inner_h_mm
        inner_h_mm = min_h_mm
        # Hacmi korumak için genişliği azalt
        inner_w_mm = (vb_cm3 * 1000) / (inner_h_mm * inner_d_mm)

    # Dış boyutlar (iki taraf)
    outer_w_mm = inner_w_mm + 2 * t
    outer_h_mm = inner_h_mm + 2 * t
    outer_d_mm = inner_d_mm + 2 * t

    # Sürücü kesim çapı (~%90 konektif çap)
    sub_cutout = sub_mm * 0.88

    panels = [
        {"name": "Ön Panel", "qty": 1,
         "w": round(outer_w_mm), "h": round(outer_h_mm),
         "note": f"Sürücü kesim: Ø{sub_cutout:.0f}mm merkez"},
        {"name": "Arka Panel", "qty": 1,
         "w": round(outer_w_mm), "h": round(outer_h_mm),
         "note": ""},
        {"name": "Üst Panel", "qty": 1,
         "w": round(outer_w_mm), "h": round(inner_d_mm),
         "note": ""},
        {"name": "Alt Panel", "qty": 1,
         "w": round(outer_w_mm), "h": round(inner_d_mm),
         "note": ""},
        {"name": "Sol Yan", "qty": 1,
         "w": round(inner_h_mm), "h": round(inner_d_mm),
         "note": ""},
        {"name": "Sağ Yan", "qty": 1,
         "w": round(inner_h_mm), "h": round(inner_d_mm),
         "note": ""},
    ]

    # ── Port Boyutlarını Yan Panele (Dikey) Sığdır ────────────────────────────
    # SPL Yan Port: Port yüksekliği = Kabin iç yüksekliği
    # Sp = slot_w * slot_h  => slot_w = Sp / inner_h
    slot_h_cm = inner_h_mm / 10
    slot_w_cm = result.port_area_cm2 / slot_h_cm
    
    # Bilgi tablosu (Info Table) ve etiketler için sonuçları güncelle
    result.slot_height_cm = round(slot_h_cm, 1)
    result.slot_width_cm = round(slot_w_cm, 1)
    
    # Port bölme paneli (iç l-panel genişliği)
    pw_mm = round(slot_w_cm * 10)
    ph_mm = round(inner_h_mm) # tam boy dikey
    
    # Sürücü kesim çapı (~%88 konektif çap)
    sub_cutout = sub_mm * 0.88

    panels = [
        {"name": "Ön Panel", "qty": 1,
         "w": round(outer_w_mm), "h": round(outer_h_mm),
         "note": f"Sürücü kesim: Ø{sub_cutout:.0f}mm | {inner_w_mm:.0f} + 2x{t:.0f}"},
        {"name": "Arka Panel", "qty": 1,
         "w": round(outer_w_mm), "h": round(outer_h_mm),
         "note": f"{inner_w_mm:.0f} + 2x{t:.0f}"},
        {"name": "Üst Panel", "qty": 1,
         "w": round(outer_w_mm), "h": round(inner_d_mm),
         "note": "Kabin tavanı"},
        {"name": "Alt Panel", "qty": 1,
         "w": round(outer_w_mm), "h": round(inner_d_mm),
         "note": "Kabin tabanı"},
        {"name": "Sol Yan", "qty": 1,
         "w": round(inner_h_mm), "h": round(inner_d_mm),
         "note": "İç yan panel"},
        {"name": "Sağ Yan", "qty": 1,
         "w": round(inner_h_mm), "h": round(inner_d_mm),
         "note": f"Port girişi olan yan panel"},
    ]

    port_brace = {"name": "İç Port Paneli", "qty": 1,
                  "w": pw_mm, "h": round(inner_d_mm),
                  "height_check": round(inner_h_mm),
                  "note": f"SPL Yan Port Genişliği: {pw_mm}mm"}

    total_area = sum(p["w"] * p["h"] * p["qty"] for p in panels) / 100  # cm²

    return PanelList(
        inner_w_mm=round(inner_w_mm, 1),
        inner_h_mm=round(inner_h_mm, 1),
        inner_d_mm=round(inner_d_mm, 1),
        outer_w_mm=round(outer_w_mm, 1),
        outer_h_mm=round(outer_h_mm, 1),
        outer_d_mm=round(outer_d_mm, 1),
        thickness_mm=t,
        panels=panels,
        port_brace=port_brace,
        total_area_cm2=round(total_area, 1),
        sub_cutout_mm=round(sub_cutout, 1),
        diameter_inch=diameter_inch,
    )


class PanelCalculator:
    """Fonksiyon tabanlı calculate_panels() için OOP wrapper."""

    def calculate(self, vb_litre: float, mat_thickness_mm: float,
                  slot_width_cm: float, slot_height_cm: float,
                  diameter_inch: int = 12) -> PanelList:
        """
        Basit çağrı: sadece temel parametrelerle panel hesabı yapar.
        Gerçek CabinetResult nesnesi olmadan çalışır.
        """
        from dataclasses import dataclass

        @dataclass
        class _FakeResult:
            vb_litre: float
            port_area_cm2: float
            port_length_cm: float
            slot_width_cm: float
            slot_height_cm: float

        fake = _FakeResult(
            vb_litre=vb_litre,
            port_area_cm2=slot_width_cm * slot_height_cm,
            port_length_cm=30.0,  # varsayılan
            slot_width_cm=slot_width_cm,
            slot_height_cm=slot_height_cm,
        )

        # PanelList alanlarına uygun property isimleri ekle
        result = calculate_panels(fake, diameter_inch, mat_thickness_mm)

        # Kısa isimli erişim için alias'lar ekle
        result.inner_w = result.inner_w_mm
        result.inner_h = result.inner_h_mm
        result.inner_d = result.inner_d_mm
        result.outer_w = result.outer_w_mm
        result.outer_h = result.outer_h_mm
        result.outer_d = result.outer_d_mm
        return result

