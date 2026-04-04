import os
import sys
from pathlib import Path

# Add project root to path
parent_dir = str(Path(__file__).resolve().parent.parent)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from dd1_lazer_agent.box_generator import BoxGenerator

def test_custom_joints():
    print("DD1 Lazer Agent - Custom Joint Test")
    
    # User parameters
    w = 400
    h = 400
    t = 18
    f_w = 40
    kerf = 0.15
    d = 400 # Just a placeholder for BoxGenerator init
    
    # Initialize main generator framework
    gen = BoxGenerator(w, h, d, t, kerf)
    
    # Top=Male, Right=Female, Bottom=None (Flat), Left=Male
    poly = gen.create_jointed_panel(w, h, [True, False, None, True], f_w)
    
    out_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output", "dxf")
    os.makedirs(out_dir, exist_ok=True)
    output_path = os.path.join(out_dir, "finger_joint_panel.dxf")
    
    # Render and export to DXF
    gen.render_polygons([{"poly": poly, "name": "JOINTED_PANEL"}])
    gen.doc.saveas(output_path)
    
    print(f"SUCCESS: Custom finger joint panel generated.")
    print(f"File Saved: {output_path}")

if __name__ == "__main__":
    test_custom_joints()
