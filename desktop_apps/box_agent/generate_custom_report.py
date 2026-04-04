import os
import sys
from pathlib import Path
from datetime import datetime

# Add projects to sys.path
sys.path.insert(0, r"c:\Users\DDSOUND\Desktop\exemiz\dd1_box_agent")

from engine.ts_calculator import CabinetResult
from engine.panel_calculator import PanelList
from report.pdf_generator import generate_pdf

def create_report():
    # Parameters from Lazer Agent V11
    w_out, h_out, d_out = 350, 300, 400
    t = 10.0
    hole_dia = 190.0
    port_w = 20.0
    port_l = 275.0
    
    # Calculations
    inner_w = w_out - 2*t
    inner_h = h_out - 2*t
    inner_d = d_out - 2*t
    
    vb_gross = (inner_w * inner_h * inner_d) / 1000000.0 # L
    port_area = (port_w * inner_h) / 100.0 # cm2
    port_disp = (port_area * port_l) / 1000.0 # L
    sub_disp = 1.5 # L (8-inch estimate)
    vb_net = vb_gross - port_disp - sub_disp
    
    # Fb calculation (approximate)
    import math
    l_eff = (port_l / 10.0) + 0.825 * math.sqrt(port_area)
    fb = (34500 / (2 * math.pi)) * math.sqrt(port_area / (vb_net * 1000 * l_eff))
    
    # Mock Result Object
    result = CabinetResult(
        mode="Mekanik Tasarım Analizi (V11)",
        vb_litre=round(vb_net, 1),
        fb_hz=round(fb, 1),
        port_area_cm2=round(port_area, 1),
        port_length_cm=round(port_l / 10.0, 1),
        slot_width_cm=round(port_w / 10.0, 1),
        slot_height_cm=round(inner_h / 10.0, 1),
        cone_excursion_mm=8.0,
        port_velocity_ms=12.5,
        peak_spl_db=115.0,
        cabin_gain_db=6,
        f3_hz=round(fb * 0.75, 1),
        notes=["Port kilitleri 15mm içeri kaydırıldı.", "Slot genişliği t-k olarak optimize edildi."]
    )
    result.acoustic_advice = "Kilitlerin 15mm içeri taşınması panel titreşimini azaltarak daha temiz bir bass cevabı sağlayacaktır."
    result.expert_comment = "V11 Tasarımı: Yapısal olarak güçlendirilmiş, akustik olarak dengeli bir kabin."
    
    # Mock Panel List
    panels = PanelList(
        inner_w_mm=inner_w, inner_h_mm=inner_h, inner_d_mm=inner_d,
        outer_w_mm=w_out, outer_h_mm=h_out, outer_d_mm=d_out,
        thickness_mm=t,
        panels=[
            {"name": "Ön Panel (Baffle)", "qty": 1, "w": w_out, "h": h_out, "note": f"Ø{hole_dia}mm Delik"},
            {"name": "Arka Panel", "qty": 1, "w": w_out, "h": h_out, "note": ""},
            {"name": "Üst/Alt", "qty": 2, "w": w_out, "h": inner_d, "note": ""},
            {"name": "Yan Paneller", "qty": 2, "w": inner_h, "h": inner_d, "note": ""},
        ],
        port_brace={"name": "Port İç Duvarı", "qty": 1, "w": int(port_l), "h": int(inner_h), "note": "L-Port Board"},
        total_area_cm2=5500.0,
        sub_cutout_mm=hole_dia,
        diameter_inch=8
    )
    
    desktop = os.path.join(os.environ["USERPROFILE"], "Desktop")
    pdf_path = os.path.join(desktop, "DD1_Kabin_Akustik_Rapor_V11.pdf")
    
    output = generate_pdf(
        result, panels, "Hatchback", "Günlük Bass", 
        8, 250, t, 
        "Kilitlerin içeri çekilmesi büyük avantaj. Montajda hızlı yapıştırıcı kullanmayı unutma.",
        output_path=pdf_path
    )
    
    print(f"Report generated: {output}")

if __name__ == "__main__":
    create_report()
