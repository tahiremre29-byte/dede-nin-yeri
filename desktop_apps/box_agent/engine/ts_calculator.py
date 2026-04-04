"""
MODE 1 — T/S Parametreli Mühendislik Hesabı
Thiele/Small parametrelerine dayalı kesin kabin tasarımı.

Referanslar:
 - Thiele, A.N. (1971) "Loudspeakers in Vented Boxes"
 - Small, R.H. (1973) "Vented-Box Loudspeaker Systems"
 - Keele, D.B. (1973) "Low-Frequency Loudspeaker Assessment"
"""
import math
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class TSParams:
    fs: float        # Rezonans frekansı (Hz)
    qts: float       # Toplam Q faktörü
    vas: float       # Eşdeğer uyum hacmi (litre)
    sd: float        # Efektif piston alanı (cm²)
    xmax: float      # Maks doğrusal salınım (mm)
    re: float        # DC direnç (Ohm)
    diameter_inch: int
    rms_power: float


@dataclass
class CabinetResult:
    """Hesap sonuçları"""
    mode: str
    vb_litre: float        # Net iç hacim
    fb_hz: float           # Tuning frekansı
    port_area_cm2: float   # Port alanı
    port_length_cm: float  # Port uzunluğu
    slot_width_cm: float   # Slot port genişlik
    slot_height_cm: float  # Slot port yükseklik
    cone_excursion_mm: float
    port_velocity_ms: float
    peak_spl_db: float
    cabin_gain_db: int
    f3_hz: float = 0.0         # -3 dB alt frekans
    group_delay_ms: float = 0.0
    acoustic_advice: str = ""
    expert_comment: str = ""
    notes: list[str] = field(default_factory=list)


# ─── Fiziksel sabitler ────────────────────────────────────────────────────────
C_AIR = 345.0          # m/s, hava ses hızı ~22°C
RHO   = 1.18           # kg/m³, hava yoğunluğu


class TSCalculator:
    """Thiele/Small parametreli kabin hesabı"""

    def calculate(self, ts: TSParams, vehicle: str, purpose: str,
                  mat_thickness_mm: float,
                  bass_karakteri: str = "Müzik Temiz Olsun",
                  sub_yonu: str = "Arkaya baksın") -> CabinetResult:

        notes = []
        from config import VEHICLE_TUNING, CABIN_GAIN

        # ── 1. Optimal Ported Box Hacmi ───────────────────────────────────────
        # QB3 alignment: Vb = 15 × Vas × Qts^2.87   (Small, 1973)
        # Daha geniş Qts aralığı için düzeltilmiş formül:
        alpha = 15.0 * (ts.qts ** 2.87)
        vb = ts.vas * alpha
        vb = max(vb, 8.0)        # minimum 8L
        vb = min(vb, ts.vas * 5)  # maksimum Vas × 5

        # Amaca göre hafif ayar
        if purpose == "SPL":
            vb *= 0.90    # SPL → biraz sıkı kabin
        elif purpose == "Günlük Bass":
            vb *= 1.10    # Günlük → biraz serbest kabin
        elif purpose == "SQL":
            # SQL modu için Vas tabanlı sınırlama (1.1x - 1.8x)
            vb_min = ts.vas * 1.1
            vb_max = ts.vas * 1.8
            if vb > vb_max:
                vb = vb_max
            elif vb < vb_min:
                vb = vb_min
            notes.append("SQL karakterli sürücüler için kabin hacmi Vas parametresine göre optimize edilmiştir.")

        # ── 2. Tuning Frekansı ────────────────────────────────────────────────
        # Fb = Fs × (Vas/Vb)^0.44   duruma göre
        fb = ts.fs * ((ts.vas / vb) ** 0.44)

        # Araç tipine göre sınırla
        fb_min, fb_max = VEHICLE_TUNING.get(vehicle, (30, 45))
        
        # SQL Modu Özel Sınırlandırma (Kullanıcı Talebi)
        if purpose == "SQL":
            if vehicle == "Hatchback":
                fb_min, fb_max = 32, 36
            elif vehicle == "Sedan":
                fb_min, fb_max = 30, 34
            elif vehicle == "SUV":
                fb_min, fb_max = 28, 33
            else:
                fb_min, fb_max = 30, 36 # Varsayılan SQL sınırı
        
        original_fb = fb
        if fb < fb_min:
            notes.append(
                f"Hesaplanan Fb={original_fb:.1f} Hz araç alt sınırının altında, "
                f"{fb_min} Hz'e yükseltildi."
            )
            fb = fb_min
        elif fb > fb_max:
            # SQL modunda tuning 36 Hz üzerine çıkamaz
            current_max = 36 if purpose == "SQL" else fb_max
            if fb > current_max:
                notes.append(
                    f"Hesaplanan Fb={original_fb:.1f} Hz SQL/Araç üst sınırında, "
                    f"{current_max} Hz'e düşürüldü."
                )
                fb = current_max

        # ── 3. Port Alanı ─────────────────────────────────────────────────────
        # Pratik kural: Sp >= Sd × 0.7 (minimum)
        # İdeal: Sp = Sd × k  (k=0.75 SPL, k=1.0 SQL, k=0.85 günlük)
        sd_cm2 = ts.sd
        if purpose == "SPL":
            sp_cm2 = sd_cm2 * 0.35    # SPL: approx 1/3 Sd
        elif purpose == "SQL":
            sp_cm2 = sd_cm2 * 0.28    # SQL: min 0.28 Sd
        else:
            sp_cm2 = sd_cm2 * 0.18

        # Helmholtz Resonator Formülü (Kullanıcı Talebi)
        # D = sqrt((4 * PortArea) / π)
        # Lv = (23562.5 * D²) / (Fb² * Vb) - 0.732 * D
        import math
        d_equiv = math.sqrt((4 * sp_cm2) / math.pi)
        # ── 2.5 Bas Karakteri Optimizasyonu ───────────────────────────────────
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

        # ── 4. Port Uzunluğu (Helmholtz) ──────────────────────────────────────
        # Karaktere göre güncellenen fb ve sp ile hesapla
        d_equiv = math.sqrt((4 * sp_cm2) / math.pi)
        lp_cm = (23562.5 * (d_equiv**2)) / (fb**2 * vb) - 0.732 * d_equiv
        lp_cm = max(lp_cm, 5.0)

        # ── 5. Slot Port Boyutları ────────────────────────────────────────────
        slot_h, slot_w = self._slot_dimensions(sp_cm2, mat_thickness_mm, notes)

        # ── 6. Akustik Analizler ──────────────────────────────────────────────
        sd_m2 = sd_cm2 / 10000.0
        xmax_m = ts.xmax / 1000.0
        sp_m2 = sp_cm2 / 10000.0

        # Cone excursion tahmini (RMS güçte)
        # Xpeak = √(Pe × Re) / (2π × Fb² × Mms_approx × Sd)
        # Basitleştirilmiş: Xrms ≈ (Vrms) / (Bl × 2π×Fb)
        # Pratik yaklaşım:
        vd_max = sd_m2 * xmax_m           # m³ — maks hacim deplasmanı
        p_nom = ts.rms_power
        # Tahmini Xpeak (güç tabanlı basit model):
        # Helmholtz yükseltme faktörü tipik ~3 dB → ×1.41
        x_est = xmax_m * math.sqrt(p_nom / max(p_nom, 1)) * 0.85
        cone_excursion_mm = min(x_est * 1000, ts.xmax)

        # Port hava hızı: v_port = Vd × ω / Sp
        omega = 2 * math.pi * fb
        v_port = (vd_max * omega) / sp_m2
        v_port = abs(v_port)

        if v_port > 25:
            notes.append(
                f"PORT HAVA HIZI KRİTİK! {v_port:.1f} m/s >> 17 m/s — "
                f"port alanını artırın veya güç girişini azaltın."
            )
        elif v_port > 17:
            notes.append(
                f"Port hava hızı yüksek ({v_port:.1f} m/s > 17 m/s), "
                f"port kenarlarını pahlayın ve port alanını artırmayı düşünün."
            )

        if cone_excursion_mm > ts.xmax * 0.85:
            notes.append(
                f"Cone excursion Xmax'ın %{cone_excursion_mm/ts.xmax*100:.0f}'ine ulaşıyor "
                f"({cone_excursion_mm:.1f}/{ts.xmax} mm). Güç sınırlaması önerilir."
            )

        # SPL tahmini
        # η₀ = (4π² × Fs³ × Vas) / (c³ × Qts)   (referans verim)
        # SPL_ref = 112.2 + 10×log10(η₀)
        vas_m3 = ts.vas / 1000.0
        eta_0 = (4 * math.pi**2 * ts.fs**3 * vas_m3) / (C_AIR**3 * ts.qts)
        eta_0 = max(eta_0, 1e-10)
        spl_1w = 112.2 + 10 * math.log10(eta_0)
        peak_spl = spl_1w + 10 * math.log10(max(p_nom, 1))
        # Ported box tipik +3 dB (Fb civarı)
        peak_spl += 3.0

        cabin_gain = CABIN_GAIN.get(vehicle, 5)
        peak_spl_with_gain = peak_spl + cabin_gain

        # -3 dB alt frekans tahmini
        f3 = fb * 0.75

        # Group delay tahmini (Fb'de)
        gd = 1000.0 / (2 * math.pi * fb) * 2  # ms, tipik ported box

        return CabinetResult(
            mode="MODE 1 — T/S Parametreli",
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

    def _slot_dimensions(self, sp_cm2: float, thickness_mm: float,
                          notes: list) -> tuple[float, float]:
        """
        Slot port yükseklik/genişlik hesabı.
        Minimum yükseklik: max(malzeme kalınlığı × 2, 5 cm)
        Slot genişliği: Sp / yükseklik
        """
        min_h = max(thickness_mm / 10.0 * 2, 5.0)  # cm
        slot_h = min_h
        slot_w = sp_cm2 / slot_h

        if slot_h < 5:
            notes.append(
                "Slot port yüksekliği düşük — port turbülansı ve gürültüsü riski var."
            )
        return slot_h, slot_w
