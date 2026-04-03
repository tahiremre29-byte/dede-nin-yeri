"""
test_state_management.py — State Management & Gating Acceptance Testleri
Beklenen davranış: "30cm morel basa göre sedan araç için kabin"
→ Sonraki sorular: bagaj önceliği + hedef kullanım
→ Araç tipi / sürücü çapı TEKRAR SORULMAMALI
→ "portlu kutu" veya "standart tuning" YANITA KATILAMAZ (veri toplama aşaması)
"""
import sys
sys.path.insert(0, r'C:\Users\DDSOUND\Desktop\exemiz\dd1_platform')
sys.path.insert(0, r'C:\Users\DDSOUND\Desktop\exemiz')
from services.chat_service import _rule_based_extract, _build_user_reply

PASS = lambda m: print(f"  [PASS] {m}")
FAIL = lambda m: print(f"  [FAIL] {m}")
def ck(cond, label):
    if cond: PASS(label)
    else: FAIL(label)
    return cond

print("=" * 60)
print("SENARYO: '30cm morel basa göre sedan araç için kabin'")
print("=" * 60)

msg = "30cm morel basa göre sedan araç için kabin"
ext = _rule_based_extract(msg)
panel = ext.get("normalized_panel", {})
reply = _build_user_reply(ext, ext["intent"], ext["confidence"])

print(f"\nIntent: {ext['intent']} ({ext['confidence']})")
print(f"Panel :")
for k, v in panel.items():
    if v not in (None, [], {}):
        print(f"  {k}: {v}")

print(f"\nReply:\n  {reply}\n")

# A) Canonical diameter
print("─── A) Canonical Diameter ───")
ck(panel.get("diameter_raw") == "30 cm", f"diameter_raw='30 cm'")
ck(panel.get("diameter_mm") == 300, f"diameter_mm=300")
ck(panel.get("diameter_inch") == 12, f"diameter_inch=12")

# B) Missing fields doğruluğu
print("─── B) Missing Fields ───")
mf = panel.get("missing_fields", [])
ml = panel.get("missing_labels", [])
ck("vehicle_type" not in mf, "vehicle_type missing_fields'de YOK (sedan bilinmekte)")
ck("diameter" not in mf, "diameter missing_fields'de YOK (30cm bilinmekte)")
ck("brand_or_model" not in mf, "brand missing_fields'de YOK (morel algılandı)")
ck("goal" in mf, "goal hâlâ eksik (BEKLENiYOR)")
ck("trunk_width_cm" in mf, "trunk_width_cm hâlâ eksik (BEKLENiYOR)")
print(f"  missing_fields   : {mf}")
print(f"  missing_labels   : {ml}")

# C) Next question — tekrar sorma
print("─── C) Next Questions (bilinen soru YOK) ───")
nq = panel.get("next_questions", [])
ck(not any("araç" in q.lower() for q in nq), "Araç sorusu next_questions'da YOK")
ck(not any("sürücü" in q.lower() or "çap" in q.lower() for q in nq), "Çap sorusu YOK")
ck(any("bagaj" in q.lower() for q in nq), "Bagaj önceliği next_questions'da VAR")
print(f"  next_questions: {nq}")

# D) Assumption kontrolü (reply'da portlu/tuning yok)
print("─── D) Assumption Control ───")
ck("portlu" not in reply.lower(), "'portlu' reply'da YOK (varsayım yapılmadı)")
ck("standart tuning" not in reply.lower(), "'standart tuning' reply'da YOK")
ck("sedan" in reply.lower(), "sedan yanıtta ACK edildi")
ck("morel" in reply.lower() or "30 cm" in reply.lower(), "sürücü bilgisi yanıtta ACK edildi")

# E) User-facing labels (iç schema adları missing_labels'de YOK)
print("─── E) User-Facing Labels ───")
for internal in ["vehicle_type", "brand_or_model", "trunk_width_cm"]:
    ck(internal not in ml, f"'{internal}' internal adı missing_labels'de YOK")
for label in ["bagaj önceliği", "hedef kullanım"]:
    ck(label in ml or any(label in l for l in ml), f"'{label}' Türkçe etiket var")

print()
print("=" * 60)
print("İKINCİ SENARYO: Portlu + tüm veri tam")
print("=" * 60)
msg2 = "12 inç sub için portlu kutu, sedan araç, bagaj gitmesin, sql hedef"
ext2 = _rule_based_extract(msg2)
panel2 = ext2.get("normalized_panel", {})
reply2 = _build_user_reply(ext2, ext2["intent"], ext2["confidence"])
print(f"Reply:\n  {reply2}\n")
mf2 = panel2.get("missing_fields", [])
nq2 = panel2.get("next_questions", [])
ck(len(mf2) == 0, f"Tüm alanlar dolu, missing_fields=[] (mevcut: {mf2})")
ck("portlu" in reply2.lower() or "ported" in reply2.lower(), "Portlu yanıtta var (kullanıcı söyledi)")
ck("hazırım" in reply2.lower() or "başlatmamı" in reply2.lower(), "Hesap hazır mesajı var")
print(f"  missing_fields: {mf2}")
print(f"  next_questions: {nq2}")
