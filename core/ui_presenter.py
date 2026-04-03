"""
core/ui_presenter.py
DD1 Dijital Atölye — UI Presenter Katmanı

GÖREV:
  ConflictReport → kullanıcı arayüzü için normalize edilmiş veri paketi.
  Tarayıcı/istemci bu modülü tüketir; teknik iç modelleri doğrudan bilmez.

ZORUNLU ÇIKTI ALANLARI (kilitli sözleşme):
  UIDesignPresenter:
    design_id, selected_option_id, production_ready,
    warning_level, badges[], compare_payload

WarningLevel sayısal kuralı:
  green      → delta ≤ %1 VE port_fit OK VE production_ready=True
  yellow     → delta ≤ %2 (usta isterse devam edebilir)
  red_block  → fiziksel imkansızlık (port sığmaz) VEYA delta > %2

ComparisonData: yapılandırılmış 6 alan, metin değil.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field, asdict
from typing import Optional

logger = logging.getLogger("dd1.ui_presenter")

# ── Sabitler ─────────────────────────────────────────────────────────────────

from core.validators import DELTA_YELLOW_PCT, DELTA_GREEN_PCT, compute_warning_level

# KURAL K2 (sertlestirildi): Presenter hesap yapmaz, okur.
# warning_level / production_ready / production_ready_reasons → design_service.py yaziyor
# compute_warning_level burada sadece select_recommended_option penalty icin import edildi.
# presenter_from_conflict_report icinde ASLA doğrudan cağrilmaz.

FIXED_EXTERNAL_NOTICE = "Dış ölçü kilitli. Sistem sessiz resize yapmaz."

BADGE_RECOMMENDED = "Recommended"
BADGE_FITS        = "Fits"
BADGE_READY       = "Ready"
BADGE_WARNING     = "Warning"
BADGE_BLOCKED     = "Blocked"

class WarningLevel:
    GREEN     = "green"
    YELLOW    = "yellow"
    RED_BLOCK = "red_block"

# ── Deterministic Recommended Seçimi ────────────────────────────────────────

def select_recommended_option(options: list[dict]) -> str:
    """
    Tek deterministic RECOMMENDED seçimi.
    Kural önceliği:
      1. fit_status == "fail" → asla recommended olamaz
      2. warning_level == "red_block" → asla recommended olamaz
      3. Adaylar arasında penalty skoru:
           penalty = delta_pct * 10 + (0 if production_ready else 50) + (0 if fit ok else 100)
      4. En düşük penalty → RECOMMENDED
      5. Tüm adaylar blocked/red ise → en az kötü aday uyarıyla recommended olur

    Döner: option_id string
    """
    if not options:
        return ""

    def _penalty(opt: dict) -> float:
        delta   = opt.get("acoustic_delta_pct", 0.0)
        pr      = opt.get("production_ready", False)
        fit     = opt.get("fit_status", "ok")
        wl      = opt.get("warning_level", "green")  # TRUTH: design_service.py yazdı
        blocked = (fit == "fail") or (wl == WarningLevel.RED_BLOCK)
        return (
            (1000 if blocked else 0)
            + (50  if not pr  else 0)
            + delta * 10
        )

    # warning_level'i onceden hesapla DEGIL — design_service'den oku
    enriched = []
    for opt in options:
        wl = opt.get("warning_level", "yellow")   # TRUTH: design_service.py yazdı
        enriched.append({**opt, "_wl": wl})

    enriched.sort(key=_penalty)
    best = enriched[0]

    # Eğer tüm adaylar blocked/red ise → yine de en az kötüyü seç (warning ile)
    all_blocked = all(
        (o.get("fit_status", "ok") == "fail" or o["_wl"] == WarningLevel.RED_BLOCK)
        for o in enriched
    )
    if all_blocked:
        logger.warning("[RECOMMENDED] Tüm seçenekler blocked — %s en az kötü aday", best.get("option_id"))

    return best.get("option_id", "A")


# compute_warning_level core/validators.py'a tasindi (K4 veto fix)
# Presenter bu fonksiyonu import eder, kendisi hesaplamaz.


def compute_badges(
    wl: str,
    recommended: bool,
    fits: bool,
    pr: bool,
) -> list[str]:
    """
    Rozet listesi — KURAL:
    - WARNING veya BLOCKED alanda RECOMMENDED olmaz
    - READY rozeti: sadece unambiguous production_ready'de (wl==GREEN)
    """
    badges: list[str] = []

    # WARNING/BLOCKED kart RECOMMENDED olamaz
    if recommended and wl == WarningLevel.GREEN and fits and pr:
        badges.append(BADGE_RECOMMENDED)
    elif wl == WarningLevel.RED_BLOCK or not fits:
        badges.append(BADGE_BLOCKED)

    if fits and wl != WarningLevel.RED_BLOCK:
        badges.append(BADGE_FITS)
    if pr and wl == WarningLevel.GREEN:
        badges.append(BADGE_READY)
    elif pr and wl == WarningLevel.YELLOW:
        badges.append(BADGE_WARNING)
    return badges if badges else [BADGE_WARNING]


# ── VisualPreview ─────────────────────────────────────────────────────────────

def _isometric_wireframe(w: float, h: float, d: float, vw: int = 200, vh: int = 140) -> dict:
    """
    Basit izometrik projeksiyon — 3 görünür yüz (Ön, Üst, Sağ).
    Döner: SVG path string'leri ve label koordinatları.

    Projeksiyon formülü (cabinet oblique, 45°, 0.5 depth):
      screen_x = x + d * cos(45°) * 0.5
      screen_y = y - d * sin(45°) * 0.5
    (Y ekseni aşağı, x sağa)
    """
    import math
    mx = max(w, h, d) or 1.0
    # Normalize [0, scale] — maksimum boyutu vw*0.55 olacak şekilde ölçekle
    scale = (min(vw, vh) * 0.55) / mx
    W = w * scale
    H = h * scale
    D = d * scale
    ang = math.radians(30)   # izometrik açı
    ox = D * math.cos(ang) * 0.5   # depth-x offset
    oy = D * math.sin(ang) * 0.5   # depth-y offset

    # İzometrik merkez orijin: sol-alt köşe (canvas içinde)
    bx = vw * 0.18   # base left
    by = vh - vh * 0.12  # base bottom

    # 8 köşe noktası (izometrik projeksiyon)
    # Ön yüz: P0=sol-alt, P1=sağ-alt, P2=sağ-üst, P3=sol-üst
    p0 = (bx,        by)
    p1 = (bx + W,    by)
    p2 = (bx + W,    by - H)
    p3 = (bx,        by - H)
    # Arka yüz (depth offset)
    p4 = (bx    + ox, by    - oy)
    p5 = (bx + W + ox, by    - oy)
    p6 = (bx + W + ox, by - H - oy)
    p7 = (bx    + ox, by - H - oy)

    def pt(p): return f"{p[0]:.1f},{p[1]:.1f}"
    def face_path(*pts): return "M" + " L".join(pt(p) for p in pts) + " Z"

    # Üç görünür yüz
    front = face_path(p0, p1, p2, p3)     # ön
    top   = face_path(p3, p7, p6, p2)     # üst (p3→p7→p6→p2)
    right = face_path(p1, p5, p6, p2)     # sağ (p1→p5→p6→p2)

    # Kenarlık çizgileri (visible edges only)
    edges = [
        f"M{pt(p0)} L{pt(p1)}",  # ön-alt
        f"M{pt(p1)} L{pt(p2)}",  # ön-sağ
        f"M{pt(p2)} L{pt(p3)}",  # ön-üst
        f"M{pt(p3)} L{pt(p0)}",  # ön-sol
        f"M{pt(p1)} L{pt(p5)}",  # sağ-alt derinlik
        f"M{pt(p2)} L{pt(p6)}",  # sağ-üst derinlik
        f"M{pt(p3)} L{pt(p7)}",  # sol-üst derinlik
        f"M{pt(p5)} L{pt(p6)}",  # arka-sağ
        f"M{pt(p6)} L{pt(p7)}",  # arka-üst
    ]

    # Boyut etiket koordinatları
    lbl_w = {"x": (p0[0] + p1[0]) / 2, "y": p0[1] + 12, "text": f"W:{w:.0f}mm"}
    lbl_h = {"x": p0[0] - 18,          "y": (p0[1] + p3[1]) / 2, "text": f"H:{h:.0f}mm"}
    lbl_d = {"x": (p1[0] + p5[0]) / 2 + 4, "y": (p1[1] + p5[1]) / 2 + 4, "text": f"D:{d:.0f}mm"}

    return {
        "viewbox":    f"0 0 {vw} {vh}",
        "face_front": front,
        "face_top":   top,
        "face_right": right,
        "edges":      " ".join(edges),
        "labels":     [lbl_w, lbl_h, lbl_d],
    }


@dataclass
class VisualPreview:
    """
    Tarayıcıda 3D bounding box wireframe çizmek için gerekli tüm data.
    """
    width_ratio:  float
    height_ratio: float
    depth_ratio:  float
    width_mm:     float
    height_mm:    float
    depth_mm:     float
    wireframe:    dict  # SVG path data — 3 görünür yüz + kenarlıklar + etiketler

    @classmethod
    def from_dims(cls, w: float, h: float, d: float) -> "VisualPreview":
        mx = max(w, h, d) or 1.0
        return cls(
            width_ratio=round(w / mx, 3),
            height_ratio=round(h / mx, 3),
            depth_ratio=round(d / mx, 3),
            width_mm=w, height_mm=h, depth_mm=d,
            wireframe=_isometric_wireframe(w, h, d),
        )

    def to_dict(self) -> dict:
        return {
            "width_ratio":  self.width_ratio,
            "height_ratio": self.height_ratio,
            "depth_ratio":  self.depth_ratio,
            "width_mm":     self.width_mm,
            "height_mm":    self.height_mm,
            "depth_mm":     self.depth_mm,
            "wireframe":    self.wireframe,
        }


# ── MaterialUsage ─────────────────────────────────────────────────────────────

# Malzeme birim fiyatları TL/m² (18mm kalınlık baz)
_MATERIAL_PRICES: dict[float, dict] = {
    18.0: {"name": "18mm MDF",        "price_per_m2": 95.0,  "density": 680.0},
    15.0: {"name": "15mm Huş Kontraplak", "price_per_m2": 140.0, "density": 650.0},
    12.0: {"name": "12mm MDF",        "price_per_m2": 78.0,  "density": 680.0},
    9.0:  {"name": "9mm Huş",         "price_per_m2": 110.0, "density": 640.0},
    21.0: {"name": "21mm MDF",        "price_per_m2": 115.0, "density": 700.0},
}
_DEFAULT_PRICE = {"name": "MDF", "price_per_m2": 95.0, "density": 680.0}


@dataclass
class MaterialUsage:
    """Tahmini levha kullanımı, ağırlık ve maliyet — kesim + fiyat planı için."""
    panel_count:           int
    total_area_m2:         float
    material_thickness_mm: float
    estimated_weight_kg:   float
    material_name:         str    # "18mm MDF" vb.
    price_per_m2_tl:       float  # TL/m²
    estimated_cost_tl:     float  # Toplam tahmini maliyet
    waste_factor_pct:      float  # Fire yüzdesi (%10)

    @classmethod
    def estimate(
        cls,
        w: float, h: float, d: float,
        t: float,
        density_kg_m3: float | None = None,
        waste_pct: float = 10.0,
    ) -> "MaterialUsage":
        """
        6 panel için m², ağırlık ve TL maliyet tahmini.
          w, h, d : mm cinsinden dış ölçüler
          t       : malzeme kalınlığı (mm)
          waste_pct: fire yüzdesi (varsayılan %10)
        """
        mat = _MATERIAL_PRICES.get(t, _DEFAULT_PRICE)
        used_density = density_kg_m3 or mat["density"]

        wm, hm, dm = w / 1000, h / 1000, d / 1000
        tm = t / 1000
        panels = [
            wm * hm,   # Ön
            wm * hm,   # Arka
            wm * dm,   # Üst
            wm * dm,   # Alt
            hm * dm,   # Sağ
            hm * dm,   # Sol
        ]
        raw_area = sum(panels)
        fire = 1 + waste_pct / 100
        area  = raw_area * fire
        weight = area * tm * used_density
        cost   = area * mat["price_per_m2"]

        return cls(
            panel_count=6,
            total_area_m2=round(area, 3),
            material_thickness_mm=t,
            estimated_weight_kg=round(weight, 2),
            material_name=mat["name"],
            price_per_m2_tl=mat["price_per_m2"],
            estimated_cost_tl=round(cost, 0),
            waste_factor_pct=waste_pct,
        )

    def to_dict(self) -> dict:
        return {
            "panel_count":           self.panel_count,
            "total_area_m2":         self.total_area_m2,
            "material_thickness_mm": self.material_thickness_mm,
            "material_name":         self.material_name,
            "estimated_weight_kg":   self.estimated_weight_kg,
            "price_per_m2_tl":       self.price_per_m2_tl,
            "estimated_cost_tl":     self.estimated_cost_tl,
            "waste_factor_pct":      self.waste_factor_pct,
        }


# ── ComparisonData ─────────────────────────────────────────────────────────────

@dataclass
class ComparisonData:
    """
    İki seçenek arası kıyaslama — yapılandırılmış alanlar, metin değil.
    (Zorunlu sözleşme — 6 alan kilitli)
    """
    option_a_id:           str
    option_b_id:           str
    net_l_diff:            float         # L farkı (A - B)
    tuning_diff_hz:        float         # Hz farkı (A - B)
    outer_dim_diff_mm:     list[float]   # [Δw, Δh, Δd]  (A - B)
    fit_diff:              str           # "A daha iyi" | "Eşit" | "B daha iyi"
    production_ready_diff: str           # "A=Ready B=NotReady" | "İkisi de Ready" vb.
    material_diff:         str           # "A=18mm MDF, B=15mm Huş" | "Aynı"
    warning_level_diff:    str = "Eşit" # "A daha güvenli" | "Eşit" | "B daha güvenli"

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def between(
        cls,
        a: "UICard",
        b: "UICard",
    ) -> "ComparisonData":
        """İki UICard arasında kıyaslama hesapla."""
        a_dims = a.outer_dims_mm
        b_dims = b.outer_dims_mm
        dim_diff = [
            round(a_dims[i] - b_dims[i], 1) if i < len(a_dims) and i < len(b_dims) else 0.0
            for i in range(3)
        ]

        # Fit karşılaştırma
        fit_score = {"ok": 2, "warning": 1, "fail": 0}
        a_fit = fit_score.get(a.fit_status, 1)
        b_fit = fit_score.get(b.fit_status, 1)
        if a_fit > b_fit:
            fit_str = "A daha iyi"
        elif b_fit > a_fit:
            fit_str = "B daha iyi"
        else:
            fit_str = "Eşit"

        # production_ready
        if a.production_ready and b.production_ready:
            pr_str = "İkisi de Ready"
        elif a.production_ready:
            pr_str = "A=Ready, B=NotReady"
        elif b.production_ready:
            pr_str = "A=NotReady, B=Ready"
        else:
            pr_str = "İkisi de NotReady"

        # material
        a_mat = f"{a.material_thickness_mm}mm"
        b_mat = f"{b.material_thickness_mm}mm"
        mat_str = "Aynı" if a_mat == b_mat else f"A={a_mat}, B={b_mat}"

        # warning_level_diff
        wl_order = {WarningLevel.GREEN: 2, WarningLevel.YELLOW: 1, WarningLevel.RED_BLOCK: 0}
        a_wl = wl_order.get(a.warning_level, 1)
        b_wl = wl_order.get(b.warning_level, 1)
        if a_wl > b_wl:
            wl_diff = "A daha güvenli"
        elif b_wl > a_wl:
            wl_diff = "B daha güvenli"
        else:
            wl_diff = "Eşit"

        return cls(
            option_a_id=a.option_id,
            option_b_id=b.option_id,
            net_l_diff=round(a.net_l - b.net_l, 3),
            tuning_diff_hz=round(a.tuning_hz - b.tuning_hz, 1),
            outer_dim_diff_mm=dim_diff,
            fit_diff=fit_str,
            production_ready_diff=pr_str,
            material_diff=mat_str,
            warning_level_diff=wl_diff,
        )


# ── UICard ─────────────────────────────────────────────────────────────────────

@dataclass
class UICard:
    """
    Tek seçenek kartı — tarayıcıda A/B/C olarak görünür.
    Expand drawer için displacement detayları dahil.
    """
    option_id:             str
    strategy:              str
    warning_level:         str           # green | yellow | red_block
    badges:                list[str]
    usta_summary:          str           # Dinamik AI özeti veya template
    recommended:           bool

    # 3 temel ölçü
    outer_dims_mm:         list[float]   # [W, H, D]
    net_l:                 float
    tuning_hz:             float

    # Hedef vs Final (kıyaslama için)
    net_target_l:          float = 0.0   # Hedeflenen hacim
    tuning_target_hz:      float = 0.0   # Hedeflenen tuning
    orig_outer_dims_mm:    list[float] = field(default_factory=list)  # Orijinal dış ölçü

    # Üretim
    production_ready:      bool  = False
    fit_status:            str   = "ok"   # ok | warning | fail
    material_thickness_mm: float = 18.0
    panel_join_strategy:   str   = "finger_joint"
    manufacturability_status: str = ""   # ok | warning | fail
    port_type:             str   = "slot"   # slot | round | aeroport | kapalı
    finger_joint_enabled:  bool  = True
    material_strategy:     str   = ""       # keep_material | change_material vb.

    # Expand drawer — displacement detayları
    gross_l:               float = 0.0
    driver_displ_l:        float = 0.0
    port_displ_l:          float = 0.0
    bracing_displ_l:       float = 0.0
    acoustic_delta_pct:    float = 0.0

    # Driver Identity — Dürüstlük katmanı
    exact_driver_name:     str   = ""     # Örn: "JBL GT-S12" | "12\" ampirik tahmini"
    driver_source:         str   = ""     # db_exact | db_fuzzy | user_manual | empirical
    ts_source:             str   = ""     # user_manual | db | empirical_table
    ts_confidence:         float = 0.0    # 0.0–1.0
    fit_validation_summary: str  = ""    # "Üretim fiziği tamam" | uyarı metni
    port_details:          dict  = field(default_factory=dict)  # width, height, fold, mouth
    panel_list:            list  = field(default_factory=list)  # panel kesim listesi

    # Görsel
    visual_preview:        Optional["VisualPreview"] = None
    material_usage:        Optional["MaterialUsage"] = None

    def to_dict(self) -> dict:
        d = asdict(self)
        return d


# ── UIDesignPresenter ───────────────────────────────────────────────────────────

@dataclass
class UIDesignPresenter:
    """
    Tam UI paketi — router bu objeyi JSON'a serialize ederek döner.
    Zorunlu alanlar kilitlidir: design_id, selected_option_id,
    production_ready, warning_level, badges[], compare_payload.
    """
    # Zorunlu (kilitli sözleşme)
    design_id:          str
    selected_option_id: str
    production_ready:   bool
    warning_level:      str
    badges:             list[str]
    compare_payload:    ComparisonData

    # Seçenek kartları (genellikle 3)
    cards:              list[UICard] = field(default_factory=list)

    # Mod bilgisi
    mode:               str = "fixed_acoustic"
    mode_lock_notice:   Optional[str] = None   # FIXED_EXTERNAL için banner

    # Arşiv/akış
    stepper_step:       int = 3   # 1-Tanışma 2-Mod 3-Havuz 4-Mühürleme

    # Konuşma katmanı — yeni alanlar
    readiness_for_mode_selection: bool = False   # minimum veri toplandı mı
    collected_info_summary: dict = field(default_factory=dict)   # araç/sürücü/hedef/bagaj/eksikler

    def to_dict(self) -> dict:
        return {
            "design_id":          self.design_id,
            "selected_option_id": self.selected_option_id,
            "production_ready":   self.production_ready,
            "warning_level":      self.warning_level,
            "badges":             self.badges,
            "compare_payload":    self.compare_payload.to_dict(),
            "cards":              [c.to_dict() for c in self.cards],
            "mode":               self.mode,
            "mode_lock_notice":   self.mode_lock_notice,
            "stepper_step":       self.stepper_step,
        }


# ── Factory ────────────────────────────────────────────────────────────────────

def presenter_from_conflict_report(
    design_id:          str,
    report_dict:        dict,
    selected_option_id: str = "A",
    usta_summaries:     dict[str, str] | None = None,
) -> UIDesignPresenter:
    """
    ConflictReport.to_dict() -> UIDesignPresenter factory.

    K2 KURAL (sertlestirildi): Presenter hesap YAPMAZ.
    warning_level / production_ready TRUTH: design_service.py (self-correction loop).
    Yoksa sessiz fallback.

    usta_summaries: {option_id: sozlu ozet} -- UstaOzeti modulunden gelir.
    """
    usta_summaries = usta_summaries or {}
    mode    = report_dict.get("mode", "fixed_acoustic")
    options = report_dict.get("options", [])

    # Step 0: Deterministic recommended secimi (K2: warning_level opts'tan okunur)
    recommended_id = select_recommended_option(options)

    cards: list[UICard] = []
    for opt in options:
        oid  = opt.get("option_id", "?")
        dims = opt.get("outer_dimensions_mm", [0, 0, 0])
        w, h, d = (dims + [0, 0, 0])[:3]
        delta   = opt.get("acoustic_delta_pct", 0.0)
        fit     = opt.get("fit_status", "ok")
        t_mm    = opt.get("material_thickness_mm", 18.0)

        # Step 1: port details
        fit_validation_dict = opt.get("port_details", {}).get("fit_checks", {})

        # Step 2: K2 KURAL -- Presenter hesap YAPMAZ, okur
        pr         = opt.get("production_ready", False)
        pr_reasons = opt.get("production_ready_reasons", [])
        wl         = opt.get("warning_level", "yellow")

        # fit_validation_summary -- Presenter metin uretmez, opts'tan okur
        fit_summary = opt.get("fit_validation_summary", "")
        if not fit_summary and pr_reasons:
            fit_summary = "; ".join(pr_reasons[:2])

        # Step 3: Badges
        is_recommended = (oid == recommended_id)
        bg = compute_badges(wl, is_recommended, fit != "fail", pr)

        summary = usta_summaries.get(oid) or opt.get("usta_summary", "")

        vp = VisualPreview.from_dims(w, h, d)
        mu = MaterialUsage.estimate(w, h, d, t_mm)

        card = UICard(
            option_id=oid,
            strategy=opt.get("strategy", ""),
            warning_level=wl,
            badges=bg,
            usta_summary=summary,
            recommended=is_recommended,
            outer_dims_mm=[w, h, d],
            net_l=opt.get("estimated_final_net_l", 0.0),
            tuning_hz=opt.get("estimated_final_tuning_hz", 0.0),
            production_ready=pr,
            fit_status=fit,
            material_thickness_mm=t_mm,
            panel_join_strategy=opt.get("panel_join_strategy", "finger_joint"),
            acoustic_delta_pct=delta,
            manufacturability_status=opt.get("manufacturability_status", ""),
            exact_driver_name=opt.get("exact_driver_name", ""),
            driver_source=opt.get("driver_source", ""),
            ts_source=opt.get("ts_source", ""),
            ts_confidence=opt.get("ts_confidence", 0.0),
            fit_validation_summary=fit_summary,
            port_details={**opt.get("port_details", {}), "fit_checks": fit_validation_dict},
            panel_list=opt.get("panel_list", []),
            visual_preview=vp,
            material_usage=mu,
        )
        cards.append(card)

    # Secili kart
    selected = next((c for c in cards if c.option_id == selected_option_id), cards[0] if cards else None)
    sel_id = selected.option_id if selected else selected_option_id
    sel_pr = selected.production_ready if selected else False
    sel_wl = selected.warning_level if selected else WarningLevel.RED_BLOCK
    sel_bg = selected.badges if selected else [BADGE_BLOCKED]

    # ComparisonData -- A vs B
    if len(cards) >= 2:
        compare = ComparisonData.between(cards[0], cards[1])
    else:
        compare = ComparisonData(
            option_a_id=sel_id, option_b_id="-",
            net_l_diff=0.0, tuning_diff_hz=0.0,
            outer_dim_diff_mm=[0.0, 0.0, 0.0],
            fit_diff="Esit", production_ready_diff="Tek secenek",
            material_diff="Ayni",
        )

    lock_notice = FIXED_EXTERNAL_NOTICE if mode == "fixed_external" else None

    return UIDesignPresenter(
        design_id=design_id,
        selected_option_id=sel_id,
        production_ready=sel_pr,
        warning_level=sel_wl,
        badges=sel_bg,
        compare_payload=compare,
        cards=cards,
        mode=mode,
        mode_lock_notice=lock_notice,
        stepper_step=3,
    )
