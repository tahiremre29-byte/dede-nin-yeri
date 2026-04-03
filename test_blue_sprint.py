"""
test_blue_sprint.py -- Mavi Sprint: DXF Tam Dongu Testi
"""
import sys, os
sys.path.insert(0, r'C:\Users\DDSOUND\Desktop\exemiz\dd1_platform')
sys.path.insert(0, r'C:\Users\DDSOUND\Desktop\exemiz')

PASS = lambda msg: print(f"  [PASS] {msg}")
FAIL = lambda msg: print(f"  [FAIL] {msg}")
def ck(cond, label):
    if cond: PASS(label)
    else: FAIL(label)
    return cond

# T1: design_enclosure -- DXF/STL fiziksel uretim
print("=== T1: design_enclosure + DXF/STL ===")
from core.engine import design_enclosure
from core.schemas import DesignRequest, EnclosureType

req = DesignRequest(
    diameter_inch=12, rms_power=600, vehicle='Sedan', purpose='SQL',
    material_thickness_mm=18.0, enclosure_type=EnclosureType.ported,
    fs=31.0, qts=0.28, vas=74.0, xmax=22.0, sd=530.0,
)
eng = design_enclosure(req)
t1_ok = True
t1_ok &= ck(eng is not None, "engine sonuc dondurdu")
t1_ok &= ck(eng.get("net_volume_l") is not None, f"net_volume_l={eng.get('net_volume_l')} L")
t1_ok &= ck(eng.get("validation_passed") == True, "validation_passed=True")
design_id = eng.get("design_id")
t1_ok &= ck(bool(design_id), f"design_id: {design_id}")

dxf_path = eng.get("dxf_path")
stl_path = eng.get("stl_path")
t1_ok &= ck(dxf_path and os.path.exists(dxf_path), f"DXF: {os.path.basename(dxf_path or '')}")
if dxf_path and os.path.exists(dxf_path):
    t1_ok &= ck(os.path.getsize(dxf_path) > 500, f"DXF boyutu: {os.path.getsize(dxf_path)} bytes")
t1_ok &= ck(stl_path and os.path.exists(stl_path), f"STL: {os.path.basename(stl_path or '')}")

# T2: Ayni parametrelerle 18 inc empirik
print("\n=== T2: 18 inc empirik (MODE2) ===")
req2 = DesignRequest(
    diameter_inch=18, rms_power=1200, vehicle='SUV', purpose='SPL',
    material_thickness_mm=18.0, enclosure_type=EnclosureType.ported,
)
eng2 = design_enclosure(req2)
t2_ok = True
t2_ok &= ck(eng2 is not None, "engine sonuc dondurdu")
t2_ok &= ck(eng2.get("validation_passed") == True, "validation_passed=True")
t2_ok &= ck(eng2.get("net_volume_l", 0) > 50, f"net_volume_l={eng2.get('net_volume_l')} L (>50L bekleniyor)")
dxf2 = eng2.get("dxf_path")
t2_ok &= ck(dxf2 and os.path.exists(dxf2), f"DXF2 var: {os.path.basename(dxf2 or '')}")

# T3: KabinUstasi - dogrudan design() - AI olmadanda store'a kaydeder mi?
print("\n=== T3: agents.kabin_ustasi -- design() ===")
from agents.kabin_ustasi import KabinUstasi
from schemas.intake_packet import IntakePacket, TSParams, build_intake

intake = build_intake(
    raw_message="sedan jbl 600w 12 inch sql",
    intent="kabin_tasarim",
    vehicle="Sedan",
    purpose="SQL",
    diameter_inch=12,
    rms_power=600,
    ts=TSParams(fs=31.0, qts=0.28, vas=74.0, xmax=22.0),
    enclosure_type="ported",
)
try:
    agent = KabinUstasi()
    result = agent.design(intake)
    acoustic = result.get("acoustic_packet")
    t3_ok = True
    t3_ok &= ck(acoustic is not None, f"acoustic_packet: {type(acoustic).__name__ if acoustic else None}")
    if acoustic:
        t3_ok &= ck(acoustic.net_volume_l > 0, f"net_volume_l={acoustic.net_volume_l}")
        t3_ok &= ck(acoustic.validation_passed, f"validation_passed: {acoustic.validation_passed}")
        from services.design_service import store_acoustic
        store_acoustic(acoustic, intake_dict={})
        PASS("store_acoustic kaydedildi")
except Exception as e:
    FAIL(f"KabinUstasi exception: {type(e).__name__}: {str(e)[:80]}")
    acoustic = None

# T4: run_full_pipeline (sadece acoustic varsa)
print("\n=== T4: run_full_pipeline -> LazerAjani ===")
if acoustic:
    from services.design_service import run_full_pipeline, get_acoustic
    stored = get_acoustic(acoustic.design_id)
    if stored:
        prod = run_full_pipeline(
            design_id=acoustic.design_id,
            joint="standard_6mm",
            fmt="DXF",
            material="MDF",
            thickness=18.0,
        )
        t4_ok = True
        t4_ok &= ck(prod.get("success") == True, f"produce success | errors={prod.get('errors')}")
        files = prod.get("files", {})
        t4_ok &= ck(bool(files), f"files: {list(files.keys())}")
        for ftype, fpath in files.items():
            if fpath and os.path.exists(fpath):
                PASS(f"{ftype.upper()}: {os.path.basename(fpath)} ({os.path.getsize(fpath)} bytes)")
            elif fpath:
                FAIL(f"{ftype.upper()} eksik: {fpath}")
    else:
        FAIL("stored acoustic bulunamadi")
else:
    FAIL("T3 basarisiz, T4 atlandi")

print("\n=== MAVI SPRINT BITTI ===")
