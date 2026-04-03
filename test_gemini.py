"""
Gemini API hızlı test
"""
import sys
sys.path.insert(0, r"c:\Users\DDSOUND\Desktop\exemiz\dd1_platform")

import os
os.environ["GEMINI_API_KEY"] = "AIzaSyDbxPSNRKILzuhAy417gavHEYBaWAkswgs"

from core.ai_assistant import get_ai_response

print("=== Gemini DD1 Asistan Testi ===\n")

msg = "30cm'lik Hertz HV 300 woofer için 45 litre portlu kabin istiyorum, 45hz."
print(f"Kullanıcı: {msg}\n")

result = get_ai_response(msg)
print(f"Action : {result['action']}")
print(f"Cevap  : {result['raw']}")
