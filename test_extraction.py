import sys
sys.path.insert(0, r'C:\Users\DDSOUND\Desktop\exemiz\dd1_platform')
from services.chat_service import _rule_based_extract, process_message

P = 'PASS'; F = 'FAIL'
results = []

def ck(label, got, exp):
    # Case insensitive, normalize Turkish i chars for comparison
    got_n = str(got).lower().replace('\u0131', 'i').replace('\u0130', 'i')
    exp_n = str(exp).lower().replace('\u0131', 'i').replace('\u0130', 'i')
    ok = got_n == exp_n
    s = P if ok else F
    print(f"  [{s}] {label}: got={got!r}")
    results.append(ok)

msg = "jbl tornado 5800 acik havada calacak 18 inc, uygun 80 hz patlamali kabin tasarla"
ext = _rule_based_extract(msg)
print("=== T1: Extraction ===")
ck("model  jbl tornado 5800", ext["woofer_model"],  "jbl tornado 5800")
ck("cap    18",               ext["diameter_inch"],  18)
ck("hz     80",               ext["target_hz"],      80.0)
ck("domain outdoor",          ext["usage_domain"],   "outdoor")
ck("char   patlamali",        ext["bass_char"],       "patlamali")

print("\n=== T2: process_message (API key yok) ===")
r = process_message(msg)
ok_action = r["action"] != "error"
ok_reply  = "Sistem hatasi" not in r.get("reply", "")
ok_ext    = "extracted_info" in r
s = P if ok_action else F; print(f"  [{s}] action={r['action']!r}  (error olmamali)")
s = P if ok_reply  else F; print(f"  [{s}] Sistem hatasi yok: {ok_reply}")
s = P if ok_ext    else F; print(f"  [{s}] extracted_info present: {ok_ext}")
results += [ok_action, ok_reply, ok_ext]

total = len(results); passed = sum(results)
print(f"\n=== {passed}/{total} PASS ===")
sys.exit(0 if passed == total else 1)
