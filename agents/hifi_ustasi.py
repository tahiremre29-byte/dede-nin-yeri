"""
agents/hifi_ustasi.py
DD1 HiFi Ustası — Ev ve Pro Audio Tasarım Uzmanı

KAPSAM:
- Ev Sineması, Studio Monitor, HiFi Müzik
- Açık Hava (Outdoor), PA Sistem, Sahne
- Kabin titreşimi (rezonans) önleme odaklı
- Kalın MDF (22-25mm) / Çift Kat Baffle önerir

YETKİ SINIRI:
- Araba bagaj hesabı YAPAMAZ (Box/Kabin Ustası'nın işi)
- "SQL/SPL" gibi araba terimleri yerine "Linearite", "F3", "Referans Hacim" odaklı çalışır.
"""
from __future__ import annotations
import logging
from typing import Optional

from schemas.intake_packet import IntakePacket
from schemas.acoustic_design_packet import AcousticDesignPacket, DimensionSpec, InternalConstraints, PortSpec

logger = logging.getLogger("dd1.hifi_ustasi")


class HifiUstasi:
    """
    Araç dışı (Home, Studio, Outdoor, PA) sistemlerin akustik tasarımından sorumlu ajan.
    """

    def __init__(self, api_key: str | None = None):
        logger.info("[HIFI USTASI] Başlatıldı")


    def design(self, packet: IntakePacket) -> dict:
        """
        KabinUstasi'na benzer şekilde AcousticDesignPacket döner, 
        ancak home_audio/outdoor kurallarıyla hesaplar.
        """
        logger.info("[HIFI USTASI] req=%s Tasarım başlatıldı", packet.intake_id)

        # Temel validasyonlar
        if packet.usage_domain not in ("home_audio", "outdoor", "pro_audio"):
            return {
                "validation_passed": False,
                "errors": [f"HifiUstasi, '{packet.usage_domain}' domainini desteklemez. Lütfen Kabin Ustası'na yönlendirin."],
                "warnings": [],
                "summary": "",
                "advice": ""
            }

        # 1. Hacim (Net Volume) Hesaplaması
        target_vol = packet.target_volume_l
        if target_vol is None:
            if packet.ts_params and packet.ts_params.vas and packet.ts_params.qts:
                vas = packet.ts_params.vas
                qts = packet.ts_params.qts
                if qts < 0.4:
                    target_vol = vas * 0.5  # Ported, sıkı
                else:
                    target_vol = vas * 0.8  # Sealed yaklaşımı
            else:
                target_vol = self._fallback_volume(packet.diameter_inch)

        # 2. Tuning (Hz)
        tuning = packet.target_freq_hz
        if tuning is None:
            if packet.usage_domain == "home_audio":
                tuning = 30.0  # Ev sineması / HiFi derin bas hedefler
            else:
                tuning = 45.0  # Outdoor/PA vurucu bas (punch) hedefler

        # 3. Port Alanı 
        port_area = self._calculate_port_area(packet.diameter_inch, packet.rms_power)

        # 4. Port Uzunluğu 
        port_length = 35.0  # Şimdilik sabit

        # 5. Geometri
        dims = DimensionSpec(
            w_mm=packet.diameter_inch * 30 + 100,
            h_mm=packet.diameter_inch * 30 + 100,
            d_mm=400,
        )
        
        ic = InternalConstraints(
            min_net_volume_l=target_vol * 0.9,
            max_net_volume_l=target_vol * 1.1,
            baffle_thickness_mm=22.0,
            woofer_hole_mm=packet.diameter_inch * 25.4 * 0.9
        )
        
        ps = PortSpec(
            type="aero" if tuning > 0 else "sealed",
            length_mm=port_length * 10,
            area_cm2=port_area
        )

        advice = self._generate_advice(packet, target_vol, tuning)

        import hashlib
        fp_str = f"{target_vol:.1f}_{tuning:.1f}_{port_area:.1f}_{port_length:.1f}_{dims.w_mm}_{dims.h_mm}_{dims.d_mm}"
        packet_hash = hashlib.md5(fp_str.encode()).hexdigest()

        design_packet = AcousticDesignPacket(
            design_id=f"hifi_{packet.intake_id[-8:]}",
            net_volume_l=target_vol,
            tuning_hz=tuning,
            port_area_cm2=port_area,
            port_length_cm=port_length,
            enclosure_type="ported" if tuning > 0 else "sealed",
            dimensions=dims,
            internal_volume_constraints=ic,
            port=ps,
            packet_hash=packet_hash,
            metadata={
                "domain": packet.usage_domain,
                "agent": "hifi_ustasi"
            }
        )

        return {
            "validation_passed": True,
            "acoustic_packet": design_packet,
            "errors": [],
            "warnings": [],
            "summary": "HiFi akustik fizik hesaplamaları tamamlandı.",
            "advice": advice
        }

    def _fallback_volume(self, dia_in: float) -> float:
        """Kaba çap -> hacim tablosu (HiFi standardı)"""
        mapping = {8: 25.0, 10: 45.0, 12: 70.0, 15: 120.0, 18: 200.0}
        # En yakın değeri bul
        closest = min(mapping.keys(), key=lambda k: abs(k - dia_in))
        return mapping[closest]

    def _calculate_port_area(self, dia_in: float, rms_power: float) -> float:
        """Ev ve sahne sistemlerinde port sesi istenmez, port alanı büyük tutulur."""
        base_area = (dia_in * 2.54 / 2) ** 2 * 3.14  # Koni alanı (cm2)
        target_port_ratio = 0.35 if rms_power > 500 else 0.25 # %25-35 kuralı
        return base_area * target_port_ratio

    def _generate_advice(self, packet: IntakePacket, vol: float, tuning: float) -> str:
        """Kullanıcıya gösterilecek çıktı"""
        if packet.usage_domain == "home_audio":
            return (
                f"Ev kullanımınız için {packet.diameter_inch}\" sürücüye {vol:.1f} Litre, "
                f"{tuning:.1f} Hz tuning frekansında bir tasarım öneriyorum.\n"
                "Not: Ev ortamında rezonansı önlemek için duvarları 22mm MDF'den veya "
                "iç kısımlara fazladan destek kirişleri (bracing) yaparak inşa etmeniz önemlidir."
            )
        else:
            return (
                f"PA/Açık Hava sisteminiz için {packet.diameter_inch}\" sürücüye {vol:.1f} Litre, "
                f"{tuning:.1f} Hz tuning frekansında vurucu karakterli bir tasarım hazırladım.\n"
                "Not: Açık alanda bas kaybı yaşanacağı için port alanını olabildiğince geniş tuttum "
                "böylece ses uzağa taşınırken port sesi yaratmayacak."
            )
