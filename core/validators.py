"""
core/validators.py
DD1 Paket Doğrulayıcıları

Tek doğrulama merkezi — hiçbir ajan kendi içinde paket doğrulamaz.

Kurallar:
- validate_intake()   → IntakePacket eksik/hatalı mı?
- validate_acoustic() → AcousticDesignPacket fizik sınırları içinde mi?
- validate_production()→ ProductionPacket immutable alanları bozmuş mu?
- check_immutable()   → Hash karşılaştırması — Lazer Ajanı müdahalesi tespiti
"""
from __future__ import annotations
import logging
from dataclasses import dataclass, field
from typing import Optional

from schemas.intake_packet import IntakePacket
from schemas.acoustic_design_packet import AcousticDesignPacket
from schemas.production_packet import ProductionPacket

logger = logging.getLogger("dd1.validators")


# ── AcousticIntegrityError ────────────────────────────────────────────────────

class AcousticIntegrityError(Exception):
    """
    Lazer Ajanı'nın kilitli akustik alanı değiştirmeye çalıştığında fırlatılır.
    
    Özellikler:
      design_id   : hangi tasarım
      field       : hangi kilitli alan
      original    : orijinal değer
      modified    : hatalı değer
      message     : kullanıcıya gösterilecek sade mesaj
    """
    def __init__(
        self,
        design_id: str,
        field: str,
        original,
        modified,
    ):
        self.design_id  = design_id
        self.field      = field
        self.original   = original
        self.modified   = modified
        self.user_msg   = (
            f"Akustik veri bütünlük hatası: '{field}' alanı üretim aşamasında "
            f"değiştirilemez.\nOrijinal: {original}  →  Hatalı: {modified}"
        )
        super().__init__(self.user_msg)
        logger.error(
            "[ACOUSTIC_INTEGRITY] design=%s field='%s' original=%s modified=%s",
            design_id, field, original, modified,
        )



@dataclass
class ValidationResult:
    passed:   bool = True
    errors:   list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def add_error(self, msg: str) -> None:
        self.errors.append(msg)
        self.passed = False

    def add_warning(self, msg: str) -> None:
        self.warnings.append(msg)

    def user_message(self) -> str:
        """Kullanıcıya gösterilecek sade hata mesajı."""
        if not self.errors:
            return ""
        return "⚠ Şu sorunlar tespit edildi:\n" + "\n".join(f"  • {e}" for e in self.errors)


# ── 1. IntakePacket Doğrulama ─────────────────────────────────────────────────

def validate_intake(packet: IntakePacket) -> ValidationResult:
    r = ValidationResult()

    if packet.diameter_inch < 5 or packet.diameter_inch > 24:
        r.add_error(f"Woofer çapı ({packet.diameter_inch}\") geçersiz aralık: 5–24 inç")

    if packet.rms_power < 50:
        r.add_error(f"RMS güç ({packet.rms_power}W) çok düşük — minimum 50W")

    if packet.vehicle.strip() == "":
        r.add_error("Araç tipi boş olamaz")

    if packet.purpose not in ("SQL", "SPL", "LowBass", "Daily"):
        r.add_warning(f"Bilinmeyen kullanım amacı: {packet.purpose} — varsayılan SQL kullanılacak")

    if packet.has_ts_params and packet.ts_params is None:
        r.add_error("has_ts_params=True ama ts_params yok")

    if packet.ts_params:
        ts = packet.ts_params
        if ts.fs is not None and not (10 <= ts.fs <= 200):
            r.add_error(f"Fs={ts.fs} Hz aralık dışı (10–200 Hz)")
        if ts.qts is not None and not (0.1 <= ts.qts <= 2.0):
            r.add_error(f"Qts={ts.qts} aralık dışı (0.1–2.0)")
        if ts.vas is not None and not (1 <= ts.vas <= 500):
            r.add_error(f"Vas={ts.vas}L aralık dışı (1–500 L)")

    if r.passed:
        logger.debug("[VAL-INTAKE] %s → PASS", packet.intake_id)
    else:
        logger.warning("[VAL-INTAKE] %s → FAIL: %s", packet.intake_id, r.errors)
    return r


# ── 2. AcousticDesignPacket Doğrulama ────────────────────────────────────────

# Fiziksel sınırlar
_VOL_LIMITS  = {"min": 5.0, "max": 600.0}
_PORT_VEL    = {"warn": 17.0, "max": 25.0}  # m/s
_TUNING_LIMS = {"min": 15.0, "max": 120.0}

def validate_acoustic(packet: AcousticDesignPacket) -> ValidationResult:
    r = ValidationResult()

    if not (_VOL_LIMITS["min"] <= packet.net_volume_l <= _VOL_LIMITS["max"]):
        r.add_error(
            f"Net hacim {packet.net_volume_l}L sınır dışı "
            f"({_VOL_LIMITS['min']}–{_VOL_LIMITS['max']}L)"
        )

    if not (_TUNING_LIMS["min"] <= packet.tuning_hz <= _TUNING_LIMS["max"]):
        r.add_error(
            f"Tuning {packet.tuning_hz}Hz sınır dışı "
            f"({_TUNING_LIMS['min']}–{_TUNING_LIMS['max']}Hz)"
        )

    enc_type_str = getattr(packet.enclosure_type, "value", str(packet.enclosure_type))
    if enc_type_str != "sealed":
        if packet.port_area_cm2 < 10:
            r.add_error(f"Port alanı {packet.port_area_cm2:.1f}cm² çok küçük (min 10cm²)")

        if packet.port_length_cm < 1:
            r.add_error(f"Port boyu {packet.port_length_cm:.1f}cm çok kısa")

        if 0 < packet.port_velocity_ms < _PORT_VEL["max"]:
            if packet.port_velocity_ms > _PORT_VEL["warn"]:
                r.add_warning(
                    f"Port hızı {packet.port_velocity_ms:.1f}m/s yüksek — türbülans riski"
                )
        elif packet.port_velocity_ms >= _PORT_VEL["max"]:
            r.add_error(f"Port hızı {packet.port_velocity_ms:.1f}m/s kritik sınırı aştı (>{_PORT_VEL['max']}m/s)")

    if not packet.validation_passed:
        r.add_warning("Paket kendi içinde validation_passed=False işaretlemiş")

    if r.passed:
        logger.debug("[VAL-ACOUSTIC] %s → PASS", packet.design_id)
    else:
        logger.warning("[VAL-ACOUSTIC] %s → FAIL: %s", packet.design_id, r.errors)
    return r


# ── 3. Immutable Kontrolü — Lazer Müdahale Tespiti ───────────────────────────

def check_immutable(
    original: AcousticDesignPacket,
    production: ProductionPacket,
) -> ValidationResult:
    """
    ProductionPacket içindeki acoustic_fingerprint'i
    orijinal AcousticDesignPacket ile karşılaştırır.
    Herhangi bir fark → hata kodu.
    """
    r = ValidationResult()
    orig_fp = original.immutable_fingerprint()
    prod_fp = production.acoustic_fingerprint

    if not prod_fp:
        r.add_error("ProductionPacket.acoustic_fingerprint boş — handoff yapılmamış")
        return r

    for key in orig_fp:
        orig_val = orig_fp[key]
        prod_val = prod_fp.get(key)
        if prod_val is None:
            r.add_error(f"fingerprint['{key}'] eksik ProductionPacket'te")
        elif abs(float(orig_val) - float(prod_val)) > 0.001 if isinstance(orig_val, float) else orig_val != prod_val:
            r.add_error(
                f"KİLİTLİ ALAN DEĞİŞTİRİLDİ: '{key}' "
                f"orijinal={orig_val} → üretim={prod_val}"
            )

    if not r.passed:
        logger.error(
            "[VAL-IMMUTABLE] %s → BÜTÜNLÜK İHLALİ! %s",
            original.design_id, r.errors
        )
    else:
        # Production validation güncelle
        production.validation["immutable_check"] = True
        logger.debug("[VAL-IMMUTABLE] %s → OK", original.design_id)

    return r


# ── 4. ProductionPacket Genel Doğrulama ──────────────────────────────────────

def validate_production(
    production: ProductionPacket,
    acoustic: Optional[AcousticDesignPacket] = None,
) -> ValidationResult:
    r = ValidationResult()

    if not production.design_id:
        r.add_error("design_id boş — akustik paket bağlantısı yok")

    if not production.acoustic_fingerprint:
        r.add_error("acoustic_fingerprint eksik")

    if acoustic:
        immutable_r = check_immutable(acoustic, production)
        r.errors.extend(immutable_r.errors)
        r.warnings.extend(immutable_r.warnings)
        if immutable_r.errors:
            r.passed = False

    if production.material_thickness_mm < 6:
        r.add_warning("Malzeme kalınlığı <6mm — dayanıklılık riski")

    if r.passed:
        production.validation["volume_ok"] = True
        production.validation["port_ok"]   = True
        logger.debug("[VAL-PROD] %s → PASS", production.production_id)
    else:
        logger.error("[VAL-PROD] %s → FAIL: %s", production.production_id, r.errors)

    return r


# ── 5. PhysicalFitValidator ────────────────────────────────────────────────────

@dataclass
class FitCheckResult:
    """Tek fiziksel kontrol sonucu."""
    name:    str
    passed:  bool
    value:   float        # ölçülen değer (mm)
    limit:   float        # eşik (mm)
    note:    str = ""

    def summary(self) -> str:
        icon = "✅" if self.passed else "❌"
        return f"{icon} {self.name}: {self.value:.1f}mm (limit: {self.limit:.1f}mm){' — '+self.note if self.note else ''}"


@dataclass
class FitValidationResult:
    """
    5 fiziksel kontrol sonucu + özet.
    fit_passed=True yalnızca tüm kontroller geçerse.
    """
    checks:      list[FitCheckResult] = field(default_factory=list)
    fit_passed:  bool = True
    summary_str: str = ""

    def add_check(self, chk: FitCheckResult) -> None:
        self.checks.append(chk)
        if not chk.passed:
            self.fit_passed = False

    def build_summary(self) -> None:
        if self.fit_passed:
            self.summary_str = "✅ Tüm fiziksel kontroller geçti."
        else:
            failed = [c for c in self.checks if not c.passed]
            self.summary_str = "❌ " + "; ".join(c.name for c in failed) + " — üretim engellenebilir."

    def to_dict(self) -> dict:
        return {
            "fit_passed":  self.fit_passed,
            "summary":     self.summary_str,
            "checks":      [
                {
                    "name": c.name, "passed": c.passed,
                    "value_mm": round(c.value, 2),
                    "limit_mm": round(c.limit, 2),
                    "note": c.note,
                }
                for c in self.checks
            ],
        }


# Standart toleranslar (mm) — exact driver verisi yoksa bu tabloya düşülür
_FIT_DEFAULTS = {
    "mounting_depth_clearance_mm": 15.0,   # arka duvara min mesafe
    "magnet_clearance_mm":          10.0,   # port / iç duvara min mesafe
    "driver_port_gap_mm":            20.0,  # sürücü çevresi ile port ağzı arası
    "cutout_tolerance_mm":            2.0,  # baffle delik toleransı
}


def evaluate_physical_fit(
    diameter_inch:       float,
    panel_thickness_mm:  float,
    inner_w_mm:          float,
    inner_h_mm:          float,
    inner_d_mm:          float,
    port_area_cm2:       float,
    port_type:           str = "slot",
    mounting_depth_mm:   Optional[float] = None,  # exact driver verisi
    magnet_dia_mm:       Optional[float] = None,  # exact driver verisi
) -> FitValidationResult:
    """
    5 fiziksel kontrol:
      1. Cutout diameter check
      2. Mounting depth check
      3. Magnet clearance
      4. Driver-to-port interference
      5. Driver-to-back-wall clearance

    Exact driver verisi yoksa standart profil kullanılır (conservative).
    """
    result = FitValidationResult()

    # ── Türetilmiş değerler ──────────────────────────────────────────────────
    cutout_dia_mm    = (diameter_inch - 0.375) * 25.4          # standart kesim çapı
    woofer_outer_mm  = diameter_inch * 25.4                     # nominal dış çap
    cone_radius_mm   = cutout_dia_mm / 2.0
    est_mounting_d   = mounting_depth_mm or (diameter_inch * 7.5)   # tahmin: 7.5mm/inç
    est_magnet_d     = magnet_dia_mm     or (woofer_outer_mm * 0.65) # tahmin: %65

    # ── 1. Cutout diameter — baffl genişliğine sığıyor mu? ──────────────────
    cutout_margin = inner_w_mm - cutout_dia_mm - 2 * panel_thickness_mm
    chk1 = FitCheckResult(
        name="Montaj Açma Çapı",
        passed=cutout_margin >= _FIT_DEFAULTS["cutout_tolerance_mm"],
        value=cutout_dia_mm,
        limit=inner_w_mm - 2 * panel_thickness_mm,
        note=f"kenar boşluğu: {cutout_margin:.1f}mm" if cutout_margin < 20 else "",
    )
    result.add_check(chk1)

    # ── 2. Mounting depth — arka duvara yeterli boşluk var mı? ─────────────
    back_clearance = inner_d_mm - est_mounting_d
    chk2 = FitCheckResult(
        name="Sürücü Derinliği",
        passed=back_clearance >= _FIT_DEFAULTS["mounting_depth_clearance_mm"],
        value=back_clearance,
        limit=_FIT_DEFAULTS["mounting_depth_clearance_mm"],
        note=f"sürücü derinliği ~{est_mounting_d:.0f}mm",
    )
    result.add_check(chk2)

    # ── 3. Magnet clearance — porta / iç duvara çarpar mı? ─────────────────
    magnet_margin = (inner_w_mm / 2.0) - (est_magnet_d / 2.0)
    chk3 = FitCheckResult(
        name="Mıknatıs Alanı",
        passed=magnet_margin >= _FIT_DEFAULTS["magnet_clearance_mm"],
        value=magnet_margin,
        limit=_FIT_DEFAULTS["magnet_clearance_mm"],
        note=f"mıknatıs çapı ~{est_magnet_d:.0f}mm",
    )
    result.add_check(chk3)

    # ── 4. Driver-to-port interference ──────────────────────────────────────
    # Port alanından türetilen etkin port genişliği (slot varsayımı)
    slot_h_mm      = 50.0  # slot yüksekliği varsayım
    slot_w_mm      = (port_area_cm2 * 100.0) / slot_h_mm   # cm² → mm²
    center_offset  = cone_radius_mm + slot_w_mm / 2.0
    driver_port_gap = inner_w_mm / 2.0 - center_offset
    chk4 = FitCheckResult(
        name="Port Çakışması",
        passed=driver_port_gap >= _FIT_DEFAULTS["driver_port_gap_mm"],
        value=driver_port_gap,
        limit=_FIT_DEFAULTS["driver_port_gap_mm"],
        note=f"slot ~{slot_w_mm:.0f}mm gen.",
    )
    result.add_check(chk4)

    # ── 5. Driver-to-back-wall clearance ────────────────────────────────────
    magnet_back = inner_d_mm - est_mounting_d
    chk5 = FitCheckResult(
        name="Arka Duvar Mesafesi",
        passed=magnet_back >= _FIT_DEFAULTS["mounting_depth_clearance_mm"],
        value=magnet_back,
        limit=_FIT_DEFAULTS["mounting_depth_clearance_mm"],
        note="mıknatıs arka duvara mesafe",
    )
    result.add_check(chk5)

    result.build_summary()
    logger.debug(
        "[FIT-VAL] diameter=%.1f\" -> %s | checks=%s",
        diameter_inch,
        "PASS" if result.fit_passed else "FAIL",
        [c.name for c in result.checks if not c.passed],
    )
    return result


DELTA_YELLOW_PCT = 2.0
DELTA_GREEN_PCT  = 1.0   # <= %1 -> yesil


def compute_warning_level(
    acoustic_delta_pct: float,
    fit_status: str,         # "ok" | "warning" | "fail"
    production_ready: bool,
) -> str:
    """
    SOURCE OF TRUTH: warning_level icin.
    KURAL: Presenter bu degeri HESAPLAMAZ, sadece import eder.

    red_block  -> port sigmıyor (fail) VEYA delta > DELTA_YELLOW_PCT
    yellow     -> delta <= DELTA_YELLOW_PCT (fiziksel mumkun ama sapma var)
    green      -> delta <= DELTA_GREEN_PCT VE fit ok VE production_ready
    """
    if fit_status == "fail" or acoustic_delta_pct > DELTA_YELLOW_PCT:
        return "red_block"
    if acoustic_delta_pct > DELTA_GREEN_PCT:
        return "yellow"
    if production_ready:
        return "green"
    return "yellow"


def evaluate_production_ready(opt: dict) -> tuple[bool, list[str]]:
    """
    production_ready = True ANCAK tüm koşullar sağlanırsa:
      1. exact_driver_name mevcut (boş değil)
      2. ts_source mevcut (boş değil)
      3. ts_confidence yeterli (≥0.5) VEYA driver_source == "manual"
      4. port geometry tam (port_area_cm2 > 0)
      5. fit_validation geçti (fit_status != "fail")
      6. panel_list üretildi (boş değil) — yoksa uyarı, engel değil
      7. acoustic_delta_pct ≤ DELTA_YELLOW_PCT (%2)

    Döner: (production_ready: bool, failed_conditions: list[str])
    """
    failed: list[str] = []

    if not opt.get("exact_driver_name", "").strip():
        failed.append("Hoparlör tam modeli netleşmedi")

    if not opt.get("ts_source", "").strip():
        failed.append("Akustik (T/S) parametre kaynağı doğrulanamadı")

    ts_conf    = opt.get("ts_confidence", 0.0)
    drv_source = opt.get("driver_source", "")
    if drv_source != "manual" and ts_conf < 0.5:
        failed.append(f"Hoparlör verilerinin doğruluğu şüpheli (güven skoru: {ts_conf:.2f}), manuel onay lazım")

    if opt.get("port_area_cm2", 0.0) <= 0:
        failed.append("Port (havalandırma) alanı hesaplanamadı")

    if opt.get("fit_status", "ok") == "fail":
        failed.append("Kabin iç fiziksel ölçüleri yetersiz (hoparlör sığmıyor)")

    panel_list = opt.get("panel_list", [])
    if not panel_list:
        logger.debug("[PROD-READY] panel_list boş — üretim paketine dahil edilmeyecek")

    delta = opt.get("acoustic_delta_pct", 0.0)
    if delta > DELTA_YELLOW_PCT:
        failed.append(f"Akustik hacim sapması (%{delta:.1f}) izin verilen sınırı ({DELTA_YELLOW_PCT}%) aşıyor")

    pr = len(failed) == 0
    if not pr:
        logger.debug("[PROD-READY] FAIL: %s", failed)
    return pr, failed
