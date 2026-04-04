"""
nesting_module.py — DD1 Lazer Agent
Otomatik parça yerleştirme (nesting) motoru.
"""

import os
import numpy as np
import ezdxf
from shapely.geometry import LineString, MultiLineString, GeometryCollection
from shapely.ops import linemerge

def perform_grid_nesting(
    paths_with_attrs, 
    table_w=1600, 
    table_h=1000, 
    margin=20, 
    spacing=5,
    output_path="nested_sheet_test.dxf"
):
    """
    Verilen yolları (parçayı) belirtilen tabla ölçülerine grid şeklinde yerleştirir.
    paths_with_attrs: [(path, attr), ...] svgpathtools formatında
    """
    
    # 1. Parçanın Bounding Box'ını ve mm ölçekli koordinatlarını çıkar
    PX_TO_MM = 0.264583
    
    all_segments = []
    for path, attr in paths_with_attrs:
        is_kazima = "red" in attr.get("stroke", "").lower() or "red" in attr.get("fill", "").lower()
        
        for segment in path:
            num_samples = max(2, int(segment.length() / 1))
            pts = []
            for t in np.linspace(0, 1, num_samples):
                p = segment.point(t)
                pts.append((p.real * PX_TO_MM, -p.imag * PX_TO_MM))
            
            if len(pts) >= 2:
                all_segments.append({
                    "line": LineString(pts),
                    "is_kazima": is_kazima
                })

    if not all_segments:
        return "HATA: Yerleştirilecek parça bulunamadı."

    # Parçanın sınırlarını bul
    all_geoms = [s["line"] for s in all_segments]
    bounds = GeometryCollection(all_geoms).bounds # (minx, miny, maxx, maxy)
    p_min_x, p_min_y, p_max_x, p_max_y = bounds
    p_w = p_max_x - p_min_x
    p_h = p_max_y - p_min_y

    # 2. Yerleşim Hesaplama
    usable_w = table_w - (2 * margin)
    usable_h = table_h - (2 * margin)
    
    col_width = p_w + spacing
    row_height = p_h + spacing
    
    cols = int(usable_w / col_width) if col_width > 0 else 0
    rows = int(usable_h / row_height) if row_height > 0 else 0
    
    if cols == 0 or rows == 0:
        return f"HATA: Parça ölçüsü ({p_w:.1f}x{p_h:.1f}) tabla ölçüsünden büyük."

    # 3. DXF Hazırlama
    doc = ezdxf.new("R2000")
    doc.units = ezdxf.units.MM
    doc.header['$INSUNITS'] = 4
    msp = doc.modelspace()
    
    doc.layers.new("CUT", dxfattribs={"color": 7})
    doc.layers.new("ENGRAVE", dxfattribs={"color": 1})

    count = 0
    for r in range(rows):
        for c in range(cols):
            # Her kopya için offset hesapla
            offset_x = margin + (c * col_width) - p_min_x
            offset_y = margin + (r * row_height) - p_min_y
            
            for seg in all_segments:
                layer = "ENGRAVE" if seg["is_kazima"] else "CUT"
                color = 1 if seg["is_kazima"] else 7
                
                # Koordinatları kaydır
                orig_pts = list(seg["line"].coords)
                new_pts = [(p[0] + offset_x, p[1] + offset_y) for p in orig_pts]
                
                # Douglas-Peucker (0.01mm)
                ls = LineString(new_pts).simplify(0.01, preserve_topology=True)
                
                # Kapanma kontrolü
                pts = list(ls.coords)
                is_closed = False
                if len(pts) > 2:
                    d = np.linalg.norm(np.array(pts[0]) - np.array(pts[-1]))
                    if d < 0.5: is_closed = True

                msp.add_lwpolyline(
                    pts,
                    dxfattribs={
                        "layer": layer,
                        "color": color,
                        "const_width": 0,
                        "closed": is_closed
                    }
                )
            count += 1

    # Tabla sınırlarını DRAWING layer'ına ekle (isteğe bağlı, referans için)
    doc.layers.new("TABLE_BOUNDS", dxfattribs={"color": 8})
    msp.add_lwpolyline(
        [(0,0), (table_w, 0), (table_w, table_h), (0, table_h), (0,0)],
        dxfattribs={"layer": "TABLE_BOUNDS"}
    )

    doc.saveas(output_path)
    return f"BAŞARILI: {count} parça yerleştirildi -> {output_path}"
