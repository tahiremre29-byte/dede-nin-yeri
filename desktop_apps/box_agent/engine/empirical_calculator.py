"""
MODE 2 — Ampirik Model (T/S parametresi olmadan)
Saha verilerine dayalı kabin öneri motoru.
"""
import math
from engine.ts_calculator import CabinetResult


class EmpiricalCalculator:
    """Saha tabanlı ampirik kabin tasarımı"""

    def calculate(self, diameter_inch: int, rms_power: float,
                  vehicle: str, purpose: str,
                  mat_thickness_mm: float,
                  bass_karakteri: str = "Müzik Temiz Olsun",
                  sub_yonu: str = "Arkaya baksın") -> CabinetResult:

        from config import (EMPIRICAL_VB, VEHICLE_TUNING, CABIN_GAIN,
                            EMPIRICAL_SD, EMPIRICAL_XMAX, EMPIRICAL_FS)

        notes = ["T/S parametreleri girilmedi — Ampirik model kullanildi."]

        # ── 1. Kabin Hacmi ────────────────────────────────────────────────────
        closest = min(EMPIRICAL_VB.keys(), key=lambda k: abs(k - diameter_inch))
        vb_range = EMPIRICAL_VB[closest].get(purpose, EMPIRICAL_VB[closest]["SQL"])

        if purpose == "SPL":
            vb = vb_range[0] + (vb_range[1] - vb_range[0]) * 0.35
        elif purpose == "SQL":
            vb = vb_range[0] + (vb_range[1] - vb_range[0]) * 0.5
        else:
            vb = vb_range[0] + (vb_range[1] - vb_range[0]) * 0.65

        # Güce göre hafif ölçek (±15%)
        power_scale = 1.0 + (rms_power - 500) / 5000 * 0.15
        vb = vb * max(0.85, min(1.15, power_scale))

        # ── 2. Tuning Frekansı ────────────────────────────────────────────────
        fb_min, fb_max = VEHICLE_TUNING.get(vehicle, (32, 40))
        if purpose == "SPL":
            fb = fb_min + (fb_max - fb_min) * 0.25
        elif purpose == "SQL":
            fb = fb_min + (fb_max - fb_min) * 0.5
        else:
            fb = fb_min + (fb_max - fb_min) * 0.7

        # ── 3. Port Alanı (Sd tabanlı) ───────────────────────────────────────
        sd_cm2 = EMPIRICAL_SD.get(closest, 490)
        xmax_mm = EMPIRICAL_XMAX.get(closest, 15)
        fs = EMPIRICAL_FS.get(closest, 32)

        # Port alanı = Sd × katsayı
        if purpose == "SPL":
            sp_cm2 = sd_cm2 * 0.35
        elif purpose == "SQL":
            sp_cm2 = sd_cm2 * 0.25
        else:
            sp_cm2 = sd_cm2 * 0.18

        # ── 3.5 Bas Karakteri Optimizasyonu ───────────────────────────────────
        if bass_karakteri == "Koltuğu Yumruklasın":
            fb += 3.0
            vb *= 0.90
            notes.append("Karakter: Koltuğu Yumruklasın (Fb +3Hz, Vb -10%)")
        elif bass_karakteri == "Yeri Titret":
            fb -= 3.0
            vb *= 1.10
            notes.append("Karakter: Yeri Titret (Fb -3Hz, Vb +10%)")
        elif bass_karakteri == "Camları Sallayalım":
            fb += 5.0
            sp_cm2 *= 1.10
            notes.append("Karakter: Camları Sallayalım (Fb +5Hz, Port +10%)")
        elif bass_karakteri == "Mahalle Duysun":
            fb += 4.0
            sp_cm2 *= 1.15
            notes.append("Karakter: Mahalle Duysun (Fb +4Hz, Port +15%)")
            
        # ── 4. Port Uzunluğu (Helmholtz) ─────────────────────────────────────
        vb_cm3 = vb * 1000.0
        k_end = 1.463
        # Constant 29975 matches speed of sound 344 m/s @ 20°C
        raw_lp = (29975 * sp_cm2) / (fb**2 * vb) - k_end * math.sqrt(sp_cm2 / math.pi)
        lp_cm = max(raw_lp, 5.0)

        # ── 5. Slot Port Boyutları ────────────────────────────────────────────
        slot_h = max(mat_thickness_mm / 10.0 * 2, 5.0)
        slot_w = sp_cm2 / slot_h

        if slot_h < 5:
            notes.append("Slot port yuksekligi dusuk — port gurultusu riski.")

        # ── 6. Akustik Analizler ──────────────────────────────────────────────
        sd_m2 = sd_cm2 / 10000.0
        sp_m2 = sp_cm2 / 10000.0
        xmax_m = xmax_mm / 1000.0
        omega = 2 * math.pi * fb

        # Port hava hızı
        vd_max = sd_m2 * xmax_m
        v_port = abs((vd_max * omega) / sp_m2)

        # Cone excursion (basit tahmin)
        cone_excursion_mm = xmax_mm * 0.85

        if v_port > 25:
            notes.append(
                f"PORT HAVA HIZI KRITIK! {v_port:.1f} m/s >> 17 m/s"
            )
        elif v_port > 17:
            notes.append(
                f"Port hava hizi yuksek ({v_port:.1f} m/s > 17 m/s)"
            )

        # SPL tahmini (ampirik referans tabanlı)
        # Referans: 12" subwoofer, 1W → ~88 dB SPL
        ref_spl = {8: 84, 10: 86, 12: 88, 15: 91, 18: 94}
        spl_1w = ref_spl.get(closest, 88)
        peak_spl = spl_1w + 10 * math.log10(max(rms_power, 1))
        # Ported box boost +3 dB
        peak_spl += 3.0

        cabin_gain = CABIN_GAIN.get(vehicle, 5)
        peak_spl_with_gain = peak_spl + cabin_gain

        # f3 ve group delay
        f3 = fb * 0.75
        gd = 1000.0 / (2 * math.pi * fb) * 2

        return CabinetResult(
            mode="MODE 2 — Ampirik Model",
            vb_litre=round(vb, 1),
            fb_hz=round(fb, 1),
            port_area_cm2=round(sp_cm2, 1),
            port_length_cm=round(lp_cm, 1),
            slot_width_cm=round(slot_w, 1),
            slot_height_cm=round(slot_h, 1),
            cone_excursion_mm=round(cone_excursion_mm, 1),
            port_velocity_ms=round(v_port, 1),
            peak_spl_db=round(peak_spl_with_gain, 1),
            cabin_gain_db=cabin_gain,
            f3_hz=round(f3, 1),
            group_delay_ms=round(gd, 1),
            acoustic_advice=self._get_acoustic_advice(sub_yonu),
            expert_comment="DD1 Yorumu:\nBu kabin hesaplanan sürücü parametrelerine göre optimize edilmiştir. Doğru montaj ve sağlam kabin yapısı sistem performansını belirgin şekilde artıracaktır.",
            notes=notes,
        )

    def _get_acoustic_advice(self, sub_yonu: str) -> str:
        advices = {
            "Arkaya baksın": "Sedan ve hatchback araçlarda en yaygın kurulumdur. Bagaj kapağından yansıyan bass araç içine daha güçlü ulaşabilir.",
            "Öne baksın": "Bass doğrudan kabine yönelir. Bazı araçlarda daha temiz ve kontrollü bass üretir.",
            "Yukarı baksın": "Geniş bagajlı araçlarda tercih edilir. Bass bagaj içinde yayılıp kabine dolaylı ulaşır."
        }
        return advices.get(sub_yonu, "")
