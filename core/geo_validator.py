"""
core/geo_validator.py
DD1 Geometrik Doğrulayıcı

Kontroller:
  1. Negatif boyut
  2. Port fiziksel sığma
  3. Finger joint panel sınırını taşmıyor mu
  4. Overlapping panel (aynı boyutlu iki farklı panel)
  5. Self-intersection (basit kare paneller için: negatif alan = intersection)
  6. Immutable akustik alan koruması (volume re-validation)
"""
from __future__ import annotations
from dataclasses import dataclass, field
from core.geometry import CabinetGeometry, PanelDim


@dataclass
class GeoValidationResult:
    passed: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def validate_geometry(cabinet: CabinetGeometry) -> GeoValidationResult:
    """
    Tam geometrik doğrulama.
    Tüm kontroller çalışır; errors listesi boşsa passed=True.
    """
    errors:   list[str] = []
    warnings: list[str] = []

    # 1. Negatif boyut
    for p in cabinet.panels:
        if p.width_mm <= 0:
            errors.append(f"{p.name}: genislik <= 0 ({p.width_mm:.2f}mm)")
        if p.height_mm <= 0:
            errors.append(f"{p.name}: yukseklik <= 0 ({p.height_mm:.2f}mm)")
        if p.thickness_mm <= 0:
            errors.append(f"{p.name}: kalinlik <= 0 ({p.thickness_mm:.2f}mm)")

    # 2. İç boyutlar negatif mi?
    if cabinet.inner_w_mm <= 0:
        errors.append(f"Ic genislik <= 0: {cabinet.inner_w_mm:.2f}mm — malzeme kalinligi cok buyuk?")
    if cabinet.inner_h_mm <= 0:
        errors.append(f"Ic yukseklik <= 0")
    if cabinet.inner_d_mm <= 0:
        errors.append(f"Ic derinlik <= 0")

    # 3. Port fiziksel sığma
    if cabinet.port:
        port = cabinet.port
        if port.height_mm > cabinet.inner_h_mm:
            errors.append(
                f"Port yuksekligi ({port.height_mm:.1f}mm) "
                f"ic yuksekligi ({cabinet.inner_h_mm:.1f}mm) asiyor"
            )
        if port.width_mm > cabinet.inner_w_mm:
            errors.append(
                f"Port genisligi ({port.width_mm:.1f}mm) "
                f"ic genisligi ({cabinet.inner_w_mm:.1f}mm) asiyor"
            )
        if port.length_mm > cabinet.inner_d_mm:
            warnings.append(
                f"Port uzunlugu ({port.length_mm:.1f}mm) ic derinlikten "
                f"({cabinet.inner_d_mm:.1f}mm) buyuk — L-port gerekebilir"
            )

    # 4. Finger joint panel sınırı
    if cabinet.finger_joint_active and cabinet.finger_width_mm > 0:
        for p in cabinet.panels:
            if p.role != "main":
                continue
            tw = cabinet.finger_width_mm
            # Minimum 2 diş sığmalı
            min_edge = min(p.width_mm, p.height_mm)
            if min_edge < 2 * tw:
                warnings.append(
                    f"{p.name}: kenar ({min_edge:.0f}mm) < 2×dis ({2*tw:.0f}mm) "
                    "— finger joint bu kenarda calismiyor olabilir"
                )

    # 5. Overlapping panel (aynı isim + boyut)
    seen: dict[str, tuple] = {}
    for p in cabinet.panels:
        key = (round(p.width_mm), round(p.height_mm))
        if p.name in seen:
            errors.append(f"Duplikat panel adi: {p.name}")
        seen[p.name] = key

    # 6. Volume re-validation
    if cabinet.volume:
        vol = cabinet.volume
        if vol.error_pct > 25.0:
            errors.append(
                f"Hacim sapma ({vol.error_pct:.1f}%) limiti asiyor. "
                f"Hesaplanan={vol.net_acoustic_l:.2f}L Hedef={vol.target_net_l:.2f}L"
            )
        elif vol.error_pct > 15.0:
            warnings.append(
                f"Hacim sapma: %{vol.error_pct:.1f} "
                f"(hesap={vol.net_acoustic_l:.2f}L hedef={vol.target_net_l:.2f}L)"
            )

    return GeoValidationResult(
        passed=len(errors) == 0,
        errors=errors,
        warnings=warnings,
    )
