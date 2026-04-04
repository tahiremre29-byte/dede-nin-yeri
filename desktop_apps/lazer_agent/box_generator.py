"""
box_generator.py — DD1 Lazer Agent (V9 — Perimeter Walker Update)
Kusursuz Çevre Dolaşma (Continuous Path) Algoritması.
"""

import os
import ezdxf
import numpy as np
from shapely.geometry import Polygon, Point, MultiPolygon
from shapely.ops import unary_union
from .joint_generator import generate_finger_joint_edge

class BoxGenerator:
    def __init__(self, width, height, depth, thickness, kerf, bed_w=1600, bed_h=1000):
        self.w = width
        self.h = height
        self.d = depth
        self.t = thickness
        self.k = kerf
        self.bed_w = bed_w
        self.bed_h = bed_h
        
        self.f_base = thickness * 2.5
        self.f_limit = 10 
        self.f_min = thickness * 1.5
        self.dogbone_r = (thickness * 0.3) / 2.0
        
        self.slot_w = thickness + kerf
        self.tab_w = thickness - kerf
        
        try:
            self.doc = ezdxf.new("R2000")
        except:
            self.doc = ezdxf.new("AC1015") # R2000 fallback
            
        self.doc.header['$INSUNITS'] = 4 
        self.msp = self.doc.modelspace()
        self.doc.layers.new("CUT", dxfattribs={"color": 7})
        self.doc.layers.new("ENGRAVE", dxfattribs={"color": 1})

    def get_v8_fingers(self, length):
        n = int(length / self.f_base)
        if n % 2 == 0: n -= 1 
        if n > self.f_limit:
            n = self.f_limit - 1 if self.f_limit % 2 == 0 else self.f_limit
        if n < 1: n = 1
        return n, length / n

    def create_panel_geometry(self, pw, ph, edge_sex):
        """
        edge_sex: [top, right, bottom, left] (True=Male, False=Female)
        Tam kapalı, kendisiyle kesişmeyen sürekli bir yol çizer.
        """
        pts = []
        
        # Helper: Edge segment üretici
        def append_edge(length, is_male, start_pt, direction, axis):
            """
            direction: 1 (ileri), -1 (geri)
            axis: 'x' veya 'y'
            """
            n, w = self.get_v8_fingers(length)
            t = self.tab_w if is_male else -self.slot_w
            
            cx, cy = start_pt
            
            # Male dizilimi:   Dışarı(T) - İçeri(0) - Dışarı(T)
            # Female dizilimi: İçeri(-T) - Dışarı(0) - İçeri(-T)
            # Fakat çevreyi döndüğümüz için "Dışarı" demek, kutu merkezinden uzaklaşmak demektir.
            
            for i in range(n):
                # i çift ise çıkıntı/girinti aktif:
                if is_male:
                    offset = t if i % 2 == 0 else 0
                else:
                    offset = t if i % 2 == 0 else 0
                    
                # X ekseninde ilerliyorsak offset Y'ye etki eder
                if axis == 'x':
                    # Alt kenar sağa gider (y=0, dışarı=-y), Üst kenar sola gider (y=ph, dışarı=+y)
                    oy = offset if direction < 0 else -offset 
                    pts.append((cx, cy + oy))
                    cx += w * direction
                    pts.append((cx, cy + oy))
                else:
                    # Y ekseninde ilerliyorsak offset X'e etki eder
                    # Sağ kenar yukarı gider (x=pw, dışarı=+x), Sol kenar aşağı gider (x=0, dışarı=-x)
                    ox = offset if direction > 0 else -offset
                    pts.append((cx + ox, cy))
                    cy += w * direction
                    pts.append((cx + ox, cy))
                    
            return (cx, cy)
            
        # KÖŞE ÇAKIŞMALARINI ÖNLEME. 
        # Matematiksel olarak köşe her zaman (x, y) de başlar.
        # offsetlerin mantığı:
        # v0 = top offset
        # v1 = right offset
        # v2 = bottom offset
        # v3 = left offset
        
        v0 = self.tab_w if edge_sex[0] else -self.slot_w
        v1 = self.tab_w if edge_sex[1] else -self.slot_w
        v2 = self.tab_w if edge_sex[2] else -self.slot_w
        v3 = self.tab_w if edge_sex[3] else -self.slot_w

        # Çevre Dolaşma (0,0 dan bailayarak Saat Yönünün Tersi)
        # 1. BOTTOM Kenarı (Soldan Sağa) x=0 -> pw
        pts.append((-v3 if edge_sex[3]==edge_sex[2] else 0, -v2 if edge_sex[2]==edge_sex[3] else 0))
        n, w = self.get_v8_fingers(pw)
        cx = 0
        for i in range(n):
            oy = -v2 if i % 2 == 0 else 0
            pts.append((cx, oy))
            cx += w
            pts.append((cx, oy))
            
        # BR Corner
        if edge_sex[2] == edge_sex[1]:
            pts.append((pw + v1, -v2))
        else:
            pts.append((pw, 0))

        # 2. RIGHT Kenarı (Aşağıdan Yukarı) y=0 -> ph
        n, w = self.get_v8_fingers(ph)
        cy = 0
        for i in range(n):
            ox = v1 if i % 2 == 0 else 0
            pts.append((pw + ox, cy))
            cy += w
            pts.append((pw + ox, cy))
            
        # TR Corner
        if edge_sex[1] == edge_sex[0]:
            pts.append((pw + v1, ph + v0))
        else:
            pts.append((pw, ph))

        # 3. TOP Kenarı (Sağdan Sola) x=pw -> 0
        n, w = self.get_v8_fingers(pw)
        cx = pw
        for i in range(n):
            oy = v0 if i % 2 == 0 else 0
            pts.append((cx, ph + oy))
            cx -= w
            pts.append((cx, ph + oy))

        # TL Corner
        if edge_sex[0] == edge_sex[3]:
            pts.append((-v3, ph + v0))
        else:
            pts.append((0, ph))

        # 4. LEFT Kenarı (Yukarıdan Aşağı) y=ph -> 0
        n, w = self.get_v8_fingers(ph)
        cy = ph
        for i in range(n):
            ox = -v3 if i % 2 == 0 else 0
            pts.append((ox, cy))
            cy -= w
            pts.append((ox, cy))

        # Close the loop
        if pts[0] != pts[-1]:
            pts.append(pts[0])

        try:
            poly = Polygon(pts).buffer(0)
        except:
            poly = Polygon(pts)
        
        # Dogbone Relief
        if self.dogbone_r > 0:
            reliefs = []
            coords = list(poly.exterior.coords)
            for i in range(len(coords)-1):
                p1, p2, p3 = np.array(coords[i-1]), np.array(coords[i]), np.array(coords[i+1])
                v1, v2 = p2 - p1, p3 - p2
                cp = v1[0] * v2[1] - v1[1] * v2[0]
                if cp > 1e-5: 
                    reliefs.append(Point(p2).buffer(self.dogbone_r))
            if reliefs: poly = unary_union([poly] + reliefs)

        if isinstance(poly, MultiPolygon): poly = poly.geoms[0]
        return poly

    def create_jointed_panel(self, pw, ph, edge_sex, f_width):
        """
        Bağımsız joint_generator.py modülünü kullanarak 4 kenarı oluşturur ve birleştirir.
        pw, ph: Dıştan Dışa (External) ölçülerdir! Panel bounding box'ı bu ölçülerde çıkar.
        edge_sex: [top, right, bottom, left] (True=Male, False=Female, None=Flat)
        """
        from .joint_generator import generate_finger_joint_edge
        
        # İç çerçeve ölçüleri (Lazer tırnakları dışarı taştığı için t kadar daraltılır)
        base_w = max(1.0, pw - (self.t * 2.0))
        base_h = max(1.0, ph - (self.t * 2.0))
        
        b_pts = generate_finger_joint_edge(base_w, self.t, f_width, self.k, edge_sex[2])
        r_pts = generate_finger_joint_edge(base_h, self.t, f_width, self.k, edge_sex[1])
        t_pts = generate_finger_joint_edge(base_w, self.t, f_width, self.k, edge_sex[0])
        l_pts = generate_finger_joint_edge(base_h, self.t, f_width, self.k, edge_sex[3])
        
        def transform(points, rotation, dx, dy):
            res = []
            cos_t = np.cos(rotation)
            sin_t = np.sin(rotation)
            for x, y in points:
                y = -y # İçten dışa doğru rotasyon dönüşümü
                nx = x * cos_t - y * sin_t
                ny = x * sin_t + y * cos_t
                # +self.t payı eklenerek tüm poligonun 0,0'dan başlaması sağlanır
                res.append((nx + dx + self.t, ny + dy + self.t))
            return res
            
        b_edge = transform(b_pts, 0, 0, 0) 
        r_edge = transform(r_pts, np.pi/2, base_w, 0)
        t_edge = transform(t_pts, np.pi, base_w, base_h)
        l_edge = transform(l_pts, 3*np.pi/2, 0, base_h)
        
        combined_pts = []
        combined_pts.extend(b_edge)
        combined_pts.append((r_edge[0][0], b_edge[-1][1])) # BR Corner
        combined_pts.extend(r_edge)
        combined_pts.append((r_edge[-1][0], t_edge[0][1])) # TR Corner
        combined_pts.extend(t_edge)
        combined_pts.append((l_edge[0][0], t_edge[-1][1])) # TL Corner
        combined_pts.extend(l_edge)
        combined_pts.append((l_edge[-1][0], b_edge[0][1])) # LB Corner
        
        try:
            poly = Polygon(combined_pts).buffer(0)
        except:
            poly = Polygon(combined_pts)
            
        return poly

    def draw_label(self, x, y, text, scale=3):
        font_data = {
            'A': [(0,0), (0.5,2), (1,0), (0.75,1), (0.25,1)], 'B': [(0,0), (0,2), (0.7,2), (1,1.5), (0.7,1), (1,0.5), (0.7,0), (0,0)],
            'C': [(1,2), (0,2), (0,0), (1,0)], 'D': [(0,0), (0,2), (0.7,2), (1,1), (0.7,0), (0,0)],
            'E': [(1,2), (0,2), (0,1), (0.7,1), (0,1), (0,0), (1,0)], 'F': [(1,2), (0,2), (0,1), (0.7,1)],
            'G': [(1,2), (0,2), (0,0), (1,0), (1,1), (0.5,1)], 'H': [(0,0), (0,2), (0,1), (1,1), (1,2), (1,0)],
            'I': [(0.5,0), (0.5,2)], 'K': [(0,0), (0,2), (0,1), (1,2), (0,1), (1,0)], 'L': [(0,2), (0,0), (1,0)],
            'M': [(0,0), (0,2), (0.5,1), (1,2), (1,0)], 'N': [(0,0), (0,2), (1,0), (1,2)],
            'O': [(0,0), (1,0), (1,2), (0,2), (0,0)], 'P': [(0,0), (0,2), (1,2), (1,1), (0,1)],
            'R': [(0,0), (0,2), (1,2), (1,1), (0,1), (1,0)], 'S': [(1,2), (0,2), (0,1), (1,1), (1,0), (0,0)],
            'T': [(0,2), (1,2), (0.5,2), (0.5,0)], 'U': [(0,2), (0,0), (1,0), (1,2)], 'W': [(0,2), (0,0), (0.5,1), (1,0), (1,2)],
            '_' : [(0,0), (1,0)], '1': [(0,1), (0.5,2), (0.5,0)], '2': [(0,2), (1,2), (1,1), (0,1), (0,0), (1,0)],
            '3': [(0,2), (1,2), (1,0), (0,0), (0.5,1), (1,1)]
        }
        cx = x
        for c in text.upper():
            if c in font_data:
                pts = [(cx + p[0]*scale, y + p[1]*scale) for p in font_data[c]]
                self.msp.add_lwpolyline(pts, dxfattribs={"layer": "ENGRAVE", "color": 1})
            cx += 1.5 * scale

    def render_polygons(self, poly_list, spacing=15.0):
        curr_x, curr_y = spacing, spacing
        row_h = 0
        for p_dict in poly_list:
            poly = p_dict["poly"]
            name = p_dict["name"]
            
            bounds = poly.bounds
            pw_real = bounds[2] - bounds[0]
            ph_real = bounds[3] - bounds[1]
            
            if curr_x + pw_real + spacing > self.bed_w:
                curr_x = spacing
                curr_y += row_h + spacing
                row_h = 0
            
            ox, oy = bounds[0], bounds[1]
            def move(plist): return [(pt[0]-ox+curr_x, pt[1]-oy+curr_y) for pt in plist]
            
            if poly.is_valid:
                ext_pts = move(list(poly.exterior.coords))
                self.msp.add_lwpolyline(ext_pts, dxfattribs={"layer": "CUT", "color": 7, "closed": True})
                for interior in poly.interiors:
                    int_pts = move(list(interior.coords))
                    self.msp.add_lwpolyline(int_pts, dxfattribs={"layer": "CUT", "color": 7, "closed": True})
            
            self.draw_label(curr_x + pw_real/2 - 20, curr_y + ph_real/2, name)
            
            curr_x += pw_real + spacing
            row_h = max(row_h, ph_real)

    def generate(self, output_path):
        panels = [
            {"poly": self.create_panel_geometry(self.w, self.h, [True, True, True, True]),   "name": "FRONT"},
            {"poly": self.create_panel_geometry(self.w, self.h, [True, True, True, True]),   "name": "BACK"},
            {"poly": self.create_panel_geometry(self.w, self.d, [False, True, False, True]), "name": "TOP"},
            {"poly": self.create_panel_geometry(self.w, self.d, [False, True, False, True]), "name": "BOTTOM"},
            {"poly": self.create_panel_geometry(self.d, self.h, [False, False, False, False]), "name": "LEFT"},
            {"poly": self.create_panel_geometry(self.d, self.h, [False, False, False, False]), "name": "RIGHT"}
        ]
        self.render_polygons(panels)
        self.doc.saveas(output_path)
        return True
