import os
import sys
from pathlib import Path

# Package context resolution: Add parent directory to path so 'dd1_lazer_agent' is discoverable
parent_dir = str(Path(__file__).resolve().parent.parent)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from dd1_lazer_agent.subwoofer_generator import generate_ported_sub_box

def generate_20cm_sub():
    print("DD1 Lazer Agent - V9 Kusursuz Portlu 20cm Subwoofer (42Hz Tuning Model)")
    
    # User Specifications
    w = 350          # Genişlik (Outer)
    h = 250          # Yükseklik (Outer) - Maksimum 250mm kuralı
    d = 300          # Derinlik (Outer)
    t = 10.0         # 10mm MDF / Plywood
    kerf = 0.15      # Lazer Kesim Hassasiyeti Toleransı
    
    # 20cm Bass (8 inch) genel Cutout çapı (yaklaşık 185mm)
    hole = 185.0
    
    # 42 Hz için tahmini L-Port veya Düz Port Değerleri
    port_w = 25.0    # 2.5cm port genişliği
    port_l = 150.0   # 15cm port duvarı derinliği
    
    # Setup output directory
    script_dir = os.path.dirname(os.path.abspath(__file__))
    out_dir = os.path.join(script_dir, "output", "dxf")
    os.makedirs(out_dir, exist_ok=True)
    
    output_dxf = os.path.join(out_dir, "sub_box_20cm_ported.dxf")
    
    try:
        success = generate_ported_sub_box(w, h, d, t, kerf, hole, port_w, port_l, output_dxf)
        if success:
             print(f"BÜYÜK BAŞARI! 10mm malzemeli V9 Kutu Hazır.")
             print(f"File Saved: {output_dxf}")
        else:
             print("HATA: Kutu üretilemedi.")
    except Exception as e:
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    generate_20cm_sub()
