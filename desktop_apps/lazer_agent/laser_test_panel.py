import ezdxf
import os

def generate_test_panel():
    # DXF Setup (R14 format for maximum laser compatibility)
    try:
        doc = ezdxf.new("R14")
    except:
        doc = ezdxf.new("R2000")
        
    doc.header['$INSUNITS'] = 4  # Millimeters
    msp = doc.modelspace()
    
    # Create Requested Layers
    doc.layers.new("CUT", dxfattribs={"color": 7})    # White/Black
    doc.layers.new("ENGRAVE", dxfattribs={"color": 1}) # Red 
    doc.layers.new("MARK", dxfattribs={"color": 3})    # Green
    
    # 1. Outer Square (400x400mm) -> CUT Layer
    # Enforce closed path with LWPOLYLINE
    square_points = [(0, 0), (400, 0), (400, 400), (0, 400), (0, 0)]
    msp.add_lwpolyline(square_points, dxfattribs={"layer": "CUT", "color": 7, "closed": True})
    
    # 2. Inner Circle (200mm diameter) -> ENGRAVE Layer
    # Center is at (200, 200), Radius = 100mm
    msp.add_circle((200, 200), radius=100, dxfattribs={"layer": "ENGRAVE", "color": 1})
    
    # 3. Four Alignment Holes (10mm diameter) -> MARK Layer
    # Near corners, 20mm offset from edges. Radius = 5mm.
    corner_offset = 20
    hole_radius = 5
    hole_centers = [
        (corner_offset, corner_offset),                 # Bottom-Left
        (400 - corner_offset, corner_offset),           # Bottom-Right
        (400 - corner_offset, 400 - corner_offset),     # Top-Right
        (corner_offset, 400 - corner_offset)            # Top-Left
    ]
    
    for cx, cy in hole_centers:
        msp.add_circle((cx, cy), radius=hole_radius, dxfattribs={"layer": "MARK", "color": 3})
    
    # Setup the save path to be strictly inside the script's directory (dd1_lazer_agent/output/dxf/)
    script_dir = os.path.dirname(os.path.abspath(__file__))
    out_dir = os.path.join(script_dir, "output", "dxf")
    os.makedirs(out_dir, exist_ok=True)
    output_path = os.path.join(out_dir, "laser_test_panel.dxf")
    
    # Export the file
    doc.saveas(output_path)
    print(f"SUCCESS: DXF file created geometrically safe and closed.")
    print(f"File Saved: {output_path}")

if __name__ == "__main__":
    generate_test_panel()
