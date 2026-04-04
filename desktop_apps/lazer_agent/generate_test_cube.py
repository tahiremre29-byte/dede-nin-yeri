import os
import sys
from pathlib import Path
from shapely.geometry import Point

# Package context resolution: Add parent directory to path so 'dd1_lazer_agent' is discoverable
parent_dir = str(Path(__file__).resolve().parent.parent)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from dd1_lazer_agent.box_generator import BoxGenerator

def generate_test_cube():
    print("DD1 Lazer Agent - Test Cube Generator (200x200x200mm, 6mm MDF)")
    
    # User parameters
    w, h, d = 200, 200, 200
    t = 6
    hole_dia = 165
    kerf = 0.15
    f_w = t * 3.0  # 18mm finger width for 6mm material looks good
    
    # Initialize main generator framework
    gen = BoxGenerator(w, h, d, t, kerf)
    
    # 1. Front (Male on all sides - M, M, M, M)
    front = gen.create_jointed_panel(w, h, [True, True, True, True], f_w)
    # Add hole (Center is w/2, h/2)
    # Note: Lazer kesim payi delik icin kerf/2 kadar KUCULTULMELIDIR, fakat 
    # create_panel_geometry gibi genel kullanimda ham capi buffer ile isleyebiliriz.
    # Hassas kesim olmasi icin woofer gibi radius'tan kerf/2 cikarilarak buyuk/kucuk ayarlanir:
    hr = (hole_dia / 2.0) - (kerf / 2.0)
    hole = Point(w / 2.0, h / 2.0).buffer(hr)
    front = front.difference(hole)
    
    # 2. Back (Male on all sides - M, M, M, M)
    back = gen.create_jointed_panel(w, h, [True, True, True, True], f_w)
    
    # 3. Top & Bottom (Top/Bottom connects to F/B -> Female; Left/Right connects to Sides -> Male)
    # Format: [Top, Right, Bottom, Left] -> [F, M, F, M]
    top = gen.create_jointed_panel(w, d, [False, True, False, True], f_w)
    bottom = gen.create_jointed_panel(w, d, [False, True, False, True], f_w)
    
    # 4. Left & Right (Connects to all Male/Female combinations cleanly as all Female - F, F, F, F)
    left = gen.create_jointed_panel(d, h, [False, False, False, False], f_w)
    right = gen.create_jointed_panel(d, h, [False, False, False, False], f_w)
    
    panels = [
        {"poly": front, "name": "FRONT"},
        {"poly": back, "name": "BACK"},
        {"poly": top, "name": "TOP"},
        {"poly": bottom, "name": "BOTTOM"},
        {"poly": left, "name": "LEFT"},
        {"poly": right, "name": "RIGHT"}
    ]
    
    # DXF kayit noktasi output/dxf icinde olacak
    script_dir = os.path.dirname(os.path.abspath(__file__))
    out_dir = os.path.join(script_dir, "output", "dxf")
    os.makedirs(out_dir, exist_ok=True)
    output_path = os.path.join(out_dir, "test_cube_200.dxf")
    
    # Nested render
    gen.render_polygons(panels)
    gen.doc.saveas(output_path)
    
    print(f"SUCCESS: 200x200x200 Geçmeli Kutu başarıyla oluşturuldu!")
    print(f"File Saved: {output_path}")

if __name__ == "__main__":
    generate_test_cube()
