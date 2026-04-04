import os
import sys
from pathlib import Path

# Package context resolution: Add parent directory to path so 'dd1_lazer_agent' is discoverable
parent_dir = str(Path(__file__).resolve().parent.parent)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from dd1_lazer_agent.subwoofer_generator import generate_ported_sub_box

def main():
    print("DD1 Lazer Agent - Generator Launcher")
    
    t = 10.0
    hole = 190.0
    kerf = 0.15
    w = 350
    h = 300
    d = 400
    port_w = 20.0
    port_l = 275.0
    
    # Setup output directory
    script_dir = os.path.dirname(os.path.abspath(__file__))
    out_dir = os.path.join(script_dir, "output", "dxf")
    os.makedirs(out_dir, exist_ok=True)
    output_dxf = os.path.join(out_dir, "sub_box_ported.dxf")
    
    success = generate_ported_sub_box(w, h, d, t, kerf, hole, port_w, port_l, output_dxf)
    
    if success:
         print(f"Success! Output generated at: {output_dxf}")
    else:
         print("Execution Failed.")

if __name__ == "__main__":
    main()
