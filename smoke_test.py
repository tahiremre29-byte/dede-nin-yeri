"""Quick smoke test for DD1 Platform engine — Sprint 1-3."""
import sys
sys.path.insert(0, r"c:\Users\DDSOUND\Desktop\exemiz\dd1_platform")
sys.path.insert(0, r"c:\Users\DDSOUND\Desktop\exemiz")

print("=== [1] Woofer DB Test ===")
from core.thiele_small import search, get_by_model
r = search("hertz")
print(f"Search 'hertz': {len(r)} sonuc — ilk: {r[0]['model']}")
w = get_by_model("Hertz HV 300")
print(f"Lookup OK: {w['model']} | Fs={w['fs']} Qts={w['qts']} Vas={w['vas']}")

print("\n=== [2] Port Uzunluk Hesabi ===")
from core.engine import calc_port_length
pl = calc_port_length(45.0, 45.0, 100.0)
print(f"45L / 45Hz / O100mm => port uzunlugu: {pl} mm")

print("\n=== [3] T/S Parametreli Hesap (Motor) ===")
from core.engine import calculate_ts
from core.schemas import DesignRequest, EnclosureType

req = DesignRequest(
    diameter_inch=12,
    rms_power=600,
    vehicle="Sedan",
    purpose="SQL",
    material_thickness_mm=18.0,
    enclosure_type=EnclosureType.ported,
    fs=31.0,
    qts=0.28,
    vas=74.0,
    xmax=22.0,
    sd=530.0,
)
result = calculate_ts(req)
print(f"Mode    : {result['mode']}")
print(f"Net Vol : {result['vb_l']} L")
print(f"Tuning  : {result['fb_hz']} Hz")
print(f"Peak SPL: {result['peak_spl']} dB")
print(f"Port Hiz: {result['v_port']} m/s")

print("\n=== [4] design_enclosure Entegrasyon Testi ===")
from core.engine import design_enclosure
from core.schemas import DesignRequest, EnclosureType

# 4a: T/S Parametreli (MODE1) — ported
req4a = DesignRequest(
    diameter_inch=12,
    rms_power=600,
    vehicle="Sedan",
    purpose="SQL",
    material_thickness_mm=18.0,
    enclosure_type=EnclosureType.ported,
    fs=31.0,
    qts=0.28,
    vas=74.0,
    xmax=22.0,
    sd=530.0,
)
r4a = design_enclosure(req4a)
assert r4a.get("net_volume_l") or r4a.get("vb_l"), \
    f"design_enclosure MODE1 yanit eksik: {list(r4a.keys())}"
print(f"MODE1 ported => net_volume_l={r4a.get('net_volume_l')} L  tuning={r4a.get('tuning_hz')} Hz")

# 4b: Empirical (MODE2) — sealed
req4b = DesignRequest(
    diameter_inch=15,
    rms_power=1000,
    vehicle="SUV",
    purpose="SPL",
    material_thickness_mm=18.0,
    enclosure_type=EnclosureType.sealed,
)
r4b = design_enclosure(req4b)
assert r4b, "design_enclosure MODE2 bos donus"
print(f"MODE2 sealed => net_volume_l={r4b.get('net_volume_l')} L  mode={r4b.get('mode')}")
print("design_enclosure [OK]")


print("\n=== ALL TESTS DONE (Sprint 1-3) ===")

