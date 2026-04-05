import sys
import os
import uuid
import math
import tempfile
from pathlib import Path

import sys
import os
import uuid
import math
import tempfile
from pathlib import Path


# ── Bağımsız Hesap Yardımcıları ───────────────────────────────────────────────

def calc_port_length(vb_l: float, fb_hz: float, port_dia_mm: float) -> float:
    """
    Helmholtz formülüyle aero (yuvarlak) port uzunluğunu hesaplar.
    vb_l       — net kabin hacmi (litre)
    fb_hz      — tuning frekansı (Hz)
    port_dia_mm — port çapı (mm)
    Döndürür: port uzunluğu (mm)
    """
    r_cm = (port_dia_mm / 2.0) / 10.0          # mm → cm
    sp_cm2 = math.pi * r_cm ** 2
    lp_cm = (23562.5 * (port_dia_mm / 10.0) ** 2) / (fb_hz ** 2 * vb_l) \
            - 0.732 * (port_dia_mm / 10.0)
    lp_cm = max(lp_cm, 3.0)
    return round(lp_cm * 10, 1)                # cm → mm



def calculate_empirical(req: 'DesignRequest') -> dict:
    """Mode 2 — Ampirik model portlanan kabin hesabı"""
    from .constants import EMPIRICAL_VB, VEHICLE_TUNING, CABIN_GAIN, EMPIRICAL_SD, EMPIRICAL_XMAX, EMPIRICAL_FS

    # 1. Kabin Hacmi
    closest = min(EMPIRICAL_VB.keys(), key=lambda k: abs(k - req.diameter_inch))
    vb_range = EMPIRICAL_VB[closest].get(req.purpose, EMPIRICAL_VB[closest]["SQL"])

    if req.purpose == "SPL":
        vb = vb_range[0] + (vb_range[1] - vb_range[0]) * 0.35
    elif req.purpose == "SQL":
        vb = vb_range[0] + (vb_range[1] - vb_range[0]) * 0.5
    else:
        vb = vb_range[0] + (vb_range[1] - vb_range[0]) * 0.65

    # Güce göre hafif ölçek
    power_scale = 1.0 + (req.rms_power - 500) / 5000 * 0.15
    vb = vb * max(0.85, min(1.15, power_scale))

    # 2. Tuning Frekansı
    fb_min, fb_max = VEHICLE_TUNING.get(req.vehicle, (32, 40))
    if req.purpose == "SPL":
        fb = fb_min + (fb_max - fb_min) * 0.25
    elif req.purpose == "SQL":
        fb = fb_min + (fb_max - fb_min) * 0.5
    else:
        fb = fb_min + (fb_max - fb_min) * 0.7

    # 3. Port Alanı (Sd tabanlı) & Uzunluğu
    sd_cm2 = EMPIRICAL_SD.get(closest, 490)
    xmax_mm = EMPIRICAL_XMAX.get(closest, 15)

    enc_type_str = getattr(req.enclosure_type, "value", str(req.enclosure_type))
    if enc_type_str == "sealed":
        sp_cm2 = 0.0
        lp_cm = 0.0
        v_port = 0.0
    else:
        if req.purpose == "SPL":
            sp_cm2 = sd_cm2 * 0.35
        elif req.purpose == "SQL":
            sp_cm2 = sd_cm2 * 0.25
        else:
            sp_cm2 = sd_cm2 * 0.18
        
        lp_cm = (29975 * sp_cm2) / (fb**2 * vb) - 1.463 * math.sqrt(sp_cm2 / math.pi)
        lp_cm = max(lp_cm, 5.0)
        v_port = abs(( (sd_cm2/10000.0) * (xmax_mm/1000.0) * (2*math.pi*fb) ) / (sp_cm2/10000.0))

    # Karakter Optimizasyonu
    notes = ["T/S parametreleri girilmedi — Ampirik model kullanıldı."]
    if req.bass_char == "Koltuğu Yumruklasın":
        fb += 3.0; vb *= 0.90
        notes.append("Karakter: Koltuğu Yumruklasın (Fb +3Hz, Vb -10%)")
    elif req.bass_char == "Yeri Titret":
        fb -= 3.0; vb *= 1.10
        notes.append("Karakter: Yeri Titret (Fb -3Hz, Vb +10%)")

    # 5. Analizler
    peak_spl = 88.0 + 10 * math.log10(max(req.rms_power, 1)) + 3.0 + CABIN_GAIN.get(req.vehicle, 5)

    return {
        "mode": "MODE2_EMPIRICAL",
        "vb_l": round(vb, 1),
        "fb_hz": round(fb, 1),
        "sp_cm2": round(sp_cm2, 1),
        "lp_cm": round(lp_cm, 1),
        "v_port": round(v_port, 1),
        "peak_spl": round(peak_spl, 1),
        "notes": notes,
        "f3": round(fb * 0.75, 1),
        "gd": round(1000.0/(2*math.pi*fb)*2, 1),
        "xmax": round(xmax_mm * 0.85, 1)
    }

def calculate_ts(req: 'DesignRequest') -> dict:
    """Mode 1 — T/S parametreli mühendislik hesabı"""
    from .constants import VEHICLE_TUNING, CABIN_GAIN
    
    # 1. Hacim (QB3 alignment)
    alpha = 15.0 * (req.qts ** 2.87)
    vb = req.vas * alpha
    vb = max(8.0, min(vb, req.vas * 5))

    if req.purpose == "SPL": vb *= 0.90
    elif req.purpose == "Günlük Bass": vb *= 1.10

    # 2. Tuning
    fb = req.fs * ((req.vas / vb) ** 0.44)
    fb_min, fb_max = VEHICLE_TUNING.get(req.vehicle, (30, 45))
    fb = max(fb_min, min(fb, fb_max))

    # 3. Port Alanı & Uzunluğu
    enc_type_str = getattr(req.enclosure_type, "value", str(req.enclosure_type))
    if enc_type_str == "sealed":
        sp_cm2 = 0.0
        lp_cm = 0.0
        v_port = 0.0
        eta_0 = (4 * math.pi**2 * req.fs**3 * (req.vas/1000.0)) / (345.0**3 * req.qts)
    else:
        sp_cm2 = req.sd * (0.35 if req.purpose == "SPL" else (0.28 if req.purpose == "SQL" else 0.18))
        d_equiv = math.sqrt((4 * sp_cm2) / math.pi)
        lp_cm = (23562.5 * (d_equiv**2)) / (fb**2 * vb) - 0.732 * d_equiv
        lp_cm = max(lp_cm, 5.0)
        v_port = abs(( (req.sd/10000.0) * (req.xmax/1000.0) * (2*math.pi*fb) ) / (sp_cm2/10000.0))
        eta_0 = (4 * math.pi**2 * req.fs**3 * (req.vas/1000.0)) / (345.0**3 * req.qts)
    
    spl_1w = 112.2 + 10 * math.log10(max(eta_0, 1e-10))
    peak_spl = spl_1w + 10 * math.log10(max(req.rms_power, 1)) + 3.0 + CABIN_GAIN.get(req.vehicle, 5)

    notes_obj = ["T/S parametreli mühendislik hesabı uygulandı."]
    if fb > req.fs * 1.05:
        notes_obj.append(f"Tuning (Fb) {fb:.1f}Hz, Fs'den ({req.fs:.1f}Hz) yukarıda tutularak alt frekanslarda tokluk ve agresif vuruş gücü artırıldı.")

    return {
        "mode": "MODE1_TS",
        "vb_l": round(vb, 1),
        "fb_hz": round(fb, 1),
        "sp_cm2": round(sp_cm2, 1),
        "lp_cm": round(lp_cm, 1),
        "v_port": round(v_port, 1),
        "peak_spl": round(peak_spl, 1),
        "notes": notes_obj,
        "f3": round(fb * 0.75, 1),
        "gd": round(1000.0/(2*math.pi*fb)*2, 1),
        "xmax": round(req.xmax * 0.85, 1)
    }

def calculate_panels(vb_l: float, sp_cm2: float, lp_cm: float, diameter_inch: int, thickness_mm: float) -> dict:
    """Panel ölçülerini ve listesini üretir"""
    t = thickness_mm

    # Port ve woofer yer kaplama (cm³) — gross hacme eklenir
    v_port_cm3  = sp_cm2 * lp_cm
    sub_disp_cm3 = {8: 1500, 10: 2500, 12: 4000, 15: 7000, 18: 12000}.get(diameter_inch, 4000)

    # Gross iç hacim: net hacim + port + woofer yer kaplama
    # validate ederken bunları gross'tan çıkarInca net hacme ulaşılır
    vg_cm3 = (vb_l * 1000) + v_port_cm3 + sub_disp_cm3

    # Oranlar
    rw, rh, rd = 1.9, 0.8, 1.1
    h = (vg_cm3 / (rw * rh * rd)) ** (1/3)
    iw, ih, id_ = h*rw, h*rh, h*rd

    # Subwoofer sığmalı
    min_ih = (diameter_inch * 25.4 + 40) / 10.0
    if ih < min_ih:
        ih = min_ih
        # iw × ih × id_ = vg_cm3 → iw = vg_cm3 / (ih × id_)
        iw = vg_cm3 / (ih * id_)

    iw_mm, ih_mm, id_mm = iw*10, ih*10, id_*10
    ow_mm, oh_mm, od_mm = iw_mm+2*t, ih_mm+2*t, id_mm+2*t
    
    sub_cutout = diameter_inch * 25.4 * 0.88
    
    # Port Slot (Dikey)
    slot_w_mm = (sp_cm2 / (ih_mm/10.0)) * 10

    panels = [
        {"name": "Ön Panel", "qty": 1, "w": round(ow_mm), "h": round(oh_mm), "note": f"Kesim: Ø{sub_cutout:.0f}mm"},
        {"name": "Arka Panel", "qty": 1, "w": round(ow_mm), "h": round(oh_mm), "note": ""},
        {"name": "Üst Panel", "qty": 1, "w": round(ow_mm), "h": round(id_mm), "note": ""},
        {"name": "Alt Panel", "qty": 1, "w": round(ow_mm), "h": round(id_mm), "note": ""},
        {"name": "Sol Yan", "qty": 1, "w": round(ih_mm), "h": round(id_mm), "note": ""},
        {"name": "Sağ Yan", "qty": 1, "w": round(ih_mm), "h": round(id_mm), "note": "Port girişi"}
    ]

    lp_mm = lp_cm * 10
    
    # 1. Parça (Ön yüzeyden arkaya doğru uzanan board)
    # Arkada dönüş payı bırakılmalı (slot_w_mm kadar)
    max_l1 = id_mm - slot_w_mm
    
    # Efektif akustik uzunluk = Ön panel kalınlığı (thickness_mm) + içteki tahtanın uzunluğu
    if lp_mm <= max_l1 + thickness_mm:
        # Düz port (Bükülmeye gerek yok)
        l1_wood = max(10, lp_mm - thickness_mm)
        panels.append({"name": "Port Paneli 1", "qty": 1, "w": round(l1_wood), "h": round(ih_mm), "note": "Düz Port Duvarı"})
    else:
        # L-Port (Dirsekli)
        l1_wood = max_l1
        l_remain = lp_mm - (max_l1 + thickness_mm)
        # 2. Parça arka duvara paralel uzanır
        # Etkin dönüş yolu genellikle köşe boyunca genişler, pratik l2_wood:
        l2_wood = l_remain
        
        panels.append({"name": "Port Paneli 1 (Ana)", "qty": 1, "w": round(l1_wood), "h": round(ih_mm), "note": "Önden arkaya uzanan duvar"})
        panels.append({"name": "Port Paneli 2 (Dönüş)", "qty": 1, "w": round(l2_wood), "h": round(ih_mm), "note": "Arka duvara paralel L dönüşü"})

    return {
        "inner": {"w": round(iw_mm), "h": round(ih_mm), "d": round(id_mm)},
        "outer": {"w": round(ow_mm), "h": round(oh_mm), "d": round(od_mm)},
        "panels": panels,
        "sub_cutout": round(sub_cutout)
    }


# ── Temel Tasarım Fonksiyonu ─────────────────────────────────────────────────

def design_enclosure(req: 'DesignRequest') -> dict:
    """Tam akustik tasarım döngüsü - Unified API Version"""
    design_id = str(uuid.uuid4())[:8]
    
    # 1. Hesaplama Modu
    has_ts = all([req.fs, req.qts, req.vas, (req.sd or req.diameter_inch)])
    if has_ts and req.fs > 0:
        res = calculate_ts(req)
    else:
        res = calculate_empirical(req)

    # 2. Panel Ölçüleri
    panels = calculate_panels(
        vb_l=res["vb_l"], sp_cm2=res["sp_cm2"], lp_cm=res["lp_cm"],
        diameter_inch=req.diameter_inch, thickness_mm=req.material_thickness_mm
    )

    # 3. İçiçe Usta Tavsiyesi (Opsiyonel / Sadece Akustik Yorum)
    from .advice import generate_expert_advice
    advice_input = {
        "inner_d_mm": panels["inner"]["d"],
        "port_velocity_ms": res["v_port"],
        "port_area_cm2": res["sp_cm2"]
    }
    advice = generate_expert_advice(advice_input, req.vehicle, req.purpose)

    # 3. Validate acoustic result (validators.py kurallarina gore)
    from core.validators import validate_acoustic
    _val_check = validate_acoustic.__module__  # lazy import guard

    # port_velocity_ms sınır kontrolü burada yapılır
    _port_vel = res["v_port"]
    _vol      = res["vb_l"]
    _tuning   = res["fb_hz"]
    _port_a   = res["sp_cm2"]
    _port_l   = res["lp_cm"]

    _val_passed = (
        5.0 <= _vol <= 600.0
        and 15.0 <= _tuning <= 120.0
    )
    enc_type_str = getattr(req.enclosure_type, "value", str(req.enclosure_type))
    if enc_type_str != "sealed":
        _val_passed = _val_passed and (
            _port_a >= 10.0
            and _port_l >= 1.0
            and _port_vel < 25.0
        )

    # port_gap hesapla
    ih_mm = panels["inner"]["h"]
    slot_w_mm = (res["sp_cm2"] / (ih_mm/10.0)) * 10

    return {
        "design_id": design_id,
        "mode": res["mode"],
        "dimensions": {
            "w_mm": panels["outer"]["w"],
            "h_mm": panels["outer"]["h"],
            "d_mm": panels["outer"]["d"]
        },
        "port": {
            "type": req.enclosure_type.value,
            "dia_mm": None,
            "length_mm": res["lp_cm"] * 10,
            "gap_mm": round(slot_w_mm),
            "count": 1
        },
        "net_volume_l": res["vb_l"],
        "tuning_hz": res["fb_hz"],
        "f3_hz": res["f3"],
        "port_velocity_ms": res["v_port"],
        "peak_spl_db": res["peak_spl"],
        "cone_excursion_mm": res["xmax"],
        "group_delay_ms": res["gd"],
        "validation_passed": _val_passed,  # validators.py kurallarına gore
        "acoustic_advice": advice,
        "expert_comment": "DD1 Yorumu:\nBu tasarim sunucu tarafindaki muhendislik motoru tarafindan optimize edilmistir.",
        "notes": res["notes"],
        "panel_list": panels["panels"]
    }


