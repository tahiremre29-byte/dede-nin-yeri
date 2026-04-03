"""
test_domain_classifier.py — Domain Classifier + Home Audio Regression Testi

Beklenen:
Input: "jbl 300 rms bas var, evde kullanacam, odam 25 metrekare, dolap tek kişilik yatak var"
- domain = home_audio
- vehicle_type SORULMAZ
- bagaj alanı GÖRÜNMEZ
- sonraki soru: oda yerleşimi / müzik karakteri
"""
import sys
sys.path.insert(0, r'C:\Users\DDSOUND\Desktop\exemiz\dd1_platform')
sys.path.insert(0, r'C:\Users\DDSOUND\Desktop\exemiz')
from services.chat_service import _rule_based_extract, _build_user_reply

PASS = lambda m: print(f"  [PASS] {m}")
FAIL = lambda m: print(f"  [FAIL] {m}")
def ck(cond, label):
    (PASS if cond else FAIL)(label)
    return cond

print("=" * 60)
print("REGRESSION: Ev / Oda Kullanımı Domain")
print("=" * 60)

msg = "jbl 300 rms bas var, evde kullanacam, odam 25 metrekare, dolap tek kişilik yatak var"
ext = _rule_based_extract(msg)
panel = ext.get("normalized_panel", {})
reply = _build_user_reply(ext, ext["intent"], ext["confidence"])

print(f"\nDomain  : {panel.get('domain')}")
print(f"Reply   : {reply}")
print(f"Missing : {panel.get('missing_fields')}")
print(f"Labels  : {panel.get('missing_labels')}")
print(f"NextQ   : {panel.get('next_questions')}")
print()

# Domain test
ck(panel.get("domain") == "home_audio", "domain = home_audio")
ck(ext.get("usage_domain") == "home_audio", "usage_domain = home_audio")

# Room size detection
ck(panel.get("room_size_m2") == 25, f"room_size_m2 = 25 (var: {panel.get('room_size_m2')})")

# Placement (dolap/yatak = dolap yanı)
ck(panel.get("placement_notes") is not None, "placement_notes algılandı")

# Brand detection
ck(panel.get("brand") == "Jbl", f"brand = Jbl (var: {panel.get('brand')})")

# Missing fields — araç ve bagaj OLMAMALI
mf = panel.get("missing_fields", [])
ck("vehicle_type" not in mf, "vehicle_type missing_fields'de YOK")
ck("trunk_width_cm" not in mf, "trunk_width_cm missing_fields'de YOK")

# Missing labels — iç alan adları OLMAMALI
ml = panel.get("missing_labels", [])
ck("araç tipi" not in ml, "'araç tipi' label'ı YOK")
ck("bagaj ölçüsü" not in ml, "'bagaj ölçüsü' label'ı YOK")

# Next questions — araç sorusu OLMAMALI
nq = panel.get("next_questions", [])
ck(not any("araç" in q.lower() for q in nq), "Araç sorusu next_questions'da YOK")
ck(not any("bagaj" in q.lower() for q in nq), "Bagaj sorusu YOK")

# Next questions — ev soruları OLMALI
ck(any("oda" in q.lower() or "boyut" in q.lower() or "m²" in q.lower() for q in nq)
   or any("yerleşim" in q.lower() or "koyma" in q.lower() for q in nq)
   or any("karakter" in q.lower() or "müzik" in q.lower() for q in nq),
   "Ev/oda soruları next_questions'da VAR")

# Reply — araç sorusu içermemeli
ck("araç tipi" not in reply.lower(), "'araç tipi' reply'da YOK")
ck("bagaj" not in reply.lower(), "'bagaj' reply'da YOK")
ck("ev" in reply.lower() or "oda" in reply.lower(), "'ev/oda' reply'da ACK edildi")

print()
print("=" * 60)
print("SENARYO 2: Araç içi (car_audio default)")
print("=" * 60)
msg2 = "30cm sub için sedan arabaya"
ext2 = _rule_based_extract(msg2)
p2 = ext2.get("normalized_panel", {})
reply2 = _build_user_reply(ext2, ext2["intent"], ext2["confidence"])
print(f"Domain  : {p2.get('domain')}")
print(f"Reply   : {reply2}")
ck(p2.get("domain") == "car_audio", "domain = car_audio")
ck("vehicle_type" not in p2.get("missing_fields", []), "vehicle_type biliniyor (sedan)")
ck("araç tipi" not in reply2.lower() or "sedan" in reply2.lower(), "Araç tekrar sorulmadı/sedan ACK edildi")

print()
print("=" * 60)
print("SENARYO 3: Açık hava / outdoor")
print("=" * 60)
msg3 = "sahne sistemi için 18 inç sub"
ext3 = _rule_based_extract(msg3)
p3 = ext3.get("normalized_panel", {})
reply3 = _build_user_reply(ext3, ext3["intent"], ext3["confidence"])
print(f"Domain  : {p3.get('domain')}")
print(f"Reply   : {reply3}")
ck(p3.get("domain") == "outdoor", "domain = outdoor")
ck("vehicle_type" not in p3.get("missing_fields", []), "vehicle_type missing_fields'de YOK")
ck(not any("araç" in q.lower() for q in p3.get("next_questions", [])), "Araç sorusu YOK")
