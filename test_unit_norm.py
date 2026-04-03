"""
test_unit_norm.py -- Birim Normalizasyon + Yanit Dili Acceptance Testi
"""
import sys
sys.path.insert(0, r'C:\Users\DDSOUND\Desktop\exemiz\dd1_platform')
sys.path.insert(0, r'C:\Users\DDSOUND\Desktop\exemiz')
from services.chat_service import _rule_based_extract, process_message

PASS = lambda m: print(f"  [PASS] {m}")
FAIL = lambda m: print(f"  [FAIL] {m}")
def ck(cond, label):
    if cond: PASS(label)
    else: FAIL(label)
    return cond

# ── Acceptance testler: (mesaj, beklenen_birim, beklenen_ham_deger, beklenen_inch)
cases = [
    ("30 cm kabin lazim",           "cm",   30.0, 12),
    ("12 inc sub icin kutu yap",    "inch", 12.0, 12),
    ("38 santim woofer icin kabin", "cm",   38.0, 15),
    ("300 mm hoparlor icin hacim",  "mm",   300.0, 12),
    ("bagaj icin 15 inch patlamali","inch", 15.0, 15),
]

print("=== ACCEPTANCE TESTLERI ===")
all_ok = True
for msg, exp_unit, exp_raw, exp_inch in cases:
    print(f"\nInput: [{msg}]")
    ext = _rule_based_extract(msg)
    ee  = ext.get("extracted_entities", {})
    ne  = ext.get("normalized_entities", {})

    ok = True
    size_raw = ee.get("size_raw")
    ok &= ck(size_raw is not None, f"size_raw = {size_raw}")

    norm_unit = ne.get("normalized_size_unit")
    ok &= ck(norm_unit == exp_unit, f"normalized_unit = {norm_unit}  (beklenen: {exp_unit})")

    norm_val = ne.get("normalized_size_value")
    ok &= ck(norm_val == exp_raw, f"normalized_value = {norm_val}  (beklenen: {exp_raw})")

    inch = ne.get("inferred_diameter_inch")
    ok &= ck(inch is not None, f"inferred_diameter_inch = {inch}  (beklenen ~{exp_inch})")

    all_ok &= ok

print()
print("=== KULLANICI YANITLARI (debug SIZMAMALI) ===")
DEBUG_MARKERS = [
    "[AI Baglanti", "[Kural Tabanli", "endpoint", "Niyet  :", "guven:", "KURAL"
]
for msg, *_ in cases:
    result = process_message(msg)
    reply  = result.get("user_visible_response") or result.get("reply", "")
    debug  = result.get("internal_debug_message", "")
    has_leak = any(m in reply for m in DEBUG_MARKERS)
    print(f"  Input : {msg}")
    print(f"  Reply : {reply[:90]}")
    print(f"  Debug : {debug[:70]}")
    ck(not has_leak, "Debug mesaji kullaniciya sizmadi")
    ck(len(reply) > 20, "Reply bos degil")
    print()

print("=== RESPONSE STANDART ALANLAR ===")
r = process_message("30 cm kabin lazim")
required = [
    "intent", "confidence",
    "extracted_entities", "normalized_entities",
    "user_visible_response", "internal_debug_message",
]
for field in required:
    ck(field in r, f"response['{field}'] mevcut")

print()
total_cases = len(cases)
print(f"=== {total_cases*4} kontrol tamamlandi ===")
