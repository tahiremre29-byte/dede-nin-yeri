"""
Usta Tavsiyesi Üretici
Statik template tabanlı teknik öneri metni.
"""
from engine.ts_calculator import CabinetResult
from engine.panel_calculator import PanelList


def uret(result: CabinetResult, panels: PanelList,
         vehicle: str, purpose: str) -> str:
    """Usta tavsiyesi metnini üret"""

    tavsiyelar = []

    # ── 1. Bagaj Rezonansı ────────────────────────────────────────────────────
    if vehicle in ("Sedan", "Hatchback"):
        tavsiyelar.append(
            "🔊 BAGAJ REZONANSI: Sedan ve Hatchback bagaj bölmesi 60–100 Hz aralığında "
            "kabin rezonansı oluşturabilir. Bagaj kapağını lastik conta veya sünger şerit "
            "ile sızdırmazlık yapın. Mümkünse bagaj iç yüzeylerine ses yalıtım örtüsü "
            "(bitüm bazlı veya CLD panel) uygulayın."
        )
    elif vehicle == "SUV":
        tavsiyelar.append(
            "🔊 BAGAJ REZONANSI: SUV'larda yük bölmesi büyüktür. Tavan/zemin "
            "yüzeylerine ses damperi uygulamak orta-bas netliğini artırır."
        )
    elif vehicle in ("Pickup", "Van"):
        tavsiyelar.append(
            "🔊 BAGAJ / KASA REZONANSI: Pickup kasası ve Van kargo bölmesi ciddi "
            "rezonans oluşturabilir. Kasa zeminine anti-vibrasyon panel eklenmesi "
            "bass temizliğini belirgin şekilde iyileştirir."
        )

    # ── 2. Gevşek Parçalar ────────────────────────────────────────────────────
    tavsiyelar.append(
        "🔩 GEVŞEKLİK VE TİTREŞİM: Tepe lambası, torpido kapakları, plakalık ve "
        "kapı iç panelleri yüksek sesde rezonansa girer. Kurulumdan önce araçtaki "
        "tüm panelleri kontrol edin; gevşek vidaları sıkın, plastik geçmelere "
        "ince sünger şerit yapıştırın. Kabin cıvataları da mutlaka kontrol edin."
    )

    # ── 3. Arka Koltuk ────────────────────────────────────────────────────────
    tavsiyelar.append(
        "💺 ARKA KOLTUK POZİSYONU: Arka koltuk yatay konumda bırakıldığında "
        "subwoofer ile dinleme noktası arasındaki akustik bariyer kalkar ve "
        "bass algısı önemli ölçüde artar. SPL yarışması yapılacaksa arka koltuğu "
        "kaldırın veya indirin. Günlük kullanımda koltuğun tam dik kapatılması "
        "bass yansımalarını düzenler."
    )

    # ── 4. Port–Sürücü Mesafesi ──────────────────────────────────────────────
    sub_clearance = panels.inner_d_mm * 0.3
    tavsiyelar.append(
        f"📐 PORT–SÜRÜCÜ MESAFESİ: Slot port çıkışı ile sürücünün geri yüzü arasında "
        f"en az {sub_clearance:.0f} mm boşluk bırakın (kabin derinliğinin ~%30'u). "
        f"Port çıkışı kabin duvarına çok yakın olmamalı — her iki tarafta da "
        f"en az {result.slot_height_cm * 10:.0f} mm açık alan kalmalı."
    )

    # ── 5. Port Gürültüsü ─────────────────────────────────────────────────────
    vel = result.port_velocity_ms
    if vel > 14:
        risk = "YÜKSEK RİSK" if vel > 17 else "ORTA RİSK"
        tavsiyelar.append(
            f"💨 PORT GÜRÜLTÜSÜ ({risk} — {vel:.1f} m/s): Port kenarlarını 45° "
            f"veya yuvarlak (R10 mm) pahlayın. Port iç yüzeyini zımpara ve "
            f"astar ile düzleştirin. Port alanını {result.port_area_cm2 * 1.2:.0f} cm²'ye "
            f"artırmayı düşünün."
        )
    else:
        tavsiyelar.append(
            f"✅ PORT GÜRÜLTÜSÜ: Port hava hızı {vel:.1f} m/s — güvenli aralıkta. "
            f"Yine de port kenarlarını hafifçe pahlamak (45°) ses kalitesini artırır."
        )

    # ── 6. Amaca Özel Not ────────────────────────────────────────────────────
    if purpose == "SPL":
        tavsiyelar.append(
            "🏆 SPL NOTU: Maksimum SPL için kabin sızdırmazlığına özellikle dikkat edin. "
            "Tüm birleşim noktalarını güçlü yapıştırıcı + contayla kapatın. "
            "İç köşelere köşe takviye profili ekleyin. Kabin içi köşelerine "
            "küçük köşebentler (brace) koyun — panel titreşimini azaltır ve SPL'i artırır."
        )
    elif purpose == "SQL":
        tavsiyelar.append(
            "🎵 SQL NOTU: Ses kalitesi + bas dengesi için kabin iç yüzeylerine "
            "3–4 cm kalınlığında akustik sünger (long-fiber wool) yapıştırın. "
            "Bu yüksek frekanslı parazit rezonansları bastırır ve bas temizliğini artırır."
        )

    separator = "\n\n" + "─" * 60 + "\n\n"
    return separator.join(tavsiyelar)
