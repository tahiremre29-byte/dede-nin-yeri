"""
DD1 Box Engine — Hızlı Konsol Testi
"""
import sys
import os

BASE = r"C:\Users\DDSOUND\Desktop\exemiz\dd1_box_agent"
sys.path.insert(0, BASE)
os.chdir(BASE)

print("=" * 60)
print("  DD1 BOX ENGINEERING AGENT — MOTOR TESTİ")
print("=" * 60)

# 1. Config
print("\n[1] Config modülü yükleniyor...")
try:
    from config import APP_NAME, APP_VERSION, VEHICLE_TUNING, CABIN_GAIN
    print(f"    OK  {APP_NAME} v{APP_VERSION}")
    print(f"    Araç profilleri: {list(VEHICLE_TUNING.keys())}")
except Exception as e:
    print(f"    HATA: {e}")
    sys.exit(1)

# 2. TSCalculator
print("\n[2] TSCalculator motor testi...")
try:
    from engine.ts_calculator import TSCalculator, TSParams
    ts = TSParams(fs=31.0, qts=0.28, vas=74.0, sd=530.0,
                  xmax=22.0, re=3.2, diameter_inch=12, rms_power=600)
    calc = TSCalculator()
    result = calc.calculate(ts=ts, vehicle="Sedan", purpose="SQL",
                            mat_thickness_mm=18.0, bass_karakteri="Yeri Titret",
                            sub_yonu="Arkaya baksın")
    print(f"    OK! Net Hacim={result.vb_litre}L, Fb={result.fb_hz}Hz, SPL={result.peak_spl_db}dB")
    for n in result.notes:
        print(f"       - {n}")
except Exception as e:
    import traceback
    print(f"    HATA: {e}")
    traceback.print_exc()

# 3. EmpiricalCalculator
print("\n[3] EmpiricalCalculator testi...")
try:
    from engine.empirical_calculator import EmpiricalCalculator
    emp = EmpiricalCalculator()
    r2 = emp.calculate(diameter_inch=12, rms_power=600, vehicle="Sedan",
                       purpose="Gunluk Bass", mat_thickness_mm=18.0)
    print(f"    OK! Net Hacim={r2.vb_litre}L, Fb={r2.fb_hz}Hz")
except Exception as e:
    import traceback
    print(f"    HATA: {e}")
    traceback.print_exc()

# 4. PanelCalculator
print("\n[4] PanelCalculator testi...")
try:
    from engine.panel_calculator import PanelCalculator
    pc = PanelCalculator()
    panels = pc.calculate(vb_litre=40.0, mat_thickness_mm=18.0,
                          slot_width_cm=14.0, slot_height_cm=5.0)
    print(f"    OK! İç: {panels.inner_w}x{panels.inner_h}x{panels.inner_d}mm")
except Exception as e:
    import traceback
    print(f"    HATA: {e}")
    traceback.print_exc()

print("\n" + "=" * 60)
print("  TEST TAMAMLANDI")
print("=" * 60)
