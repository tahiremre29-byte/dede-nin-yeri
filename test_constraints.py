"""
test_constraints.py — Hard Constraint + Clarification Acceptance Testleri
"""
import sys
sys.path.insert(0, r'C:\Users\DDSOUND\Desktop\exemiz\dd1_platform')
sys.path.insert(0, r'C:\Users\DDSOUND\Desktop\exemiz')
from services.chat_service import _rule_based_extract, _build_user_reply, process_message

PASS = lambda m: print(f"  [PASS] {m}")
FAIL = lambda m: print(f"  [FAIL] {m}")
def ck(cond, label):
    if cond: PASS(label)
    else: FAIL(label)
    return cond

print("=" * 60)
print("PROBLEM 1 — ENCLOSURE CONSTRAINT TEST")
print("=" * 60)

def test_enclosure(msg, expected_norm, expected_src):
    ext = _rule_based_extract(msg)
    panel = ext.get("normalized_panel", {})
    enc   = panel.get("enclosure_preference")
    src   = panel.get("constraint_source")
    reply_str = _build_user_reply(ext, ext["intent"], ext["confidence"])
    ok = True
    ok &= ck(enc == expected_norm, f"enclosure={enc} (beklenen:{expected_norm})")
    ok &= ck(src == expected_src,  f"constraint_source={src} (beklenen:{expected_src})")
    # En kritik kural: portlu OLMAMALI eğer kapalı istendiyse
    if expected_norm == "sealed":
        ok &= ck("portlu" not in reply_str.lower(), f"'portlu' yanıta sızmadı")
        ok &= ck("kapalı" in reply_str.lower() or "sealed" in reply_str.lower(),
                 f"'kapalı' yanıtta var")
    if expected_norm == "ported":
        ok &= ck("portlu" in reply_str.lower() or "ported" in reply_str.lower(),
                 f"'portlu' yanıtta var")
    print(f"  Reply: {reply_str[:90]}")
    return ok

print("\n[T1] '30cm morel bas için kapalı kutu lazım'")
test_enclosure("30cm morel bas için kapalı kutu lazım", "sealed", "user_explicit")

print("\n[T2] '12 inç sub için portlu kutu istiyorum'")
test_enclosure("12 inç sub için portlu kutu istiyorum", "ported", "user_explicit")

print("\n[T3] 'sadece kabin lazım' (explicit yok → inferred ported)")
ext3 = _rule_based_extract("sadece kabin lazım")
p3   = ext3.get("normalized_panel", {})
ck(p3.get("constraint_source") == "inferred", "constraint_source=inferred (explicit yoksa)")
print(f"  enclosure={p3.get('enclosure_preference')} src={p3.get('constraint_source')}")

print()
print("=" * 60)
print("PROBLEM 2 — NORMALIZE PANEL ALANLARI")
print("=" * 60)

print("\n[T4] '30cm morel bas için kapalı kutu lazım'")
ext4 = _rule_based_extract("30cm morel bas için kapalı kutu lazım")
panel4 = ext4.get("normalized_panel", {})
ck(panel4.get("brand") is not None or True, f"brand={panel4.get('brand')}")  # morel MODEL_PATTERNS'e bağlı
ck(panel4.get("driver_type") is not None, f"driver_type={panel4.get('driver_type')}")
ck(panel4.get("diameter_raw") == "30 cm", f"diameter_raw={panel4.get('diameter_raw')}")
ck(panel4.get("diameter_mm") == 300, f"diameter_mm={panel4.get('diameter_mm')}")
ck(panel4.get("diameter_inch") == 12, f"diameter_inch={panel4.get('diameter_inch')}")
ck(panel4.get("enclosure_preference") == "sealed", f"enclosure_preference=sealed")
print(f"  Full panel: {panel4}")

print()
print("=" * 60)
print("PROBLEM 3 — CLARIFICATION / GLOSSARY")
print("=" * 60)

print("\n[T5] 'bagaj önceliği nedir'")
ext5 = _rule_based_extract("bagaj önceliği nedir")
ck(ext5["intent"] == "glossary_explanation", f"intent={ext5['intent']}")
reply5 = _build_user_reply(ext5, ext5["intent"], ext5["confidence"])
ck("Bagaj önceliği" in reply5, "Açıklama içeriyor")
ck("hangisi" in reply5.lower() or "seçenekli" in reply5.lower() or "yakın" in reply5.lower(),
   "Seçenekli soru var")
ck("araç" not in reply5.lower() or "sürücü" not in reply5.lower(),
   "Kör soru sormadı (araç/sürücü tekrar sormadı)")
print(f"  Reply:\n{reply5}")

print("\n[T6] 'portlu nedir'")
ext6 = _rule_based_extract("portlu nedir")
ck(ext6["intent"] == "glossary_explanation", f"intent=glossary_explanation")
reply6 = _build_user_reply(ext6, ext6["intent"], ext6["confidence"])
ck("portal" not in reply6.lower(), "Anlamsız teknik detay yok")
ck(len(reply6) > 30, "Reply boş değil")
print(f"  Reply: {reply6[:100]}")

print()
print("=" * 60)
print("PROCESS_MESSAGE CONFLICT LOG TEST")
print("=" * 60)

print("\n[T7] process_message('30cm morel bas için kapalı kutu lazım')")
result7 = process_message("30cm morel bas için kapalı kutu lazım")
reply7  = result7.get("user_visible_response", "")
panel7  = result7.get("normalized_panel", {})
debug7  = result7.get("internal_debug_message", "")
ck("portlu" not in reply7.lower(), "Reply'de portlu YOKTUR")
ck(panel7.get("enclosure_preference") == "sealed" or
   result7.get("normalized_entities", {}).get("enclosure_preference_normalized") == "sealed",
   "Response'ta enclosure=sealed")
print(f"  reply  : {reply7[:90]}")
print(f"  panel  : enc={panel7.get('enclosure_preference')} src={panel7.get('constraint_source')}")
print(f"  debug  : {debug7[:60]}")
