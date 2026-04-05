import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__)))

from agents.ses_ustasi import SesUstasi

def run_test():
    usta = SesUstasi()
    
    # 1. Test
    soru1 = "Ustacım kolay gelsin, elimde 4 ohm çift bobin (DVC) subwoofer var, amfim bunu nasıl besler? Direncini naıl bağlayayım, paralel mi seri mi?"
    print("--- SORU 1: Garmin/JL Audio (Ohm Bilgisi) Testi ---")
    cevap1 = usta._ask_gemini(soru1)
    print("\nSes Ustası:\n", cevap1)
    
    print("\n" + "="*80 + "\n")
    
    # 2. Test
    soru2 = "Usta, DD marka bass'a 50 litre net kapalı kabin yapıyorum, ama marangoz ahşabın et kalınlığını hesaplamadan kutuyu direk dıştan 50 litre kesti. Sence doğru mu? Bir de sonradan port açarsam vent mach diye bir ölçü varmış, port ıslık çalmasın diye hızı kaça ayarlayalım?"
    print("--- SORU 2: Kabin & Port Limits (Omni + DIYAudioTR) Testi ---")
    cevap2 = usta._ask_gemini(soru2)
    print("\nSes Ustası:\n", cevap2)

if __name__ == "__main__":
    run_test()
