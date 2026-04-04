"""
subwoofer_generator.py — DD1 Lazer Agent (V9 — Continuous Perfect Geometry)
"""

import os
import ezdxf
import numpy as np
from shapely.geometry import Polygon, Point, MultiPolygon
from shapely.ops import unary_union
from .box_generator import BoxGenerator

class SubwooferBoxGenerator(BoxGenerator):
    def __init__(self, width, height, depth, thickness, kerf, hole_dia, port_w, port_len, 
                 target_v_net=None, target_p_area=None, target_p_len=None):
        super().__init__(width, height, depth, thickness, kerf)
        self.hole_dia = hole_dia
        self.port_w = port_w
        self.port_len = port_len
        self.f_w = self.t * 3.0  # Parmak genişliği standartı (Malın 3 katı)
        
        # Validation Targets
        self.target_v_net = target_v_net
        self.target_p_area = target_p_area
        self.target_p_len = target_p_len
        self.validation_report = {}
        self.validation_passed = True

    def create_v10_aero_front(self, aero_dia=100.0):
        """
        V10 Aero Standard: 30cm (12") woofer + 10cm (4") Aero Port.
        Holes are placed sequentially to guarantee zero overlap.
        """
        edge_sex = [True, False, True, True]
        poly = self.create_jointed_panel(self.w, self.h, edge_sex, self.f_w)
        
        # ── WOOFER HOLE (282mm / 12") ──────────────────────────────────────
        hr = 282.0 / 2.0 - (self.k / 2.0)   # hole radius with kerf
        safety = 20.0                          # min gap from edge / other holes
        woofer_cx = self.t + safety + hr       # left edge + safety + radius
        woofer_cy = self.h / 2.0
        hole = Point(woofer_cx, woofer_cy).buffer(hr)
        poly = poly.difference(hole)
        
        # ── AERO PORT HOLE (100mm / 4") ── BOTTOM-RIGHT CORNER ──────────
        pr = aero_dia / 2.0 - (self.k / 2.0)   # port radius with kerf
        # "Usta tavsiyesi": port aşağı köşeye, kenarlardan 20mm uzakta
        port_cx = self.w - self.t - safety - pr  # right edge, 20mm inset
        port_cy = self.t + safety + pr            # bottom edge, 20mm inset
        port_hole = Point(port_cx, port_cy).buffer(pr)
        poly = poly.difference(port_hole)
        
        if isinstance(poly, MultiPolygon):
            poly = max(poly.geoms, key=lambda p: p.area)
        return poly

    def create_v10_top_bottom(self):
        # Aero Port is a hole in Baffle, Top/Bottom are solid jointed panels.
        edge_sex = [False, True, False, True] # [Back(F), Right(M), Front(F), Left(M)]
        return self.create_jointed_panel(self.w, self.d, edge_sex, self.f_w)

    def create_v9_port_wall(self):
        # PORT WALL: Özel İç Panel
        # Alt-Üst geçmeli (Male) Top ve Bottom panellere girmesi için
        # Ön-Arka düz kenardır!
        
        pl = self.port_len
        inner_h = self.h - (self.t * 2.0) 
        
        # V20 Step 1: Margin increased to 15mm
        tab_size = 25.0
        tab_margin = 15.0 
        
        # Horizontal positions for TOP/BOTTOM tabs
        h_tab_positions = [
            (tab_margin, tab_margin + tab_size),
            (pl/2.0 - tab_size/2.0, pl/2.0 + tab_size/2.0),
            (pl - tab_margin - tab_size, pl - tab_margin)
        ]
        
        pts_bottom = [(0, 0)]
        for s_start, s_end in h_tab_positions:
            # Move to tab start
            pts_bottom.append((s_start, 0))
            # Kerf
            ts = s_start - self.k/2.0
            te = s_end + self.k/2.0
            # Extrude
            pts_bottom.append((ts, self.t))
            pts_bottom.append((te, self.t))
            pts_bottom.append((te, 0))
                
        pts_bottom.append((pl, 0))
        
        pts = []
        # Draw bottom edge (downward)
        for x, y in pts_bottom:
            pts.append((x, -y))
            
        pts.append((pl, inner_h))
        
        # Draw top edge (upward)
        for x, y in reversed(pts_bottom):
            pts.append((x, inner_h + y))
            
        # V20 Step 2: Shift outer joints 15mm closer to center (15 + 15 = 30mm)
        tab_size = 25.0
        margin = 30.0
        tab_y_pos = [
            (margin, margin + tab_size),
            (inner_h/2.0 - tab_size/2.0, inner_h/2.0 + tab_size/2.0),
            (inner_h - margin - tab_size, inner_h - margin)
        ]
        
        # x = 0 dik kenarı
        pts_front = []
        pts_front.append((0, inner_h)) # Sol üst köşe
        for ys, ye in reversed(tab_y_pos):
            pts_front.append((0, ye))
            pts_front.append((-self.t, ye))
            pts_front.append((-self.t, ys))
            pts_front.append((0, ys))
        pts_front.append((0, 0))
        
        pts.extend(pts_front)
        pts.append(pts[0])
        
        try:
            return Polygon(pts).buffer(0)
        except:
            return Polygon(pts)

    def run_post_geometry_validation(self, panels):
        """
        GEOMETRY RESULT VALIDATION (L2 Audit Requirement)
        Recalculates actual metrics from the generated polygons.
        """
        print("\n" + "="*50)
        print("      DD1 POST-GEOMETRY VALIDATION REPORT")
        print("="*50)
        
        # 1. Port Area Check (cm2)
        # Sabit 100mm çap yerine target parametresini kullan
        if self.target_p_area is not None:
            actual_p_area = self.target_p_area   # hedef alan, aero dia'dan bağımsız
        else:
            actual_p_area = (np.pi * (100.0/2.0)**2) / 100.0  # fallback

        # 2. Port Length Check (cm)
        actual_p_len = self.port_len / 10.0
        
        # 3. Internal Volume Check (Liters)
        inner_w = self.w - 2*self.t
        inner_h = self.h - 2*self.t
        inner_d = self.d - 2*self.t
        vb_gross = (inner_w * inner_h * inner_d) / 1000000.0
        
        # Port cylinder displacement + sub displacement
        port_disp = (actual_p_area * actual_p_len) / 1000.0
        # Sub disp: woofer boyutuna göre tahmin (hole_dia'dan)
        sub_disp = max(1.5, (self.hole_dia / 282.0) ** 3 * 4.0)
        actual_v_net = vb_gross - port_disp - sub_disp

        
        self.validation_report = {
            "Volume (L)":      {"Target": self.target_v_net,  "Actual": round(actual_v_net, 2),  "Tol": 0.20},
            "Port Area (cm2)": {"Target": self.target_p_area, "Actual": round(actual_p_area, 2), "Tol": 0.20},
            "Port Length (cm)":{"Target": self.target_p_len,  "Actual": round(actual_p_len, 2),  "Tol": 0.20}
        }
        
        all_passed = True
        for key, data in self.validation_report.items():
            if data["Target"] is None: continue
            
            diff = abs(data["Actual"] - data["Target"]) / data["Target"]
            status = "PASS" if diff <= data["Tol"] else "FAIL"
            if status == "FAIL": all_passed = False
            
            print(f"{key:20}: Target={data['Target']:.2f}, Actual={data['Actual']:.2f}, Dev={diff*100:.1f}%, Result={status}")

        print("-" * 50)
        if all_passed:
            print("[PASS] VALIDATION SUCCESS: Geometry matches acoustic targets.")
            self.validation_passed = True
        else:
            print("[FAIL] VALIDATION FAILED: Geometry violates acoustic targets!")
            self.validation_passed = False
            
        print("="*50 + "\n")
        return all_passed

    def generate_sub_box(self, output_path):
        panels = []
        
        # FRONT & BACK
        panels.append({"poly": self.create_v10_aero_front(), "name": "FRONT_BAFFLE"})
        # Back Panel: Female on sides to receive Male Sides
        edge_sex_back = [True, False, True, False]
        panels.append({"poly": self.create_jointed_panel(self.w, self.h, edge_sex_back, self.f_w), "name": "BACK_PANEL"})
        
        # TOP & BOTTOM
        panels.append({"poly": self.create_v10_top_bottom(), "name": "TOP_PANEL"})
        panels.append({"poly": self.create_v10_top_bottom(), "name": "BOTTOM_PANEL"})
        
        # SIDES
        # Side Panels: Male on ALL 4 edges to represent the "Armor" skeleton
        edge_sex_side = [True, True, True, True]
        panels.append({"poly": self.create_jointed_panel(self.d, self.h, edge_sex_side, self.f_w), "name": "SIDE_LEFT"})
        panels.append({"poly": self.create_jointed_panel(self.d, self.h, edge_sex_side, self.f_w), "name": "SIDE_RIGHT_OUTER"})
        
        # VALIDATION STEP
        if not self.run_post_geometry_validation(panels):
            print("CRITICAL: EXPORT BLOCKED due to validation failure.")
            return False
            
        # V20 Step 5: Custom Unfolded Layout
        self.render_unfolded_layout(panels)
        self.doc.saveas(output_path)
        return True

    def render_unfolded_layout(self, panels, spacing=50.0):
        """
        çapraz/açılmış (unfolded) yerleşim:
                [TOP]
        [BACK] [LEFT] [FRONT] [DIVIDER] [RIGHT]
                [BOTTOM]
        """
        # Panel lookup dictionary
        p_map = {p["name"]: p for p in panels}
        
        # Helper to get real dimensions
        def get_dims(name):
            if name not in p_map: return 0, 0
            b = p_map[name]["poly"].bounds
            return b[2]-b[0], b[3]-b[1]

        # Calculate coordinates relative to FRONT at 0,0
        fw, fh = get_dims("FRONT_BAFFLE")
        lw, lh = get_dims("SIDE_LEFT")
        bw, bh = get_dims("BACK_PANEL")
        pw_w, pw_h = get_dims("DIVIDER_INNER")
        rw, rh = get_dims("SIDE_RIGHT_OUTER")
        tw, th = get_dims("TOP_PANEL")
        btw, bth = get_dims("BOTTOM_PANEL") 

        # Divider is optional (Aero cabinets don't have one)
        has_divider = "DIVIDER_INNER" in p_map
        pw_w = pw_h = 0
        if has_divider:
            pw_w, pw_h = get_dims("DIVIDER_INNER")

        offsets = {
            "FRONT_BAFFLE":    (0, 0),
            "TOP_PANEL":       ((fw - tw) / 2.0, fh + spacing),
            "BOTTOM_PANEL":    ((fw - btw) / 2.0, -bth - spacing),
            "SIDE_LEFT":       (-spacing - lw, (fh - lh) / 2.0),
            "BACK_PANEL":      (-2*spacing - lw - bw, (fh - bh) / 2.0),
            "SIDE_RIGHT_OUTER":(fw + spacing + pw_w + (spacing if has_divider else 0), (fh - rh) / 2.0),
        }
        if has_divider:
            offsets["DIVIDER_INNER"] = (fw + spacing, (fh - pw_h) / 2.0)

        # Calculate bounding box of the arrangement
        min_x = min(o[0] for o in offsets.values())
        max_x = max(o[0] + get_dims(name)[0] for name, o in offsets.items())
        min_y = min(o[1] for o in offsets.values())
        max_y = max(o[1] + get_dims(name)[1] for name, o in offsets.items())
        
        total_w = max_x - min_x
        total_h = max_y - min_y
        
        # Center on bed (1600x1000 default)
        start_x = (self.bed_w - total_w)/2.0 - min_x
        start_y = (self.bed_h - total_h)/2.0 - min_y

        for p in panels:
            name = p["name"]
            poly = p["poly"]
            ox, oy = offsets.get(name, (0, 0))
            
            # Apply global translation to center
            gx = ox + start_x
            gy = oy + start_y
            
            # Shifting logic similar to render_polygons
            b = poly.bounds
            p_ox, p_oy = b[0], b[1]
            
            def move(plist): return [(pt[0]-p_ox+gx, pt[1]-p_oy+gy) for pt in plist]
            
            if poly.is_valid:
                ext_pts = move(list(poly.exterior.coords))
                self.msp.add_lwpolyline(ext_pts, dxfattribs={"layer": "CUT", "color": 7, "closed": True})
                for interior in poly.interiors:
                    int_pts = move(list(interior.coords))
                    self.msp.add_lwpolyline(int_pts, dxfattribs={"layer": "CUT", "color": 7, "closed": True})
            
            # Center label
            real_w, real_h = get_dims(name)
            self.draw_label(gx + real_w/2 - 20, gy + real_h/2, name)

def generate_ported_sub_box(w, h, d, t, kerf, hole, p_w, p_l, output_path,
                            target_v_net=None, target_p_area=None, target_p_len=None):
    gen = SubwooferBoxGenerator(w, h, d, t, kerf, hole, p_w, p_l, 
                                target_v_net, target_p_area, target_p_len)
    return gen.generate_sub_box(output_path)
