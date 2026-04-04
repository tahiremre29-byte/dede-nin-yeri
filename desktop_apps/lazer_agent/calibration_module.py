import ezdxf
import os
import math

class CalibrationGenerator:
    def __init__(self, output_path):
        self.output_path = output_path
        # MODULE 1: R2000 Format (CorelDRAW Uyumluluğu ve Stabilite için)
        self.doc = ezdxf.new("R2000")
        self.doc.header['$INSUNITS'] = 4 # MM
        self.msp = self.doc.modelspace()
        
        # Katmanlar
        self.doc.layers.new("CUT", dxfattribs={"color": 7}) # Siyah
        self.doc.layers.new("ENGRAVE", dxfattribs={"color": 1}) # Kırmızı

    def draw_segment_number(self, x, y, number_str, scale=3.5):
        """Basit bir 7-segment tipi polyline fontu ile numara çizimi."""
        font_data = {
            '0': [(0,0), (1,0), (1,2), (0,2), (0,0)],
            '1': [(1,0), (1,2)],
            '2': [(0,2), (1,2), (1,1), (0,1), (0,0), (1,0)],
            '3': [(0,2), (1,2), (1,0), (0,0), (0,1), (1,1)],
            '4': [(0,2), (0,1), (1,1), (1,2), (1,0)],
            '5': [(1,2), (0,2), (0,1), (1,1), (1,0), (0,0)],
            '6': [(1,2), (0,2), (0,0), (1,0), (1,1), (0,1)],
            '7': [(0,2), (1,2), (1,0)],
            '8': [(0,0), (1,0), (1,2), (0,2), (0,0), (0,1), (1,1)],
            '9': [(1,1), (0,1), (0,2), (1,2), (1,0), (0,0)],
            '.': [(0.4, 0), (0.6, 0), (0.6, 0.2), (0.4, 0.2), (0.4, 0)]
        }
        
        curr_x = x
        for char in number_str:
            if char in font_data:
                pts = [(curr_x + p[0]*scale, y + p[1]*scale) for p in font_data[char]]
                self.msp.add_lwpolyline(pts, dxfattribs={"layer": "ENGRAVE", "color": 1})
            curr_x += 1.5 * scale

    def generate(self):
        # 1. Ana Panel (300x200mm)
        panel_pts = [(0,0), (300,0), (300,200), (0,200), (0,0)]
        self.msp.add_lwpolyline(panel_pts, dxfattribs={"layer": "CUT", "color": 7, "closed": True})
        
        # 2. Slotlar (10.00 - 10.30mm)
        # MODULE 1: NO KERF, NO TOLERANCE
        base_width = 10.0
        slots = [10.00, 10.05, 10.10, 10.15, 10.20, 10.25, 10.30]
        slot_height = 30.0
        start_x = 20.0
        start_y = 100.0
        spacing = 10.0 # User Request Spacing
        
        for i, val in enumerate(slots):
            x = start_x + i * (base_width + spacing)
            
            # Slot Çizimi (LWPOLYLINE, CLOSED)
            slot_pts = [
                (x, start_y),
                (x + val, start_y),
                (x + val, start_y + slot_height),
                (x, start_y + slot_height),
                (x, start_y)
            ]
            self.msp.add_lwpolyline(slot_pts, dxfattribs={"layer": "CUT", "color": 7, "closed": True})
            
            # Etiket
            self.draw_segment_number(x, start_y - 15, f"{val:.2f}")

        # 3. Erkek Parça (10.00mm SABİT)
        male_x = 20.0
        male_y = 30.0
        # MODULE 1: 10.00 mm Test Piece
        male_pts = [
            (male_x, male_y),
            (male_x + 10.00, male_y),
            (male_x + 10.00, male_y + 80),
            (male_x, male_y + 80),
            (male_x, male_y)
        ]
        self.msp.add_lwpolyline(male_pts, dxfattribs={"layer": "CUT", "color": 7, "closed": True})
        
        # Engrave Texts
        self.draw_segment_number(20, 170, "MODULE 1 - KERF CALIBRATION", scale=3)
        self.draw_segment_number(male_x + 15, male_y + 35, "MALE 10.00MM", scale=2.5)

        # Kaydet
        try:
            self.doc.saveas(self.output_path)
            return True
        except Exception as e:
            print(f"Calibration panel save error: {e}")
            return False

def generate_calibration_dxf(output_path):
    gen = CalibrationGenerator(output_path)
    return gen.generate()
