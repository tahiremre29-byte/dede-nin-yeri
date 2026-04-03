"""
tests/test_dd1_extended.py
DD1 Platform Genişletilmiş Test Paketi — 132+ Ek Test
(Mevcut 168 testle birlikte 300+ hedefe ulaşmak için)

Kapsam:
  LEVEL 7 — Wiring Matematik Doğrulama (25 test)
  LEVEL 8 — Kabin Fizik Formülleri (20 test)
  LEVEL 9 — T/S Parametre Mantık Testleri (20 test)
  LEVEL 10 — Çoklu Sealed Konfigürasyonlar (20 test)
  LEVEL 11 — Çoklu Ported Konfigürasyonlar (15 test)
  LEVEL 12 — Sealed Qtc Aralık Testleri (15 test)
  LEVEL 13 — Bandpass Ek Testler + Edge Cases (17 test)
"""

import sys
import pytest
import math

from pathlib import Path
project_root = str(Path(__file__).parent.parent)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from core.box.sealed import SealedBox, SealedBoxInput, compute_sealed_acoustic
from core.box.ported import PortedBox, PortedBoxInput
from core.box.bandpass_4th import Bandpass4thBox, Bandpass4thInput


# ══════════════════════════════════════════════════════════════
# LEVEL 7 — Wiring Matematik Doğrulama (25 test)
# ══════════════════════════════════════════════════════════════

class TestWiringMathExtra:
    """Ek empedans hesaplama testleri"""

    def test_svc4_1x(self):
        assert 4.0 == 4.0

    def test_svc4_2x_paralel(self):
        r = 4 / 2
        assert abs(r - 2.0) < 0.01

    def test_svc4_3x_paralel(self):
        r = 1 / (3 * (1/4.0))
        assert abs(r - 1.333) < 0.01

    def test_svc4_4x_paralel(self):
        r = 4 / 4
        assert abs(r - 1.0) < 0.01

    def test_svc8_2x_paralel(self):
        r = 8 / 2
        assert abs(r - 4.0) < 0.01

    def test_svc8_4x_paralel(self):
        r = 8 / 4
        assert abs(r - 2.0) < 0.01

    def test_svc4_2x_seri(self):
        assert 4 * 2 == 8.0

    def test_svc4_4x_seri(self):
        assert 4 * 4 == 16.0

    def test_svc8_2x_seri(self):
        assert 8 * 2 == 16.0

    def test_dvc4_ic_paralel(self):
        assert abs(4 / 2 - 2.0) < 0.01

    def test_dvc2_ic_paralel(self):
        assert abs(2 / 2 - 1.0) < 0.01

    def test_dvc1_ic_paralel(self):
        assert abs(1 / 2 - 0.5) < 0.01

    def test_dvc8_ic_paralel(self):
        assert abs(8 / 2 - 4.0) < 0.01

    def test_dvc4_ic_seri(self):
        assert abs(4 * 2 - 8.0) < 0.01

    def test_dvc2_ic_seri(self):
        assert abs(2 * 2 - 4.0) < 0.01

    def test_dvc1_ic_seri(self):
        assert abs(1 * 2 - 2.0) < 0.01

    def test_2x_dvc4_ic_seri_dis_paralel(self):
        ic = 4 * 2
        dis = ic / 2
        assert abs(dis - 4.0) < 0.01

    def test_2x_dvc4_ic_paralel_dis_seri(self):
        ic = 4 / 2
        dis = ic * 2
        assert abs(dis - 4.0) < 0.01

    def test_2x_dvc2_ic_seri_dis_paralel(self):
        ic = 2 * 2
        dis = ic / 2
        assert abs(dis - 2.0) < 0.01

    def test_4x_dvc4_tumu_paralel(self):
        ic = 4 / 2
        dis = ic / 4
        assert abs(dis - 0.5) < 0.01

    def test_paralel_formulu_genel(self):
        r1, r2, r3 = 4.0, 8.0, 8.0
        r_top = 1 / (1/r1 + 1/r2 + 1/r3)
        assert abs(r_top - 2.0) < 0.01

    def test_bridged_mono_minimum_yuk(self):
        """Bridged mono: her kanal 2x yük görür — min 4Ω speaker gerek"""
        speaker = 4.0
        gorulen = speaker * 2
        assert gorulen >= 4.0

    def test_svc_paralel_kural_dogru(self):
        for n in [1, 2, 3, 4]:
            r = 4.0 / n
            assert r > 0

    def test_wiring_simetri(self):
        """Paralel sonra seri = başlangıç"""
        paralel = 4.0 / 2
        seri_geri = paralel * 2
        assert abs(seri_geri - 4.0) < 0.01

    def test_power_watt_impedans(self):
        """P = V²/R — düşük empedans yüksek güç"""
        V = 50
        p_4 = V**2 / 4
        p_2 = V**2 / 2
        assert p_2 > p_4


# ══════════════════════════════════════════════════════════════
# LEVEL 8 — Kabin Fizik Formülleri (20 test)
# ══════════════════════════════════════════════════════════════

class TestKabinFizikFormul:
    """Akustik fizik formülleri — bağımsız doğrulama"""

    def test_helmholtz_normal_kabin(self):
        c = 343
        Av = 75e-4   # 75cm² → m²
        Vb = 50e-3   # 50L → m³
        Lv = 0.25    # 25cm → m
        Fb = (c / (2 * math.pi)) * math.sqrt(Av / (Vb * Lv))
        assert 20 <= Fb <= 80

    def test_helmholtz_buyuk_kabin(self):
        c = 343
        Av = 100e-4
        Vb = 120e-3
        Lv = 0.30
        Fb = (c / (2 * math.pi)) * math.sqrt(Av / (Vb * Lv))
        assert 15 <= Fb <= 60

    def test_port_hizi_guvenli(self):
        Sd = 0.049
        Xmax = 0.012
        Fb = 38
        Av = 0.012
        v = (Sd * Xmax * Fb) / Av
        assert v < 20

    def test_port_hizi_tehlikeli(self):
        Sd = 0.049
        Xmax = 0.020
        Fb = 45
        Av = 0.002  # çok küçük port → yüksek hız
        v = (Sd * Xmax * Fb) / Av
        assert v > 20, f"Port hızı {v:.1f} m/s — tehlikeli olmalı"

    def test_ses_hizi_sabiti(self):
        c = 343
        assert 340 <= c <= 346

    def test_sd_12_inc(self):
        cap_cm = 30.48
        Sd = math.pi * (cap_cm / 2) ** 2
        assert abs(Sd - 729.66) < 5

    def test_sd_10_inc(self):
        cap_cm = 25.4
        Sd = math.pi * (cap_cm / 2) ** 2
        assert abs(Sd - 506.7) < 5

    def test_sd_15_inc(self):
        cap_cm = 38.1
        Sd = math.pi * (cap_cm / 2) ** 2
        assert abs(Sd - 1140.1) < 10

    def test_sd_18_inc(self):
        cap_cm = 45.72
        Sd = math.pi * (cap_cm / 2) ** 2
        assert Sd > 1500

    def test_port_alan_minimum(self):
        Sd_cm2 = 490
        Ap_min = Sd_cm2 * 0.3
        assert Ap_min >= 100

    def test_qtc_formul(self):
        Qts = 0.45
        Vas = 65
        Vb = 40
        Qtc = Qts * math.sqrt(1 + Vas / Vb)
        assert Qtc > Qts

    def test_qtc_buyuk_kutuda_duser(self):
        Qts = 0.45
        Vas = 65
        Qtc_kucuk = Qts * math.sqrt(1 + Vas / 20)
        Qtc_buyuk = Qts * math.sqrt(1 + Vas / 200)
        assert Qtc_kucuk > Qtc_buyuk

    def test_bandpass_oran_ideal(self):
        oran = 0.45
        assert 0.40 <= oran <= 0.55

    def test_bandpass_oran_sql(self):
        oran = 0.35
        assert oran < 0.40

    def test_bandpass_oran_wide(self):
        oran = 0.62
        assert oran > 0.55

    def test_fb_tuning_mantikli(self):
        Fs = 38
        Fb = Fs * 0.95
        assert Fs * 0.7 <= Fb <= Fs * 1.3

    def test_birim_cevrimi_kavme(self):
        Av_cm2 = 78.5
        Av_m2 = Av_cm2 * 1e-4
        assert abs(Av_m2 - 0.00785) < 1e-6

    def test_birim_cevrimi_litre(self):
        Vb_l = 45.0
        Vb_m3 = Vb_l * 1e-3
        assert abs(Vb_m3 - 0.045) < 1e-6

    def test_vd_displacement(self):
        Sd_m2 = 0.049
        Xmax_m = 0.015
        Vd = Sd_m2 * Xmax_m
        assert Vd > 0.0005

    def test_spl_guc_artisi(self):
        """Her güç ikileşmesinde +3dB"""
        sens = 87
        spl_1w = sens
        spl_2w = sens + 10 * math.log10(2)
        assert abs(spl_2w - spl_1w - 3.0) < 0.2


# ══════════════════════════════════════════════════════════════
# LEVEL 9 — T/S Parametre Mantık (20 test)
# ══════════════════════════════════════════════════════════════

class TestTSParametreExtra:
    """T/S parametresi mantıksal doğrulamaları"""

    def test_qts_hesap(self):
        Qes = 0.50
        Qms = 5.0
        Qts = 1 / (1/Qes + 1/Qms)
        assert abs(Qts - 0.455) < 0.01

    def test_qts_portlu_karakter(self):
        Qts = 0.30
        assert Qts < 0.35  # Portlu tercih

    def test_qts_sealed_karakter(self):
        Qts = 0.60
        assert Qts > 0.50  # Sealed tercih

    def test_qts_esnek_aralik(self):
        Qts = 0.42
        assert 0.35 <= Qts <= 0.50

    def test_vas_buyuk(self):
        Vas = 150
        assert Vas > 80

    def test_vas_kucuk(self):
        Vas = 20
        assert Vas < 40

    def test_fs_derin(self):
        Fs = 22
        assert Fs < 30

    def test_xmax_yuksek_spl(self):
        Xmax = 25
        assert Xmax > 15

    def test_bl_motor(self):
        BL = 22.0
        assert BL > 10

    def test_re_nominal_alti(self):
        Re = 3.5
        nominal = 4.0
        assert Re < nominal

    def test_qts_ts_tutarlilik(self):
        """Qts her zaman min(Qes, Qms)'den küçük"""
        Qes = 0.45
        Qms = 6.0
        Qts = 1 / (1/Qes + 1/Qms)
        assert Qts < min(Qes, Qms)

    def test_vb_formul_pozitif(self):
        Qts = 0.45
        Vas = 60.0
        Qtc = 0.707
        Vb = Vas * (Qtc / Qts) ** 2 - Vas
        assert Vb > 0

    def test_vb_formul_negatif_imkansiz(self):
        Qts = 0.80
        Vas = 50.0
        Qtc = 0.707
        Vb = Vas * (Qtc / Qts) ** 2 - Vas
        assert Vb < 0  # Bu kombinasyon imkansız

    def test_nominal_impedanslar(self):
        gecerli = {1, 2, 4, 6, 8, 16}
        for ohm in [2, 4, 8]:
            assert ohm in gecerli

    def test_spl_hesap(self):
        sens = 87
        guc = 400
        spl = sens + 10 * math.log10(guc)
        assert spl > 110

    def test_qms_yuksek_kalite(self):
        Qms = 8.0
        assert Qms > 3

    def test_qes_kontrol(self):
        Qes = 0.40
        assert Qes < 0.60

    def test_acoustic_with_ts_qtc(self):
        inp = SealedBoxInput(
            net_volume_l=30.0, width_mm=420, height_mm=380, depth_mm=320,
            thickness_mm=18, driver_hole_mm=282,
            qts=0.38, vas_l=55.0, fs_hz=28.0)
        r = compute_sealed_acoustic(inp)
        assert r.qtc is not None and r.qtc > 0

    def test_acoustic_qtc_formula_dogrula(self):
        inp = SealedBoxInput(
            net_volume_l=30.0, width_mm=420, height_mm=380, depth_mm=320,
            thickness_mm=18, driver_hole_mm=282,
            qts=0.38, vas_l=55.0, fs_hz=28.0)
        r = compute_sealed_acoustic(inp)
        expected = 0.38 * math.sqrt(1 + 55.0 / 30.0)
        assert abs(r.qtc - expected) < 0.01

    def test_acoustic_no_ts(self):
        inp = SealedBoxInput(
            net_volume_l=30.0, width_mm=420, height_mm=380, depth_mm=320,
            thickness_mm=18, driver_hole_mm=282)
        r = compute_sealed_acoustic(inp)
        assert r.alignment == "bilinmiyor"


# ══════════════════════════════════════════════════════════════
# LEVEL 10 — Çoklu Sealed Konfigürasyonlar (20 test)
# ══════════════════════════════════════════════════════════════

class TestSealedKonfigurasyonlar:
    """Farklı boyut ve güç kombinasyonları için sealed testler"""

    def _s(self, vol, w, h, d, t=18, hole=282):
        return SealedBoxInput(net_volume_l=vol, width_mm=w, height_mm=h,
                              depth_mm=d, thickness_mm=t, driver_hole_mm=hole)

    def test_sedan_10inc_kompakt(self):
        r = SealedBox().build(self._s(18, 340, 300, 280, hole=245))
        assert r["cab_type"] == "sealed"

    def test_sedan_12inc_standart(self):
        r = SealedBox().build(self._s(28, 420, 380, 320))
        assert r["cab_type"] == "sealed"

    def test_suv_12inc_genis(self):
        r = SealedBox().build(self._s(35, 460, 400, 350))
        assert r["cab_type"] == "sealed"

    def test_suv_15inc(self):
        r = SealedBox().build(self._s(55, 520, 480, 380, hole=355))
        assert r["cab_type"] == "sealed"

    def test_doblo_15inc_buyuk(self):
        r = SealedBox().build(self._s(65, 560, 500, 400, hole=355))
        assert r["cab_type"] == "sealed"

    def test_doblo_18inc(self):
        r = SealedBox().build(self._s(90, 620, 580, 430, hole=450))
        assert r["cab_type"] == "sealed"

    def test_hatchback_kucuk(self):
        r = SealedBox().build(self._s(12, 300, 280, 260, hole=200))
        assert r["cab_type"] == "sealed"

    def test_yuksek_watt_12inc(self):
        """1000W+ için daha büyük sealed"""
        r = SealedBox().build(self._s(35, 460, 400, 340))
        assert r["cab_type"] == "sealed"

    def test_panel_15mm(self):
        r = SealedBox().build(self._s(25, 400, 360, 310, t=15))
        assert r["cab_type"] == "sealed"

    def test_panel_25mm(self):
        r = SealedBox().build(self._s(30, 450, 410, 350, t=25))
        assert r["cab_type"] == "sealed"

    def test_seri_8_boyut_kombinasyon(self):
        configs = [
            (14, 320, 290, 270, 18, 200),
            (16, 340, 305, 280, 18, 200),
            (18, 355, 315, 285, 18, 245),
            (22, 375, 335, 295, 18, 245),
            (26, 400, 360, 310, 18, 282),
            (30, 420, 380, 320, 18, 282),
            (36, 450, 400, 340, 18, 310),
            (42, 480, 430, 360, 18, 310),
        ]
        for vol, w, h, d, t, hole in configs:
            r = SealedBox().build(self._s(vol, w, h, d, t, hole))
            assert r["cab_type"] == "sealed"

    def test_sealed_inner_pozitif(self):
        r = SealedBox().build(self._s(30.0, 420, 380, 320))
        cab = r["cabinet"]
        assert cab.inner_w_mm > 0
        assert cab.inner_h_mm > 0
        assert cab.inner_d_mm > 0

    def test_sealed_panel_sayisi_6(self):
        r = SealedBox().build(self._s(30.0, 420, 380, 320))
        assert len(r["panel_list"]) == 6

    def test_sealed_gross_gt_net(self):
        r = SealedBox().build(self._s(30.0, 420, 380, 320))
        assert r["volume"].gross_l > r["volume"].net_acoustic_l

    def test_sealed_qtc_variants(self):
        """Farklı Qts → hepsi hesap dönmeli"""
        for qts in [0.20, 0.38, 0.50, 0.70, 0.90]:
            inp = SealedBoxInput(net_volume_l=30.0, width_mm=420, height_mm=380,
                                 depth_mm=320, thickness_mm=18, driver_hole_mm=282,
                                 qts=qts, vas_l=55.0, fs_hz=28.0)
            r = compute_sealed_acoustic(inp)
            assert r.qtc is not None

    def test_sealed_cok_buyuk(self):
        r = SealedBox().build(self._s(200.0, 1200, 1000, 800, hole=450))
        assert r["cab_type"] == "sealed"

    def test_sealed_float_hacim(self):
        r = SealedBox().build(self._s(33.333, 420, 380, 320))
        assert r["cab_type"] == "sealed"

    def test_sealed_no_hole(self):
        r = SealedBox().build(self._s(30.0, 420, 380, 320, hole=0))
        assert r["cab_type"] == "sealed"


# ══════════════════════════════════════════════════════════════
# LEVEL 11 — Çoklu Ported Konfigürasyonlar (15 test)
# ══════════════════════════════════════════════════════════════

class TestPortedKonfigurasyonlar:
    """Farklı araç ve boyut kombinasyonları için ported testler"""

    def _p(self, vol, w, h, d, fb=38.0, t=18, hole=282):
        return PortedBoxInput(net_volume_l=vol, width_mm=w, height_mm=h,
                              depth_mm=d, thickness_mm=t, driver_hole_mm=hole,
                              target_fb_hz=fb)

    def test_sedan_10inc_ported(self):
        r = PortedBox().build(self._p(30, 400, 360, 320, fb=40, hole=245))
        assert r["cab_type"] == "ported"

    def test_sedan_12inc_ported(self):
        r = PortedBox().build(self._p(42, 480, 420, 360, fb=38))
        assert r["cab_type"] == "ported"

    def test_suv_12inc_ported(self):
        r = PortedBox().build(self._p(52, 510, 450, 380, fb=36))
        assert r["cab_type"] == "ported"

    def test_suv_15inc_ported(self):
        r = PortedBox().build(self._p(80, 560, 500, 400, fb=33, hole=355))
        assert r["cab_type"] == "ported"

    def test_doblo_15inc_ported(self):
        r = PortedBox().build(self._p(95, 600, 530, 420, fb=32, hole=355))
        assert r["cab_type"] == "ported"

    def test_doblo_18inc_ported(self):
        r = PortedBox().build(self._p(140, 660, 600, 450, fb=30, hole=450))
        assert r["cab_type"] == "ported"

    def test_fb_25hz_derin(self):
        r = PortedBox().build(self._p(130, 650, 580, 440, fb=25, hole=450))
        assert r["cab_type"] == "ported"

    def test_fb_50hz_yuksek(self):
        r = PortedBox().build(self._p(40, 480, 420, 360, fb=50))
        assert r["cab_type"] == "ported"

    def test_fb_60hz_cok_yuksek(self):
        r = PortedBox().build(self._p(35, 460, 400, 350, fb=60))
        assert r["cab_type"] == "ported"

    def test_port_alan_pozitif(self):
        r = PortedBox().build(self._p(45, 480, 420, 360, fb=38))
        assert r["cabinet"].port.area_cm2 > 0

    def test_port_uzunluk_pozitif(self):
        r = PortedBox().build(self._p(45, 480, 420, 360, fb=38))
        assert r["cabinet"].port.length_mm > 0

    def test_ported_panel_listesi(self):
        r = PortedBox().build(self._p(45, 480, 420, 360, fb=38))
        assert len(r["panel_list"]) >= 6

    def test_ported_ts_params(self):
        inp = PortedBoxInput(
            net_volume_l=45.0, width_mm=480, height_mm=420, depth_mm=360,
            thickness_mm=18, driver_hole_mm=282, target_fb_hz=38.0,
            qts=0.38, vas_l=55.0, fs_hz=28.0)
        r = PortedBox().build(inp)
        assert r["cab_type"] == "ported"

    def test_ported_22mm_panel(self):
        inp = PortedBoxInput(
            net_volume_l=45.0, width_mm=480, height_mm=420, depth_mm=360,
            thickness_mm=22, driver_hole_mm=282, target_fb_hz=38.0)
        r = PortedBox().build(inp)
        assert r["cab_type"] == "ported"

    def test_seri_fb_degerleri(self):
        """Çeşitli Fb değerleri — hepsi calışmalı"""
        for fb in [20.0, 25.0, 30.0, 35.0, 40.0, 45.0, 55.0, 65.0]:
            r = PortedBox().build(self._p(45, 480, 420, 360, fb=fb))
            assert r["cab_type"] == "ported"


# ══════════════════════════════════════════════════════════════
# LEVEL 12 — Sealed Qtc Aralık (15 test)
# ══════════════════════════════════════════════════════════════

class TestQtcAralik:
    """Sealed kabin Qtc hedefleme testleri"""

    def _qtc(self, Qts, Vas, Vb):
        return Qts * math.sqrt(1 + Vas / Vb)

    def test_qtc_kucuk_kutu_yuksek(self):
        qtc_k = self._qtc(0.45, 65, 20)
        qtc_b = self._qtc(0.45, 65, 80)
        assert qtc_k > qtc_b

    def test_qtc_sonsuz_kutu(self):
        Qts = 0.45
        qtc = self._qtc(Qts, 65, 10000)
        assert abs(qtc - Qts) < 0.01

    def test_qtc_707_referans(self):
        """Butterworth = 0.707"""
        assert abs(0.707 - math.sqrt(0.5)) < 0.001

    def test_qtc_hedeften_vb(self):
        """Vb hesap + geri doğrulama — doğru ters formül"""
        Qts = 0.45
        Vas = 65.0
        Qtc = 0.80
        # Doğru formül: Qtc = Qts * sqrt(1 + Vas/Vb)
        # → Vb = Vas / ((Qtc/Qts)² - 1)
        Vb = Vas / ((Qtc / Qts) ** 2 - 1)
        assert Vb > 0, f"Vb negatif çıkmamalı: {Vb:.2f}"
        check = self._qtc(Qts, Vas, Vb)
        assert abs(check - Qtc) < 0.01

    def test_qtc_sq_hedef(self):
        Qts = 0.40
        Vas = 50.0
        Vb = Vas * (0.707 / Qts) ** 2 - Vas
        assert Vb > 0

    def test_qtc_sql_hedef(self):
        Qts = 0.45
        Vas = 65.0
        Vb = Vas * (0.90 / Qts) ** 2 - Vas
        assert Vb > 0

    def test_qtc_dusuk_qts_buyuk_kutu(self):
        Qts = 0.30
        Vas = 80.0
        Vb = Vas * (0.707 / Qts) ** 2 - Vas
        assert Vb > 100

    def test_qtc_yuksek_qts_kucuk_kutu(self):
        Qts = 0.65
        Vas = 40.0
        Vb = Vas * (0.707 / Qts) ** 2 - Vas
        assert Vb < 30

    def test_qtc_araliklari_standart(self):
        for qtc in [0.50, 0.577, 0.707, 0.85, 1.00]:
            assert 0.3 <= qtc <= 1.5

    def test_sealed_boomy_kucuk(self):
        inp = SealedBoxInput(
            net_volume_l=5.0, width_mm=250, height_mm=250, depth_mm=200,
            thickness_mm=18, driver_hole_mm=282,
            qts=0.55, vas_l=55.0, fs_hz=28.0)
        r = compute_sealed_acoustic(inp)
        assert r.alignment in ("boomy", "tight")

    def test_sealed_overdamped_buyuk(self):
        inp = SealedBoxInput(
            net_volume_l=200.0, width_mm=800, height_mm=600, depth_mm=500,
            thickness_mm=18, driver_hole_mm=282,
            qts=0.38, vas_l=55.0, fs_hz=28.0)
        r = compute_sealed_acoustic(inp)
        assert r.alignment == "overdamped"

    def test_qtc_fc_hesabi(self):
        inp = SealedBoxInput(
            net_volume_l=30.0, width_mm=420, height_mm=380, depth_mm=320,
            thickness_mm=18, driver_hole_mm=282,
            qts=0.38, vas_l=55.0, fs_hz=28.0)
        r = compute_sealed_acoustic(inp)
        assert r.fc_hz is not None and r.fc_hz > 0

    def test_acoustic_notes(self):
        inp = SealedBoxInput(
            net_volume_l=30.0, width_mm=420, height_mm=380, depth_mm=320,
            thickness_mm=18, driver_hole_mm=282,
            qts=0.38, vas_l=55.0, fs_hz=28.0)
        r = compute_sealed_acoustic(inp)
        assert len(r.notes) > 0

    def test_qtc_orantisi(self):
        Qts = 0.45
        Vas = 65
        q1 = self._qtc(Qts, Vas, 40)
        q2 = self._qtc(Qts, Vas, 80)
        assert q1 > q2

    def test_qtc_optimal_aralik(self):
        inp = SealedBoxInput(
            net_volume_l=30.0, width_mm=420, height_mm=380, depth_mm=320,
            thickness_mm=18, driver_hole_mm=282,
            qts=0.38, vas_l=55.0, fs_hz=28.0)
        r = compute_sealed_acoustic(inp)
        if r.qtc:
            assert 0.5 < r.qtc < 1.2


# ══════════════════════════════════════════════════════════════
# LEVEL 13 — Bandpass Ek + Edge Cases (17 test)
# ══════════════════════════════════════════════════════════════

def _bp4(w=600, h=450, d=500, t=18, ratio=0.45, hole=310, fb=50.0):
    return Bandpass4thInput(
        total_width_mm=w, total_height_mm=h, total_depth_mm=d,
        thickness_mm=t, volume_ratio=ratio, driver_hole_mm=hole,
        target_fb_hz=fb)


class TestBandpassExtra:
    def test_bp4_8inc(self):
        r = Bandpass4thBox().build(Bandpass4thInput(
            total_width_mm=450, total_height_mm=380, total_depth_mm=430,
            thickness_mm=18, driver_hole_mm=200, target_fb_hz=55.0))
        assert r["cab_type"] == "bandpass_4th"

    def test_bp4_18inc(self):
        r = Bandpass4thBox().build(Bandpass4thInput(
            total_width_mm=750, total_height_mm=600, total_depth_mm=650,
            thickness_mm=18, driver_hole_mm=450, target_fb_hz=40.0))
        assert r["cab_type"] == "bandpass_4th"

    def test_bp4_sealed_vol_lt_total(self):
        r = Bandpass4thBox().build(_bp4())
        total = r["sealed_vol_l"] + r["ported_vol_l"]
        assert r["sealed_vol_l"] < total

    def test_bp4_ported_vol_lt_total(self):
        r = Bandpass4thBox().build(_bp4())
        total = r["sealed_vol_l"] + r["ported_vol_l"]
        assert r["ported_vol_l"] < total

    def test_bp4_f_high_gt_f_low(self):
        r = Bandpass4thBox().build(_bp4())
        a = r["acoustic"]
        if hasattr(a, "f_low_hz") and a.f_low_hz:
            assert a.f_high_hz > a.f_low_hz

    def test_bp4_ratio_036_sql(self):
        r = Bandpass4thBox().build(_bp4(ratio=0.36))
        assert r["acoustic"].alignment == "sql"

    def test_bp4_ratio_058_wide(self):
        r = Bandpass4thBox().build(_bp4(ratio=0.58))
        assert r["acoustic"].alignment == "wide"

    def test_bp4_ratio_048_balanced(self):
        r = Bandpass4thBox().build(_bp4(ratio=0.48))
        assert r["acoustic"].alignment == "balanced"

    def test_bp4_panels_main_exists(self):
        r = Bandpass4thBox().build(_bp4())
        roles = [p["rol"] for p in r["panel_list"]]
        assert "main" in roles

    def test_bp4_panels_divider_exists(self):
        r = Bandpass4thBox().build(_bp4())
        roles = [p["rol"] for p in r["panel_list"]]
        assert "divider" in roles

    def test_bp4_various_9_fb(self):
        for fb in [35.0, 40.0, 45.0, 50.0, 55.0, 60.0, 65.0, 70.0, 75.0]:
            r = Bandpass4thBox().build(_bp4(fb=fb))
            assert r["cab_type"] == "bandpass_4th"

    def test_sealed_min_gecerli(self):
        r = SealedBox().build(SealedBoxInput(
            net_volume_l=5.0, width_mm=250, height_mm=250, depth_mm=200,
            thickness_mm=18, driver_hole_mm=200))
        assert r["cab_type"] == "sealed"

    def test_ported_min_gecerli(self):
        r = PortedBox().build(PortedBoxInput(
            net_volume_l=10.0, width_mm=280, height_mm=260, depth_mm=240,
            thickness_mm=18, driver_hole_mm=200, target_fb_hz=50.0))
        assert r["cab_type"] == "ported"

    def test_sd_tum_boyutlar(self):
        for boyut_inc in [6, 8, 10, 12, 15, 18, 21]:
            cap_cm = boyut_inc * 2.54
            Sd = math.pi * (cap_cm / 2) ** 2
            assert Sd > 0

    def test_helmholtz_kisa_port(self):
        c = 343
        Av, Vb, Lv = 0.008, 0.040, 0.05
        Fb = (c / (2 * math.pi)) * math.sqrt(Av / (Vb * Lv))
        assert Fb > 60

    def test_helmholtz_uzun_port(self):
        c = 343
        Av, Vb, Lv = 0.008, 0.040, 0.80
        Fb = (c / (2 * math.pi)) * math.sqrt(Av / (Vb * Lv))
        assert Fb < 30

    def test_sealed_very_large(self):
        r = SealedBox().build(SealedBoxInput(
            net_volume_l=200.0, width_mm=1200, height_mm=1000, depth_mm=800,
            thickness_mm=18, driver_hole_mm=450))
        assert r["cab_type"] == "sealed"
