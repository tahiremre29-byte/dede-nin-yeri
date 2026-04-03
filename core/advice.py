"""
DD1 Platform — Usta Tavsiyesi Üretici
"""
from typing import List

def generate_expert_advice(result_dict: dict, vehicle: str, purpose: str) -> str:
    """Usta tavsiyesi metnini üret (Daha kısa ve net versiyon)"""
    tavsiyelar = []

    # 1. Bagaj Rezonansı
    if vehicle in ("Sedan", "Hatchback"):
        tavsiyelar.append(
            "🔊 BAGAJ YALITIMI: Sedan/HB araçlarda 60-100Hz rezonansını önlemek için "
            "bagaj kapağına yalıtım örtüsü ve conta uygulaması şarttır."
        )
    elif vehicle == "SUV":
        tavsiyelar.append(
            "🔊 TAVAN/ZEMİN: SUV'larda geniş tavan yüzeyine ses damperi uygulamak "
            "orta-bas netliğini ve akustik kararlılığı artırır."
        )
    elif vehicle in ("Pickup", "Van"):
        tavsiyelar.append(
            "🔊 KASA REZONANSI: Kasa zeminine anti-vibrasyon panel ekleyerek "
            "bass temizliğini üst seviyeye taşıyın."
        )

    # 2. Gevşek Parçalar
    tavsiyelar.append(
        "🔩 TİTREŞİM KONTROLÜ: Plakalık, tavan lambası ve trimleri sabitleyin. "
        "Klipslere sünger bant uygulayarak trim seslerini kesin."
    )

    # 3. Port–Sürücü Mesafesi
    inner_d = result_dict.get("inner_d_mm", 300)
    sub_clearance = inner_d * 0.3
    tavsiyelar.append(
        f"📐 PORT MESAFESİ: Sürücü arkası ile port girişi arasında en az {sub_clearance:.0f}mm "
        f"hava yolu bırakın. Portu kabin duvarına çok yakın tutmayın."
    )

    # 4. Port Gürültüsü
    vel = result_dict.get("port_velocity_ms", 0)
    if vel > 14:
        risk = "KRİTİK" if vel > 17 else "YÜKSEK"
        tavsiyelar.append(
            f"💨 PORT TÜRBÜLANSI ({risk} — {vel:.1f} m/s): Port ağzını R10mm yuvarlatın. "
            f"İç yüzey pürüzlerini zımparalayarak hava akışını iyileştirin."
        )
    else:
        tavsiyelar.append(
            f"✅ AKIŞ VERİMİ: Port hava hızı {vel:.1f} m/s — Türbülans riski düşük."
        )

    # 5. Amaca Özel Not
    if purpose == "SPL":
        tavsiyelar.append(
            "🏆 SPL PERFORMANS: Maksimum basınç için tüm birleşim noktalarını "
            "polimer yapıştırıcı + vidayla sızdırmaz hale getirin."
        )
    elif purpose == "SQL":
        tavsiyelar.append(
            "🎵 AKUSTİK KONFOR: Kabin içine 3cm yumurta sünger veya elyaf ekleyerek "
            "ayrıntılı ve pürüzsüz bas elde edin."
        )

    return "\n\n".join(tavsiyelar)
